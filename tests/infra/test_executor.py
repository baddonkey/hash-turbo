"""Tests for infra.executor — parallel file hashing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from hash_turbo.core.models import Algorithm, HashResult
from hash_turbo.infra.executor import HashExecutor


class TestHashFiles:
    def test_hash_single_file(self, sample_file: Path) -> None:
        executor = HashExecutor()
        results = executor.hash_files([sample_file], Algorithm.SHA256)
        assert len(results) == 1
        assert results[0].algorithm is Algorithm.SHA256
        assert len(results[0].hex_digest) == 64

    def test_hash_multiple_files(
        self, sample_file_factory: Callable[[str, str], Path]
    ) -> None:
        executor = HashExecutor()
        f1 = sample_file_factory("a.txt", "aaa")
        f2 = sample_file_factory("b.txt", "bbb")
        results = executor.hash_files([f1, f2], Algorithm.SHA256)
        assert len(results) == 2
        assert results[0].hex_digest != results[1].hex_digest

    def test_hash_preserves_input_order(
        self, sample_file_factory: Callable[[str, str], Path]
    ) -> None:
        executor = HashExecutor()
        files = [sample_file_factory(f"file{i}.txt", f"content{i}") for i in range(5)]
        results = executor.hash_files(files, Algorithm.SHA256)
        assert [r.path for r in results] == [str(f) for f in files]

    def test_hash_sequential_with_jobs_1(self, sample_file: Path) -> None:
        executor = HashExecutor()
        results = executor.hash_files([sample_file], Algorithm.SHA256, jobs=1)
        assert len(results) == 1

    def test_hash_progress_callback_invoked(
        self, sample_file_factory: Callable[[str, str], Path]
    ) -> None:
        executor = HashExecutor()
        f1 = sample_file_factory("a.txt", "aaa")
        f2 = sample_file_factory("b.txt", "bbb")
        progress: list[HashResult] = []
        executor.hash_files([f1, f2], Algorithm.SHA256, on_progress=progress.append)
        assert len(progress) == 2

    def test_hash_empty_paths(self) -> None:
        executor = HashExecutor()
        results = executor.hash_files([], Algorithm.SHA256)
        assert results == []

    def test_hash_with_md5(self, sample_file: Path) -> None:
        executor = HashExecutor()
        results = executor.hash_files([sample_file], Algorithm.MD5)
        assert results[0].algorithm is Algorithm.MD5
        assert len(results[0].hex_digest) == 32

    def test_hash_cancel_returns_partial_results(
        self, sample_file_factory: Callable[[str, str], Path]
    ) -> None:
        import threading

        cancel = threading.Event()
        cancel.set()  # Cancel immediately
        executor = HashExecutor()
        files = [sample_file_factory(f"f{i}.txt", f"c{i}") for i in range(10)]
        results = executor.hash_files(files, Algorithm.SHA256, cancel_event=cancel)
        assert len(results) < len(files)

    def test_hash_missing_file_skipped(
        self, sample_file: Path, tmp_path: Path
    ) -> None:
        missing = tmp_path / "ghost.txt"
        executor = HashExecutor()
        results = executor.hash_files([sample_file, missing], Algorithm.SHA256)
        assert len(results) == 1
        assert results[0].path == str(sample_file)
