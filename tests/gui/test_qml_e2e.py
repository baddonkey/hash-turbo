"""Visual end-to-end tests â€” exercises the full QML window.

These tests launch the real QML UI (Main.qml), wire up all view models,
and drive user flows through the Python model API while the QML window
renders the results live.

Run with ``--visual`` to watch the GUI update in real time:

    pytest tests/gui/test_qml_e2e.py --visual -v
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QUrl
from pytestqt.qtbot import QtBot

from hash_turbo.gui.hash_view_model import HashViewModel
from hash_turbo.gui.sanitize_view_model import SanitizeViewModel
from hash_turbo.gui.verify_view_model import VerifyViewModel

_GNU_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 *empty.txt\n"
    "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef *hello.txt\n"
)

_TAB_HASH = 0
_TAB_VERIFY = 1
_TAB_SANITIZE = 2
_TAB_SETTINGS = 3

_VISUAL_STEP_MS = 800


def _switch_tab(window: Any, index: int) -> None:
    """Switch the QML TabBar to the given tab index."""
    from PySide6.QtCore import QCoreApplication

    # Set the QML property which triggers: tabBar.currentIndex = index
    window.setProperty("testTabIndex", index)
    QCoreApplication.processEvents()


def _folder_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path)).toString()


def _wait_hash_done(qtbot: QtBot, model: HashViewModel, timeout: int = 15_000) -> None:
    qtbot.waitUntil(lambda: not model.isHashing, timeout=timeout)


def _wait_verify_done(qtbot: QtBot, model: VerifyViewModel, timeout: int = 15_000) -> None:
    qtbot.waitUntil(lambda: not model.isVerifying, timeout=timeout)


class TestQmlHashTab:
    """Visual e2e: Hash tab â€” add folder, hash, see results in the live window."""

    def test_hash_folder_shows_results_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        populated_dir: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        hash_model: HashViewModel = qml_app["hash_model"]

        _switch_tab(window, _TAB_HASH)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        assert hash_model.pendingCount == 1

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        hash_model.startHash(
            "sha256", "gnu", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert output_path.is_file()
        assert "alpha.txt" in hash_model.resultText
        assert "bravo.txt" in hash_model.resultText
        assert "charlie.txt" in hash_model.resultText
        assert hash_model.canOpenOutput

    def test_hash_bsd_format_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        populated_dir: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        hash_model: HashViewModel = qml_app["hash_model"]

        _switch_tab(window, _TAB_HASH)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "bsd", True, True,
            str(populated_dir), str(populated_dir / "checksums.sha256"),
        )
        _wait_hash_done(qtbot, hash_model)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert "SHA256 (" in hash_model.resultText
        assert "alpha.txt" in hash_model.resultText

    def test_hash_cancel_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        tmp_path: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        hash_model: HashViewModel = qml_app["hash_model"]

        _switch_tab(window, _TAB_HASH)

        for i in range(200):
            (tmp_path / f"file_{i:04d}.txt").write_text(f"content {i}")

        hash_model.addFolder(_folder_url(tmp_path))
        hash_model.startHash(
            "sha256", "gnu", True, True,
            str(tmp_path), str(tmp_path / "checksums.sha256"),
        )

        if visual:
            qtbot.wait(300)

        hash_model.cancelHash()
        _wait_hash_done(qtbot, hash_model)
        assert not hash_model.isHashing


class TestQmlVerifyTab:
    """Visual e2e: Verify tab â€” verify a hash file, see pass/fail in the QML window."""

    def test_verify_all_pass_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        populated_dir: Path,
        hash_file_factory: Any,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        verify_model: VerifyViewModel = qml_app["verify_model"]

        _switch_tab(window, _TAB_VERIFY)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        hash_file = hash_file_factory(populated_dir)
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0
        assert "Passed: 3" in verify_model.logText
        assert verify_model.resultText.count("OK") == 3

    def test_verify_detects_tamper_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        populated_dir: Path,
        hash_file_factory: Any,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        verify_model: VerifyViewModel = qml_app["verify_model"]

        _switch_tab(window, _TAB_VERIFY)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        hash_file = hash_file_factory(populated_dir)
        (populated_dir / "bravo.txt").write_text("tampered!", encoding="utf-8")
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert verify_model.passed_count == 2
        assert verify_model.failed_count == 1
        assert "FAILED" in verify_model.resultText
        assert "bravo.txt" in verify_model.resultText

    def test_verify_detects_missing_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        populated_dir: Path,
        hash_file_factory: Any,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        verify_model: VerifyViewModel = qml_app["verify_model"]

        _switch_tab(window, _TAB_VERIFY)

        hash_file = hash_file_factory(populated_dir)
        (populated_dir / "charlie.txt").unlink()
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert verify_model.passed_count == 2
        assert verify_model.missing_count == 1
        assert "MISSING" in verify_model.resultText


class TestQmlSanitizeTab:
    """Visual e2e: Sanitize tab â€” transform hash content, see output in the QML window."""

    def test_sanitize_gnu_to_bsd_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        sanitize_model: SanitizeViewModel = qml_app["sanitize_model"]

        _switch_tab(window, _TAB_SANITIZE)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        with qtbot.waitSignal(sanitize_model.output_text_changed, timeout=5000):
            sanitize_model.transform(
                _GNU_SHA256, "bsd", "keep", "",
                "lower", "none", False, False, "lf",
            )

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert "SHA256 (" in sanitize_model.outputText
        assert ") = " in sanitize_model.outputText

    def test_sanitize_sort_and_upper_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        sanitize_model: SanitizeViewModel = qml_app["sanitize_model"]

        _switch_tab(window, _TAB_SANITIZE)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        with qtbot.waitSignal(sanitize_model.output_text_changed, timeout=5000):
            sanitize_model.transform(
                _GNU_SHA256, "gnu", "keep", "",
                "upper", "path", False, False, "lf",
            )

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        assert len(lines) == 2
        for line in lines:
            digest = line.split(" *", 1)[0]
            assert digest == digest.upper()
        paths = [ln.split(" *", 1)[1] for ln in lines]
        assert paths == sorted(paths, key=str.lower)


class TestQmlSettingsTab:
    """Visual e2e: Settings tab â€” change settings, observe model updates."""

    def test_settings_algorithm_change_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        settings_model = qml_app["settings_model"]

        _switch_tab(window, _TAB_SETTINGS)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        settings_model.defaultAlgorithm = "md5"
        assert settings_model.defaultAlgorithm == "md5"

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        settings_model.defaultAlgorithm = "sha256"

    def test_settings_theme_toggle_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        settings_model = qml_app["settings_model"]

        _switch_tab(window, _TAB_SETTINGS)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        original = settings_model.theme
        settings_model.theme = "dark"

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        settings_model.theme = "light"

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        settings_model.theme = original


class TestQmlFullWorkflow:
    """Visual e2e: Hash -> Verify round-trip through the live QML window."""

    def test_hash_then_verify_roundtrip_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        populated_dir: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        hash_model: HashViewModel = qml_app["hash_model"]
        verify_model: VerifyViewModel = qml_app["verify_model"]

        # Step 1: Hash tab â€” generate checksums
        _switch_tab(window, _TAB_HASH)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True,
            str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert output_path.is_file()
        assert hash_model.canOpenOutput

        # Step 2: Switch to Verify tab â€” verify the just-generated file
        _switch_tab(window, _TAB_VERIFY)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        content = output_path.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(output_path), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0
        assert "Passed: 3" in verify_model.logText


class TestQmlNestedStress:
    """Stress: 1 000 x 1 MB files across 10 sub-folders â€” hash, verify, sanitize."""

    _TIMEOUT = 180_000

    @pytest.mark.stress
    def test_hash_nested_1k_files_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        large_nested_dir: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        hash_model: HashViewModel = qml_app["hash_model"]

        _switch_tab(window, _TAB_HASH)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        output_path = large_nested_dir / "out.sha256"
        hash_model.addFolder(_folder_url(large_nested_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True,
            str(large_nested_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model, timeout=self._TIMEOUT)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert output_path.is_file()
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1_000
        # Verify paths contain sub-folder components (/ on POSIX, \ on Windows)
        for ln in lines:
            path_part = ln.split(" *", 1)[1]
            assert "/" in path_part or "\\" in path_part
        assert hash_model.canOpenOutput

    @pytest.mark.stress
    def test_hash_verify_nested_1k_roundtrip_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        large_nested_dir: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        hash_model: HashViewModel = qml_app["hash_model"]
        verify_model: VerifyViewModel = qml_app["verify_model"]

        # Hash
        _switch_tab(window, _TAB_HASH)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        output_path = large_nested_dir / "out.sha256"
        hash_model.addFolder(_folder_url(large_nested_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True,
            str(large_nested_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model, timeout=self._TIMEOUT)
        assert output_path.is_file()

        # Verify
        _switch_tab(window, _TAB_VERIFY)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        content = output_path.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(output_path), str(large_nested_dir), False,
            str(large_nested_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model, timeout=self._TIMEOUT)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert verify_model.passed_count == 1_000
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0
        assert "Passed: 1000" in verify_model.logText

    @pytest.mark.stress
    def test_hash_sanitize_nested_1k_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        large_nested_dir: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        hash_model: HashViewModel = qml_app["hash_model"]
        sanitize_model: SanitizeViewModel = qml_app["sanitize_model"]

        # Hash first
        _switch_tab(window, _TAB_HASH)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        output_path = large_nested_dir / "out.sha256"
        hash_model.addFolder(_folder_url(large_nested_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True,
            str(large_nested_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model, timeout=self._TIMEOUT)
        assert output_path.is_file()

        content = output_path.read_text(encoding="utf-8")

        # Sanitize: GNU â†’ BSD, uppercase, sorted by path
        _switch_tab(window, _TAB_SANITIZE)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        with qtbot.waitSignal(sanitize_model.output_text_changed, timeout=10000):
            sanitize_model.transform(
                content, "bsd", "keep", "",
                "upper", "path", False, False, "lf",
            )

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        output_lines = [
            ln for ln in sanitize_model.outputText.splitlines() if ln.strip()
        ]
        assert len(output_lines) == 1_000

        # Verify BSD format
        assert all(ln.startswith("SHA256 (") for ln in output_lines)
        assert all(") = " in ln for ln in output_lines)

        # Verify uppercase digests
        for line in output_lines:
            digest = line.split(") = ", 1)[1]
            assert digest == digest.upper()

        # Verify sorted by path
        paths = [ln.split("(", 1)[1].split(")", 1)[0] for ln in output_lines]
        assert paths == sorted(paths, key=str.lower)


class TestQmlVerifyStress:
    """Stress: verify 1 000 pre-hashed files in the QML window."""

    _TIMEOUT = 180_000

    @pytest.mark.stress
    def test_verify_1k_files_in_qml(
        self,
        qtbot: QtBot,
        qml_app: dict[str, Any],
        large_populated_dir: Path,
        visual: bool,
    ) -> None:
        window = qml_app["window"]
        verify_model: VerifyViewModel = qml_app["verify_model"]

        _switch_tab(window, _TAB_VERIFY)
        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        hash_file = large_populated_dir / "checksums.sha256"
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(large_populated_dir), False,
            str(large_populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model, timeout=self._TIMEOUT)

        if visual:
            qtbot.wait(_VISUAL_STEP_MS)

        assert verify_model.passed_count == 1_000
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0
        assert "Passed: 1000" in verify_model.logText
        assert verify_model.canOpenReport
