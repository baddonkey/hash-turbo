"""PySide6 QML application entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_APP_ID = "hash-turbo.hash-turbo.gui.1"


def _fix_windows_dll_search() -> None:
    """Add PySide6 directory to Windows DLL search path.

    PySide6's __init__ only adds shiboken6 via os.add_dll_directory(),
    and puts its own directory on PATH. On Python 3.8+ Windows restricts
    DLL loading to directories registered with os.add_dll_directory(),
    so QML plugin DLLs fail to resolve their Qt dependencies.
    """
    if sys.platform != "win32":
        return
    try:
        import PySide6

        pyside_dir = Path(PySide6.__file__).parent.resolve()
        os.add_dll_directory(os.fspath(pyside_dir))
    except (ImportError, OSError):
        pass


def _set_windows_app_id() -> None:
    """Set the Windows AppUserModelID so the taskbar shows our icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass


def _set_macos_dock_icon(icon_path: Path) -> None:
    """Set the macOS dock icon at runtime via AppKit."""
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSData  # type: ignore[import-untyped]
        from AppKit import NSApplication, NSImage  # type: ignore[import-untyped]

        data = NSData.dataWithContentsOfFile_(str(icon_path))
        if data is None:
            return
        image = NSImage.alloc().initWithData_(data)
        NSApplication.sharedApplication().setApplicationIconImage_(image)
    except ImportError:
        pass


def _set_macos_process_name(name: str) -> None:
    """Set the macOS menu bar title to the app name instead of 'Python'."""
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle  # type: ignore[import-untyped]

        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = name
    except ImportError:
        pass


def _set_windows_taskbar_icon(hwnd: int, ico_path: Path) -> None:
    """Force-set the taskbar and title-bar icon via Win32 SendMessage.

    ``QGuiApplication.setWindowIcon`` is often ignored on Windows when
    the process executable (e.g. a pip console-scripts wrapper) embeds
    Python's icon.  Sending ``WM_SETICON`` directly on the HWND
    overrides the taskbar icon reliably.
    """
    if sys.platform != "win32" or not ico_path.exists():
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_SHARED = 0x8000

        load_image = user32.LoadImageW
        load_image.restype = wintypes.HANDLE
        load_image.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]

        ico_str = str(ico_path)
        flags = LR_LOADFROMFILE | LR_SHARED

        big = load_image(None, ico_str, IMAGE_ICON, 32, 32, flags)
        small = load_image(None, ico_str, IMAGE_ICON, 16, 16, flags)

        send = user32.SendMessageW
        if big:
            send(hwnd, WM_SETICON, ICON_BIG, big)
        if small:
            send(hwnd, WM_SETICON, ICON_SMALL, small)
    except (AttributeError, OSError):
        pass


class GuiApp:
    """Manages the PySide6 QML application lifecycle."""

    @staticmethod
    def _create_engine() -> tuple[
        "QApplication", "QQmlApplicationEngine", dict[str, object],
    ]:
        """Build the QML engine and view models without entering the event loop.

        Returns ``(app, engine, models)`` where *models* maps context
        property names to their view-model instances.
        """
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QIcon
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
        from PySide6.QtWidgets import QApplication

        from hash_turbo import __version__
        from hash_turbo.gui.gettext_translator import GettextTranslator
        from hash_turbo.gui.hash_view_model import HashViewModel
        from hash_turbo.gui.sanitize_view_model import SanitizeViewModel
        from hash_turbo.gui.settings_model import SettingsModel
        from hash_turbo.gui.verify_view_model import VerifyViewModel

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # Install gettext-backed translator so QML qsTr() resolves via gettext
        translator = GettextTranslator(app)
        app.installTranslator(translator)

        app.setApplicationName("hash-turbo")
        app.setApplicationDisplayName("hash-turbo")
        app.setOrganizationName("hash-turbo")

        assets_dir = Path(__file__).parent.parent / "assets"
        ico_path = assets_dir / "icon.ico"
        png_path = assets_dir / "icon.png"
        if ico_path.exists():
            app.setWindowIcon(QIcon(str(ico_path)))
        elif png_path.exists():
            app.setWindowIcon(QIcon(str(png_path)))

        # Set macOS dock icon early so it appears as soon as the app launches.
        _set_macos_dock_icon(png_path)

        QQuickStyle.setStyle("Material")

        engine = QQmlApplicationEngine()

        # Create view models
        settings_model = SettingsModel()
        hash_model = HashViewModel()
        verify_model = VerifyViewModel()
        sanitize_model = SanitizeViewModel()

        models: dict[str, object] = {
            "settingsModel": settings_model,
            "hashModel": hash_model,
            "verifyModel": verify_model,
            "sanitizeModel": sanitize_model,
        }

        # Expose to QML context
        ctx = engine.rootContext()
        ctx.setContextProperty("appVersion", __version__)
        for name, model in models.items():
            ctx.setContextProperty(name, model)

        manual_path = assets_dir / "user-manual.pdf"
        if not manual_path.exists():
            # Dev mode: look in the project docs/ directory
            dev_manual = Path(__file__).parent.parent.parent.parent / "docs" / "user-manual.pdf"
            if dev_manual.exists():
                manual_path = dev_manual
        ctx.setContextProperty(
            "userManualUrl",
            QUrl.fromLocalFile(str(manual_path)).toString() if manual_path.exists() else "",
        )

        # Third-party licenses text — bundled beside assets in frozen builds,
        # or read from the project root in dev mode.
        _licenses_candidates = [
            assets_dir / "THIRD-PARTY-LICENSES.md",
            Path(__file__).parent.parent.parent.parent / "THIRD-PARTY-LICENSES.md",
        ]
        _licenses_text = ""
        for _p in _licenses_candidates:
            if _p.exists():
                _licenses_text = _p.read_text(encoding="utf-8")
                break
        ctx.setContextProperty("thirdPartyLicensesText", _licenses_text)

        qml_path = Path(__file__).parent / "qml" / "Main.qml"
        engine.load(QUrl.fromLocalFile(str(qml_path)))

        if not engine.rootObjects():
            sys.exit(-1)

        # Re-evaluate all qsTr() bindings in live QML objects when language changes.
        settings_model.retranslate_requested.connect(engine.retranslate)

        return app, engine, models

    @staticmethod
    def run() -> None:
        """Launch the hash-turbo GUI application with QML."""
        import logging

        from hash_turbo.infra.logging import LoggingSetup

        # GUI sessions get the rotating file log so users can attach it
        # to bug reports; CLI invocations stay stderr-only.
        LoggingSetup.configure(level=logging.INFO, file_logging=True)
        _set_windows_app_id()
        _fix_windows_dll_search()
        _set_macos_process_name("hash-turbo")

        app, engine, _models = GuiApp._create_engine()

        assets_dir = Path(__file__).parent.parent / "assets"
        ico_path = assets_dir / "icon.ico"

        root_window = engine.rootObjects()[0]
        if sys.platform == "win32":
            _set_windows_taskbar_icon(root_window.winId(), ico_path)
        sys.exit(app.exec())


__all__ = ["GuiApp"]
