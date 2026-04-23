"""Filename exclusion filter supporting fnmatch and regex patterns."""

from __future__ import annotations

import fnmatch
import logging
import re
from typing import Sequence

_log = logging.getLogger(__name__)
_REGEX_PREFIX = "re:"


class ExcludeFilter:
    """Matches filenames against a list of exclude patterns.

    Each pattern is either:
    - A plain fnmatch glob (e.g. ``Thumbs.db``, ``*.log``)
    - A regex prefixed with ``re:`` (e.g. ``re:^\\..*`` for hidden files)

    Matching is performed against the filename only (not the full path).
    """

    # Patterns the *user* sees as defaults in the Settings UI.  Kept
    # short so it doesn't intimidate; the user can extend it freely.
    USER_DEFAULT_PATTERNS: list[str] = [
        "Thumbs.db",
        r"re:^\..+",
    ]

    # Internal exclusions for hash-file outputs.  These are *always*
    # added on top of the user patterns by callers that scan files —
    # we never want to hash or re-verify our own manifests.
    INTERNAL_HASH_EXTENSIONS: tuple[str, ...] = (
        "*.md5",
        "*.sha1",
        "*.sha224",
        "*.sha256",
        "*.sha384",
        "*.sha512",
        "*.sha3-256",
        "*.sha3-512",
        "*.blake2b",
        "*.blake2s",
    )

    # Backwards-compatible combined view — kept for any external
    # imports.  New code should use ``USER_DEFAULT_PATTERNS`` and merge
    # ``INTERNAL_HASH_EXTENSIONS`` explicitly.
    DEFAULT_PATTERNS: list[str] = [*USER_DEFAULT_PATTERNS, *INTERNAL_HASH_EXTENSIONS]

    def __init__(self, patterns: Sequence[str]) -> None:
        self._fnmatch: list[str] = []
        self._regex: list[re.Pattern[str]] = []
        for raw in patterns:
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.startswith(_REGEX_PREFIX):
                expr = stripped[len(_REGEX_PREFIX) :]
                try:
                    self._regex.append(re.compile(expr))
                except re.error as exc:
                    _log.warning("Invalid exclude regex pattern %r: %s", expr, exc)
            else:
                self._fnmatch.append(stripped)

    @classmethod
    def with_internal_defaults(cls, user_patterns: Sequence[str]) -> ExcludeFilter:
        """Construct a filter from *user_patterns* plus internal defaults.

        The returned filter always excludes hash-file outputs (see
        :data:`INTERNAL_HASH_EXTENSIONS`) so scans never include
        previously-written manifests.
        """
        merged = list(user_patterns) + list(cls.INTERNAL_HASH_EXTENSIONS)
        return cls(merged)

    @property
    def is_empty(self) -> bool:
        """True when no patterns are configured."""
        return not self._fnmatch and not self._regex

    def is_excluded(self, filename: str) -> bool:
        """Return True if *filename* matches any exclude pattern."""
        for pat in self._fnmatch:
            if fnmatch.fnmatch(filename, pat):
                return True
        for rx in self._regex:
            if rx.search(filename):
                return True
        return False


__all__ = ["ExcludeFilter"]
