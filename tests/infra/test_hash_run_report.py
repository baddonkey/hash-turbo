"""Tests for ``HashExecutor.hash_files_with_report`` (M9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hash_turbo.core.models import Algorithm
from hash_turbo.infra.executor import HashExecutor, HashRunReport


class TestHashRunReport:
    def test_successful_run_has_no_errors(self, tmp_path: Path) -> None:
        f = tmp_path / "a.bin"
        f.write_bytes(b"hello")

        executor = HashExecutor()
        report = executor.hash_files_with_report([f], algorithm=Algorithm.SHA256)

        assert isinstance(report, HashRunReport)
        assert len(report.results) == 1
        assert report.errors == []
        assert report.cancelled is False

    def test_missing_file_shows_up_in_errors(self, tmp_path: Path) -> None:
        executor = HashExecutor()
        report = executor.hash_files_with_report(
            [tmp_path / "does-not-exist"], algorithm=Algorithm.SHA256,
        )

        assert report.results == []
        assert len(report.errors) == 1
        _item, exc = report.errors[0]
        assert isinstance(exc, OSError)

    def test_empty_input_returns_empty_report(self) -> None:
        executor = HashExecutor()
        report = executor.hash_files_with_report([], algorithm=Algorithm.SHA256)

        assert report == HashRunReport(results=[], errors=[], cancelled=False)
