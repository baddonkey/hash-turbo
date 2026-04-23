"""Tests for core.models domain types."""

from __future__ import annotations

import pytest

from hash_turbo.core.models import (
    Algorithm,
    HashEntry,
    HashResult,
    VerifyResult,
    VerifyStatus,
)


class TestAlgorithm:
    def test_algorithm_default_is_sha256(self) -> None:
        assert Algorithm.default() is Algorithm.SHA256

    def test_algorithm_from_str_valid(self) -> None:
        assert Algorithm.from_str("sha256") is Algorithm.SHA256
        assert Algorithm.from_str("SHA256") is Algorithm.SHA256
        assert Algorithm.from_str("md5") is Algorithm.MD5
        assert Algorithm.from_str("sha3-256") is Algorithm.SHA3_256
        assert Algorithm.from_str("blake2b") is Algorithm.BLAKE2B

    def test_algorithm_from_str_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            Algorithm.from_str("not-a-real-algorithm")

    def test_algorithm_values_match_hashlib_names(self) -> None:
        import hashlib

        for algo in Algorithm:
            # Every enum value must be accepted by hashlib.new()
            h = hashlib.new(algo.value)
            assert h is not None

    def test_algorithm_available_returns_all_members(self) -> None:
        available = Algorithm.available()
        assert len(available) == len(Algorithm)
        assert all(isinstance(a, Algorithm) for a in available)

    def test_algorithm_display_name(self) -> None:
        assert Algorithm.SHA256.display_name == "SHA-256"
        assert Algorithm.MD5.display_name == "MD5"
        assert Algorithm.BLAKE2B.display_name == "BLAKE2B"

    def test_algorithm_display_name_all_members(self) -> None:
        expected = {
            Algorithm.MD5: "MD5",
            Algorithm.SHA1: "SHA-1",
            Algorithm.SHA224: "SHA-224",
            Algorithm.SHA256: "SHA-256",
            Algorithm.SHA384: "SHA-384",
            Algorithm.SHA512: "SHA-512",
            Algorithm.SHA3_256: "SHA3-256",
            Algorithm.SHA3_512: "SHA3-512",
            Algorithm.BLAKE2B: "BLAKE2B",
            Algorithm.BLAKE2S: "BLAKE2S",
        }
        for algo, name in expected.items():
            assert algo.display_name == name, f"{algo} expected {name!r}, got {algo.display_name!r}"


class TestHashResult:
    def test_hash_result_construction(self) -> None:
        result = HashResult(path="file.txt", algorithm=Algorithm.SHA256, hex_digest="abc123")
        assert result.path == "file.txt"
        assert result.algorithm is Algorithm.SHA256
        assert result.hex_digest == "abc123"

    def test_hash_result_is_frozen(self) -> None:
        result = HashResult(path="f.txt", algorithm=Algorithm.MD5, hex_digest="abc")
        with pytest.raises(AttributeError):
            result.path = "other.txt"  # type: ignore[misc]


class TestHashEntry:
    def test_hash_entry_construction(self) -> None:
        entry = HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="abc123")
        assert entry.path == "file.txt"
        assert entry.algorithm is Algorithm.SHA256
        assert entry.expected_hash == "abc123"


class TestVerifyResult:
    def test_verify_result_ok(self) -> None:
        entry = HashEntry(path="f.txt", algorithm=Algorithm.SHA256, expected_hash="abc")
        result = VerifyResult(entry=entry, status=VerifyStatus.OK)
        assert result.status is VerifyStatus.OK

    def test_verify_result_failed(self) -> None:
        entry = HashEntry(path="f.txt", algorithm=Algorithm.SHA256, expected_hash="abc")
        result = VerifyResult(entry=entry, status=VerifyStatus.FAILED)
        assert result.status is VerifyStatus.FAILED


