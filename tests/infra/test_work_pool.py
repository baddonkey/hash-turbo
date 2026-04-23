"""Tests for ``hash_turbo.infra.work_pool``."""

from __future__ import annotations

import threading
import time

import pytest

from hash_turbo.infra.work_pool import WorkPool


class TestWorkPoolRun:
    def test_run_returns_results_in_submission_order(self) -> None:
        pool = WorkPool[int, int](lambda x: x * 2, max_workers=4)

        results, errors = pool.run(range(10))

        assert errors == []
        assert [r for _idx, r in results] == [x * 2 for x in range(10)]

    def test_run_collects_errors_without_aborting(self) -> None:
        def fn(x: int) -> int:
            if x == 3:
                raise ValueError("boom")
            return x

        pool = WorkPool[int, int](fn, max_workers=2)
        results, errors = pool.run(range(5))

        assert {r for _idx, r in results} == {0, 1, 2, 4}
        assert len(errors) == 1
        idx, item, exc = errors[0]
        assert item == 3
        assert isinstance(exc, ValueError)

    def test_cancel_short_circuits_pending_work(self) -> None:
        cancel = threading.Event()
        started = threading.Event()

        def fn(x: int) -> int:
            started.set()
            cancel.wait(0.5)  # let cancellation propagate
            return x

        pool = WorkPool[int, int](fn, max_workers=1, cancel_event=cancel)
        pool.start()
        pool.submit(0)
        started.wait(1.0)
        cancel.set()
        # Submitting after cancel returns -1 (no-op).
        assert pool.submit(99) == -1
        pool.shutdown(wait=True)


class TestWorkPoolStreaming:
    def test_on_result_is_called_for_each_completion(self) -> None:
        seen: list[tuple[int, int]] = []
        lock = threading.Lock()

        def record(idx: int, value: int) -> None:
            with lock:
                seen.append((idx, value))

        pool = WorkPool[int, int](
            lambda x: x + 1, max_workers=2, on_result=record,
        )
        pool.start()
        for x in range(5):
            pool.submit(x)
        pool.wait_until_done(5)
        pool.shutdown(wait=True)

        assert sorted(seen) == [(i, i + 1) for i in range(5)]

    def test_drain_yields_completed_pairs(self) -> None:
        pool = WorkPool[int, int](lambda x: x, max_workers=2)
        pool.start()
        for x in range(3):
            pool.submit(x)
        pool.wait_until_done(3)
        batch = pool.drain(max_items=10)
        pool.shutdown(wait=True)

        assert sorted(b[1] for b in batch) == [0, 1, 2]


class TestWorkPoolValidation:
    def test_max_workers_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            WorkPool[int, int](lambda x: x, max_workers=0)

    def test_submit_without_start_raises(self) -> None:
        pool = WorkPool[int, int](lambda x: x, max_workers=1)
        with pytest.raises(RuntimeError):
            pool.submit(1)
