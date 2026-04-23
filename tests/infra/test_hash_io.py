"""Tests for infra.hash_io — file I/O adapter for the core hasher."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from hash_turbo.core.hasher import Hasher
from hash_turbo.core.models import Algorithm
from hash_turbo.infra.hash_io import hash_file


class TestHashFileErrorPaths:
    def test_hash_file_not_found_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.txt"

        with pytest.raises(FileNotFoundError):
            hash_file(Hasher(), missing, Algorithm.SHA256)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission model")
    def test_hash_file_permission_error_raises(self, tmp_path: Path) -> None:
        # Arrange — create a file then remove read permission
        locked = tmp_path / "locked.txt"
        locked.write_text("secret")
        locked.chmod(0o000)

        # Act / Assert
        try:
            with pytest.raises(PermissionError):
                hash_file(Hasher(), locked, Algorithm.SHA256)
        finally:
            locked.chmod(0o644)

    def test_hash_file_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises((IsADirectoryError, PermissionError)):
            hash_file(Hasher(), tmp_path, Algorithm.SHA256)
