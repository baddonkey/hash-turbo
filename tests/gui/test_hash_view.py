"""End-to-end tests for the Hash generation view model."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from pytestqt.qtbot import QtBot

from hash_turbo.gui.hash_view_model import HashViewModel
from hash_turbo.gui.verify_view_model import VerifyViewModel


def _folder_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path)).toString()


def _wait_hash_done(qtbot: QtBot, model: HashViewModel, timeout: int = 10_000) -> None:
    qtbot.waitUntil(lambda: not model.isHashing, timeout=timeout)


class TestHashViewModelE2E:
    """Full user flows through HashViewModel -- real files, real workers."""

    def test_hash_folder_writes_output_and_shows_results(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        assert hash_model.pendingCount == 1

        hash_model.startHash(
            "sha256", "gnu", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)

        assert output_path.is_file()
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 3
        assert "alpha.txt" in hash_model.resultText
        assert "bravo.txt" in hash_model.resultText
        assert "charlie.txt" in hash_model.resultText
        assert hash_model.canOpenOutput

    def test_hash_progress_label_updates_during_hashing(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)

        # After completion the label must show the final count, not "0"
        assert "Hashing: 3 / 3 files" in hash_model.progressLabel

    def test_hash_clear_resets_state(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True, str(populated_dir),
            str(populated_dir / "checksums.sha256"),
        )
        _wait_hash_done(qtbot, hash_model)
        hash_model.clear()
        assert hash_model.pendingCount == 0
        assert hash_model.resultText == ""

    def test_hash_button_condition_no_pending(self, hash_model: HashViewModel) -> None:
        assert hash_model.pendingCount == 0

    def test_hash_cancel_stops_worker(
        self, qtbot: QtBot, hash_model: HashViewModel, tmp_path: Path,
    ) -> None:
        for i in range(200):
            (tmp_path / f"file_{i:04d}.txt").write_text(f"content {i}")
        hash_model.addFolder(_folder_url(tmp_path))
        hash_model.startHash(
            "sha256", "gnu", True, True, str(tmp_path), str(tmp_path / "checksums.sha256"),
        )
        hash_model.cancelHash()
        _wait_hash_done(qtbot, hash_model, timeout=10_000)
        assert not hash_model.isHashing

    def test_hash_respects_algorithm_selection(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.md5"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "md5", "gnu", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 3
        for line in lines:
            digest = line.split(" *")[0]
            assert len(digest) == 32

    def test_hash_output_contains_relative_paths(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                path_part = line.split(" *", 1)[1]
                assert not Path(path_part).is_absolute()

    def test_hash_recursive_includes_nested_files(
        self, qtbot: QtBot, hash_model: HashViewModel, nested_dir: Path,
    ) -> None:
        output_path = nested_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(nested_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True, str(nested_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 3
        assert "root.txt" in hash_model.resultText
        assert "child.txt" in hash_model.resultText
        assert "grandchild.txt" in hash_model.resultText

    def test_hash_non_recursive_skips_nested_files(
        self, qtbot: QtBot, hash_model: HashViewModel, nested_dir: Path,
    ) -> None:
        output_path = nested_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(nested_dir))
        hash_model.startHash(
            "sha256", "gnu", False, True, str(nested_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1
        assert "root.txt" in hash_model.resultText
        assert "child.txt" not in hash_model.resultText

    def test_hash_add_files_accumulates(
        self, qtbot: QtBot, hash_model: HashViewModel, tmp_path: Path,
    ) -> None:
        f1 = tmp_path / "first.txt"
        f1.write_text("first", encoding="utf-8")
        f2 = tmp_path / "second.txt"
        f2.write_text("second", encoding="utf-8")
        output_path = tmp_path / "checksums.sha256"
        hash_model.addFiles([QUrl.fromLocalFile(str(f1)).toString()])
        hash_model.addFiles([QUrl.fromLocalFile(str(f2)).toString()])
        assert hash_model.pendingCount == 2
        hash_model.startHash(
            "sha256", "gnu", False, True, str(tmp_path), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 2
        assert "first.txt" in hash_model.resultText
        assert "second.txt" in hash_model.resultText

    def test_add_files_with_folder_replaces_pending(
        self, hash_model: HashViewModel, tmp_path: Path,
    ) -> None:
        # Arrange — pre-populate with a file
        f1 = tmp_path / "existing.txt"
        f1.write_text("existing", encoding="utf-8")
        hash_model.addFiles([QUrl.fromLocalFile(str(f1)).toString()])
        assert hash_model.pendingCount == 1

        # Act — drop a folder via addFiles
        sub = tmp_path / "subdir"
        sub.mkdir()
        hash_model.addFiles([QUrl.fromLocalFile(str(sub)).toString()])

        # Assert — only the folder remains
        assert hash_model.pendingCount == 1
        assert "subdir" in hash_model.pendingDisplay

    def test_add_files_with_mixed_keeps_only_first_folder(
        self, hash_model: HashViewModel, tmp_path: Path,
    ) -> None:
        # Arrange — two folders and a file
        dir_a = tmp_path / "dir_a"
        dir_a.mkdir()
        dir_b = tmp_path / "dir_b"
        dir_b.mkdir()
        f1 = tmp_path / "file.txt"
        f1.write_text("data", encoding="utf-8")

        # Act — drop all three at once
        urls = [
            QUrl.fromLocalFile(str(f1)).toString(),
            QUrl.fromLocalFile(str(dir_a)).toString(),
            QUrl.fromLocalFile(str(dir_b)).toString(),
        ]
        hash_model.addFiles(urls)

        # Assert — file before the folder is added, but once folder is
        # hit the method returns early with only the folder
        assert hash_model.pendingCount == 1
        assert "dir_a" in hash_model.pendingDisplay

    def test_hash_output_preserves_scan_order_flat(
        self, qtbot: QtBot, hash_model: HashViewModel, tmp_path: Path,
    ) -> None:
        for name in ["zebra.txt", "alpha.txt", "middle.txt"]:
            (tmp_path / name).write_text(name, encoding="utf-8")
        output_path = tmp_path / "checksums.sha256"
        hash_model.addFolder(_folder_url(tmp_path))
        hash_model.startHash(
            "sha256", "gnu", False, True, str(tmp_path), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        paths = [ln.split(" *", 1)[1] for ln in lines]
        assert paths == sorted(paths, key=str.lower)


class TestHashViewModelFormat:
    """Tests for the output format selector (GNU vs BSD)."""

    def test_hash_gnu_format_writes_gnu_output(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 3
        for line in lines:
            assert " *" in line
            assert "SHA256 (" not in line

    def test_hash_bsd_format_writes_bsd_output(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "bsd", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 3
        for line in lines:
            assert line.startswith("SHA256 (")
            assert ") = " in line

    def test_hash_bsd_format_terminal_shows_bsd(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "bsd", True, True, str(populated_dir),
            str(populated_dir / "checksums.sha256"),
        )
        _wait_hash_done(qtbot, hash_model)
        assert "SHA256 (" in hash_model.resultText
        assert "alpha.txt" in hash_model.resultText

    def test_hash_bsd_with_md5_shows_correct_algo_tag(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.md5"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "md5", "bsd", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 3
        for line in lines:
            assert line.startswith("MD5 (")
            assert ") = " in line

    def test_hash_bsd_output_parseable_roundtrip(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        from hash_turbo.core.hash_file import HashFileParser
        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "bsd", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        content = output_path.read_text(encoding="utf-8")
        entries = HashFileParser.parse(content)
        assert len(entries) == 3
        paths = {e.path for e in entries}
        assert "alpha.txt" in paths
        assert "bravo.txt" in paths
        assert "charlie.txt" in paths

    def test_hash_format_file_and_terminal_match(
        self, qtbot: QtBot, hash_model: HashViewModel, populated_dir: Path,
    ) -> None:
        output_path = populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(populated_dir))
        hash_model.startHash(
            "sha256", "bsd", True, True, str(populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model)
        file_lines = sorted(
            ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()
        )
        terminal_lines = sorted(
            ln for ln in hash_model.resultText.splitlines() if ln.strip()
        )
        assert file_lines == terminal_lines


class TestHashViewModelStress:
    """Stress tests -- 1 000 x 1 MB files (~1 GB)."""

    _TIMEOUT = 120_000

    @pytest.mark.stress
    def test_hash_1k_files_completes(
        self, qtbot: QtBot, hash_model: HashViewModel, large_populated_dir: Path,
    ) -> None:
        output_path = large_populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(large_populated_dir))
        hash_model.startHash(
            "sha256", "gnu", True, True, str(large_populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model, timeout=self._TIMEOUT)
        assert output_path.is_file()
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1_000
        assert hash_model.resultText != ""
        assert hash_model.canOpenOutput

    @pytest.mark.stress
    def test_hash_1k_files_absolute_paths_and_verify(
        self,
        qtbot: QtBot,
        hash_model: HashViewModel,
        verify_model: VerifyViewModel,
        large_populated_dir: Path,
    ) -> None:
        output_path = large_populated_dir / "checksums.sha256"
        hash_model.addFolder(_folder_url(large_populated_dir))
        hash_model.startHash(
            "sha256", "gnu", True, False, str(large_populated_dir), str(output_path),
        )
        _wait_hash_done(qtbot, hash_model, timeout=self._TIMEOUT)
        assert output_path.is_file()
        lines = [ln for ln in output_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1_000
        for line in lines:
            file_path = line.split(" *", 1)[1]
            assert Path(file_path).is_absolute(), f"Expected absolute: {file_path}"

        from tests.gui.test_verify_view import _verify_hash_file
        _verify_hash_file(
            qtbot, verify_model, output_path, large_populated_dir,
            custom_base=True, timeout=self._TIMEOUT,
        )
        assert verify_model._passed == 1_000
        assert verify_model._failed == 0
        assert verify_model._missing == 0
