"""Shared fixtures for GUI view model tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Generator

import pytest
from pytestqt.qtbot import QtBot

from hash_turbo.gui.hash_view_model import HashViewModel
from hash_turbo.gui.sanitize_view_model import SanitizeViewModel
from hash_turbo.gui.verify_view_model import VerifyViewModel
from hash_turbo.i18n import current_language, set_language

_VISUAL_DELAY_MS = 1200


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Initialize QtWebEngine before QApplication is created by pytest-qt."""
    try:
        from PySide6.QtWebEngineQuick import QtWebEngineQuick
        QtWebEngineQuick.initialize()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _ensure_english_locale() -> Generator[None, None, None]:
    previous = current_language()
    set_language("en")
    yield
    set_language(previous)


@pytest.fixture
def visual(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--visual"))


@pytest.fixture(autouse=True)
def _visual_teardown_pause(request: pytest.FixtureRequest, qtbot: QtBot) -> None:  # noqa: PT004
    yield  # type: ignore[misc]
    if request.config.getoption("--visual"):
        qtbot.wait(_VISUAL_DELAY_MS)


@pytest.fixture(autouse=True)
def _flush_qt_events_between_tests() -> Generator[None, None, None]:  # noqa: PT004
    """Drain leftover deferred deletes and posted events between tests.

    Empirically required on macOS under ``--visual``: without this flush,
    queued cross-thread signals from the previous test's worker QThread
    can starve the next test's ``work_finished`` delivery and cause
    spurious 10-second ``waitUntil`` timeouts.
    """
    import gc

    from PySide6.QtCore import QCoreApplication

    yield

    QCoreApplication.processEvents()
    QCoreApplication.processEvents()
    gc.collect()
    QCoreApplication.processEvents()


@pytest.fixture
def qml_app(
    qtbot: QtBot,
    visual: bool,
) -> Generator[dict[str, Any], None, None]:
    """Launch the full QML window with all view models wired up.

    Yields a dict with 'engine', 'window', and all four view models.
    The window is shown when ``--visual`` is passed, hidden otherwise.
    """
    from hash_turbo.gui.app import _fix_windows_dll_search

    _fix_windows_dll_search()

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    from hash_turbo import __version__
    from hash_turbo.gui.gettext_translator import GettextTranslator
    from hash_turbo.gui.settings_model import SettingsModel

    QQuickStyle.setStyle("Material")

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
    ctx.setContextProperty("thirdPartyLicensesHtml", "")

    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    assert app is not None
    translator = GettextTranslator(app)
    app.installTranslator(translator)

    import hash_turbo.gui.app as _gui_app_mod
    qml_path = Path(_gui_app_mod.__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    assert engine.rootObjects(), "QML failed to load"

    window = engine.rootObjects()[0]
    if visual:
        window.show()
    else:
        window.setVisible(False)

    result = {
        "engine": engine,
        "window": window,
        "settings_model": settings_model,
        "hash_model": hash_model,
        "verify_model": verify_model,
        "sanitize_model": sanitize_model,
    }
    yield result

    window.close()
    # Flush any deferred deletions and pending Qt events before destroying
    # the engine to prevent access violations from lingering worker threads.
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    QCoreApplication.processEvents()
    engine.deleteLater()
    QCoreApplication.processEvents()


@pytest.fixture
def hash_model() -> HashViewModel:
    return HashViewModel()


@pytest.fixture
def verify_model() -> VerifyViewModel:
    return VerifyViewModel()


@pytest.fixture
def sanitize_model(qtbot: QtBot) -> SanitizeViewModel:
    model = SanitizeViewModel()
    _original_transform = model.transform

    def _blocking_transform(*args: object, **kwargs: object) -> None:
        # The worker runs in a QThread.  Wait for output_text_changed
        # which fires when the result is ready.
        with qtbot.waitSignal(model.output_text_changed, timeout=5000):
            _original_transform(*args, **kwargs)

    model.transform = _blocking_transform  # type: ignore[assignment]
    return model


@pytest.fixture
def populated_dir(tmp_path: Path) -> Path:
    for name, text in [
        ("alpha.txt", "alpha content"),
        ("bravo.txt", "bravo content"),
        ("charlie.txt", "charlie content"),
    ]:
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


@pytest.fixture
def nested_dir(tmp_path: Path) -> Path:
    for name, text in [
        ("root.txt", "root content"),
        ("sub/child.txt", "child content"),
        ("sub/deep/grandchild.txt", "grandchild content"),
    ]:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


@pytest.fixture
def hash_file_factory(tmp_path: Path) -> Callable[[Path, str], Path]:
    def _create(
        directory: Path,
        filename: str = "checksums.sha256",
        algorithm: str = "sha256",
    ) -> Path:
        lines: list[str] = []
        for child in sorted(directory.iterdir()):
            if child.is_file() and child.suffix != ".sha256":
                digest = hashlib.new(algorithm, child.read_bytes()).hexdigest()
                lines.append(f"{digest} *{child.name}")
        hash_file = directory / filename
        hash_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return hash_file
    return _create


@pytest.fixture
def large_populated_dir(tmp_path: Path) -> Path:
    one_mb = b"\x00" * (1024 * 1024)
    hash_lines: list[str] = []
    for i in range(1_000):
        data = i.to_bytes(4, "big") + one_mb[4:]
        name = f"file_{i:05d}.bin"
        (tmp_path / name).write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        hash_lines.append(f"{digest} *{name}")
    (tmp_path / "checksums.sha256").write_text(
        "\n".join(hash_lines) + "\n", encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def large_nested_dir(tmp_path: Path) -> Path:
    """Create 1 000 x 1 MB files spread across 10 sub-folders.

    Unlike ``large_populated_dir``, no pre-built checksum file is
    included — tests generate their own output files.
    """
    one_mb = b"\x00" * (1024 * 1024)
    folders = [f"group_{g:02d}" for g in range(10)]
    for folder in folders:
        (tmp_path / folder).mkdir()
    for i in range(1_000):
        data = i.to_bytes(4, "big") + one_mb[4:]
        folder = folders[i % len(folders)]
        name = f"file_{i:05d}.bin"
        (tmp_path / folder / name).write_bytes(data)
    return tmp_path
