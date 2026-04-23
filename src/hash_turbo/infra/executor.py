"""Parallel file hashing using concurrent.futures."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import Algorithm, AlgorithmLike, HashResult
from hash_turbo.infra.hash_io import hash_file
from hash_turbo.infra.work_pool import WorkPool

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HashRunReport:
    """Outcome of :meth:`HashExecutor.hash_files_with_report`.

    Attributes:
        results: Successfully computed hashes, in input order.
        errors:  ``(path, exception)`` pairs for files that failed.
        cancelled: ``True`` if the run stopped because cancellation was
            requested before all paths finished.
    """

    results: list[HashResult]
    errors: list[tuple[Path, BaseException]]
    cancelled: bool


class HashExecutor:
    """Hashes multiple files, optionally in parallel."""

    def __init__(self, hasher: Hasher | None = None) -> None:
        self._hasher = hasher or Hasher()

    def hash_files(
        self,
        paths: Sequence[Path],
        algorithm: AlgorithmLike = Algorithm.SHA256,
        jobs: int | None = None,
        on_progress: Callable[[HashResult], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> list[HashResult]:
        """Hash multiple files; return successful results in input order.

        Failures are logged and dropped — use
        :meth:`hash_files_with_report` to inspect them.
        """
        report = self.hash_files_with_report(
            paths, algorithm, jobs=jobs,
            on_progress=on_progress, cancel_event=cancel_event,
        )
        return report.results

    def hash_files_with_report(
        self,
        paths: Sequence[Path],
        algorithm: AlgorithmLike = Algorithm.SHA256,
        jobs: int | None = None,
        on_progress: Callable[[HashResult], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> HashRunReport:
        """Hash *paths* in parallel and return a structured report.

        The report exposes both the successful :class:`HashResult`\\ s
        (in input order) and the per-file errors that occurred, plus a
        ``cancelled`` flag indicating whether the user aborted the run.
        """
        if not paths:
            return HashRunReport(results=[], errors=[], cancelled=False)

        workers = min(jobs or os.cpu_count() or 1, len(paths))
        hasher = self._hasher

        def _do(path: Path) -> HashResult:
            return hash_file(hasher, path, algorithm)

        on_result = (
            (lambda _idx, res: on_progress(res)) if on_progress is not None else None
        )

        pool: WorkPool[Path, HashResult] = WorkPool(
            _do,
            max_workers=workers,
            cancel_event=cancel_event,
            on_result=on_result,
        )

        indexed_results, errors_list = pool.run(paths)

        # Re-map results back to input-path order (input is already
        # ordered, but we want to drop missing entries cleanly).
        path_to_result: dict[str, HashResult] = {}
        for _idx, res in indexed_results:
            path_to_result[res.path] = res

        ordered = [path_to_result[str(p)] for p in paths if str(p) in path_to_result]
        errors = [(item, exc) for _idx, item, exc in errors_list]
        cancelled = pool.cancel_event.is_set()
        return HashRunReport(results=ordered, errors=errors, cancelled=cancelled)


__all__ = ["HashExecutor", "HashRunReport"]
