"""Background worker thread for hash file sanitization."""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from hash_turbo.core.hash_file import HashFileParser
from hash_turbo.core.models import HashFileFormat
from hash_turbo.core.sanitizer import (
    HashCase,
    LineEnding,
    PathSeparator,
    SanitizeOptions,
    Sanitizer,
    SortKey,
)
from hash_turbo.i18n import _


class SanitizeWorker(QThread):
    """Run the sanitize transform off the main thread so the UI stays responsive."""

    finished_with_result = Signal(str, list)  # formatted text, list of entry dicts
    work_error = Signal(str)
    work_cancelled = Signal()

    def __init__(  # noqa: PLR0913
        self,
        content: str,
        fmt: str,
        separator: str,
        strip_prefix: str,
        hash_case: str,
        sort_key: str,
        deduplicate: bool,
        normalize_ws: bool,
        line_ending: str,
    ) -> None:
        super().__init__()
        self._content = content
        self._fmt = fmt
        self._separator = separator
        self._strip_prefix = strip_prefix
        self._hash_case = hash_case
        self._sort_key = sort_key
        self._deduplicate = deduplicate
        self._normalize_ws = normalize_ws
        self._line_ending = line_ending
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        """Signal the worker to stop at the next check-point."""
        self._cancel_event.set()

    def run(self) -> None:
        try:
            result, entries = self._do_transform()
            if self._cancel_event.is_set():
                self.work_cancelled.emit()
            else:
                self.finished_with_result.emit(result, entries)
        except Exception as exc:  # noqa: BLE001
            self.work_error.emit(str(exc))

    def _do_transform(self) -> tuple[str, list[dict[str, str]]]:
        content = self._content.strip()
        if not content:
            return "", []

        options = SanitizeOptions(
            output_format=HashFileFormat(self._fmt),
            path_separator=PathSeparator(self._separator),
            strip_prefix=self._strip_prefix,
            hash_case=HashCase(self._hash_case),
            sort_key=SortKey(self._sort_key),
            deduplicate=self._deduplicate,
            line_ending=LineEnding(self._line_ending),
        )

        try:
            entries = HashFileParser.parse(
                content, flexible_whitespace=self._normalize_ws,
            )
        except ValueError as exc:
            return _("Error: {}").format(exc), []

        if self._cancel_event.is_set() or not entries:
            return "", []

        sanitizer = Sanitizer(options)
        transformed = sanitizer.transform(entries, cancel_event=self._cancel_event)

        if self._cancel_event.is_set():
            return "", []

        entry_dicts = [
            {
                "algorithm": e.algorithm.display_name,
                "hash": e.expected_hash,
                "path": e.path,
            }
            for e in transformed
        ]

        output = sanitizer.format(transformed, cancel_event=self._cancel_event)
        return output.rstrip("\n"), entry_dicts


__all__ = ["SanitizeWorker"]
