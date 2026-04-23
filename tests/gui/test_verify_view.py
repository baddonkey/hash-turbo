"""End-to-end tests for the Verify view model."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from PySide6.QtCore import QUrl
from pytestqt.qtbot import QtBot

from hash_turbo.gui.hash_view_model import HashViewModel
from hash_turbo.gui.verify_view_model import VerifyViewModel


def _wait_verify_done(
    qtbot: QtBot, model: VerifyViewModel, timeout: int = 10_000,
) -> None:
    qtbot.waitUntil(lambda: not model.isVerifying, timeout=timeout)


def _verify_hash_file(
    qtbot: QtBot,
    model: VerifyViewModel,
    hash_file: Path,
    base_dir: Path,
    *,
    custom_base: bool,
    timeout: int = 10_000,
) -> None:
    content = hash_file.read_text(encoding="utf-8")
    base = str(base_dir) if custom_base else str(hash_file.parent)
    model.verify(
        content, str(hash_file), base, custom_base,
        str(hash_file.parent), True, True, True,
    )
    _wait_verify_done(qtbot, model, timeout=timeout)


class TestVerifyViewModelE2E:
    """Full user flows through VerifyViewModel -- real files, real workers."""

    def test_verify_all_pass_for_known_good_files(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0
        assert "Passed: 3" in verify_model.logText
        assert "Failed: 0" in verify_model.logText
        assert "Missing: 0" in verify_model.logText
        assert verify_model.resultText.count("OK") == 3

    def test_verify_detects_failed_hash(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        (populated_dir / "bravo.txt").write_text("tampered!", encoding="utf-8")
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert verify_model.passed_count == 2
        assert verify_model.failed_count == 1
        assert verify_model.missing_count == 0
        assert "FAILED" in verify_model.resultText
        assert "bravo.txt" in verify_model.resultText

    def test_verify_detects_missing_file(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        (populated_dir / "charlie.txt").unlink()
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert verify_model.passed_count == 2
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 1
        assert "MISSING" in verify_model.resultText
        assert "charlie.txt" in verify_model.resultText

    def test_verify_writes_report(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert verify_model.report_path is not None
        assert verify_model.report_path.is_file()
        assert verify_model.canOpenReport
        report_text = verify_model.report_path.read_text(encoding="utf-8")
        assert "hash-turbo verification report" in report_text
        assert "Passed: 3" in report_text

    def test_verify_report_written_to_output_folder(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
        tmp_path: Path,
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        content = hash_file.read_text(encoding="utf-8")
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(output_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert verify_model.report_path is not None
        assert verify_model.report_path.parent == output_dir
        assert verify_model.report_path.is_file()

    def test_verify_detects_new_files(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        (populated_dir / "delta.txt").write_text("new file", encoding="utf-8")
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert "New: 1" in verify_model.logText
        assert "NEW" in verify_model.resultText
        assert "delta.txt" in verify_model.resultText

    def test_verify_excludes_hash_file_from_new_detection(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert "checksums.sha256" not in verify_model.resultText
        assert "New: 0" in verify_model.logText

    def test_verify_cancel_stops_worker(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        tmp_path: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        for i in range(200):
            (tmp_path / f"file_{i:04d}.txt").write_text(f"content {i}")
        hash_file = hash_file_factory(tmp_path)
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(tmp_path), False,
            str(tmp_path), True, True, True,
        )
        verify_model.cancel()
        qtbot.waitUntil(lambda: not verify_model.isVerifying, timeout=10_000)

    def test_verify_clear_resets_state(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(populated_dir), False,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        verify_model.clear()
        assert verify_model.resultText == ""
        assert verify_model.logText == ""
        assert not verify_model.canOpenReport

    def test_verify_pasted_content_with_custom_base(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        populated_dir: Path,
        hash_file_factory: Callable[..., Path],
    ) -> None:
        hash_file = hash_file_factory(populated_dir)
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, "", str(populated_dir), True,
            str(populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model)
        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0


class TestPathCombinations:
    """Hash -> Verify with all relative/absolute path combinations."""

    def _hash_folder(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        folder: Path,
        *,
        relative: bool,
    ) -> Path:
        output_path = folder / "checksums.sha256"
        hash_model.addFolder(QUrl.fromLocalFile(str(folder)).toString())
        hash_model.startHash(
            "sha256", "gnu", True, relative, str(folder), str(output_path),
        )
        qtbot.waitUntil(lambda: not hash_model.isHashing, timeout=10_000)
        return output_path

    def test_hash_relative_verify_relative(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        verify_model: VerifyViewModel,
        populated_dir: Path,
    ) -> None:
        output = self._hash_folder(qtbot, hash_model, populated_dir, relative=True)
        for line in output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert not Path(line.split(" *", 1)[1]).is_absolute()
        _verify_hash_file(qtbot, verify_model, output, populated_dir, custom_base=False)
        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0

    def test_hash_relative_verify_with_custom_base(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        verify_model: VerifyViewModel,
        populated_dir: Path,
    ) -> None:
        output = self._hash_folder(qtbot, hash_model, populated_dir, relative=True)
        _verify_hash_file(qtbot, verify_model, output, populated_dir, custom_base=True)
        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0

    def test_hash_absolute_verify_with_custom_base(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        verify_model: VerifyViewModel,
        populated_dir: Path,
    ) -> None:
        output = self._hash_folder(qtbot, hash_model, populated_dir, relative=False)
        for line in output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert Path(line.split(" *", 1)[1]).is_absolute()
        _verify_hash_file(qtbot, verify_model, output, populated_dir, custom_base=True)
        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0

    def test_hash_absolute_verify_without_custom_base(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        verify_model: VerifyViewModel,
        populated_dir: Path,
    ) -> None:
        output = self._hash_folder(qtbot, hash_model, populated_dir, relative=False)
        _verify_hash_file(qtbot, verify_model, output, populated_dir, custom_base=False)
        assert verify_model.passed_count == 3
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0


class TestVerifyViewModelStress:
    """Stress tests -- 1 000 x 1 MB files (~1 GB)."""

    _TIMEOUT = 120_000

    @pytest.mark.stress
    def test_verify_1k_files_all_pass(
        self,
        qtbot: QtBot,
        verify_model: VerifyViewModel,
        large_populated_dir: Path,
    ) -> None:
        hash_file = large_populated_dir / "checksums.sha256"
        content = hash_file.read_text(encoding="utf-8")
        verify_model.verify(
            content, str(hash_file), str(large_populated_dir), False,
            str(large_populated_dir), True, True, True,
        )
        _wait_verify_done(qtbot, verify_model, timeout=self._TIMEOUT)
        assert verify_model.passed_count == 1_000
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0
        assert "Passed: 1000" in verify_model.logText


class TestPathCombinationsStress:
    """Stress: hash -> verify with all path combos on 1 000 x 1 MB files."""

    _TIMEOUT = 120_000

    @pytest.mark.stress
    def test_hash_relative_verify_relative_1k(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        verify_model: VerifyViewModel,
        large_populated_dir: Path,
    ) -> None:
        output_path = large_populated_dir / "checksums.sha256"
        hash_model.addFolder(QUrl.fromLocalFile(str(large_populated_dir)).toString())
        hash_model.startHash(
            "sha256", "gnu", True, True, str(large_populated_dir), str(output_path),
        )
        qtbot.waitUntil(lambda: not hash_model.isHashing, timeout=self._TIMEOUT)
        first_line = output_path.read_text(encoding="utf-8").split("\n", 1)[0]
        assert not Path(first_line.split(" *", 1)[1]).is_absolute()
        _verify_hash_file(
            qtbot, verify_model, output_path, large_populated_dir,
            custom_base=False, timeout=self._TIMEOUT,
        )
        assert verify_model.passed_count == 1_000
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0

    @pytest.mark.stress
    def test_hash_absolute_verify_custom_base_1k(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        verify_model: VerifyViewModel,
        large_populated_dir: Path,
    ) -> None:
        output_path = large_populated_dir / "checksums.sha256"
        hash_model.addFolder(QUrl.fromLocalFile(str(large_populated_dir)).toString())
        hash_model.startHash(
            "sha256", "gnu", True, False, str(large_populated_dir), str(output_path),
        )
        qtbot.waitUntil(lambda: not hash_model.isHashing, timeout=self._TIMEOUT)
        first_line = output_path.read_text(encoding="utf-8").split("\n", 1)[0]
        assert Path(first_line.split(" *", 1)[1]).is_absolute()
        _verify_hash_file(
            qtbot, verify_model, output_path, large_populated_dir,
            custom_base=True, timeout=self._TIMEOUT,
        )
        assert verify_model.passed_count == 1_000
        assert verify_model.failed_count == 0
        assert verify_model.missing_count == 0
