"""Sanitize view model — async hash file transformation with cancellation."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject, QUrl, Property, Signal, Slot
from PySide6.QtGui import QDesktopServices

from hash_turbo.gui._view_model_base import ViewModelBase
from hash_turbo.gui.sanitize_worker import SanitizeWorker
from hash_turbo.i18n import _


class SanitizeViewModel(ViewModelBase):
    """Backend for the Sanitize tab — parse, transform, and format hash entries."""

    output_text_changed = Signal()
    is_sanitizing_changed = Signal()
    is_loading_changed = Signal()
    fileLoaded = Signal(str, str)  # preview, local_path
    entry_count_changed = Signal()
    result_entries_changed = Signal()
    output_path_changed = Signal()
    can_open_result_changed = Signal()
    log_text_changed = Signal()

    # Maximum lines shown in the QML TextArea preview.
    _PREVIEW_LINES = 200

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._output_text = ""
        self._is_sanitizing = False
        self._is_loading = False
        self._entry_count = 0
        self._loaded_content: str | None = None
        self._worker: SanitizeWorker | None = None
        self._result_entries: list[dict[str, str]] = []
        self._output_path = ""
        self._can_open_result = False
        self._log_text = ""
        self._start_time: float | None = None
        self.fileLoaded.connect(self._on_file_loaded)

    # -- outputText property ---------------------------------------------

    def _get_output_text(self) -> str:
        return self._output_text

    outputText = Property(str, _get_output_text, notify=output_text_changed)  # noqa: N815

    # -- isSanitizing property -------------------------------------------

    def _get_is_sanitizing(self) -> bool:
        return self._is_sanitizing

    isSanitizing = Property(bool, _get_is_sanitizing, notify=is_sanitizing_changed)  # noqa: N815

    # -- isLoading property ----------------------------------------------

    def _get_is_loading(self) -> bool:
        return self._is_loading

    isLoading = Property(bool, _get_is_loading, notify=is_loading_changed)  # noqa: N815

    def _get_entry_count(self) -> int:
        return self._entry_count

    entryCount = Property(int, _get_entry_count, notify=entry_count_changed)  # noqa: N815

    def _get_result_entries(self) -> list[dict[str, str]]:
        return self._result_entries

    resultEntries = Property(list, _get_result_entries, notify=result_entries_changed)  # noqa: N815

    def _get_output_path(self) -> str:
        return self._output_path

    def _set_output_path_value(self, value: str) -> None:
        if self._output_path != value:
            self._output_path = value
            self.output_path_changed.emit()

    outputPath = Property(str, _get_output_path, _set_output_path_value, notify=output_path_changed)  # noqa: N815

    def _get_can_open_result(self) -> bool:
        return self._can_open_result

    canOpenResult = Property(bool, _get_can_open_result, notify=can_open_result_changed)  # noqa: N815

    def _get_log_text(self) -> str:
        return self._log_text

    logText = Property(str, _get_log_text, notify=log_text_changed)  # noqa: N815

    # -- slots -----------------------------------------------------------

    @Slot(str, result=str)
    def urlToPath(self, url: str) -> str:  # noqa: N802
        """Convert a file URL to a local filesystem path."""
        return QUrl(url).toLocalFile()

    @Slot(str)
    def loadFile(self, url: str) -> None:  # noqa: N802
        """Load a file asynchronously; emits fileLoaded(content, path) when done."""
        local_path = QUrl(url).toLocalFile()
        if not local_path:
            return
        self._load_from_path(local_path)

    @Slot(str)
    def reloadFile(self, local_path: str) -> None:  # noqa: N802
        """Re-read a previously loaded file from disk."""
        if not local_path or not Path(local_path).is_file():
            return
        self._load_from_path(local_path)

    def _load_from_path(self, local_path: str) -> None:
        """Shared helper — read *local_path* in a background thread."""
        self._set_loading(True)

        def _read() -> None:
            try:
                content = Path(local_path).read_text(encoding="utf-8")
            except OSError:
                content = ""
            self._loaded_content = content
            lines = content.splitlines()
            count = len([ln for ln in lines if ln.strip()])
            self._entry_count = count
            self.entry_count_changed.emit()
            if len(lines) > self._PREVIEW_LINES:
                preview = "\n".join(lines[: self._PREVIEW_LINES])
            else:
                preview = content
            self.fileLoaded.emit(preview, local_path)

        Thread(target=_read, daemon=True).start()

    @Slot(str, str, str, str, str, str, bool, bool, str)
    def transform(  # noqa: PLR0913
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
        """Launch the transform in a background thread."""
        effective_content = self._loaded_content if self._loaded_content is not None else content
        self._loaded_content = None
        self._set_prop("_log_text", "", self.log_text_changed)
        self._set_sanitizing(True)
        self._start_time = time.monotonic()

        worker = SanitizeWorker(
            effective_content, fmt, separator, strip_prefix,
            hash_case, sort_key, deduplicate, normalize_ws, line_ending,
        )
        worker.finished_with_result.connect(self._on_finished)
        worker.work_error.connect(self._on_error)
        worker.work_cancelled.connect(self._on_cancelled)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    @Slot()
    def cancelTransform(self) -> None:  # noqa: N802
        """Request cancellation of the running transform."""
        if self._worker is not None:
            self._worker.request_cancel()

    @Slot(str, result=str)
    def defaultOutputPath(self, input_path: str) -> str:  # noqa: N802
        """Derive a default output path: ``<stem>-sanitized.<suffix>``."""
        if not input_path:
            return ""
        p = Path(input_path)
        return str(p.with_stem(p.stem + "-sanitized"))

    @Slot(str)
    def openHashFile(self, path: str) -> None:  # noqa: N802
        """Open a hash file with the OS default application."""
        if path and Path(path).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    @Slot()
    def openResult(self) -> None:  # noqa: N802
        """Open the output file with the OS default application."""
        if self._output_path and Path(self._output_path).is_file():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(self._output_path).resolve())),
            )

    @Slot()
    def clear(self) -> None:
        """Reset output text and result entries."""
        self._loaded_content = None
        self._entry_count = 0
        self.entry_count_changed.emit()
        self._set_output_text("")
        self._result_entries = []
        self.result_entries_changed.emit()
        self._set_can_open_result(False)
        self._set_prop("_log_text", "", self.log_text_changed)

    # -- worker callbacks ------------------------------------------------

    def _on_file_loaded(self) -> None:
        self._set_loading(False)

    def _on_finished(self, result: str, entries: list[dict[str, str]]) -> None:
        self._set_output_text(result)
        self._result_entries = entries
        self.result_entries_changed.emit()
        self._auto_save(result)
        elapsed = time.monotonic() - self._start_time if self._start_time is not None else 0.0
        elapsed_label = _("Completed in {:.2f}s").format(elapsed)
        entry_count = len(entries)
        self._append_log(
            _("Done. {} entries.").format(entry_count) + "  \u2014  " + elapsed_label
        )
        self._set_sanitizing(False)

    def _on_error(self, message: str) -> None:
        self._set_output_text(_("Error: {}").format(message))
        self._append_log(_("Error: {}").format(message))
        self._set_sanitizing(False)

    def _on_cancelled(self) -> None:
        self._append_log(_("Cancelled."))
        self._set_sanitizing(False)

    # -- internal --------------------------------------------------------

    def _set_sanitizing(self, value: bool) -> None:
        if self._is_sanitizing != value:
            self._is_sanitizing = value
            self.is_sanitizing_changed.emit()

    def _set_loading(self, value: bool) -> None:
        if self._is_loading != value:
            self._is_loading = value
            self.is_loading_changed.emit()

    def _set_output_text(self, value: str) -> None:
        if self._output_text != value:
            self._output_text = value
            self.output_text_changed.emit()

    def _set_can_open_result(self, value: bool) -> None:
        if self._can_open_result != value:
            self._can_open_result = value
            self.can_open_result_changed.emit()

    def _auto_save(self, content: str) -> None:
        """Write *content* to the configured output path.

        Uses an atomic write so an interrupted save can never replace
        the user's previous output with a truncated file.
        """
        path = self._output_path
        if not path or not content.strip():
            return
        try:
            from hash_turbo.infra.atomic_write import atomic_write_bytes

            atomic_write_bytes(path, content.encode("utf-8"))
            self._set_can_open_result(True)
        except OSError:
            self._set_output_text(_("Error: could not write to {}").format(path))


__all__ = ["SanitizeViewModel"]
