"""Tests for ``hash_turbo.infra.atomic_write``."""

from __future__ import annotations

from pathlib import Path

from hash_turbo.infra.atomic_write import atomic_write_bytes, atomic_write_text


class TestAtomicWriteText:
    def test_creates_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"

        atomic_write_text(target, "hello\n")

        assert target.read_text() == "hello\n"

    def test_replaces_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("old")

        atomic_write_text(target, "new")

        assert target.read_text() == "new"

    def test_no_temp_file_left_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"

        atomic_write_text(target, "ok")

        leftovers = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []


class TestAtomicWriteBytes:
    def test_round_trips_binary_payload(self, tmp_path: Path) -> None:
        target = tmp_path / "out.bin"
        payload = b"\x00\x01\x02\xff"

        atomic_write_bytes(target, payload)

        assert target.read_bytes() == payload

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "file.bin"

        atomic_write_bytes(target, b"x")

        assert target.read_bytes() == b"x"
