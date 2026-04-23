"""Background worker thread for hash verification."""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from PySide6.QtCore import QObject, QThread, Signal

from hash_turbo.core.exclude_filter import ExcludeFilter
from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import HashEntry, HashResult, VerifyResult, VerifyStatus
from hash_turbo.infra.hash_io import hash_file
from hash_turbo.infra.work_pool import WorkPool

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Retry / drive-probe abstractions (extracted for unit testing)
# ---------------------------------------------------------------------------


class DriveProbe(Protocol):
    """Probe whether a base directory is reachable."""

    def is_reachable(self, base_dir: Path) -> bool: ...


class _DefaultDriveProbe:
    def is_reachable(self, base_dir: Path) -> bool:
        try:
            return base_dir.exists()
        except OSError:
            return False


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential-backoff retry settings for the verifier."""

    max_retries: int = 3
    initial_delay: float = 1.0
    drive_recovery_timeout: float = 30.0
    drive_poll_interval: float = 2.0

    def delay_for(self, attempt: int) -> float:
        return self.initial_delay * (2 ** attempt)


def _wait_for_drive(
    base_dir: Path,
    cancel_event: threading.Event,
    policy: RetryPolicy,
    probe: DriveProbe,
) -> bool:
    """Return True when the drive is reachable again, False on timeout/cancel.

    Sleeps via :meth:`threading.Event.wait` so cancellation interrupts
    the wait immediately instead of after one full poll interval.
    """
    import time

    deadline = time.monotonic() + policy.drive_recovery_timeout
    _log.warning("Drive unreachable, waiting for reconnection: %s", base_dir)
    while time.monotonic() < deadline:
        if cancel_event.wait(policy.drive_poll_interval):
            return False
        if probe.is_reachable(base_dir):
            _log.info("Drive reconnected: %s", base_dir)
            return True
    _log.warning(
        "Drive recovery timed out after %.0fs: %s",
        policy.drive_recovery_timeout, base_dir,
    )
    return False


def hash_with_retry(
    hasher: Hasher,
    entry: HashEntry,
    file_path: Path,
    base_dir: Path,
    cancel_event: threading.Event,
    *,
    binary_mode: bool = True,
    policy: RetryPolicy | None = None,
    probe: DriveProbe | None = None,
) -> HashResult | None:
    """Hash a single file with retry + drive recovery; return ``None`` if missing."""
    pol = policy or RetryPolicy()
    drv = probe or _DefaultDriveProbe()
    last_err: Exception | None = None

    for attempt in range(pol.max_retries + 1):
        if cancel_event.is_set():
            return None
        try:
            if not file_path.is_file():
                if not drv.is_reachable(base_dir):
                    if _wait_for_drive(base_dir, cancel_event, pol, drv):
                        if file_path.is_file():
                            return hash_file(
                                hasher, file_path, entry.algorithm,
                                binary_mode=binary_mode,
                            )
                    return None
                if attempt < pol.max_retries:
                    if cancel_event.wait(pol.delay_for(attempt)):
                        return None
                    continue
                return None

            return hash_file(hasher, file_path, entry.algorithm,
                             binary_mode=binary_mode)
        except OSError as exc:
            last_err = exc
            if not drv.is_reachable(base_dir):
                if _wait_for_drive(base_dir, cancel_event, pol, drv):
                    try:
                        return hash_file(
                            hasher, file_path, entry.algorithm,
                            binary_mode=binary_mode,
                        )
                    except OSError:
                        pass
                _log.warning("I/O error (drive unreachable): %s", file_path,
                             exc_info=True)
                return None
            if attempt < pol.max_retries:
                if cancel_event.wait(pol.delay_for(attempt)):
                    return None
                continue
            _log.warning("I/O error after %d attempts: %s", attempt + 1,
                         file_path, exc_info=True)
            return None

    _log.warning("Exhausted retries for %s (last error: %s)", file_path, last_err)
    return None


# ---------------------------------------------------------------------------
# QThread worker
# ---------------------------------------------------------------------------


class VerifyWorker(QThread):
    """Background worker that hashes files referenced by hash entries."""

    work_finished = Signal()
    work_error = Signal(str)

    def __init__(
        self,
        entries: Sequence[HashEntry],
        base_dir: Path,
        *,
        detect_new: bool = False,
        binary_only: bool = True,
        exclude_filter: ExcludeFilter | None = None,
        exclude_paths: Sequence[Path] | None = None,
        retry_policy: RetryPolicy | None = None,
        drive_probe: DriveProbe | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._entries = list(entries)
        self._base_dir = base_dir
        self._detect_new = detect_new
        self._binary_only = binary_only
        self._exclude_filter = exclude_filter
        self._exclude_paths: set[str] = set()
        if exclude_paths:
            for ep in exclude_paths:
                self._exclude_paths.add(os.path.abspath(ep).casefold())
        self._cancel_event = threading.Event()
        self._retry_policy = retry_policy or RetryPolicy()
        self._drive_probe = drive_probe or _DefaultDriveProbe()
        self._pool: WorkPool[HashEntry, VerifyResult] | None = None
        self._result_queue: deque[tuple[int, VerifyResult]] = deque()

        self.total_count = len(self._entries)
        self.is_scanning_new = False
        self.new_files: list[str] = []

    @property
    def completed_count(self) -> int:
        return self._pool.completed if self._pool is not None else 0

    def drain_results(self, max_items: int = 20) -> list[tuple[int, VerifyResult]]:
        batch: list[tuple[int, VerifyResult]] = []
        for _ in range(max_items):
            try:
                batch.append(self._result_queue.popleft())
            except IndexError:
                break
        return batch

    def run(self) -> None:
        try:
            _log.info(
                "Verify started: %d entries, base_dir=%s, detect_new=%s",
                self.total_count, self._base_dir, self._detect_new,
            )
            self._hash_entries()
            if self._detect_new and not self._cancel_event.is_set():
                self.is_scanning_new = True
                self._scan_new_files()
                self.is_scanning_new = False
            if not self._cancel_event.is_set():
                _log.info(
                    "Verify finished: %d/%d completed",
                    self.completed_count, self.total_count,
                )
                self.work_finished.emit()
            else:
                _log.info("Verify cancelled at %d/%d",
                          self.completed_count, self.total_count)
        except Exception as e:
            _log.exception("Verify error")
            self.work_error.emit(str(e))

    def _hash_entries(self) -> None:
        hasher = Hasher()
        workers = max(1, (os.cpu_count() or 2) - 1)
        base_resolved = self._base_dir.resolve()

        def _verify_one(entry: HashEntry) -> VerifyResult:
            file_path = self._base_dir / entry.path
            try:
                resolved = file_path.resolve()
            except OSError:
                return VerifyResult(entry=entry, status=VerifyStatus.MISSING)
            if not resolved.is_relative_to(base_resolved):
                _log.warning("Path traversal blocked: %s", entry.path)
                return VerifyResult(entry=entry, status=VerifyStatus.MISSING)
            binary_mode = True if self._binary_only else entry.binary_mode
            result = hash_with_retry(
                hasher, entry, file_path, self._base_dir, self._cancel_event,
                binary_mode=binary_mode, policy=self._retry_policy,
                probe=self._drive_probe,
            )
            if result is None:
                return VerifyResult(entry=entry, status=VerifyStatus.MISSING)
            if entry.expected_hash.lower() == result.hex_digest.lower():
                return VerifyResult(entry=entry, status=VerifyStatus.OK)
            return VerifyResult(entry=entry, status=VerifyStatus.FAILED)

        # WorkPool's submission index == manifest index because we submit
        # entries in their original order.
        def _on_result(idx: int, vr: VerifyResult) -> None:
            self._result_queue.append((idx, vr))

        self._pool = WorkPool[HashEntry, VerifyResult](
            _verify_one,
            max_workers=workers,
            cancel_event=self._cancel_event,
            on_result=_on_result,
        )
        self._pool.start()

        try:
            for entry in self._entries:
                if self._cancel_event.is_set():
                    break
                self._pool.submit(entry)
            self._pool.wait_until_done(self.total_count)
        finally:
            cancelled = self._cancel_event.is_set()
            self._pool.shutdown(wait=not cancelled)

    def _scan_new_files(self) -> None:
        """Find files in entry directories that have no hash entry."""
        base_abs = Path(os.path.abspath(self._base_dir))

        tracked_normalized: set[str] = set()
        entry_dirs: set[Path] = set()
        for entry in self._entries:
            entry_path = Path(entry.path)
            if entry_path.is_absolute():
                abs_path = Path(os.path.abspath(entry_path))
            else:
                abs_path = Path(os.path.abspath(self._base_dir / entry_path))
            try:
                rel = abs_path.relative_to(base_abs)
            except ValueError:
                rel = entry_path
            tracked_normalized.add(str(rel).replace("\\", "/").casefold())
            entry_dirs.add(abs_path.parent)

        found: list[str] = []
        for directory in entry_dirs:
            if self._cancel_event.is_set():
                break
            if not directory.is_dir():
                continue
            for child in directory.iterdir():
                if self._cancel_event.is_set():
                    break
                if not child.is_file():
                    continue
                if self._exclude_filter and self._exclude_filter.is_excluded(child.name):
                    continue
                if os.path.abspath(child).casefold() in self._exclude_paths:
                    continue
                try:
                    rel = Path(os.path.abspath(child)).relative_to(base_abs)
                except ValueError:
                    continue
                if str(rel).replace("\\", "/").casefold() not in tracked_normalized:
                    found.append(str(rel))

        found.sort()
        self.new_files = found

    def request_cancel(self) -> None:
        self._cancel_event.set()


__all__ = ["DriveProbe", "RetryPolicy", "VerifyWorker", "hash_with_retry"]
