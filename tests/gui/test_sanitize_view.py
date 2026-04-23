"""End-to-end tests for the Sanitize view model."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from pytestqt.qtbot import QtBot

from hash_turbo.gui.sanitize_view_model import SanitizeViewModel


_GNU_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 *empty.txt\n"
    "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef *hello.txt\n"
)

_GNU_SHA256_UNSORTED = (
    "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef *zebra.txt\n"
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 *alpha.txt\n"
)


class TestSanitizeIdentity:
    def test_identity_transform_preserves_content(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        sanitize_model.transform(
            _GNU_SHA256, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        assert len(lines) == 2


class TestSanitizeFormatConversion:
    def test_gnu_to_bsd_conversion(self, sanitize_model: SanitizeViewModel) -> None:
        sanitize_model.transform(
            _GNU_SHA256, "bsd", "keep", "",
            "lower", "none", False, False, "lf",
        )
        output = sanitize_model.outputText
        assert "SHA256 (" in output
        assert ") = " in output

    def test_bsd_to_gnu_conversion(self, sanitize_model: SanitizeViewModel) -> None:
        bsd_input = (
            "SHA256 (empty.txt) = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n"
            "SHA256 (hello.txt) = a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef\n"
        )
        sanitize_model.transform(
            bsd_input, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        output = sanitize_model.outputText
        assert " *" in output
        assert "SHA256 (" not in output


class TestSanitizeSorting:
    def test_sort_path_ascending(self, sanitize_model: SanitizeViewModel) -> None:
        sanitize_model.transform(
            _GNU_SHA256_UNSORTED, "gnu", "keep", "",
            "lower", "path", False, False, "lf",
        )
        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        paths = [ln.split(" *", 1)[1] for ln in lines]
        assert paths == sorted(paths, key=str.lower)

    def test_sort_hash_ascending(self, sanitize_model: SanitizeViewModel) -> None:
        sanitize_model.transform(
            _GNU_SHA256_UNSORTED, "gnu", "keep", "",
            "lower", "hash", False, False, "lf",
        )
        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        hashes = [ln.split(" *", 1)[0] for ln in lines]
        assert hashes == sorted(hashes)

    def test_sort_none_preserves_original_order(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        sanitize_model.transform(
            _GNU_SHA256_UNSORTED, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        paths = [ln.split(" *", 1)[1] for ln in lines]
        assert paths == ["zebra.txt", "alpha.txt"]


class TestSanitizeHashCase:
    def test_upper_case(self, sanitize_model: SanitizeViewModel) -> None:
        sanitize_model.transform(
            _GNU_SHA256, "gnu", "keep", "",
            "upper", "none", False, False, "lf",
        )
        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        for line in lines:
            digest = line.split(" *", 1)[0]
            assert digest == digest.upper()

    def test_lower_case(self, sanitize_model: SanitizeViewModel) -> None:
        upper_input = _GNU_SHA256.upper()
        sanitize_model.transform(
            upper_input, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        for line in lines:
            digest = line.split(" *", 1)[0]
            assert digest == digest.lower()


class TestSanitizePathSeparator:
    def test_posix_separator(self, sanitize_model: SanitizeViewModel) -> None:
        input_text = "abc123 *sub\\dir\\file.txt\n"
        sanitize_model.transform(
            input_text, "gnu", "posix", "",
            "lower", "none", False, False, "lf",
        )
        assert "sub/dir/file.txt" in sanitize_model.outputText

    def test_windows_separator(self, sanitize_model: SanitizeViewModel) -> None:
        input_text = "abc123 *sub/dir/file.txt\n"
        sanitize_model.transform(
            input_text, "gnu", "windows", "",
            "lower", "none", False, False, "lf",
        )
        assert "sub\\dir\\file.txt" in sanitize_model.outputText


class TestSanitizeStripPrefix:
    def test_strip_prefix_removes_matching_prefix(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        input_text = (
            "abc123 *data/project/file1.txt\n"
            "def456 *data/project/file2.txt\n"
        )
        sanitize_model.transform(
            input_text, "gnu", "keep", "data/project/",
            "lower", "none", False, False, "lf",
        )
        output = sanitize_model.outputText
        assert "file1.txt" in output
        assert "file2.txt" in output
        assert "data/project/" not in output

    def test_strip_prefix_no_match_preserves_paths(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        input_text = "abc123 *file.txt\n"
        sanitize_model.transform(
            input_text, "gnu", "keep", "nonexistent/",
            "lower", "none", False, False, "lf",
        )
        assert "file.txt" in sanitize_model.outputText


class TestSanitizeDeduplicate:
    def test_dedup_removes_duplicate_entries(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        input_text = (
            "abc123 *file.txt\n"
            "abc123 *file.txt\n"
            "def456 *other.txt\n"
        )
        sanitize_model.transform(
            input_text, "gnu", "keep", "",
            "lower", "path", True, False, "lf",
        )
        lines = [ln for ln in sanitize_model.outputText.splitlines() if ln.strip()]
        assert len(lines) == 2


class TestSanitizeNormalizeWhitespace:
    def test_normalize_whitespace_collapses_spaces(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        input_text = "abc123 *path/to  /  file.txt\n"
        sanitize_model.transform(
            input_text, "gnu", "keep", "",
            "lower", "none", False, True, "lf",
        )
        assert "file.txt" in sanitize_model.outputText


class TestSanitizeLineEnding:
    def test_crlf_line_ending(self, sanitize_model: SanitizeViewModel) -> None:
        sanitize_model.transform(
            _GNU_SHA256, "gnu", "keep", "",
            "lower", "none", False, False, "crlf",
        )
        assert "\r\n" in sanitize_model.outputText

    def test_lf_line_ending(self, sanitize_model: SanitizeViewModel) -> None:
        # Use multi-line input — single-line output has trailing newline stripped
        crlf_input = _GNU_SHA256.replace("\n", "\r\n")
        sanitize_model.transform(
            crlf_input, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        output = sanitize_model.outputText
        assert "\r\n" not in output
        assert "\n" in output


class TestSanitizeClear:
    def test_clear_resets_output_text(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        sanitize_model.transform(
            _GNU_SHA256, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        assert sanitize_model.outputText != ""
        sanitize_model.clear()
        assert sanitize_model.outputText == ""


class TestSanitizeLoadAndSave:
    def test_load_file_returns_content(
        self, sanitize_model: SanitizeViewModel, qtbot: QtBot, tmp_path: Path,
    ) -> None:
        f = tmp_path / "test.sha256"
        f.write_text(_GNU_SHA256, encoding="utf-8")
        url = QUrl.fromLocalFile(str(f)).toString()
        with qtbot.waitSignal(sanitize_model.fileLoaded, timeout=5000) as blocker:
            sanitize_model.loadFile(url)
        content = blocker.args[0]
        assert "empty.txt" in content
        assert "hello.txt" in content

    def test_auto_save_writes_output_file(
        self, sanitize_model: SanitizeViewModel, tmp_path: Path,
    ) -> None:
        out = tmp_path / "output.sha256"
        sanitize_model.outputPath = str(out)
        sanitize_model.transform(
            _GNU_SHA256, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "empty.txt" in content

    def test_default_output_path(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        result = sanitize_model.defaultOutputPath("/data/checksums.sha256")
        assert result.endswith("-sanitized.sha256")
        assert "checksums-sanitized" in result

    def test_result_entries_populated_after_transform(
        self, sanitize_model: SanitizeViewModel,
    ) -> None:
        sanitize_model.transform(
            _GNU_SHA256, "gnu", "keep", "",
            "lower", "none", False, False, "lf",
        )
        entries = sanitize_model.resultEntries
        assert len(entries) == 2
        assert entries[0]["path"] == "empty.txt"
        assert "hash" in entries[0]
        assert "algorithm" in entries[0]
