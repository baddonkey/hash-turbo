"""Tests for cli.app sanitize command — Click integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from click.testing import CliRunner

from hash_turbo.cli.app import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def gnu_hash_file(tmp_path: Path) -> Path:
    """Create a GNU-format hash file with known content."""
    content = (
        "aabbccdd00112233aabbccdd00112233aabbccdd00112233aabbccdd00112233  C:/projects/src/main.py\n"
        "11223344556677881122334455667788112233445566778811223344556677AA  C:/projects/src/utils.py\n"
        "AABBCCDD00112233AABBCCDD00112233AABBCCDD00112233AABBCCDD00112233  C:/projects/tests/test_main.py\n"
    )
    path = tmp_path / "checksums.sha256"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def bsd_hash_file(tmp_path: Path) -> Path:
    """Create a BSD-format hash file with known content."""
    content = (
        "SHA256 (src/main.py) = aabbccdd00112233aabbccdd00112233aabbccdd00112233aabbccdd00112233\n"
        "SHA256 (src/utils.py) = 11223344556677881122334455667788112233445566778811223344556677aa\n"
    )
    path = tmp_path / "checksums.sha256"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def duplicate_hash_file(tmp_path: Path) -> Path:
    """Create a hash file with duplicate paths (different case)."""
    content = (
        "aabbccdd00112233aabbccdd00112233aabbccdd00112233aabbccdd00112233  src/main.py\n"
        "11223344556677881122334455667788112233445566778811223344556677aa  src/utils.py\n"
        "aabbccdd00112233aabbccdd00112233aabbccdd00112233aabbccdd00112233  src/Main.py\n"
    )
    path = tmp_path / "checksums.sha256"
    path.write_text(content, encoding="utf-8")
    return path


class TestSanitizeCommand:
    def test_sanitize_identity_gnu(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(gnu_hash_file)])

        # Assert — output keeps original GNU format
        assert result.exit_code == 0
        assert "C:/projects/src/main.py" in result.output
        assert "C:/projects/src/utils.py" in result.output

    def test_sanitize_convert_gnu_to_bsd(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(gnu_hash_file), "--format", "bsd"])

        # Assert
        assert result.exit_code == 0
        assert "SHA256 (" in result.output
        assert ") = " in result.output

    def test_sanitize_convert_bsd_to_gnu(self, runner: CliRunner, bsd_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(bsd_hash_file), "--format", "gnu"])

        # Assert
        assert result.exit_code == 0
        assert "SHA256 (" not in result.output
        assert " *src/main.py" in result.output

    def test_sanitize_strip_prefix(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(gnu_hash_file), "--strip-prefix", "C:/projects"])

        # Assert — paths should be relative
        assert result.exit_code == 0
        assert "C:/projects" not in result.output
        assert "src/main.py" in result.output
        assert "tests/test_main.py" in result.output

    def test_sanitize_separator_posix(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(gnu_hash_file), "--separator", "posix"])

        # Assert — all paths use forward slashes (already do in this case)
        assert result.exit_code == 0
        assert "\\" not in result.output

    def test_sanitize_separator_windows(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Arrange — create file with posix paths
        content = (
            "aabbccdd00112233aabbccdd00112233aabbccdd00112233aabbccdd00112233  src/main.py\n"
            "11223344556677881122334455667788112233445566778811223344556677aa  src/utils.py\n"
        )
        hash_file = gnu_hash_file.parent / "posix.sha256"
        hash_file.write_text(content, encoding="utf-8")

        # Act
        result = runner.invoke(main, ["sanitize", str(hash_file), "--separator", "windows"])

        # Assert
        assert result.exit_code == 0
        assert "src\\main.py" in result.output
        assert "src\\utils.py" in result.output

    def test_sanitize_hash_case_lower(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(gnu_hash_file), "--hash-case", "lower"])

        # Assert — the mixed-case entry should be lowered
        assert result.exit_code == 0
        assert "AABBCCDD" not in result.output
        assert "aabbccdd" in result.output

    def test_sanitize_hash_case_upper(self, runner: CliRunner, bsd_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(bsd_hash_file), "--hash-case", "upper"])

        # Assert
        assert result.exit_code == 0
        assert "1122334455667788112233445566778811223344556677AA" in result.output

    def test_sanitize_sort_by_path(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(gnu_hash_file), "--sort", "path"])

        # Assert — lines should be sorted alphabetically by path
        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().splitlines() if ln.strip()]
        # GNU text-mode format: "<hash>  <path>" (two spaces — no binary indicator)
        paths = [ln.split("  ", 1)[1] for ln in lines]
        assert paths == sorted(paths, key=str.lower)

    def test_sanitize_deduplicate(self, runner: CliRunner, duplicate_hash_file: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(duplicate_hash_file), "--deduplicate"])

        # Assert — 3 entries → 2 (main.py and Main.py collapse)
        assert result.exit_code == 0
        lines = [ln for ln in result.output.strip().splitlines() if ln.strip()]
        assert len(lines) == 2

    def test_sanitize_output_to_file(self, runner: CliRunner, gnu_hash_file: Path, tmp_path: Path) -> None:
        # Arrange
        output_path = tmp_path / "sanitized.sha256"

        # Act
        result = runner.invoke(
            main,
            ["sanitize", str(gnu_hash_file), "--format", "bsd", "-o", str(output_path)],
        )

        # Assert
        assert result.exit_code == 0
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "SHA256 (" in content
        assert "Written 3 entry/entries" in result.output

    def test_sanitize_combined_transforms(self, runner: CliRunner, gnu_hash_file: Path) -> None:
        # Act — strip prefix + lowercase + sort + convert to BSD
        result = runner.invoke(
            main,
            [
                "sanitize",
                str(gnu_hash_file),
                "--strip-prefix", "C:/projects",
                "--hash-case", "lower",
                "--sort", "path",
                "--format", "bsd",
            ],
        )

        # Assert
        assert result.exit_code == 0
        assert "SHA256 (src/main.py)" in result.output
        assert "C:/projects" not in result.output
        # All hashes lowercase
        import re
        hashes = re.findall(r"= ([0-9a-f]+)", result.output)
        assert all(h == h.lower() for h in hashes)

    def test_sanitize_empty_file_exits_2(self, runner: CliRunner, tmp_path: Path) -> None:
        # Arrange
        empty = tmp_path / "empty.sha256"
        empty.write_text("", encoding="utf-8")

        # Act
        result = runner.invoke(main, ["sanitize", str(empty)])

        # Assert
        assert result.exit_code == 2
        assert "No hash entries" in result.output

    def test_sanitize_nonexistent_file_exits_2(self, runner: CliRunner, tmp_path: Path) -> None:
        # Act
        result = runner.invoke(main, ["sanitize", str(tmp_path / "nope.sha256")])

        # Assert
        assert result.exit_code == 2

    def test_sanitize_detects_bsd_format_by_default(self, runner: CliRunner, bsd_hash_file: Path) -> None:
        # Act — no --format, should auto-detect and keep BSD
        result = runner.invoke(main, ["sanitize", str(bsd_hash_file)])

        # Assert
        assert result.exit_code == 0
        assert "SHA256 (" in result.output

    def test_sanitize_line_ending_lf_in_output_file(
        self, runner: CliRunner, gnu_hash_file: Path, tmp_path: Path,
    ) -> None:
        # Arrange
        output_path = tmp_path / "lf.sha256"

        # Act
        result = runner.invoke(
            main,
            ["sanitize", str(gnu_hash_file), "--line-ending", "lf", "-o", str(output_path)],
        )

        # Assert — file written with LF only
        assert result.exit_code == 0
        raw = output_path.read_bytes()
        assert b"\r\n" not in raw
        assert b"\r" not in raw
        assert raw.count(b"\n") == 3

    def test_sanitize_line_ending_crlf_in_output_file(
        self, runner: CliRunner, gnu_hash_file: Path, tmp_path: Path,
    ) -> None:
        # Arrange
        output_path = tmp_path / "crlf.sha256"

        # Act
        result = runner.invoke(
            main,
            ["sanitize", str(gnu_hash_file), "--line-ending", "crlf", "-o", str(output_path)],
        )

        # Assert — file written with CRLF
        assert result.exit_code == 0
        raw = output_path.read_bytes()
        assert raw.count(b"\r\n") == 3

    def test_sanitize_line_ending_cr_in_output_file(
        self, runner: CliRunner, gnu_hash_file: Path, tmp_path: Path,
    ) -> None:
        # Arrange
        output_path = tmp_path / "cr.sha256"

        # Act
        result = runner.invoke(
            main,
            ["sanitize", str(gnu_hash_file), "--line-ending", "cr", "-o", str(output_path)],
        )

        # Assert — file written with CR only
        assert result.exit_code == 0
        raw = output_path.read_bytes()
        assert b"\n" not in raw
        assert raw.count(b"\r") == 3
