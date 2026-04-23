"""Tests for ``hash_turbo.gui.verify_worker.RetryPolicy`` and friends."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import Algorithm, HashEntry
from hash_turbo.gui.verify_worker import (
    DriveProbe,
    RetryPolicy,
    hash_with_retry,
)


class _OfflineThenOnlineProbe:
    """Drive probe that becomes reachable after N polls."""

    def __init__(self, polls_until_back: int) -> None:
        self._remaining = polls_until_back
        self.calls = 0

    def is_reachable(self, base_dir: Path) -> bool:
        self.calls += 1
        if self._remaining <= 0:
            return True
        self._remaining -= 1
        return False


class _AlwaysOfflineProbe:
    def is_reachable(self, base_dir: Path) -> bool:
        return False


class TestRetryPolicy:
    def test_delay_doubles_per_attempt(self) -> None:
        p = RetryPolicy(initial_delay=0.5)
        assert p.delay_for(0) == 0.5
        assert p.delay_for(1) == 1.0
        assert p.delay_for(2) == 2.0


class TestHashWithRetryCancellation:
    def test_cancel_returns_immediately(self, tmp_path: Path) -> None:
        cancel = threading.Event()
        cancel.set()
        entry = HashEntry(path="missing.txt", algorithm=Algorithm.SHA256,
                          expected_hash="x")
        result = hash_with_retry(
            Hasher(), entry, tmp_path / "missing.txt", tmp_path, cancel,
        )
        assert result is None

    def test_cancel_during_retry_wait_aborts_quickly(
        self, tmp_path: Path,
    ) -> None:
        # File doesn't exist; drive *is* reachable, so the function
        # would normally sleep before retrying.  Cancel during the wait
        # and verify the call returns within a small bound.
        cancel = threading.Event()
        entry = HashEntry(path="missing.txt", algorithm=Algorithm.SHA256,
                          expected_hash="x")
        # Long delay; if cancel-aware wait works, we won't ever sleep
        # the full delay.
        policy = RetryPolicy(max_retries=3, initial_delay=10.0)

        def cancel_soon() -> None:
            time.sleep(0.05)
            cancel.set()

        threading.Thread(target=cancel_soon, daemon=True).start()
        start = time.monotonic()
        result = hash_with_retry(
            Hasher(), entry, tmp_path / "missing.txt", tmp_path, cancel,
            policy=policy,
        )
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed < 1.0, f"cancel took too long: {elapsed:.2f}s"


class TestHashWithRetryDriveRecovery:
    def test_returns_none_when_drive_never_recovers(
        self, tmp_path: Path,
    ) -> None:
        cancel = threading.Event()
        entry = HashEntry(path="x.txt", algorithm=Algorithm.SHA256,
                          expected_hash="x")
        policy = RetryPolicy(
            max_retries=1, initial_delay=0.01,
            drive_recovery_timeout=0.2, drive_poll_interval=0.05,
        )
        result = hash_with_retry(
            Hasher(), entry, tmp_path / "x.txt", tmp_path, cancel,
            policy=policy, probe=_AlwaysOfflineProbe(),
        )
        assert result is None
