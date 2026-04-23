"""Parse and write hash files in GNU, BSD, and JSON formats."""

from __future__ import annotations

import json
import logging
import re
from typing import Sequence, TextIO

_log = logging.getLogger(__name__)

from hash_turbo.core.models import (
    Algorithm,
    AlgorithmLike,
    HashEntry,
    HashFileFormat,
    HashResult,
)

# GNU format: <hash> *<path> (binary) or <hash>  <path> (text)
_GNU_PATTERN = re.compile(r"^([0-9a-fA-F]+) ([ *])(.+)$")

# GNU format with flexible whitespace — tabs, multiple spaces, etc.
_GNU_PATTERN_FLEXIBLE = re.compile(r"^([0-9a-fA-F]+)\s+(\*?)(.+)$")

# BSD format: ALGO (path) = hash
_BSD_PATTERN = re.compile(r"^(\w[\w-]*)\s*\((.+)\)\s*=\s*([0-9a-fA-F]+)$")

# Hash length → algorithm mapping for GNU format auto-detection.
# NOTE: SHA3-256 and SHA-256 both produce 64-char hex digests, and
# SHA3-512 and SHA-512 both produce 128-char hex digests.  GNU format
# does not carry an algorithm tag, so SHA3 hashes will be misidentified
# as their SHA-2 counterpart.  Use BSD format or pass an explicit
# *algorithm_hint* to :meth:`HashFileParser.parse` to disambiguate.
_LENGTH_TO_ALGORITHM: dict[int, Algorithm] = {
    32: Algorithm.MD5,
    40: Algorithm.SHA1,
    56: Algorithm.SHA224,
    64: Algorithm.SHA256,
    96: Algorithm.SHA384,
    128: Algorithm.SHA512,
}


def _gnu_line(hex_digest: str, path: str, binary: bool) -> str:
    """Format a single GNU-style line — shared by ``format_gnu`` and sanitizer."""
    mode = "*" if binary else " "
    return f"{hex_digest} {mode}{path}"


class HashFileFormatter:
    """Formats hash results into GNU, BSD, or JSON output."""

    @staticmethod
    def format_gnu(result: HashResult, *, binary: bool = True) -> str:
        """Format a hash result in GNU coreutils style.

        ``binary=True`` (default) emits ``*<path>`` (binary mode);
        ``binary=False`` emits `` <path>`` (text mode).
        """
        return _gnu_line(result.hex_digest, result.path, binary)

    @staticmethod
    def format_bsd(result: HashResult) -> str:
        """Format a hash result in BSD style: 'ALGO (path) = hash'."""
        return f"{result.algorithm.value.upper()} ({result.path}) = {result.hex_digest}"

    @staticmethod
    def format_json(results: Sequence[HashResult]) -> str:
        """Format hash results as a JSON array."""
        records = [
            {
                "path": r.path,
                "algorithm": r.algorithm.value,
                "hash": r.hex_digest,
            }
            for r in results
        ]
        return json.dumps(records, indent=2)

    @staticmethod
    def write(
        results: Sequence[HashResult],
        output: TextIO,
        fmt: HashFileFormat = HashFileFormat.GNU,
    ) -> None:
        """Write hash results to a text stream in the given format."""
        if fmt is HashFileFormat.JSON:
            output.write(HashFileFormatter.format_json(results))
            output.write("\n")
            return

        formatter = HashFileFormatter.format_gnu if fmt is HashFileFormat.GNU else HashFileFormatter.format_bsd
        for result in results:
            output.write(formatter(result))
            output.write("\n")

    @staticmethod
    def detect_format(line: str, *, flexible_whitespace: bool = False) -> HashFileFormat:
        """Detect whether a line is GNU or BSD format."""
        if _BSD_PATTERN.match(line):
            return HashFileFormat.BSD
        gnu = _GNU_PATTERN_FLEXIBLE if flexible_whitespace else _GNU_PATTERN
        if gnu.match(line):
            return HashFileFormat.GNU
        raise ValueError(f"Cannot detect hash file format from line: {line!r}")


class HashFileParser:
    """Parses hash file content in GNU or BSD format."""

    @staticmethod
    def parse(
        content: str,
        *,
        flexible_whitespace: bool = False,
        algorithm_hint: AlgorithmLike | None = None,
    ) -> list[HashEntry]:
        """Parse hash file content, auto-detecting GNU vs BSD format.

        :param algorithm_hint:
            Override the auto-detected algorithm for GNU-format lines
            that don't carry an algorithm tag.  Required to distinguish
            e.g. SHA3-256 from SHA-256 in a GNU manifest.
        """
        gnu_pattern = _GNU_PATTERN_FLEXIBLE if flexible_whitespace else _GNU_PATTERN
        entries: list[HashEntry] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            bsd_match = _BSD_PATTERN.match(line)
            if bsd_match:
                algo_tag, path, hex_hash = bsd_match.groups()
                algorithm: AlgorithmLike = Algorithm.from_str(algo_tag)
                entries.append(HashEntry(path=path, algorithm=algorithm, expected_hash=hex_hash))
                continue

            gnu_match = gnu_pattern.match(line)
            if gnu_match:
                hex_hash, mode_char, path = gnu_match.groups()
                if algorithm_hint is not None:
                    algorithm = algorithm_hint
                else:
                    inferred = _LENGTH_TO_ALGORITHM.get(len(hex_hash))
                    if inferred is None:
                        _log.warning(
                            "Cannot infer algorithm from hash length %d, "
                            "defaulting to SHA-256: %r",
                            len(hex_hash), line,
                        )
                        inferred = Algorithm.SHA256
                    algorithm = inferred
                binary_mode = mode_char == "*"
                entries.append(HashEntry(
                    path=path, algorithm=algorithm,
                    expected_hash=hex_hash, binary_mode=binary_mode,
                ))
                continue

            raise ValueError(f"Unrecognized hash file line: {line!r}")

        return entries


__all__ = [
    "HashFileFormatter",
    "HashFileParser",
]
