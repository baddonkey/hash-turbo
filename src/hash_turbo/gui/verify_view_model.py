"""Verify view model — manages hash verification with background worker."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject, QTimer, QUrl, Property, Signal, Slot
from PySide6.QtGui import QDesktopServices

from hash_turbo.core.exclude_filter import ExcludeFilter
from hash_turbo.core.hash_file import HashFileParser
from hash_turbo.core.models import HashEntry, VerifyResult, VerifyStatus
from hash_turbo.gui._view_model_base import ViewModelBase
from hash_turbo.gui.settings_model import SettingsModel
from hash_turbo.gui.verify_worker import VerifyWorker
from hash_turbo.i18n import _
from hash_turbo.infra.atomic_write import atomic_write_text


@dataclass(frozen=True)
class VerifyOptions:
    """Bundles verification parameters to avoid long argument lists."""

    content: str
    hash_file_path: str
    base_dir: str
    custom_base: bool
    output_dir: str
    detect_new: bool
    flexible_ws: bool
    binary_only: bool


class VerifyViewModel(ViewModelBase):
    """Backend for the Verify tab."""

    # Property notification signals
    result_text_changed = Signal()
    log_text_changed = Signal()
    log_visible_changed = Signal()
    progress_value_changed = Signal()
    progress_max_changed = Signal()
    progress_visible_changed = Signal()
    progress_label_changed = Signal()
    is_verifying_changed = Signal()
    can_open_report_changed = Signal()
    is_loading_changed = Signal()
    fileLoaded = Signal(str, str)  # preview, local_path
    entry_count_changed = Signal()

    # Maximum lines shown in the QML TextArea preview.
    _PREVIEW_LINES = 200

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._result_text = ""
        self._log_text = ""
        self._log_visible = False
        self._progress_value = 0
        self._progress_max = 0
        self._progress_visible = False
        self._progress_label = ""
        self._is_verifying = False
        self._can_open_report = False
        self._is_loading = False
        self._entry_count = 0
        self._loaded_content: str | None = None

        self._hash_file_path: str = ""
        self._entries: list[HashEntry] = []
        self._verify_results: list[tuple[int, VerifyResult]] = []
        self._passed = 0
        self._failed = 0
        self._missing = 0
        self._last_new_files: list[str] = []
        self._report_path: Path | None = None
        self._output_dir: str = ""
        self._worker: VerifyWorker | None = None
        self._logged_scanning_new = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)
        self._poll_timer.timeout.connect(self._poll_results)
        self.fileLoaded.connect(self._on_file_loaded)

    # -- Properties ------------------------------------------------------

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

    def _get_is_verifying(self) -> bool:
        return self._is_verifying

    isVerifying = Property(bool, _get_is_verifying, notify=is_verifying_changed)  # noqa: N815

    def _get_can_open_report(self) -> bool:
        return self._can_open_report

    canOpenReport = Property(bool, _get_can_open_report, notify=can_open_report_changed)  # noqa: N815

    def _get_is_loading(self) -> bool:
        return self._is_loading

    isLoading = Property(bool, _get_is_loading, notify=is_loading_changed)  # noqa: N815

    def _get_entry_count(self) -> int:
        return self._entry_count

    entryCount = Property(int, _get_entry_count, notify=entry_count_changed)  # noqa: N815

    # -- Public read-only accessors (for tests / programmatic use) -------

    @property
    def passed_count(self) -> int:
        return self._passed

    @property
    def failed_count(self) -> int:
        return self._failed

    @property
    def missing_count(self) -> int:
        return self._missing

    @property
    def report_path(self) -> Path | None:
        return self._report_path

    # -- Slots -----------------------------------------------------------

    @Slot(str, result=str)
    def urlToPath(self, url: str) -> str:  # noqa: N802
        """Convert a file URL to a local filesystem path."""
        return QUrl(url).toLocalFile()

    @Slot(str, result=str)
    def parentDir(self, path: str) -> str:  # noqa: N802
        """Return the parent directory of a path."""
        return str(Path(path).parent) if path else ""

    @Slot(str, result=str)
    def loadFile(self, url: str) -> str:  # noqa: N802
        """Load a file asynchronously; emits fileLoaded(content, path) when done.

        Returns an empty string immediately — callers should connect to
        ``fileLoaded`` to receive the content once I/O finishes.
        """
        local_path = QUrl(url).toLocalFile()
        if not local_path or not Path(local_path).is_file():
            return ""
        self._hash_file_path = local_path
        self._load_from_path(local_path)
        return ""

    @Slot(str)
    def reloadFile(self, local_path: str) -> None:  # noqa: N802
        """Re-read a previously loaded file from disk."""
        if not local_path or not Path(local_path).is_file():
            return
        self._hash_file_path = local_path
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

    @Slot(str, str, str, bool, str, bool, bool, bool)
    def verify(  # noqa: N802
        self,
        content: str,
        hash_file_path: str,
        base_dir: str,
        custom_base: bool,
        output_dir: str,
        detect_new: bool,
        flexible_ws: bool,
        binary_only: bool,
    ) -> None:
        """Parse entries and start background verification."""
        effective_content = self._loaded_content if self._loaded_content is not None else content
        self._loaded_content = None
        opts = VerifyOptions(
            content=effective_content,
            hash_file_path=hash_file_path,
            base_dir=base_dir,
            custom_base=custom_base,
            output_dir=output_dir,
            detect_new=detect_new,
            flexible_ws=flexible_ws,
            binary_only=binary_only,
        )
        self._start_verify(opts)

    def _start_verify(self, opts: VerifyOptions) -> None:
        """Internal implementation that accepts a bundled options object."""
        content = opts.content.strip()
        if not content or self._is_verifying:
            return

        try:
            entries = HashFileParser.parse(
                content, flexible_whitespace=opts.flexible_ws,
            )
        except ValueError:
            self._set_prop("_log_visible", True, self.log_visible_changed)
            self._append_log(_("Error: could not parse hash entries"))
            return

        if not entries:
            return

        self._entries = entries
        self._hash_file_path = opts.hash_file_path

        if opts.custom_base and opts.base_dir:
            effective_base = Path(opts.base_dir)
        elif opts.hash_file_path:
            effective_base = Path(opts.hash_file_path).parent
        else:
            effective_base = Path.cwd()

        # Reset
        self._verify_results.clear()
        self._passed = 0
        self._failed = 0
        self._missing = 0
        self._last_new_files.clear()
        self._logged_scanning_new = False
        self._output_dir = opts.output_dir
        self._set_prop("_result_text", "", self.result_text_changed)
        self._set_prop("_log_text", "", self.log_text_changed)
        self._set_prop("_log_visible", True, self.log_visible_changed)
        self._set_prop("_progress_visible", True, self.progress_visible_changed)
        self._set_prop("_progress_max", len(entries), self.progress_max_changed)
        self._set_prop("_progress_value", 0, self.progress_value_changed)
        self._set_prop(
            "_progress_label",
            _("Verifying\u2026 {} / {} files").format(0, len(entries)),
            self.progress_label_changed,
        )
        self._set_prop("_is_verifying", True, self.is_verifying_changed)
        self._set_prop("_can_open_report", False, self.can_open_report_changed)

        self._append_log(
            _("Verifying {} hash(es) against {}\u2026").format(len(entries), effective_base)
        )

        patterns = SettingsModel.load_exclude_patterns()
        exclude_filter = ExcludeFilter(patterns) if patterns else None

        exclude_paths: list[Path] = []
        if opts.hash_file_path:
            hp = Path(opts.hash_file_path)
            exclude_paths.append(hp)
            report_name = f"{hp.name}.verify.log"
            exclude_paths.append(hp.parent / report_name)
            if opts.output_dir:
                exclude_paths.append(Path(opts.output_dir) / report_name)

        self._worker = VerifyWorker(
            entries,
            effective_base,
            detect_new=opts.detect_new,
            binary_only=opts.binary_only,
            exclude_filter=exclude_filter,
            exclude_paths=exclude_paths or None,
        )
        self._worker.work_finished.connect(self._on_finished)
        self._worker.work_error.connect(self._on_error)
        self._worker.start()
        self._poll_timer.start()

    @Slot()
    def cancel(self) -> None:
        """Cancel the running verification."""
        if self._worker is None:
            return
        self._worker.request_cancel()
        self._poll_timer.stop()
        self._drain_all()
        self._worker.wait(3000)
        self._worker = None
        self._append_log(
            _("Cancelled. {} file(s) verified.").format(len(self._verify_results))
        )
        self._set_prop("_is_verifying", False, self.is_verifying_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)

    @Slot()
    def clear(self) -> None:
        """Reset all state for a fresh verification."""
        if self._worker is not None:
            self.cancel()
        self._entries.clear()
        self._verify_results.clear()
        self._passed = 0
        self._failed = 0
        self._missing = 0
        self._hash_file_path = ""
        self._loaded_content = None
        self._set_prop("_entry_count", 0, self.entry_count_changed)
        self._last_new_files.clear()
        self._report_path = None
        self._set_prop("_result_text", "", self.result_text_changed)
        self._set_prop("_log_text", "", self.log_text_changed)
        self._set_prop("_log_visible", False, self.log_visible_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)
        self._set_prop("_can_open_report", False, self.can_open_report_changed)
        self._set_prop("_is_verifying", False, self.is_verifying_changed)

    @Slot()
    def openReport(self) -> None:  # noqa: N802
        """Open the report file with the OS default application."""
        if self._report_path and self._report_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._report_path)))

    @Slot(str)
    def openHashFile(self, path: str) -> None:  # noqa: N802
        """Open a hash file with the OS default application."""
        if path and Path(path).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    # -- Internal --------------------------------------------------------

    def _on_file_loaded(self) -> None:
        self._set_loading(False)

    def _set_loading(self, value: bool) -> None:
        if self._is_loading != value:
            self._is_loading = value
            self.is_loading_changed.emit()

    _BATCH_SIZE = 20

    def _poll_results(self) -> None:
        if self._worker is None:
            return

        self._set_prop(
            "_progress_value", self._worker.completed_count,
            self.progress_value_changed,
        )

        if self._worker.is_scanning_new:
            self._set_prop(
                "_progress_label", _("Detecting new files\u2026"),
                self.progress_label_changed,
            )
            if not self._logged_scanning_new:
                self._logged_scanning_new = True
                c = self._worker.completed_count
                t = self._worker.total_count
                self._append_log(
                    _("Verified {}/{}. Scanning for new files\u2026").format(c, t)
                )
        else:
            c = self._worker.completed_count
            t = self._worker.total_count
            parts = [_("Verifying\u2026 {} / {} files").format(c, t)]
            if self._passed:
                parts.append(_("{} passed").format(self._passed))
            if self._failed:
                parts.append(_("{} failed").format(self._failed))
            if self._missing:
                parts.append(_("{} missing").format(self._missing))
            self._set_prop(
                "_progress_label", "  \u2014  ".join(parts),
                self.progress_label_changed,
            )

        batch = self._worker.drain_results(self._BATCH_SIZE)
        if batch:
            self._accumulate(batch)

    def _accumulate(self, batch: list[tuple[int, VerifyResult]]) -> None:
        lines: list[str] = []
        for index, vr in batch:
            self._verify_results.append((index, vr))
            if vr.status is VerifyStatus.OK:
                self._passed += 1
                lines.append(f"OK      {vr.entry.path}")
            elif vr.status is VerifyStatus.FAILED:
                self._failed += 1
                lines.append(
                    f"FAILED  {vr.entry.path}  (expected: {vr.entry.expected_hash})"
                )
            else:
                self._missing += 1
                lines.append(f"MISSING {vr.entry.path}")
        text = self._result_text
        if text:
            text += "\n" + "\n".join(lines)
        else:
            text = "\n".join(lines)
        # Rolling window: keep only the last 200 lines while verifying
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

    def _on_finished(self) -> None:
        self._poll_timer.stop()
        if self._worker is None:
            return
        self._drain_all()

        # Reorder results by manifest index
        self._verify_results.sort(key=lambda item: item[0])
        ordered: list[str] = []
        results_for_report: list[VerifyResult] = []
        for _idx, vr in self._verify_results:
            results_for_report.append(vr)
            if vr.status is VerifyStatus.OK:
                ordered.append(f"OK      {vr.entry.path}")
            elif vr.status is VerifyStatus.FAILED:
                ordered.append(
                    f"FAILED  {vr.entry.path}  (expected: {vr.entry.expected_hash})"
                )
            else:
                ordered.append(f"MISSING {vr.entry.path}")

        new_files = self._worker.new_files
        for nf in new_files:
            ordered.append(f"NEW     {nf}")
        self._last_new_files = new_files

        self._set_prop("_result_text", "\n".join(ordered), self.result_text_changed)

        total = len(self._entries)
        self._write_report(
            results_for_report, total,
            self._passed, self._failed, self._missing, new_files,
        )

        new_count = len(new_files)
        self._append_log(
            _("Done. Passed: {}  Failed: {}  Missing: {}  New: {}").format(
                self._passed, self._failed, self._missing, new_count,
            )
        )
        self._set_prop("_is_verifying", False, self.is_verifying_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)
        self._worker = None

    def _on_error(self, message: str) -> None:
        self._poll_timer.stop()
        self._worker = None
        self._append_log(_("Error: {}").format(message))
        self._set_prop("_is_verifying", False, self.is_verifying_changed)
        self._set_prop("_progress_visible", False, self.progress_visible_changed)

    def _write_report(
        self,
        results: list[VerifyResult],
        total: int,
        passed: int,
        failed: int,
        missing: int,
        new_files: list[str],
    ) -> None:
        if self._output_dir:
            output_dir = Path(self._output_dir)
        elif self._hash_file_path:
            output_dir = Path(self._hash_file_path).parent
        else:
            self._set_prop(
                "_can_open_report", False, self.can_open_report_changed,
            )
            return

        if self._hash_file_path:
            report_name = f"{Path(self._hash_file_path).name}.verify.log"
            hash_file_label = self._hash_file_path
        else:
            report_name = "verify.log"
            hash_file_label = "(pasted content)"

        self._report_path = Path(os.path.abspath(output_dir / report_name))
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            _("hash-turbo verification report"),
            _("Date: {}").format(timestamp),
            _("Hash file: {}").format(hash_file_label),
            "",
            _("Total: {}  Passed: {}  Failed: {}  Missing: {}  New: {}").format(
                total, passed, failed, missing, len(new_files),
            ),
            "",
        ]

        for vr in results:
            if vr.status is VerifyStatus.OK:
                lines.append(f"  OK      {vr.entry.path}")
            elif vr.status is VerifyStatus.FAILED:
                lines.append(f"  FAILED  {vr.entry.path}")
                lines.append(f"          expected: {vr.entry.expected_hash}")
            else:
                lines.append(f"  MISSING {vr.entry.path}")

        if new_files:
            lines.append("")
            lines.append(_("New files (no hash entry):"))
            for nf in new_files:
                lines.append(f"  NEW     {nf}")

        try:
            atomic_write_text(self._report_path, "\n".join(lines) + "\n")
            self._set_prop(
                "_can_open_report", True, self.can_open_report_changed,
            )
        except OSError:
            self._set_prop(
                "_can_open_report", False, self.can_open_report_changed,
            )


__all__ = ["VerifyViewModel"]
