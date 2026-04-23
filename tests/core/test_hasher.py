"""Tests for core.hasher — streaming hash computation."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import Algorithm
from hash_turbo.infra.hash_io import hash_file


class TestHashStream:
    def test_hash_stream_sha256_known_vector(self) -> None:
        hasher = Hasher()
        data = io.BytesIO(b"hello")
        digest = hasher.hash_stream(data, Algorithm.SHA256)
        assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_hash_stream_md5_known_vector(self) -> None:
        hasher = Hasher()
        data = io.BytesIO(b"hello")
        digest = hasher.hash_stream(data, Algorithm.MD5)
        assert digest == "5d41402abc4b2a76b9719d911017c592"

    def test_hash_stream_empty_input(self) -> None:
        hasher = Hasher()
        data = io.BytesIO(b"")
        digest = hasher.hash_stream(data, Algorithm.SHA256)
        assert digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hash_stream_small_chunk_size(self) -> None:
        content = b"hello world" * 100
        hasher_full = Hasher(chunk_size=8192)
        hasher_small = Hasher(chunk_size=3)
        digest_full = hasher_full.hash_stream(io.BytesIO(content), Algorithm.SHA256)
        digest_small = hasher_small.hash_stream(io.BytesIO(content), Algorithm.SHA256)
        assert digest_full == digest_small


class TestHashFile:
    def test_hash_file_sha256(self, sample_file: Path) -> None:
        hasher = Hasher()
        result = hash_file(hasher, sample_file, Algorithm.SHA256)
        assert result.hex_digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        assert result.algorithm is Algorithm.SHA256
        assert result.path == str(sample_file)

    def test_hash_file_default_algorithm(self, sample_file: Path) -> None:
        hasher = Hasher()
        result = hash_file(hasher, sample_file)
        assert result.algorithm is Algorithm.SHA256

    def test_hash_file_binary_content(self, sample_binary_file: Path) -> None:
        hasher = Hasher()
        result = hash_file(hasher, sample_binary_file, Algorithm.SHA256)
        assert len(result.hex_digest) == 64

    def test_hash_file_empty(self, tmp_path: Path) -> None:
        hasher = Hasher()
        empty = tmp_path / "empty.txt"
        empty.write_bytes(b"")
        result = hash_file(hasher, empty, Algorithm.SHA256)
        assert result.hex_digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hash_file_blake2b(self, sample_file: Path) -> None:
        hasher = Hasher()
        result = hash_file(hasher, sample_file, Algorithm.BLAKE2B)
        assert len(result.hex_digest) > 0
        assert result.algorithm is Algorithm.BLAKE2B


class TestTextMode:
    """Text mode hashing normalises \\r\\n → \\n before computing the digest."""

    def test_text_mode_strips_crlf(self, tmp_path: Path) -> None:
        # Arrange — file with CRLF line endings
        crlf_file = tmp_path / "crlf.txt"
        crlf_file.write_bytes(b"line1\r\nline2\r\n")
        expected = hashlib.sha256(b"line1\nline2\n").hexdigest()

        # Act
        result = hash_file(Hasher(), crlf_file, Algorithm.SHA256, binary_mode=False)

        # Assert
        assert result.hex_digest == expected

    def test_binary_mode_preserves_crlf(self, tmp_path: Path) -> None:
        # Arrange
        crlf_file = tmp_path / "crlf.txt"
        crlf_file.write_bytes(b"line1\r\nline2\r\n")
        expected = hashlib.sha256(b"line1\r\nline2\r\n").hexdigest()

        # Act
        result = hash_file(Hasher(), crlf_file, Algorithm.SHA256, binary_mode=True)

        # Assert
        assert result.hex_digest == expected

    def test_text_mode_no_crlf_matches_binary(self, tmp_path: Path) -> None:
        # Arrange — file with only LF, no CR
        lf_file = tmp_path / "lf.txt"
        lf_file.write_bytes(b"line1\nline2\n")

        # Act
        binary_result = hash_file(Hasher(), lf_file, Algorithm.SHA256, binary_mode=True)
        text_result = hash_file(Hasher(), lf_file, Algorithm.SHA256, binary_mode=False)

        # Assert — on pure LF content, both modes produce the same hash
        assert binary_result.hex_digest == text_result.hex_digest

    def test_text_mode_preserves_standalone_cr(self, tmp_path: Path) -> None:
        # Arrange — file with bare CR (not part of CRLF)
        cr_file = tmp_path / "cr.txt"
        cr_file.write_bytes(b"line1\rline2\r")
        expected = hashlib.sha256(b"line1\rline2\r").hexdigest()

        # Act
        result = hash_file(Hasher(), cr_file, Algorithm.SHA256, binary_mode=False)

        # Assert — bare CR is not stripped
        assert result.hex_digest == expected

    def test_text_mode_crlf_at_chunk_boundary(self, tmp_path: Path) -> None:
        # Arrange — \\r falls at end of one chunk, \\n at start of next
        chunk_size = 16
        data = b"a" * 15 + b"\r\n" + b"b" * 14
        f = tmp_path / "boundary.txt"
        f.write_bytes(data)
        expected = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()

        # Act
        result = hash_file(Hasher(chunk_size=chunk_size), f, Algorithm.SHA256, binary_mode=False)

        # Assert
        assert result.hex_digest == expected
