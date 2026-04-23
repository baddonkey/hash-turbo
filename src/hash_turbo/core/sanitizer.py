"""Transform hash entries — format conversion, path normalization, deduplication."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from hash_turbo.core.models import HashEntry, HashFileFormat
from hash_turbo.core.path_key import normalize_path_key


class PathSeparator(Enum):
    """Target path separator style."""

    KEEP = "keep"
    POSIX = "posix"
    WINDOWS = "windows"


class HashCase(Enum):
    """Hash digest casing."""

    KEEP = "keep"
    LOWER = "lower"
    UPPER = "upper"


class SortKey(Enum):
    """Sort order for entries."""

    NONE = "none"
    PATH = "path"
    HASH = "hash"
    FILESYSTEM = "filesystem"


class LineEnding(Enum):
    """Line ending style for output."""

    SYSTEM = "system"
    LF = "lf"
    CRLF = "crlf"
    CR = "cr"

    @property
    def sequence(self) -> str:
        """Return the actual character sequence for this line ending."""
        if self is LineEnding.LF:
            return "\n"
        if self is LineEnding.CRLF:
            return "\r\n"
        if self is LineEnding.CR:
            return "\r"
        return os.linesep


@dataclass(frozen=True)
class SanitizeOptions:
    """Immutable value object holding all sanitize transform options."""

    output_format: HashFileFormat = HashFileFormat.GNU
    path_separator: PathSeparator = PathSeparator.KEEP
    strip_prefix: str = ""
    hash_case: HashCase = HashCase.KEEP
    sort_key: SortKey = SortKey.NONE
    deduplicate: bool = False
    line_ending: LineEnding = LineEnding.SYSTEM


class Sanitizer:
    """Pure-domain transformer for hash entries.

    Applies format conversion, path normalization, prefix stripping,
    hash-case normalization, sorting, and deduplication — all without I/O.

    Each transform stage checks ``cancel_event`` (when supplied) before
    starting; long-running stages also check between batches of entries.
    """

    _CANCEL_CHECK_EVERY = 1024

    def __init__(self, options: SanitizeOptions) -> None:
        self._options = options

    @property
    def options(self) -> SanitizeOptions:
        return self._options

    def transform(
        self,
        entries: Sequence[HashEntry],
        *,
        cancel_event: threading.Event | None = None,
    ) -> list[HashEntry]:
        """Apply all configured transformations in a deterministic order.

        If *cancel_event* is set during processing, returns the
        partially-transformed list as-is.
        """
        result = list(entries)
        steps = [
            (bool(self._options.strip_prefix), self._strip_prefix),
            (self._options.path_separator is not PathSeparator.KEEP, self._normalize_separators),
            (self._options.hash_case is not HashCase.KEEP, self._normalize_hash_case),
            (self._options.deduplicate, self._deduplicate),
            (self._options.sort_key is not SortKey.NONE, self._sort),
        ]
        for enabled, fn in steps:
            if cancel_event is not None and cancel_event.is_set():
                return result
            if enabled:
                result = fn(result)
        return result

    def format(
        self,
        entries: Sequence[HashEntry],
        *,
        cancel_event: threading.Event | None = None,
    ) -> str:
        """Format entries as text in the configured output format."""
        fmt = self._options.output_format
        eol = self._options.line_ending.sequence
        lines: list[str] = []
        for i, e in enumerate(entries):
            if (
                cancel_event is not None
                and i % self._CANCEL_CHECK_EVERY == 0
                and cancel_event.is_set()
            ):
                break
            if fmt is HashFileFormat.BSD:
                lines.append(f"{e.algorithm.value.upper()} ({e.path}) = {e.expected_hash}")
            else:
                mode = "*" if e.binary_mode else " "
                lines.append(f"{e.expected_hash} {mode}{e.path}")
        return eol.join(lines) + eol if lines else ""

    # -- private transform steps ------------------------------------------

    def _normalize_separators(self, entries: list[HashEntry]) -> list[HashEntry]:
        result: list[HashEntry] = []
        sep = self._options.path_separator
        for e in entries:
            if sep is PathSeparator.POSIX:
                path = e.path.replace("\\", "/")
            else:
                path = e.path.replace("/", "\\")
            result.append(HashEntry(path=path, algorithm=e.algorithm, expected_hash=e.expected_hash, binary_mode=e.binary_mode))
        return result

    def _strip_prefix(self, entries: list[HashEntry]) -> list[HashEntry]:
        clean = self._options.strip_prefix.replace("\\", "/").rstrip("/") + "/"
        result: list[HashEntry] = []
        for e in entries:
            normalized = e.path.replace("\\", "/")
            if normalized.startswith(clean):
                path = normalized[len(clean):]
            elif normalized == clean.rstrip("/"):
                path = "."
            else:
                path = e.path
            result.append(HashEntry(path=path, algorithm=e.algorithm, expected_hash=e.expected_hash, binary_mode=e.binary_mode))
        return result

    def _normalize_hash_case(self, entries: list[HashEntry]) -> list[HashEntry]:
        result: list[HashEntry] = []
        case = self._options.hash_case
        for e in entries:
            h = e.expected_hash.lower() if case is HashCase.LOWER else e.expected_hash.upper()
            result.append(HashEntry(path=e.path, algorithm=e.algorithm, expected_hash=h, binary_mode=e.binary_mode))
        return result

    def _sort(self, entries: list[HashEntry]) -> list[HashEntry]:
        if self._options.sort_key is SortKey.PATH:
            return sorted(entries, key=lambda e: normalize_path_key(e.path))
        if self._options.sort_key is SortKey.FILESYSTEM:
            return sorted(entries, key=self._filesystem_sort_key)
        return sorted(entries, key=lambda e: e.expected_hash.lower())

    @staticmethod
    def _filesystem_sort_key(entry: HashEntry) -> tuple[tuple[str, ...], str]:
        """Sort key mimicking recursive directory walk order.

        Sorts by directory components first (hierarchically, case-insensitive),
        then by filename within each directory — matching the order that
        ``os.walk`` + sorted filenames would produce.
        """
        normalized = normalize_path_key(entry.path)
        parts = normalized.rsplit("/", 1)
        if len(parts) == 2:
            dir_parts = tuple(parts[0].split("/"))
            filename = parts[1]
        else:
            dir_parts = ()
            filename = parts[0]
        return (dir_parts, filename)

    def _deduplicate(self, entries: list[HashEntry]) -> list[HashEntry]:
        seen: set[str] = set()
        result: list[HashEntry] = []
        for e in entries:
            key = normalize_path_key(e.path)
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result


__all__ = [
    "HashCase",
    "LineEnding",
    "PathSeparator",
    "SanitizeOptions",
    "Sanitizer",
    "SortKey",
]
