"""Directory walking, glob filtering, and file resolution."""

from __future__ import annotations

import fnmatch
import os
import threading
from pathlib import Path
from typing import Callable, Sequence

from hash_turbo.core.exclude_filter import ExcludeFilter


class FileScanner:
    """Resolves file paths from a mix of files, directories, and patterns."""

    @staticmethod
    def scan_paths(
        paths: Sequence[Path],
        *,
        recursive: bool = False,
        glob_pattern: str | None = None,
        exclude: str | None = None,
        exclude_filter: ExcludeFilter | None = None,
        exclude_paths: Sequence[Path] | None = None,
        cancel_event: threading.Event | None = None,
        on_file: Callable[[Path], None] | None = None,
    ) -> list[Path]:
        """Resolve file paths from a mix of files, directories, and patterns."""
        seen: set[str] = set()
        if exclude_paths:
            for ep in exclude_paths:
                seen.add(os.path.normcase(os.path.abspath(ep)))
        result: list[Path] = []

        def _add(p: Path) -> None:
            key = os.path.normcase(os.path.abspath(p))
            if key in seen:
                return
            if exclude_filter and exclude_filter.is_excluded(p.name):
                return
            seen.add(key)
            result.append(p)
            if on_file:
                on_file(p)

        for path in paths:
            if cancel_event and cancel_event.is_set():
                break
            if path.is_file():
                _add(path)
            elif path.is_dir():
                if recursive:
                    FileScanner._walk_recursive(
                        path, _add, cancel_event=cancel_event,
                    )
                else:
                    with os.scandir(path) as it:
                        for entry in sorted(it, key=lambda e: e.name):
                            if cancel_event and cancel_event.is_set():
                                break
                            if entry.is_file(follow_symlinks=False):
                                _add(Path(entry.path))

        if glob_pattern:
            result = [p for p in result if fnmatch.fnmatch(p.name, glob_pattern)]

        if exclude:
            result = [p for p in result if not fnmatch.fnmatch(p.name, exclude)]

        return result

    @staticmethod
    def _walk_recursive(
        directory: Path,
        add: Callable[[Path], None],
        *,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Walk a directory tree using os.walk (avoids per-file stat calls).

        Sorts directory and file names at each level so the walk order
        is deterministic: files in alphabetical order first, then
        subdirectories in alphabetical order.
        """
        for dirpath, dirnames, filenames in os.walk(directory):
            if cancel_event and cancel_event.is_set():
                break
            dirnames.sort()
            for name in sorted(filenames):
                if cancel_event and cancel_event.is_set():
                    break
                add(Path(dirpath, name))


__all__ = ["FileScanner"]
