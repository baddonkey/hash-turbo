"""Domain types for hash-turbo."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Union, runtime_checkable


_ALGORITHM_DISPLAY_NAMES: dict[str, str] = {
    "md5": "MD5",
    "sha1": "SHA-1",
    "sha224": "SHA-224",
    "sha256": "SHA-256",
    "sha384": "SHA-384",
    "sha512": "SHA-512",
    "sha3-256": "SHA3-256",
    "sha3-512": "SHA3-512",
    "blake2b": "BLAKE2B",
    "blake2s": "BLAKE2S",
}


@runtime_checkable
class AlgorithmLike(Protocol):
    """Anything that identifies a hashlib algorithm.

    Both :class:`Algorithm` (enum of well-known names) and
    :class:`DynamicAlgorithm` (wrapper for arbitrary
    ``hashlib.new()`` names) satisfy this protocol.
    """

    @property
    def value(self) -> str: ...

    @property
    def display_name(self) -> str: ...


class Algorithm(Enum):
    """Well-known hash algorithms.

    For algorithms outside this enum, :meth:`Algorithm.from_str` returns a
    :class:`DynamicAlgorithm` instance instead.  Both implement
    :class:`AlgorithmLike`.
    """

    MD5 = "md5"
    SHA1 = "sha1"
    SHA224 = "sha224"
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    SHA3_256 = "sha3-256"
    SHA3_512 = "sha3-512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"

    @classmethod
    def default(cls) -> Algorithm:
        return cls.SHA256

    @classmethod
    def from_str(cls, value: str) -> AlgorithmLike:
        """Resolve any string to an :class:`AlgorithmLike`.

        Accepts every name :func:`hashlib.new` accepts.  Returns an
        :class:`Algorithm` enum member for well-known names and a
        :class:`DynamicAlgorithm` wrapper otherwise.

        Raises :class:`ValueError` if hashlib does not recognise the name.
        """
        normalized = value.lower().replace("_", "-")
        for member in cls:
            if member.value == normalized:
                return member
        # Validate via hashlib.  Try the normalised form first, then the
        # raw lowercase form (some hashlib names like ``shake_128`` use
        # underscores that the dash-normalisation above would mangle).
        for candidate in (normalized, value.lower()):
            try:
                hashlib.new(candidate)
            except (ValueError, TypeError):
                continue
            return DynamicAlgorithm(value=candidate)
        raise ValueError(f"Unsupported algorithm: {value}")

    @property
    def display_name(self) -> str:
        """Human-readable name, e.g. ``'SHA-256'``."""
        return _ALGORITHM_DISPLAY_NAMES.get(self.value, self.value.upper())

    @classmethod
    def available(cls) -> list[Algorithm]:
        """Return all enum-registered algorithms (well-known set)."""
        return list(cls)


@dataclass(frozen=True)
class DynamicAlgorithm:
    """Wrapper for any :func:`hashlib.new`-supported algorithm name.

    Returned by :meth:`Algorithm.from_str` for algorithms outside the
    well-known :class:`Algorithm` enum (e.g. ``shake_128``,
    ``sha512_256``, OpenSSL-provided digests).
    """

    value: str

    @property
    def display_name(self) -> str:
        return _ALGORITHM_DISPLAY_NAMES.get(self.value, self.value.upper())


# Concrete union type for runtime ``isinstance`` checks and serialisation.
AnyAlgorithm = Union[Algorithm, DynamicAlgorithm]


class HashFileFormat(Enum):
    """Output format for hash files."""

    GNU = "gnu"
    BSD = "bsd"
    JSON = "json"


class PathMode(Enum):
    """Path representation in hash file output."""

    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class VerifyStatus(Enum):
    """Result of verifying a single file."""

    OK = "OK"
    FAILED = "FAILED"
    MISSING = "MISSING"


@dataclass(frozen=True)
class HashResult:
    """Result of hashing a single file."""

    path: str
    algorithm: AlgorithmLike
    hex_digest: str


@dataclass(frozen=True)
class HashEntry:
    """Expected hash entry parsed from a hash file."""

    path: str
    algorithm: AlgorithmLike
    expected_hash: str
    binary_mode: bool = True


@dataclass(frozen=True)
class VerifyResult:
    """Verification result for a single file."""

    entry: HashEntry
    status: VerifyStatus


__all__ = [
    "Algorithm",
    "AlgorithmLike",
    "AnyAlgorithm",
    "DynamicAlgorithm",
    "HashEntry",
    "HashFileFormat",
    "HashResult",
    "PathMode",
    "VerifyResult",
    "VerifyStatus",
]
