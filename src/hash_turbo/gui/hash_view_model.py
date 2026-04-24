"""Hash generation view model — manages file selection, hashing, and output."""

from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Property, Signal, Slot
from PySide6.QtGui import QDesktopServices

from hash_turbo.core.exclude_filter import ExcludeFilter
from hash_turbo.core.hash_file import HashFileFormatter
from hash_turbo.core.models import Algorithm, HashFileFormat, HashResult
from hash_turbo.gui._view_model_base import ViewModelBase
from hash_turbo.gui.hash_worker import HashWorker
from hash_turbo.gui.settings_model import SettingsModel
from hash_turbo.i18n import _
from hash_turbo.infra.atomic_write import atomic_write_text


class HashViewModel(ViewModelBase):
    """Backend for the Hash generation tab."""

    # Property notification signals
    pending_count_changed = Signal()
    pending_display_changed = Signal()
    result_text_changed = Signal()
    log_text_changed = Signal()
    log_visible_changed = Signal()
    progress_value_changed = Signal()
    progress_max_changed = Signal()
    progress_visible_changed = Signal()
    progress_label_changed = Signal()
    is_hashing_changed = Signal()
    can_open_output_changed = Signal()

    # Event signals for QML
    folderSelected = Signal(str)
    filesAdded = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pending: list[str] = []
        self._results: list[tuple[int, HashResult]] = []
        self._cached_base: str | None = None
        self._worker: HashWorker | None = None
        self._current_format: HashFileFormat = HashFileFormat.GNU

        self._pending_count = 0
        self._pending_display = ""
        self._result_text = ""
        self._log_text = ""
        self._log_visible = False
        self._progress_value = 0
        self._progress_max = 0
        self._progress_visible = False
        self._progress_label = ""
        self._is_hashing = False
        self._can_open_output = False
        self._output_path = ""
        self._start_time: float | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_results)

    # -- Properties ------------------------------------------------------

    def _get_pending_count(self) -> int:
        return self._pending_count

    pendingCount = Property(int, _get_pending_count, notify=pending_count_changed)  # noqa: N815

    def _get_pending_display(self) -> str:
        return self._pending_display

    pendingDisplay = Property(str, _get_pending_display, notify=pending_display_changed)  # noqa: N815

    def _get_result_text(self) -> str:
        return self._result_text

    resultText = Property(str, _get_result_text, notify=result_text_changed)  # noqa: N815

    def _get_log_text(self) -> str:
        return self._log_text

    logText = Property(str, _get_log_text, notify=log_text_changed)  # noqa: N815

    def _get_log_visible(self) -> bool:
        return self._log_visible

    logVisible = Property(bool, _get_log_visible, notify=log_visible_changed)  # noqa: N815

    def _get_progress_value(self) -> int:
        return self._progress_value

    progressValue = Property(int, _get_progress_value, notify=progress_value_changed)  # noqa: N815

    def _get_progress_max(self) -> int:
        return self._progress_max

    progressMax = Property(int, _get_progress_max, notify=progress_max_changed)  # noqa: N815

    def _get_progress_visible(self) -> bool:
        return self._progress_visible

    progressVisible = Property(bool, _get_progress_visible, notify=progress_visible_changed)  # noqa: N815

    def _get_progress_label(self) -> str:
        return self._progress_label

    progressLabel = Property(str, _get_progress_label, notify=progress_label_changed)  # noqa: N815

    def _get_is_hashing(self) -> bool:
        return self._is_hashing

    isHashing = Property(bool, _get_is_hashing, notify=is_hashing_changed)  # noqa: N815

    def _get_can_open_output(self) -> bool:
        return self._can_open_output

    canOpenOutput = Property(bool, _get_can_open_output, notify=can_open_output_changed)  # noqa: N815

    # -- Slots -----------------------------------------------------------

    @Slot(str, result=str)
    def urlToPath(self, url: str) -> str:  # noqa: N802
        """Convert a file URL to a local filesystem path."""
        return QUrl(url).toLocalFile()

    @Slot("QVariantList")
    def addFiles(self, urls: list[object]) -> None:  # noqa: N802
        """Add files or folders from a QML FileDialog or drop selection.

        If any dropped item is a directory, only the first directory is
        kept and all other items are discarded (single-folder constraint).
        """
        first_parent: str | None = None
        for url in urls:
            # drop.urls delivers QUrl objects; FileDialog delivers strings
            qurl = url if isinstance(url, QUrl) else QUrl(str(url))
            path = qurl.toLocalFile()
            if not path:
                continue
            p = Path(path)
            if p.is_dir():
                # Single-folder mode: replace everything with this folder
                self._pending = [path]
                self._update_pending()
                self.folderSelected.emit(path)
                return
            elif p.is_file():
                self._pending.append(path)
                if first_parent is None:
                    first_parent = str(p.parent)
        self._update_pending()
        if first_parent is not None:
            self.filesAdded.emit(first_parent)

    @Slot(str)
    def addFolder(self, url: str) -> None:  # noqa: N802
        """Replace pending items with a single folder."""
        path = QUrl(url).toLocalFile()
        if path:
            self._pending = [path]
            self._update_pending()
            self.folderSelected.emit(path)

    @Slot(str, str, bool, bool, str, str)
    def startHash(  # noqa: N802
        self,
        algorithm: str,
        fmt: str,
        recursive: bool,
        relative_paths: bool,
        base_dir: str,
        output_file: str,
    ) -> None:
        """Start hashing pending files."""
        if not self._pending or self._is_hashing:
            return

        algo = Algorithm.from_str(algorithm)
        self._current_format = HashFileFormat(fmt)
        self._output_path = output_file

        # Cache base dir for relativization
        if relative_paths and base_dir:
            self._cached_base = str(Path(os.path.abspath(base_dir)))
        else:
            self._cached_base = None

        # Build exclude filter from persisted settings
        patterns = SettingsModel.load_exclude_patterns()
        exclude_filter = ExcludeFilter(patterns) if patterns else None

        # Exclude output file from scanning
        exclude_paths = [Path(output_file)] if output_file else None

        # Reset
        self._results.clear()
        self._set_prop("_result_text", "", self.result_text_changed)
        self._set_prop("_log_text", "", self.log_text_changed)
        self._set_prop("_log_visible", True, self.log_visible_changed)
        self._set_prop("_progress_visible", True, self.progress_visible_changed)
        self._set_prop("_progress_max", 0, self.progress_max_changed)
        self._set_prop("_progress_value", 0, self.progress_value_changed)
        self._set_prop("_progress_label", _("Scanning files\u2026"), self.progress_label_changed)
        self._set_prop("_is_hashing", True, self.is_hashing_changed)
        self._set_prop("_can_open_output", False, self.can_open_output_changed)
        self._start_time = time.monotonic()

        paths = [Path(p) for p in self._pending]
        self._worker = HashWorker(
            paths, algo, exclude_filter, exclude_paths,
            recursive=recursive,
        )
        self._worker.scanning.connect(self._on_scanning)
        self._worker.scan_done.connect(self._on_scan_done)
        self._worker.work_finished.connect(self._on_finished)
        self._worker.work_cancelled.connect(self._on_cancelled)
        self._worker.work_error.connect(self._on_error)

        self._poll_timer.start()
        self._worker.start()

    @Slot()
    def cancelHash(self) -> None:  # noqa: N802
        """Request cancellation."""
        if self._worker:
            self._worker.request_cancel()

    @Slot()
    def clear(self) -> None:
        """Clear all state."""
        self._pending.clear()
        self._results.clear()
        self._update_pending()
        self._set_prop("_result_text", "", self.result_text_changed)
        self._set_prop("_log_text", "", self.log_text_changed)
        self._set_prop("_log_visible", False, self.log_visible_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)
        self._set_prop("_can_open_output", False, self.can_open_output_changed)


    @Slot(str)
    def openOutput(self, path: str) -> None:  # noqa: N802
        """Open output file with OS default application."""
        if path and Path(path).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))

    # -- Internal --------------------------------------------------------

    def _update_pending(self) -> None:
        self._set_prop("_pending_count", len(self._pending), self.pending_count_changed)
        self._set_prop(
            "_pending_display", "\n".join(self._pending), self.pending_display_changed,
        )

    def _relativize(self, result: HashResult) -> HashResult:
        if self._cached_base is None:
            return result
        try:
            rel = os.path.relpath(result.path, self._cached_base)
        except ValueError:
            return result
        if rel.startswith(".."):
            return result
        return HashResult(
            path=rel, algorithm=result.algorithm, hex_digest=result.hex_digest,
        )

    def _format_result(self, result: HashResult) -> str:
        if self._current_format is HashFileFormat.BSD:
            return HashFileFormatter.format_bsd(result)
        return HashFileFormatter.format_gnu(result)

    _BATCH_SIZE = 20

    def _update_progress_from_worker(self) -> None:
        """Sync progress properties from the worker's counters."""
        if self._worker is None:
            return
        if self._worker.is_scan_done:
            self._set_prop(
                "_progress_max", self._worker.submitted_count,
                self.progress_max_changed,
            )
        completed = self._worker.completed_count
        self._set_prop(
            "_progress_value", completed,
            self.progress_value_changed,
        )
        if self._worker.is_scan_done:
            self._set_prop(
                "_progress_label",
                _("Hashing: {} / {} files").format(completed, self._worker.submitted_count),
                self.progress_label_changed,
            )

    def _poll_results(self) -> None:
        if self._worker is None:
            return

        self._update_progress_from_worker()

        batch = self._worker.drain_results(self._BATCH_SIZE)
        if batch:
            self._accumulate(batch)

    def _accumulate(self, batch: list[tuple[int, HashResult]]) -> None:
        lines: list[str] = []
        for index, result in batch:
            self._results.append((index, result))
            display = self._relativize(result)
            lines.append(self._format_result(display))
        text = self._result_text
        if text:
            text += "\n" + "\n".join(lines)
        else:
            text = "\n".join(lines)
        # Rolling window: keep only the last 200 lines while hashing
        text_lines = text.split("\n")
        if len(text_lines) > 200:
            text = "\n".join(text_lines[-200:])
        self._set_prop("_result_text", text, self.result_text_changed)

    def _drain_all(self) -> None:
        if self._worker is None:
            return
        while True:
            batch = self._worker.drain_results(self._BATCH_SIZE)
            if not batch:
                break
            self._accumulate(batch)

    # Cap on the number of result lines kept in the QML TextArea.
    # Building a multi-MiB string for a million-file run would lock
    # the renderer; the full result is always written to disk via
    # atomic_write_text below.
    _DISPLAY_LINES = 1000

    def _write_sorted_output(self) -> None:
        self._results.sort(key=lambda item: item[0])
        sorted_lines = [
            self._format_result(self._relativize(r)) for _idx, r in self._results
        ]
        if len(sorted_lines) > self._DISPLAY_LINES:
            head = self._DISPLAY_LINES // 2
            tail = self._DISPLAY_LINES - head
            display_lines = (
                sorted_lines[:head]
                + [_("… ({} more lines hidden — see output file) …").format(
                    len(sorted_lines) - self._DISPLAY_LINES,
                )]
                + sorted_lines[-tail:]
            )
        else:
            display_lines = sorted_lines
        self._set_prop("_result_text", "\n".join(display_lines), self.result_text_changed)

        # Atomic write so a previous good manifest survives a crash mid-write.
        if self._output_path:
            try:
                atomic_write_text(
                    self._output_path,
                    "\n".join(sorted_lines) + ("\n" if sorted_lines else ""),
                )
                self._set_prop(
                    "_can_open_output", True, self.can_open_output_changed,
                )
            except OSError:
                self._set_prop(
                    "_can_open_output", False, self.can_open_output_changed,
                )

    # -- Worker signal handlers ------------------------------------------

    def _on_scanning(self) -> None:
        self._set_prop(
            "_progress_label", _("Scanning files\u2026"), self.progress_label_changed,
        )
        self._append_log(_("Scanning directory\u2026"))

    def _on_scan_done(self, total: int) -> None:
        self._set_prop("_progress_max", total, self.progress_max_changed)
        self._set_prop(
            "_progress_label", _("Hashing: {} / {} files").format(0, total),
            self.progress_label_changed,
        )
        self._append_log(_("Found {} file(s). Hashing\u2026").format(total))

    def _on_finished(self) -> None:
        self._poll_timer.stop()
        self._drain_all()
        self._update_progress_from_worker()
        self._write_sorted_output()
        elapsed = time.monotonic() - self._start_time if self._start_time is not None else 0.0
        elapsed_label = _("Completed in {:.2f}s").format(elapsed)
        self._append_log(
            _("Done. {} hash(es) written.").format(len(self._results))
            + "  \u2014  " + elapsed_label
        )
        self._set_prop("_is_hashing", False, self.is_hashing_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)

    def _on_cancelled(self) -> None:
        self._poll_timer.stop()
        self._drain_all()
        self._update_progress_from_worker()
        self._write_sorted_output()
        self._append_log(_("Cancelled. {} file(s) completed.").format(len(self._results)))
        self._set_prop("_is_hashing", False, self.is_hashing_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)

    def _on_error(self, message: str) -> None:
        self._poll_timer.stop()
        self._append_log(f"Error: {message}")
        self._set_prop("_is_hashing", False, self.is_hashing_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)


__all__ = ["HashViewModel"]
