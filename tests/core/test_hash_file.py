"""Tests for core.hash_file — parsing and writing hash files."""

from __future__ import annotations

import io
import json
import logging

import pytest

from hash_turbo.core.hash_file import (
    HashFileFormatter,
    HashFileParser,
)
from hash_turbo.core.models import Algorithm, HashFileFormat, HashResult


@pytest.fixture
def sha256_result() -> HashResult:
    return HashResult(path="file.txt", algorithm=Algorithm.SHA256, hex_digest="abcd1234" * 8)


@pytest.fixture
def md5_result() -> HashResult:
    return HashResult(path="other.txt", algorithm=Algorithm.MD5, hex_digest="abcd1234" * 4)


class TestFormatGnu:
    def test_format_gnu_basic(self, sha256_result: HashResult) -> None:
        line = HashFileFormatter.format_gnu(sha256_result)
        assert line == f"{sha256_result.hex_digest} *file.txt"


class TestFormatBsd:
    def test_format_bsd_basic(self, sha256_result: HashResult) -> None:
        line = HashFileFormatter.format_bsd(sha256_result)
        assert line == f"SHA256 (file.txt) = {sha256_result.hex_digest}"


class TestFormatJson:
    def test_format_json_single(self, sha256_result: HashResult) -> None:
        output = HashFileFormatter.format_json([sha256_result])
        parsed = json.loads(output)
        assert len(parsed) == 1
        assert parsed[0]["path"] == "file.txt"
        assert parsed[0]["algorithm"] == "sha256"
        assert parsed[0]["hash"] == sha256_result.hex_digest

    def test_format_json_multiple(self, sha256_result: HashResult, md5_result: HashResult) -> None:
        output = HashFileFormatter.format_json([sha256_result, md5_result])
        parsed = json.loads(output)
        assert len(parsed) == 2


class TestWriteHashFile:
    def test_write_gnu_format(self, sha256_result: HashResult) -> None:
        # Arrange
        buf = io.StringIO()

        # Act
        HashFileFormatter.write([sha256_result], buf, HashFileFormat.GNU)

        # Assert
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        assert len(lines) == 1
        assert lines[0] == f"{sha256_result.hex_digest} *file.txt"

    def test_write_bsd_format(self, sha256_result: HashResult) -> None:
        # Arrange
        buf = io.StringIO()

        # Act
        HashFileFormatter.write([sha256_result], buf, HashFileFormat.BSD)

        # Assert
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        assert len(lines) == 1
        assert lines[0] == f"SHA256 (file.txt) = {sha256_result.hex_digest}"

    def test_write_multiple_results_gnu(self, sha256_result: HashResult, md5_result: HashResult) -> None:
        # Arrange
        buf = io.StringIO()

        # Act
        HashFileFormatter.write([sha256_result, md5_result], buf, HashFileFormat.GNU)

        # Assert
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        assert len(lines) == 2
        assert "file.txt" in lines[0]
        assert "other.txt" in lines[1]

    def test_write_multiple_results_bsd(self, sha256_result: HashResult, md5_result: HashResult) -> None:
        # Arrange
        buf = io.StringIO()

        # Act
        HashFileFormatter.write([sha256_result, md5_result], buf, HashFileFormat.BSD)

        # Assert
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        assert len(lines) == 2
        assert lines[0].startswith("SHA256 (")
        assert lines[1].startswith("MD5 (")

    def test_write_json_format(self, sha256_result: HashResult) -> None:
        buf = io.StringIO()
        HashFileFormatter.write([sha256_result], buf, HashFileFormat.JSON)
        parsed = json.loads(buf.getvalue())
        assert len(parsed) == 1

    def test_write_empty_results_gnu(self) -> None:
        buf = io.StringIO()
        HashFileFormatter.write([], buf, HashFileFormat.GNU)
        assert buf.getvalue() == ""

    def test_write_empty_results_bsd(self) -> None:
        buf = io.StringIO()
        HashFileFormatter.write([], buf, HashFileFormat.BSD)
        assert buf.getvalue() == ""

    def test_write_empty_results_json(self) -> None:
        buf = io.StringIO()
        HashFileFormatter.write([], buf, HashFileFormat.JSON)
        parsed = json.loads(buf.getvalue())
        assert parsed == []


class TestDetectFormat:
    def test_detect_gnu(self) -> None:
        line = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234  file.txt"
        assert HashFileFormatter.detect_format(line) is HashFileFormat.GNU

    def test_detect_bsd(self) -> None:
        line = "SHA256 (file.txt) = abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234"
        assert HashFileFormatter.detect_format(line) is HashFileFormat.BSD

    def test_detect_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot detect"):
            HashFileFormatter.detect_format("this is not a hash line")


class TestParseHashFile:
    def test_parse_gnu_format(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234  file.txt\n"
        entries = HashFileParser.parse(content)
        assert len(entries) == 1
        assert entries[0].path == "file.txt"
        assert entries[0].algorithm is Algorithm.SHA256

    def test_parse_bsd_format(self) -> None:
        content = "SHA256 (file.txt) = abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\n"
        entries = HashFileParser.parse(content)
        assert len(entries) == 1
        assert entries[0].path == "file.txt"
        assert entries[0].algorithm is Algorithm.SHA256

    def test_parse_skips_comments_and_blank_lines(self) -> None:
        content = "# comment\n\nabcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234  file.txt\n"
        entries = HashFileParser.parse(content)
        assert len(entries) == 1

    def test_parse_multiple_entries(self) -> None:
        content = (
            "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234  file1.txt\n"
            "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234  file2.txt\n"
        )
        entries = HashFileParser.parse(content)
        assert len(entries) == 2

    def test_parse_roundtrip_gnu(self, sha256_result: HashResult) -> None:
        buf = io.StringIO()
        HashFileFormatter.write([sha256_result], buf, HashFileFormat.GNU)
        entries = HashFileParser.parse(buf.getvalue())
        assert len(entries) == 1
        assert entries[0].expected_hash == sha256_result.hex_digest
        assert entries[0].path == sha256_result.path

    def test_parse_roundtrip_bsd(self, sha256_result: HashResult) -> None:
        buf = io.StringIO()
        HashFileFormatter.write([sha256_result], buf, HashFileFormat.BSD)
        entries = HashFileParser.parse(buf.getvalue())
        assert len(entries) == 1
        assert entries[0].expected_hash == sha256_result.hex_digest

    def test_parse_malformed_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized"):
            HashFileParser.parse("not a valid line\n")

    def test_parse_md5_gnu_infers_algorithm(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234  file.txt\n"
        entries = HashFileParser.parse(content)
        assert entries[0].algorithm is Algorithm.MD5

    def test_parse_gnu_unknown_hash_length_defaults_to_sha256_with_warning(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Arrange — 20-char hex digest has no entry in the length→algorithm map
        short_hash = "ab" * 10
        content = f"{short_hash}  file.txt\n"

        # Act
        with caplog.at_level(logging.WARNING):
            entries = HashFileParser.parse(content)

        # Assert — falls back to SHA-256 and logs a warning
        assert len(entries) == 1
        assert entries[0].algorithm is Algorithm.SHA256
        assert entries[0].expected_hash == short_hash
        assert any("Cannot infer algorithm" in msg for msg in caplog.messages)


class TestFlexibleWhitespace:
    """Flexible whitespace parsing for GNU format lines."""

    def test_parse_gnu_with_tab_separator(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\tfile.txt\n"

        entries = HashFileParser.parse(content, flexible_whitespace=True)

        assert len(entries) == 1
        assert entries[0].path == "file.txt"

    def test_parse_gnu_with_multiple_spaces(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234     file.txt\n"

        entries = HashFileParser.parse(content, flexible_whitespace=True)

        assert len(entries) == 1
        assert entries[0].path == "file.txt"

    def test_parse_gnu_with_mixed_whitespace(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\t  file.txt\n"

        entries = HashFileParser.parse(content, flexible_whitespace=True)

        assert len(entries) == 1
        assert entries[0].path == "file.txt"

    def test_parse_strict_tab_rejected_without_flexible(self) -> None:
        # Strict pattern requires literal space + [space or *]; tab doesn't match
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\tfile.txt\n"

        with pytest.raises(ValueError, match="Unrecognized"):
            HashFileParser.parse(content, flexible_whitespace=False)

    def test_parse_strict_many_spaces_corrupts_path(self) -> None:
        # Strict mode eats only 2 spaces; the rest become part of the path
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234     file.txt\n"

        entries = HashFileParser.parse(content, flexible_whitespace=False)

        assert len(entries) == 1
        assert entries[0].path == "   file.txt"  # leading spaces leak into path

    def test_detect_format_flexible_matches_gnu_with_tabs(self) -> None:
        line = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\tfile.txt"

        result = HashFileFormatter.detect_format(line, flexible_whitespace=True)

        assert result is HashFileFormat.GNU

    def test_detect_format_strict_with_many_spaces_still_matches(self) -> None:
        # Strict pattern matches but would produce a corrupted path
        line = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234     file.txt"

        result = HashFileFormatter.detect_format(line, flexible_whitespace=False)

        assert result is HashFileFormat.GNU


class TestBinaryModeDetection:
    """Parser extracts binary/text mode from the GNU mode indicator."""

    def test_parse_gnu_binary_indicator_sets_binary_mode_true(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234 *file.txt\n"

        entries = HashFileParser.parse(content)

        assert entries[0].binary_mode is True

    def test_parse_gnu_text_indicator_sets_binary_mode_false(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234  file.txt\n"

        entries = HashFileParser.parse(content)

        assert entries[0].binary_mode is False

    def test_parse_bsd_defaults_to_binary_mode(self) -> None:
        content = "SHA256 (file.txt) = abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\n"

        entries = HashFileParser.parse(content)

        assert entries[0].binary_mode is True

    def test_parse_flexible_asterisk_sets_binary_mode_true(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\t*file.txt\n"

        entries = HashFileParser.parse(content, flexible_whitespace=True)

        assert entries[0].binary_mode is True
        assert entries[0].path == "file.txt"

    def test_parse_flexible_no_asterisk_sets_binary_mode_false(self) -> None:
        content = "abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234\tfile.txt\n"

        entries = HashFileParser.parse(content, flexible_whitespace=True)

        assert entries[0].binary_mode is False
