"""Tests for the CLI ``verify`` command \u2014 H2 (--base-dir) and H7 (OSError)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from hash_turbo.cli.app import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class TestVerifyBaseDir:
    def test_relative_paths_resolve_against_base_dir(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        # Manifest in one dir, files in a sibling dir.
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        target = files_dir / "data.bin"
        target.write_bytes(b"hello")

        manifest = tmp_path / "manifest.sha256"
        manifest.write_text(f"{_sha256(b'hello')} *data.bin\n")

        result = runner.invoke(
            main, ["verify", str(manifest), "--base-dir", str(files_dir)],
        )
        assert result.exit_code == 0, result.output
        assert "data.bin: OK" in result.output

    def test_absolute_paths_are_honored_verbatim(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        target = tmp_path / "abs.bin"
        target.write_bytes(b"abs")

        manifest = tmp_path / "manifest.sha256"
        manifest.write_text(f"{_sha256(b'abs')} *{target}\n")

        result = runner.invoke(main, ["verify", str(manifest)])
        assert result.exit_code == 0, result.output
        assert f"{target}: OK" in result.output


class TestVerifyOSError:
    def test_unreadable_file_reports_io_error(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "data.bin"
        target.write_bytes(b"hello")
        manifest = tmp_path / "manifest.sha256"
        manifest.write_text(f"{_sha256(b'hello')} *data.bin\n")

        # Force hash_file to raise OSError to simulate I/O error.
        from hash_turbo.cli import app as cli_app

        def boom(*args: object, **kwargs: object) -> None:
            raise OSError("simulated read error")

        monkeypatch.setattr(cli_app, "hash_file", boom)

        result = runner.invoke(main, ["verify", str(manifest)])
        assert result.exit_code == 1
        assert "I/O error" in result.output


class TestVerifyAlgorithmHint:
    def test_algorithm_hint_used_for_typeless_lines(
        self, runner: CliRunner, tmp_path: Path,
    ) -> None:
        # md5 of "x" so we can write a raw "<hash>  <path>" line that
        # the parser would otherwise have to guess.
        digest = hashlib.md5(b"x").hexdigest()
        target = tmp_path / "x.bin"
        target.write_bytes(b"x")

        manifest = tmp_path / "manifest.txt"
        manifest.write_text(f"{digest}  x.bin\n")

        result = runner.invoke(
            main, ["verify", str(manifest), "--algorithm-hint", "md5"],
        )
        assert result.exit_code == 0, result.output
        assert "x.bin: OK" in result.output
