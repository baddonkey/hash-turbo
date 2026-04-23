"""Shared helpers for normalising path strings used as comparison keys.

Hash file entries arrive with mixed separators (``/`` vs ``\\``), case
variants on case-insensitive filesystems, and ``./`` prefixes.  The
helpers here produce a single canonical key so deduplication, lookups,
and sorting all agree on what "the same path" means.
"""

from __future__ import annotations


def normalize_path_key(path: str) -> str:
    """Return a stable, case-folded, slash-normalised lookup key for *path*.

    - Backslashes are converted to forward slashes.
    - A leading ``./`` is stripped (entries written by some tools).
    - The result is :py:meth:`str.casefold`-ed for case-insensitive equality.
    """
    if not path:
        return ""
    normalised = path.replace("\\", "/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised.casefold()


__all__ = ["normalize_path_key"]
