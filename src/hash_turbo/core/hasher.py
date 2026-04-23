"""Streaming hash computation."""

from __future__ import annotations

import hashlib
from typing import Protocol

from hash_turbo.core.models import AlgorithmLike

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB — good balance for I/O throughput


class _Readable(Protocol):
    """Minimal protocol for streams supported by :class:`Hasher`.

    Matches :class:`io.BufferedIOBase` and :class:`io.RawIOBase` (any
    binary file opened with ``open(path, 'rb')``).
    """

    def readinto(self, buffer: bytearray, /) -> int | None: ...


class Hasher:
    """Computes file hashes using streaming reads."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self._chunk_size = chunk_size

    def hash_stream(self, stream: _Readable, algorithm: AlgorithmLike) -> str:
        """Compute hex digest by streaming from a binary IO object."""
        h = hashlib.new(algorithm.value)
        buf = bytearray(self._chunk_size)
        view = memoryview(buf)
        while True:
            n = stream.readinto(buf)
            if not n:
                break
            h.update(view[:n])
        return h.hexdigest()

    def hash_stream_text(self, stream: _Readable, algorithm: AlgorithmLike) -> str:
        """Compute hex digest with ``\\r\\n`` → ``\\n`` normalisation."""
        h = hashlib.new(algorithm.value)
        buf = bytearray(self._chunk_size)
        leftover_cr = False
        while True:
            n = stream.readinto(buf)
            if not n:
                if leftover_cr:
                    h.update(b"\r")
                break
            chunk = bytes(buf[:n])
            if leftover_cr:
                chunk = b"\r" + chunk
                leftover_cr = False
            if chunk.endswith(b"\r"):
                chunk = chunk[:-1]
                leftover_cr = True
            chunk = chunk.replace(b"\r\n", b"\n")
            h.update(chunk)
        return h.hexdigest()


__all__ = ["Hasher"]
