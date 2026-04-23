"""Tests for ``Verifier.verify_with_lookup``."""

from __future__ import annotations

from hash_turbo.core.models import (
    Algorithm,
    HashEntry,
    HashResult,
    VerifyStatus,
)
from hash_turbo.core.verifier import Verifier


def _entry(path: str, expected: str) -> HashEntry:
    return HashEntry(path=path, algorithm=Algorithm.SHA256, expected_hash=expected)


def _result(path: str, digest: str) -> HashResult:
    return HashResult(path=path, algorithm=Algorithm.SHA256, hex_digest=digest)


class TestVerifyWithLookup:
    def test_all_ok(self) -> None:
        entries = [_entry("a.txt", "deadbeef")]
        results = Verifier.verify_with_lookup(
            entries, lambda e: _result(e.path, "deadbeef"),
        )
        assert [r.status for r in results] == [VerifyStatus.OK]

    def test_missing_returns_missing(self) -> None:
        entries = [_entry("gone.txt", "deadbeef")]
        results = Verifier.verify_with_lookup(entries, lambda _e: None)
        assert results[0].status is VerifyStatus.MISSING

    def test_mismatch_returns_failed(self) -> None:
        entries = [_entry("a.txt", "deadbeef")]
        results = Verifier.verify_with_lookup(
            entries, lambda e: _result(e.path, "cafef00d"),
        )
        assert results[0].status is VerifyStatus.FAILED

    def test_case_insensitive_match(self) -> None:
        entries = [_entry("a.txt", "DEADBEEF")]
        results = Verifier.verify_with_lookup(
            entries, lambda e: _result(e.path, "deadbeef"),
        )
        assert results[0].status is VerifyStatus.OK
