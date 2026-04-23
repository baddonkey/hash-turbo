"""File I/O adapter for the core hasher."""

from __future__ import annotations

from pathlib import Path

from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import Algorithm, AlgorithmLike, HashResult


def hash_file(
    hasher: Hasher,
    path: Path,
    algorithm: AlgorithmLike = Algorithm.SHA256,
    *,
    binary_mode: bool = True,
) -> HashResult:
    """Hash a file by streaming it in chunks.

    When *binary_mode* is False, ``\\r\\n`` sequences are normalised
    to ``\\n`` before hashing — matching GNU coreutils text-mode
    behaviour.
    """
    with open(path, "rb") as f:
        if binary_mode:
            digest = hasher.hash_stream(f, algorithm)
        else:
            digest = hasher.hash_stream_text(f, algorithm)
    return HashResult(path=str(path), algorithm=algorithm, hex_digest=digest)


__all__ = ["hash_file"]
