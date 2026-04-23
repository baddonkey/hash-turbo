#!/usr/bin/env python3
"""Capture documentation screenshots of all four hash-turbo GUI views.

Populates each view with realistic sample data (files, hash results,
verification output, sanitize transforms) before capturing.

Run from the project root with the venv activated:
    python scripts/capture_screenshots.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure src/ is importable
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

SCREENSHOT_DIR = _project_root / "docs" / "screenshots"

VIEW_NAMES = ["hash-view", "verify-view", "sanitize-view", "settings-view"]

# -- Sample data -----------------------------------------------------------

SAMPLE_FILES = {
    "alpha.txt": "alpha content",
    "bravo.txt": "bravo content",
    "charlie.txt": "charlie content",
    "delta.bin": "delta binary payload",
    "echo.log": "echo log output data",
}

GNU_SAMPLE = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 *empty.txt\n"
    "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef *README.md\n"
    "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08 *src/main.py\n"
    "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592 *docs/SPEC.md\n"
    "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8 *tests/test_app.py\n"
    "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824 *src/utils.py\n"
    "b133a0c0e9bee3be20163d2ad31d6248db292aa6dcb1ee087a2aa50e0fc75ae2 *config.yaml\n"
)


def _create_sample_dir(base: Path) -> Path:
    """Create a directory with sample files for hashing and verification."""
    for name, content in SAMPLE_FILES.items():
        (base / name).write_text(content, encoding="utf-8")
    return base


def _create_hash_file(directory: Path) -> Path:
    """Generate a real SHA-256 hash file for the sample files."""
    lines: list[str] = []
    for child in sorted(directory.iterdir()):
        if child.is_file() and child.suffix != ".sha256":
            digest = hashlib.sha256(child.read_bytes()).hexdigest()
            lines.append(f"{digest} *{child.name}")
    hash_file = directory / "checksums.sha256"
    hash_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hash_file


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # Create temp directory with sample data
    tmp_dir = Path(tempfile.mkdtemp(prefix="hash-turbo-screenshots-"))
    sample_dir = tmp_dir / "project-files"
    sample_dir.mkdir(parents=True, exist_ok=True)
    _create_sample_dir(sample_dir)
    hash_file = _create_hash_file(sample_dir)

    try:
        _run_gui(tmp_dir, sample_dir, hash_file)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_gui(tmp_dir: Path, sample_dir: Path, hash_file: Path) -> None:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("hash-turbo")
    app.setOrganizationName("hash-turbo")

    QQuickStyle.setStyle("Material")

    # Force English locale before importing view models
    from hash_turbo.i18n import apply_language
    apply_language("en")

    from hash_turbo import __version__
    from hash_turbo.gui.gettext_translator import GettextTranslator
    from hash_turbo.gui.hash_view_model import HashViewModel
    from hash_turbo.gui.sanitize_view_model import SanitizeViewModel
    from hash_turbo.gui.settings_model import SettingsModel
    from hash_turbo.gui.verify_view_model import VerifyViewModel

    translator = GettextTranslator(app)
    app.installTranslator(translator)

    engine = QQmlApplicationEngine()

    settings_model = SettingsModel()
    hash_model = HashViewModel()
    verify_model = VerifyViewModel()
    sanitize_model = SanitizeViewModel()

    ctx = engine.rootContext()
    ctx.setContextProperty("appVersion", __version__)
    ctx.setContextProperty("settingsModel", settings_model)
    ctx.setContextProperty("hashModel", hash_model)
    ctx.setContextProperty("verifyModel", verify_model)
    ctx.setContextProperty("sanitizeModel", sanitize_model)
    ctx.setContextProperty("userManualUrl", "")

    qml_path = _project_root / "src" / "hash_turbo" / "gui" / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        print("ERROR: Failed to load QML", file=sys.stderr)
        sys.exit(1)

    root_window = engine.rootObjects()[0]

    # Write a GNU hash file for the sanitize tab to load
    sanitize_input_file = tmp_dir / "gnu-checksums.sha256"
    sanitize_input_file.write_text(GNU_SAMPLE, encoding="utf-8")

    def force_light_theme() -> None:
        settings_model._theme = "light"
        settings_model.theme_changed.emit()

    def switch_tab(index: int) -> None:
        header = root_window.property("header")
        if header:
            header.setProperty("currentIndex", index)

    def grab(name: str) -> None:
        output_path = SCREENSHOT_DIR / f"{name}.png"
        img = root_window.grabWindow()
        img.save(str(output_path))
        idx = VIEW_NAMES.index(name) + 1
        print(f"  [{idx}/{len(VIEW_NAMES)}] {output_path.name}")

    def set_comboboxes(view_index: int, indices: list[int]) -> None:
        """Set ComboBox currentIndex values in a StackLayout view.

        *indices* maps to ComboBoxes in document order within the view.
        """
        from PySide6.QtCore import QObject

        stack = None
        for child in root_window.findChildren(QObject):
            if "StackLayout" in child.metaObject().className():
                stack = child
                break
        if stack is None:
            return

        views = stack.childItems()
        if view_index >= len(views):
            return

        combos = [
            child
            for child in views[view_index].findChildren(QObject)
            if "ComboBox" in child.metaObject().className()
        ]
        for i, idx in enumerate(indices):
            if i < len(combos):
                combos[i].setProperty("currentIndex", idx)

    # ── Step 0: Hash tab — add folder, hash, wait for results ──────────
    def step_0_hash_start() -> None:
        switch_tab(0)
        folder_url = QUrl.fromLocalFile(str(sample_dir)).toString()
        hash_model.addFolder(folder_url)
        output_file = str(tmp_dir / "output" / "checksums.sha256")
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        hash_model.startHash(
            "sha256", "gnu", True, True, str(sample_dir), output_file,
        )
        QTimer.singleShot(100, step_0_hash_wait)

    def step_0_hash_wait() -> None:
        if hash_model.isHashing:
            QTimer.singleShot(100, step_0_hash_wait)
            return
        QTimer.singleShot(500, step_0_hash_grab)

    def step_0_hash_grab() -> None:
        grab("hash-view")
        QTimer.singleShot(300, step_1_verify_load)

    # ── Step 1: Verify tab — load hash file, then verify ───────────────
    def step_1_verify_load() -> None:
        switch_tab(1)
        url = QUrl.fromLocalFile(str(hash_file)).toString()
        verify_model.loadFile(url)
        QTimer.singleShot(100, step_1_verify_wait_load)

    def step_1_verify_wait_load() -> None:
        if verify_model.isLoading:
            QTimer.singleShot(100, step_1_verify_wait_load)
            return
        # File loaded — input TextArea is now populated via onFileLoaded.
        # Start verification using the loaded content.
        QTimer.singleShot(200, step_1_verify_run)

    def step_1_verify_run() -> None:
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(sample_dir), False,
            str(sample_dir), True, True, True,
        )
        QTimer.singleShot(100, step_1_verify_wait)

    def step_1_verify_wait() -> None:
        if verify_model.isVerifying:
            QTimer.singleShot(100, step_1_verify_wait)
            return
        QTimer.singleShot(500, step_1_verify_grab)

    def step_1_verify_grab() -> None:
        grab("verify-view")
        QTimer.singleShot(300, step_2_sanitize_load)

    # ── Step 2: Sanitize tab — load file, then transform GNU → BSD ─────
    def step_2_sanitize_load() -> None:
        switch_tab(2)
        url = QUrl.fromLocalFile(str(sanitize_input_file)).toString()
        sanitize_model.loadFile(url)
        QTimer.singleShot(100, step_2_sanitize_wait_load)

    def step_2_sanitize_wait_load() -> None:
        if sanitize_model.isLoading:
            QTimer.singleShot(100, step_2_sanitize_wait_load)
            return
        # File loaded — input TextArea is now populated via onFileLoaded.
        # Set ComboBoxes to match transform params:
        # fmtCombo=BSD(1), sepCombo=POSIX(1), caseCombo=Lower(1),
        # sortCombo=path(1), endingCombo=LF(1)
        set_comboboxes(2, [1, 1, 1, 1, 1])
        QTimer.singleShot(200, step_2_sanitize_run)

    def step_2_sanitize_run() -> None:
        sanitize_model.transform(
            GNU_SAMPLE, "bsd", "posix", "",
            "lower", "path", False, True, "lf",
        )
        QTimer.singleShot(100, step_2_sanitize_wait)

    def step_2_sanitize_wait() -> None:
        if sanitize_model.isSanitizing:
            QTimer.singleShot(100, step_2_sanitize_wait)
            return
        QTimer.singleShot(500, step_2_sanitize_grab)

    def step_2_sanitize_grab() -> None:
        grab("sanitize-view")
        QTimer.singleShot(300, step_3_settings)

    # ── Step 3: Settings tab — just show defaults ─────────────────────
    def step_3_settings() -> None:
        switch_tab(3)
        QTimer.singleShot(500, step_3_settings_grab)

    def step_3_settings_grab() -> None:
        grab("settings-view")
        print(f"Done — {len(VIEW_NAMES)} screenshots saved to {SCREENSHOT_DIR}/")
        app.quit()

    # Kick off: force light theme after QML init, then start capture pipeline
    QTimer.singleShot(300, force_light_theme)
    QTimer.singleShot(800, step_0_hash_start)

    app.exec()


if __name__ == "__main__":
    main()
