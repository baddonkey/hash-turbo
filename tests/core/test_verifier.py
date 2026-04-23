"""Tests for core.verifier — hash verification logic."""

from __future__ import annotations

from hash_turbo.core.models import (
    Algorithm,
    HashEntry,
    HashResult,
    VerifyStatus,
)
from hash_turbo.core.verifier import Verifier


def _entry(path: str = "file.txt", expected: str = "abc123") -> HashEntry:
    return HashEntry(path=path, algorithm=Algorithm.SHA256, expected_hash=expected)


def _result(path: str = "file.txt", digest: str = "abc123") -> HashResult:
    return HashResult(path=path, algorithm=Algorithm.SHA256, hex_digest=digest)


class TestVerifyEntry:
    def test_verify_entry_match_returns_ok(self) -> None:
        entry = _entry(expected="aabb")
        computed = _result(digest="aabb")
        result = Verifier.verify_entry(entry, computed)
        assert result.status is VerifyStatus.OK

    def test_verify_entry_mismatch_returns_failed(self) -> None:
        entry = _entry(expected="aabb")
        computed = _result(digest="ccdd")
        result = Verifier.verify_entry(entry, computed)
        assert result.status is VerifyStatus.FAILED

    def test_verify_entry_case_insensitive(self) -> None:
        entry = _entry(expected="AABB")
        computed = _result(digest="aabb")
        result = Verifier.verify_entry(entry, computed)
        assert result.status is VerifyStatus.OK


class TestVerifyResults:
    def test_verify_results_all_ok(self) -> None:
        entries = [_entry("a.txt", "111"), _entry("b.txt", "222")]
        computed = {"a.txt": _result("a.txt", "111"), "b.txt": _result("b.txt", "222")}
        results = Verifier.verify_results(entries, computed)
        assert all(r.status is VerifyStatus.OK for r in results)

    def test_verify_results_one_failed(self) -> None:
        entries = [_entry("a.txt", "111"), _entry("b.txt", "222")]
        computed = {"a.txt": _result("a.txt", "111"), "b.txt": _result("b.txt", "999")}
        results = Verifier.verify_results(entries, computed)
        assert results[0].status is VerifyStatus.OK
        assert results[1].status is VerifyStatus.FAILED

    def test_verify_results_missing_file(self) -> None:
        entries = [_entry("a.txt", "111"), _entry("missing.txt", "222")]
        computed = {"a.txt": _result("a.txt", "111")}
        results = Verifier.verify_results(entries, computed)
        assert results[0].status is VerifyStatus.OK
        assert results[1].status is VerifyStatus.MISSING

    def test_verify_results_empty_entries(self) -> None:
        results = Verifier.verify_results([], {})
        assert results == []
