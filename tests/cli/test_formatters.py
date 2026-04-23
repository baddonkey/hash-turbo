"""Tests for cli.formatters — output formatting."""

from __future__ import annotations

from hash_turbo.cli.formatters import OutputFormatter
from hash_turbo.core.models import Algorithm, HashResult


class TestFormatSingle:
    def test_format_single_sha256(self) -> None:
        result = HashResult(path="file.txt", algorithm=Algorithm.SHA256, hex_digest="abc123")
        output = OutputFormatter.format_single(result)
        assert output == "SHA-256: abc123"

    def test_format_single_md5(self) -> None:
        result = HashResult(path="file.txt", algorithm=Algorithm.MD5, hex_digest="abc123")
        output = OutputFormatter.format_single(result)
        assert output == "MD5: abc123"


class TestFormatTable:
    def test_format_table_single(self) -> None:
        results = [HashResult(path="file.txt", algorithm=Algorithm.SHA256, hex_digest="abc123")]
        output = OutputFormatter.format_table(results)
        assert output == "abc123  file.txt"

    def test_format_table_multiple(self) -> None:
        results = [
            HashResult(path="a.txt", algorithm=Algorithm.SHA256, hex_digest="aaa"),
            HashResult(path="b.txt", algorithm=Algorithm.SHA256, hex_digest="bbb"),
        ]
        output = OutputFormatter.format_table(results)
        lines = output.split("\n")
        assert len(lines) == 2
        assert "aaa  a.txt" in lines[0]
        assert "bbb  b.txt" in lines[1]

    def test_format_table_empty(self) -> None:
        output = OutputFormatter.format_table([])
        assert output == ""
