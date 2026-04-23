"""Tests for core.sanitizer — hash entry transformations."""

from __future__ import annotations

import pytest

from hash_turbo.core.models import Algorithm, HashEntry, HashFileFormat
from hash_turbo.core.sanitizer import (
    HashCase,
    LineEnding,
    PathSeparator,
    SanitizeOptions,
    Sanitizer,
    SortKey,
)


@pytest.fixture
def gnu_entries() -> list[HashEntry]:
    """Three GNU-style entries with mixed-case hashes and POSIX paths."""
    return [
        HashEntry(path="dir/bravo.txt", algorithm=Algorithm.SHA256, expected_hash="BBbb1234" * 8),
        HashEntry(path="dir/alpha.txt", algorithm=Algorithm.SHA256, expected_hash="AAaa5678" * 8),
        HashEntry(path="dir/charlie.txt", algorithm=Algorithm.SHA256, expected_hash="CCcc9012" * 8),
    ]


@pytest.fixture
def default_sanitizer() -> Sanitizer:
    """Sanitizer with all-default (keep-everything) options."""
    return Sanitizer(SanitizeOptions())


class TestSanitizerTransformIdentity:
    """When all options are 'keep' / defaults, transform is identity."""

    def test_transform_defaults_returns_same_entries(
        self, default_sanitizer: Sanitizer, gnu_entries: list[HashEntry],
    ) -> None:
        # Act
        result = default_sanitizer.transform(gnu_entries)

        # Assert
        assert result == gnu_entries


class TestNormalizeSeparators:
    def test_transform_posix_converts_backslashes(self) -> None:
        # Arrange
        entries = [HashEntry(path="dir\\sub\\file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(path_separator=PathSeparator.POSIX))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "dir/sub/file.txt"

    def test_transform_windows_converts_slashes(self) -> None:
        # Arrange
        entries = [HashEntry(path="dir/sub/file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(path_separator=PathSeparator.WINDOWS))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "dir\\sub\\file.txt"

    def test_transform_keep_preserves_original(self) -> None:
        # Arrange
        entries = [HashEntry(path="dir\\sub/file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(path_separator=PathSeparator.KEEP))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "dir\\sub/file.txt"


class TestStripPrefix:
    def test_transform_strip_prefix_removes_matching_prefix(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="/home/user/project/file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32),
            HashEntry(path="/home/user/project/sub/other.txt", algorithm=Algorithm.SHA256, expected_hash="cd" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(strip_prefix="/home/user/project"))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "file.txt"
        assert result[1].path == "sub/other.txt"

    def test_transform_strip_prefix_leaves_non_matching_paths(self) -> None:
        # Arrange
        entries = [HashEntry(path="other/file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(strip_prefix="/home/user"))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "other/file.txt"

    def test_transform_strip_prefix_with_trailing_slash(self) -> None:
        # Arrange
        entries = [HashEntry(path="/data/file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(strip_prefix="/data/"))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "file.txt"

    def test_transform_strip_prefix_exact_match_returns_dot(self) -> None:
        # Arrange
        entries = [HashEntry(path="/data", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(strip_prefix="/data"))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "."

    def test_transform_strip_prefix_normalizes_backslashes(self) -> None:
        # Arrange
        entries = [HashEntry(path="C:\\Users\\project\\file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(strip_prefix="C:\\Users\\project"))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "file.txt"


class TestNormalizeHashCase:
    def test_transform_lowercase_digests(self) -> None:
        # Arrange
        entries = [HashEntry(path="f.txt", algorithm=Algorithm.SHA256, expected_hash="AABB1234" * 8)]
        sanitizer = Sanitizer(SanitizeOptions(hash_case=HashCase.LOWER))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].expected_hash == ("aabb1234" * 8)

    def test_transform_uppercase_digests(self) -> None:
        # Arrange
        entries = [HashEntry(path="f.txt", algorithm=Algorithm.SHA256, expected_hash="aabb1234" * 8)]
        sanitizer = Sanitizer(SanitizeOptions(hash_case=HashCase.UPPER))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].expected_hash == ("AABB1234" * 8)

    def test_transform_keep_case_unchanged(self) -> None:
        # Arrange
        original_hash = "AaBb1234" * 8
        entries = [HashEntry(path="f.txt", algorithm=Algorithm.SHA256, expected_hash=original_hash)]
        sanitizer = Sanitizer(SanitizeOptions(hash_case=HashCase.KEEP))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].expected_hash == original_hash


class TestSort:
    def test_transform_sort_by_path(self, gnu_entries: list[HashEntry]) -> None:
        # Arrange
        sanitizer = Sanitizer(SanitizeOptions(sort_key=SortKey.PATH))

        # Act
        result = sanitizer.transform(gnu_entries)

        # Assert — alpha < bravo < charlie
        assert [e.path for e in result] == [
            "dir/alpha.txt",
            "dir/bravo.txt",
            "dir/charlie.txt",
        ]

    def test_transform_sort_by_hash(self, gnu_entries: list[HashEntry]) -> None:
        # Arrange
        sanitizer = Sanitizer(SanitizeOptions(sort_key=SortKey.HASH))

        # Act
        result = sanitizer.transform(gnu_entries)

        # Assert — AAaa < BBbb < CCcc
        assert result[0].expected_hash.startswith("AAaa")
        assert result[1].expected_hash.startswith("BBbb")
        assert result[2].expected_hash.startswith("CCcc")

    def test_transform_sort_none_preserves_order(self, gnu_entries: list[HashEntry]) -> None:
        # Arrange
        sanitizer = Sanitizer(SanitizeOptions(sort_key=SortKey.NONE))

        # Act
        result = sanitizer.transform(gnu_entries)

        # Assert — original order preserved (bravo, alpha, charlie)
        assert [e.path for e in result] == [
            "dir/bravo.txt",
            "dir/alpha.txt",
            "dir/charlie.txt",
        ]

    def test_transform_sort_filesystem_groups_by_directory(self) -> None:
        # Arrange — entries deliberately scrambled across directories
        entries = [
            HashEntry(path="z_root.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="sub/beta.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
            HashEntry(path="a_root.txt", algorithm=Algorithm.SHA256, expected_hash="cc" * 32),
            HashEntry(path="sub/alpha.txt", algorithm=Algorithm.SHA256, expected_hash="dd" * 32),
            HashEntry(path="sub/deep/file.txt", algorithm=Algorithm.SHA256, expected_hash="ee" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(sort_key=SortKey.FILESYSTEM))

        # Act
        result = sanitizer.transform(entries)

        # Assert — root files first (sorted), then sub/ files, then sub/deep/
        assert [e.path for e in result] == [
            "a_root.txt",
            "z_root.txt",
            "sub/alpha.txt",
            "sub/beta.txt",
            "sub/deep/file.txt",
        ]

    def test_transform_sort_filesystem_handles_backslashes(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="dir\\bravo.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="dir\\alpha.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
            HashEntry(path="other.txt", algorithm=Algorithm.SHA256, expected_hash="cc" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(sort_key=SortKey.FILESYSTEM))

        # Act
        result = sanitizer.transform(entries)

        # Assert — root first, then dir/ alphabetically
        assert [e.path for e in result] == [
            "other.txt",
            "dir\\alpha.txt",
            "dir\\bravo.txt",
        ]

    def test_transform_sort_filesystem_case_insensitive(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="DIR/Bravo.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="dir/alpha.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(sort_key=SortKey.FILESYSTEM))

        # Act
        result = sanitizer.transform(entries)

        # Assert — alpha before Bravo, case-insensitive
        assert [e.path for e in result] == [
            "dir/alpha.txt",
            "DIR/Bravo.txt",
        ]


class TestDeduplicate:
    def test_transform_deduplicate_removes_duplicates(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
            HashEntry(path="other.txt", algorithm=Algorithm.SHA256, expected_hash="cc" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(deduplicate=True))

        # Act
        result = sanitizer.transform(entries)

        # Assert — first occurrence kept
        assert len(result) == 2
        assert result[0].expected_hash == "aa" * 32
        assert result[1].path == "other.txt"

    def test_transform_deduplicate_case_insensitive_paths(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="File.TXT", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(deduplicate=True))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert len(result) == 1
        assert result[0].path == "File.TXT"

    def test_transform_deduplicate_normalizes_separators(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="dir/file.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="dir\\file.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(deduplicate=True))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert len(result) == 1


class TestFormat:
    def test_format_gnu(self) -> None:
        # Arrange
        entries = [HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(output_format=HashFileFormat.GNU, line_ending=LineEnding.LF))

        # Act
        output = sanitizer.format(entries)

        # Assert
        assert output == f"{'ab' * 32} *file.txt\n"

    def test_format_bsd(self) -> None:
        # Arrange
        entries = [HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(output_format=HashFileFormat.BSD, line_ending=LineEnding.LF))

        # Act
        output = sanitizer.format(entries)

        # Assert
        assert output == f"SHA256 (file.txt) = {'ab' * 32}\n"

    def test_format_gnu_respects_binary_mode_flag(self) -> None:
        # Arrange — text-mode entry (binary_mode=False)
        entries = [
            HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32, binary_mode=False),
        ]
        sanitizer = Sanitizer(SanitizeOptions(output_format=HashFileFormat.GNU, line_ending=LineEnding.LF))

        # Act
        output = sanitizer.format(entries)

        # Assert — text mode uses space, not asterisk
        assert output == f"{'ab' * 32}  file.txt\n"

    def test_format_gnu_binary_mode_uses_asterisk(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32, binary_mode=True),
        ]
        sanitizer = Sanitizer(SanitizeOptions(output_format=HashFileFormat.GNU, line_ending=LineEnding.LF))

        # Act
        output = sanitizer.format(entries)

        # Assert
        assert output == f"{'ab' * 32} *file.txt\n"

    def test_format_empty_entries_returns_empty_string(self) -> None:
        # Arrange
        sanitizer = Sanitizer(SanitizeOptions())

        # Act
        output = sanitizer.format([])

        # Assert
        assert output == ""

    def test_format_multiple_entries(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="a.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="b.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(output_format=HashFileFormat.GNU, line_ending=LineEnding.LF))

        # Act
        output = sanitizer.format(entries)

        # Assert
        lines = output.rstrip("\n").split("\n")
        assert len(lines) == 2
        assert "a.txt" in lines[0]
        assert "b.txt" in lines[1]


class TestCombinedTransforms:
    """Verify that multiple transforms compose correctly."""

    def test_transform_strip_prefix_then_posix_separators(self) -> None:
        # Arrange
        entries = [
            HashEntry(
                path="C:\\Users\\project\\sub\\file.txt",
                algorithm=Algorithm.SHA256,
                expected_hash="ab" * 32,
            ),
        ]
        sanitizer = Sanitizer(SanitizeOptions(
            strip_prefix="C:\\Users\\project",
            path_separator=PathSeparator.POSIX,
        ))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].path == "sub/file.txt"

    def test_transform_all_options_together(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="/data/b.txt", algorithm=Algorithm.SHA256, expected_hash="BB" * 32),
            HashEntry(path="/data/a.txt", algorithm=Algorithm.SHA256, expected_hash="AA" * 32),
            HashEntry(path="/data/a.txt", algorithm=Algorithm.SHA256, expected_hash="CC" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(
            strip_prefix="/data",
            path_separator=PathSeparator.POSIX,
            hash_case=HashCase.LOWER,
            sort_key=SortKey.PATH,
            deduplicate=True,
        ))

        # Act
        result = sanitizer.transform(entries)

        # Assert — deduplicated (2 entries), sorted by path, lowercase hashes
        assert len(result) == 2
        assert result[0].path == "a.txt"
        assert result[0].expected_hash == "aa" * 32
        assert result[1].path == "b.txt"
        assert result[1].expected_hash == "bb" * 32


class TestBinaryModePreservation:
    """Transforms must propagate binary_mode through entry reconstruction."""

    def test_transform_normalize_separators_preserves_text_mode(self) -> None:
        # Arrange
        entries = [HashEntry(path="dir\\file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32, binary_mode=False)]
        sanitizer = Sanitizer(SanitizeOptions(path_separator=PathSeparator.POSIX))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].binary_mode is False

    def test_transform_strip_prefix_preserves_text_mode(self) -> None:
        # Arrange
        entries = [HashEntry(path="/data/file.txt", algorithm=Algorithm.SHA256, expected_hash="ab" * 32, binary_mode=False)]
        sanitizer = Sanitizer(SanitizeOptions(strip_prefix="/data"))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].binary_mode is False

    def test_transform_hash_case_preserves_text_mode(self) -> None:
        # Arrange
        entries = [HashEntry(path="file.txt", algorithm=Algorithm.SHA256, expected_hash="AB" * 32, binary_mode=False)]
        sanitizer = Sanitizer(SanitizeOptions(hash_case=HashCase.LOWER))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert result[0].binary_mode is False

    def test_transform_all_options_preserves_text_mode(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="/data/b.txt", algorithm=Algorithm.SHA256, expected_hash="BB" * 32, binary_mode=False),
            HashEntry(path="/data/a.txt", algorithm=Algorithm.SHA256, expected_hash="AA" * 32, binary_mode=False),
        ]
        sanitizer = Sanitizer(SanitizeOptions(
            strip_prefix="/data",
            path_separator=PathSeparator.POSIX,
            hash_case=HashCase.LOWER,
            sort_key=SortKey.PATH,
        ))

        # Act
        result = sanitizer.transform(entries)

        # Assert
        assert all(e.binary_mode is False for e in result)


class TestLineEnding:
    def test_format_lf_line_endings(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="a.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="b.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(line_ending=LineEnding.LF))

        # Act
        output = sanitizer.format(entries)

        # Assert
        assert "\r" not in output
        assert output.count("\n") == 2

    def test_format_crlf_line_endings(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="a.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="b.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(line_ending=LineEnding.CRLF))

        # Act
        output = sanitizer.format(entries)

        # Assert
        assert output.count("\r\n") == 2

    def test_format_cr_line_endings(self) -> None:
        # Arrange
        entries = [
            HashEntry(path="a.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32),
            HashEntry(path="b.txt", algorithm=Algorithm.SHA256, expected_hash="bb" * 32),
        ]
        sanitizer = Sanitizer(SanitizeOptions(line_ending=LineEnding.CR))

        # Act
        output = sanitizer.format(entries)

        # Assert
        assert "\n" not in output
        assert output.count("\r") == 2

    def test_format_system_uses_os_linesep(self) -> None:
        # Arrange
        import os
        entries = [HashEntry(path="a.txt", algorithm=Algorithm.SHA256, expected_hash="aa" * 32)]
        sanitizer = Sanitizer(SanitizeOptions(line_ending=LineEnding.SYSTEM))

        # Act
        output = sanitizer.format(entries)

        # Assert
        assert output.endswith(os.linesep)

    def test_format_empty_entries_ignores_line_ending(self) -> None:
        # Arrange
        sanitizer = Sanitizer(SanitizeOptions(line_ending=LineEnding.CRLF))

        # Act
        output = sanitizer.format([])

        # Assert
        assert output == ""
