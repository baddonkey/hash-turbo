"""Shared thread-pool work coordinator used by CLI executor and GUI workers.

The ``WorkPool`` extracts the "submit jobs to a ``ThreadPoolExecutor``,
honour cancellation, count completions, and stream results" pattern that
otherwise gets re-implemented (slightly differently) in each adapter.

Two consumption styles are supported:

- :meth:`run` returns when all submitted work has finished and yields a
  ``(results, errors)`` pair.  Used by the synchronous CLI executor.
- :meth:`submit` + :meth:`drain` push results into a thread-safe queue
  that a GUI timer can poll.  Used by the QThread workers.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Generic, Iterable, TypeVar

_log = logging.getLogger(__name__)

T = TypeVar("T")  # input type
R = TypeVar("R")  # result type


class WorkPool(Generic[T, R]):
    """Coordinates parallel execution of ``fn(item)`` over an iterable.

    All progress counters are guarded by an internal lock so they are
    safe to read from any thread (including readers that may run on
    interpreters without atomic int operations).
    """

    def __init__(
        self,
        fn: Callable[[T], R],
        *,
        max_workers: int,
        cancel_event: threading.Event | None = None,
        on_result: Callable[[int, R], None] | None = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self._fn = fn
        self._max_workers = max_workers
        self._cancel_event = cancel_event or threading.Event()
        self._on_result = on_result
        self._pool: ThreadPoolExecutor | None = None

        self._lock = threading.Lock()
        self._submitted = 0
        self._completed = 0

        self._results: deque[tuple[int, R]] = deque()
        self._errors: list[tuple[int, T, BaseException]] = []

    # ------------------------------------------------------------------
    # Properties — always read under the lock so torn reads are
    # impossible regardless of interpreter.
    # ------------------------------------------------------------------

    @property
    def submitted(self) -> int:
        with self._lock:
            return self._submitted

    @property
    def completed(self) -> int:
        with self._lock:
            return self._completed

    @property
    def errors(self) -> list[tuple[int, T, BaseException]]:
        with self._lock:
            return list(self._errors)

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel_event

    # ------------------------------------------------------------------
    # Async / streaming API — for QThread workers.
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open the pool.  Must be called before :meth:`submit`."""
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def submit(self, item: T) -> int:
        """Submit *item* for processing; returns its 0-based index.

        No-op (returns -1) when cancellation has been requested.
        """
        if self._cancel_event.is_set():
            return -1
        if self._pool is None:
            raise RuntimeError("WorkPool.start() must be called before submit()")
        with self._lock:
            index = self._submitted
            self._submitted += 1
        future = self._pool.submit(self._fn, item)
        future.add_done_callback(self._make_callback(index, item))
        return index

    def drain(self, max_items: int = 50) -> list[tuple[int, R]]:
        """Pop up to *max_items* completed ``(index, result)`` pairs."""
        batch: list[tuple[int, R]] = []
        for _ in range(max_items):
            try:
                batch.append(self._results.popleft())
            except IndexError:
                break
        return batch

    def wait_until_done(self, total: int, *, poll_interval: float = 0.1) -> None:
        """Block until ``completed >= total`` or cancellation fires."""
        while True:
            with self._lock:
                done = self._completed >= total
            if done or self._cancel_event.is_set():
                return
            if self._cancel_event.wait(timeout=poll_interval):
                return

    def shutdown(self, *, wait: bool = False) -> None:
        """Tear down the underlying executor.  Idempotent."""
        if self._pool is None:
            return
        cancelled = self._cancel_event.is_set()
        self._pool.shutdown(wait=wait, cancel_futures=cancelled)
        self._pool = None

    # ------------------------------------------------------------------
    # Synchronous API — for the CLI executor.
    # ------------------------------------------------------------------

    def run(self, items: Iterable[T]) -> tuple[list[tuple[int, R]], list[tuple[int, T, BaseException]]]:
        """Execute *fn* over *items* in parallel and collect every result.

        Returns ``(results, errors)`` where ``results`` is sorted by
        submission index and ``errors`` lists the items that raised.
        Cancelled items are silently skipped (neither in *results* nor
        *errors*).
        """
        self.start()
        try:
            for item in items:
                if self._cancel_event.is_set():
                    break
                self.submit(item)
            self.wait_until_done(self.submitted)
        finally:
            self.shutdown(wait=True)

        all_results = list(self._results)
        all_results.sort(key=lambda pair: pair[0])
        return all_results, self.errors

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_callback(self, index: int, item: T) -> Callable[[Future[R]], None]:
        def _on_done(future: Future[R]) -> None:
            try:
                if future.cancelled():
                    return
                if self._cancel_event.is_set():
                    return
                try:
                    result = future.result()
                except BaseException as exc:  # noqa: BLE001 — user fn may raise anything
                    _log.warning("Work item %d failed: %s", index, exc, exc_info=True)
                    with self._lock:
                        self._errors.append((index, item, exc))
                    return
                self._results.append((index, result))
                if self._on_result is not None:
                    try:
                        self._on_result(index, result)
                    except BaseException:  # noqa: BLE001
                        _log.exception("on_result callback raised")
            finally:
                with self._lock:
                    self._completed += 1

        return _on_done


__all__ = ["WorkPool"]
