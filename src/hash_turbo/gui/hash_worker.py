"""Background worker thread for hashing files."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QThread, Signal

from hash_turbo.core.exclude_filter import ExcludeFilter
from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import AlgorithmLike, HashResult
from hash_turbo.infra.file_scanner import FileScanner
from hash_turbo.infra.hash_io import hash_file
from hash_turbo.infra.work_pool import WorkPool

_log = logging.getLogger(__name__)


class HashWorker(QThread):
    """Background worker that scans and hashes files concurrently.

    Concurrency is delegated to :class:`WorkPool`, which owns the
    thread pool, the cancel event, the result deque, and the
    submitted/completed counters (all updated under a single lock).
    The GUI polls :meth:`drain_results` on a timer.
    """

    # One-time lifecycle signals only — no per-item signals.
    scanning = Signal()
    scan_done = Signal(int)  # total files discovered
    work_finished = Signal()
    work_cancelled = Signal()
    work_error = Signal(str)

    def __init__(
        self,
        paths: Sequence[Path],
        algorithm: AlgorithmLike,
        exclude_filter: ExcludeFilter | None = None,
        exclude_paths: Sequence[Path] | None = None,
        recursive: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = list(paths)
        self._algorithm = algorithm
        self._exclude_filter = exclude_filter
        self._exclude_paths = exclude_paths
        self._recursive = recursive
        self._cancel_event = threading.Event()
        self._pool: WorkPool[Path, HashResult] | None = None
        self.is_scan_done = False

    @property
    def submitted_count(self) -> int:
        return self._pool.submitted if self._pool is not None else 0

    @property
    def completed_count(self) -> int:
        return self._pool.completed if self._pool is not None else 0

    def drain_results(self, max_items: int = 50) -> list[tuple[int, HashResult]]:
        """Drain up to *max_items* indexed results from the queue (thread-safe)."""
        if self._pool is None:
            return []
        return self._pool.drain(max_items)

    def run(self) -> None:
        try:
            self.scanning.emit()
            _log.info(
                "Hash started: algorithm=%s, paths=%s",
                self._algorithm.value, [str(p) for p in self._paths],
            )

            hasher = Hasher()
            workers = max(1, (os.cpu_count() or 2) - 1)
            algorithm = self._algorithm

            def _hash_one(path: Path) -> HashResult:
                return hash_file(hasher, path, algorithm)

            self._pool = WorkPool[Path, HashResult](
                _hash_one,
                max_workers=workers,
                cancel_event=self._cancel_event,
            )
            self._pool.start()

            def _on_file(path: Path) -> None:
                if self._cancel_event.is_set():
                    return
                assert self._pool is not None
                self._pool.submit(path)

            try:
                FileScanner.scan_paths(
                    self._paths,
                    recursive=self._recursive,
                    exclude_filter=self._exclude_filter,
                    exclude_paths=self._exclude_paths,
                    cancel_event=self._cancel_event,
                    on_file=_on_file,
                )

                self.is_scan_done = True
                self.scan_done.emit(self._pool.submitted)

                self._pool.wait_until_done(self._pool.submitted)
            finally:
                cancelled = self._cancel_event.is_set()
                if self._pool is not None:
                    self._pool.shutdown(wait=not cancelled)

            if not self._cancel_event.is_set():
                _log.info(
                    "Hash finished: %d/%d completed",
                    self._pool.completed, self._pool.submitted,
                )
                self.work_finished.emit()
            else:
                _log.info(
                    "Hash cancelled at %d/%d",
                    self._pool.completed, self._pool.submitted,
                )
                self.work_cancelled.emit()
        except Exception as e:
            _log.exception("Hash error")
            self.work_error.emit(str(e))

    def request_cancel(self) -> None:
        """Request cancellation of the scanning/hashing operation."""
        self._cancel_event.set()


__all__ = ["HashWorker"]
