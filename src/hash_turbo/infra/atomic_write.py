"""Atomic file write helpers — write-temp + rename pattern.

A Ctrl-C during a long write must not leave the user with a truncated
manifest in place of their previously-valid file.  These helpers write
to a sibling temporary file first and only rename once the bytes are
flushed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union


PathLike = Union[str, "os.PathLike[str]"]


def atomic_write_text(
    path: PathLike,
    content: str,
    *,
    encoding: str = "utf-8",
    newline: str = "",
) -> None:
    """Write *content* to *path* atomically.

    The data is first written to ``<path>.tmp`` and only then
    :func:`os.replace`-d into place.  On POSIX, the rename is atomic on
    the same filesystem; on Windows, ``os.replace`` overwrites
    atomically as well.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding=encoding, newline=newline) as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


def atomic_write_bytes(path: PathLike, data: bytes) -> None:
    """Atomically write *data* to *path*.  See :func:`atomic_write_text`."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


__all__ = ["atomic_write_bytes", "atomic_write_text"]
