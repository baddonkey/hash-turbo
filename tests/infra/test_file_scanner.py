"""Tests for infra.file_scanner — directory walking and filtering."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from hash_turbo.core.exclude_filter import ExcludeFilter
from hash_turbo.infra.file_scanner import FileScanner


class TestScanPathsRecursiveDepth:
    """Verify recursive scanning across multiple directory levels."""

    def test_recursive_finds_files_in_subfolders(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Arrange
        sample_file_factory("root.txt", "r")
        sample_file_factory("a/child.txt", "c")
        sample_file_factory("a/b/grandchild.txt", "g")

        # Act
        result = FileScanner.scan_paths([tmp_path], recursive=True)

        # Assert
        names = {p.name for p in result}
        assert names == {"root.txt", "child.txt", "grandchild.txt"}

    def test_recursive_finds_files_in_sub_subfolders(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Arrange
        sample_file_factory("l1/l2/l3/deep.txt", "d")
        sample_file_factory("l1/l2/l3/l4/deeper.txt", "dd")

        # Act
        result = FileScanner.scan_paths([tmp_path], recursive=True)

        # Assert
        names = {p.name for p in result}
        assert names == {"deep.txt", "deeper.txt"}

    def test_non_recursive_ignores_all_subfolders(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Arrange
        sample_file_factory("top.txt", "t")
        sample_file_factory("a/child.txt", "c")
        sample_file_factory("a/b/grandchild.txt", "g")
        sample_file_factory("a/b/c/deep.txt", "d")

        # Act
        result = FileScanner.scan_paths([tmp_path], recursive=False)

        # Assert
        assert len(result) == 1
        assert result[0].name == "top.txt"

    def test_recursive_with_exclude_filter_across_levels(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Arrange
        sample_file_factory("a/keep.txt", "k")
        sample_file_factory("a/b/.DS_Store", "ds")
        sample_file_factory("a/b/c/data.csv", "d")
        sample_file_factory("a/b/c/Thumbs.db", "t")

        ef = ExcludeFilter([r"re:^\..*", "Thumbs.db"])

        # Act
        result = FileScanner.scan_paths([tmp_path], recursive=True, exclude_filter=ef)

        # Assert
        names = {p.name for p in result}
        assert names == {"keep.txt", "data.csv"}

    def test_recursive_with_glob_across_levels(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Arrange
        sample_file_factory("root.py", "pass")
        sample_file_factory("src/app.py", "pass")
        sample_file_factory("src/utils/helper.py", "pass")
        sample_file_factory("src/utils/readme.md", "# hi")
        sample_file_factory("src/utils/sub/deep.py", "pass")

        # Act
        result = FileScanner.scan_paths([tmp_path], recursive=True, glob_pattern="*.py")

        # Assert
        names = {p.name for p in result}
        assert names == {"root.py", "app.py", "helper.py", "deep.py"}

    def test_recursive_preserves_full_paths(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Arrange
        sample_file_factory("a/b/c/nested.txt", "n")

        # Act
        result = FileScanner.scan_paths([tmp_path], recursive=True)

        # Assert
        assert len(result) == 1
        assert result[0] == tmp_path / "a" / "b" / "c" / "nested.txt"


class TestScanPaths:
    def test_scan_single_file(self, sample_file: Path) -> None:
        result = FileScanner.scan_paths([sample_file])
        assert result == [sample_file]

    def test_scan_flat_directory(self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path) -> None:
        sample_file_factory("a.txt", "aaa")
        sample_file_factory("b.txt", "bbb")
        result = FileScanner.scan_paths([tmp_path])
        assert len(result) == 2
        assert all(p.name in ("a.txt", "b.txt") for p in result)

    def test_scan_directory_non_recursive_skips_subdirs(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("top.txt", "top")
        sample_file_factory("sub/nested.txt", "nested")
        result = FileScanner.scan_paths([tmp_path], recursive=False)
        assert len(result) == 1
        assert result[0].name == "top.txt"

    def test_scan_directory_recursive(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("top.txt", "top")
        sample_file_factory("sub/nested.txt", "nested")
        result = FileScanner.scan_paths([tmp_path], recursive=True)
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"top.txt", "nested.txt"}

    def test_scan_with_glob_filter(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("code.py", "print()")
        sample_file_factory("readme.md", "# hi")
        result = FileScanner.scan_paths([tmp_path], glob_pattern="*.py")
        assert len(result) == 1
        assert result[0].name == "code.py"

    def test_scan_with_exclude(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("keep.txt", "keep")
        sample_file_factory("skip.log", "skip")
        result = FileScanner.scan_paths([tmp_path], exclude="*.log")
        assert len(result) == 1
        assert result[0].name == "keep.txt"

    def test_scan_nonexistent_path_ignored(self, tmp_path: Path) -> None:
        fake = tmp_path / "does_not_exist.txt"
        result = FileScanner.scan_paths([fake])
        assert result == []

    def test_scan_deduplicates(self, sample_file: Path) -> None:
        result = FileScanner.scan_paths([sample_file, sample_file])
        assert len(result) == 1

    def test_scan_returns_sorted(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("z.txt", "z")
        sample_file_factory("a.txt", "a")
        result = FileScanner.scan_paths([tmp_path])
        assert result == sorted(result)

    def test_recursive_walk_returns_sorted_files_before_subdirs(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        # Arrange — files and dirs at each level in non-alphabetical creation order
        sample_file_factory("zebra.txt", "z")
        sample_file_factory("alpha.txt", "a")
        sample_file_factory("sub_b/beta.txt", "b")
        sample_file_factory("sub_a/gamma.txt", "g")
        sample_file_factory("sub_a/deep/delta.txt", "d")

        # Act
        result = FileScanner.scan_paths([tmp_path], recursive=True)
        names = [p.name for p in result]

        # Assert — root files sorted first, then sub_a (sorted), then sub_b
        assert names == ["alpha.txt", "zebra.txt", "gamma.txt", "delta.txt", "beta.txt"]

    def test_scan_with_exclude_filter(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("photo.jpg", "img")
        sample_file_factory("Thumbs.db", "thumb")
        sample_file_factory(".hidden", "secret")

        ef = ExcludeFilter(["Thumbs.db", r"re:^\..*"])
        result = FileScanner.scan_paths([tmp_path], exclude_filter=ef)

        names = {p.name for p in result}
        assert names == {"photo.jpg"}

    def test_scan_exclude_filter_applies_during_recursive_walk(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        sample_file_factory("sub/.DS_Store", "ds")
        sample_file_factory("sub/data.csv", "data")

        ef = ExcludeFilter([r"re:^\..*"])
        result = FileScanner.scan_paths([tmp_path], recursive=True, exclude_filter=ef)

        names = {p.name for p in result}
        assert names == {"data.csv"}

    def test_scan_with_exclude_paths(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        a = sample_file_factory("a.txt", "aaa")
        b = sample_file_factory("b.txt", "bbb")
        sample_file_factory("c.txt", "ccc")

        result = FileScanner.scan_paths([tmp_path], exclude_paths=[a, b])
        names = {p.name for p in result}
        assert names == {"c.txt"}

    def test_scan_cancel_returns_partial(
        self, sample_file_factory: Callable[[str, str], Path], tmp_path: Path
    ) -> None:
        import threading

        for i in range(20):
            sample_file_factory(f"f{i:02d}.txt", f"c{i}")

        cancel = threading.Event()
        cancel.set()  # Cancel immediately

        result = FileScanner.scan_paths(
            [tmp_path], recursive=True, cancel_event=cancel,
        )
        assert len(result) < 20
