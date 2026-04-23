"""Tests for cli.app — Click command integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from click.testing import CliRunner

from hash_turbo.cli.app import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestHashCommand:
    def test_hash_single_file(self, runner: CliRunner, sample_file: Path) -> None:
        result = runner.invoke(main, ["hash", str(sample_file)])
        assert result.exit_code == 0
        assert "SHA-256:" in result.output

    def test_hash_with_algorithm(self, runner: CliRunner, sample_file: Path) -> None:
        result = runner.invoke(main, ["hash", str(sample_file), "-a", "md5"])
        assert result.exit_code == 0
        assert "MD5:" in result.output

    def test_hash_multiple_files(
        self, runner: CliRunner, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        f1 = sample_file_factory("a.txt", "aaa")
        f2 = sample_file_factory("b.txt", "bbb")
        result = runner.invoke(main, ["hash", str(f1), str(f2)])
        assert result.exit_code == 0
        # Multiple files → table format
        assert "a.txt" in result.output
        assert "b.txt" in result.output

    def test_hash_directory_recursive(
        self, runner: CliRunner, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("top.txt", "top")
        sample_file_factory("sub/nested.txt", "nested")
        result = runner.invoke(main, ["hash", str(tmp_path), "-r"])
        assert result.exit_code == 0
        assert "top.txt" in result.output
        assert "nested.txt" in result.output

    def test_hash_output_to_file(
        self, runner: CliRunner, sample_file: Path, tmp_path: Path
    ) -> None:
        output_path = tmp_path / "checksums.sha256"
        result = runner.invoke(main, ["hash", str(sample_file), "-o", str(output_path)])
        assert result.exit_code == 0
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "sample.txt" in content

    def test_hash_glob_filter(
        self, runner: CliRunner, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("code.py", "print()")
        sample_file_factory("readme.md", "# hi")
        result = runner.invoke(main, ["hash", str(tmp_path), "-g", "*.py"])
        assert result.exit_code == 0
        assert "code.py" in result.output
        assert "readme.md" not in result.output

    def test_hash_json_format(self, runner: CliRunner, sample_file: Path) -> None:
        result = runner.invoke(main, ["hash", str(sample_file), "--format", "json"])
        assert result.exit_code == 0
        assert '"algorithm"' in result.output

    def test_hash_bsd_format(
        self, runner: CliRunner, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        f1 = sample_file_factory("a.txt", "aaa")
        f2 = sample_file_factory("b.txt", "bbb")
        result = runner.invoke(main, ["hash", str(f1), str(f2), "--format", "bsd"])
        assert result.exit_code == 0
        assert "SHA256 (" in result.output

    def test_hash_no_files_exits_2(self, runner: CliRunner, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = runner.invoke(main, ["hash", str(empty_dir)])
        assert result.exit_code == 2


class TestVerifyCommand:
    def test_verify_valid_hash_file(
        self, runner: CliRunner, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Create a file and hash it
        f = sample_file_factory("data.txt", "hello")
        hash_result = runner.invoke(main, ["hash", str(f), "-o", str(tmp_path / "check.sha256")])
        assert hash_result.exit_code == 0

        # Verify
        result = runner.invoke(main, ["verify", str(tmp_path / "check.sha256")])
        assert result.exit_code == 0
        assert "OK" in result.output

    def test_verify_expect_inline(self, runner: CliRunner, sample_file: Path) -> None:
        # SHA-256 of "hello"
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        result = runner.invoke(main, ["verify", str(sample_file), "--expect", expected])
        assert result.exit_code == 0
        assert "OK" in result.output

    def test_verify_expect_mismatch(self, runner: CliRunner, sample_file: Path) -> None:
        result = runner.invoke(main, ["verify", str(sample_file), "--expect", "wronghash"])
        assert result.exit_code == 1
        assert "FAILED" in result.output

    def test_verify_no_args_exits_2(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["verify"])
        assert result.exit_code == 2


class TestAlgorithmsCommand:
    def test_algorithms_lists_all(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["algorithms"])
        assert result.exit_code == 0
        assert "sha256" in result.output
        assert "md5" in result.output
        assert "blake2b" in result.output


class TestVersion:
    def test_version_flag(self, runner: CliRunner) -> None:
        from hash_turbo import __version__

        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestAlgorithmType:
    def test_invalid_algorithm_shows_error(self, runner: CliRunner, sample_file: Path) -> None:
        result = runner.invoke(main, ["hash", str(sample_file), "-a", "not-real"])
        assert result.exit_code != 0
        assert "Unknown algorithm" in result.output
