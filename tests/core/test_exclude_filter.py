"""Tests for core.exclude_filter — fnmatch and regex exclusion."""

from __future__ import annotations

from hash_turbo.core.exclude_filter import ExcludeFilter


class TestExcludeFilter:
    def test_empty_patterns_excludes_nothing(self) -> None:
        ef = ExcludeFilter([])
        assert ef.is_empty
        assert not ef.is_excluded("anything.txt")

    def test_fnmatch_exact_name(self) -> None:
        import sys

        ef = ExcludeFilter(["Thumbs.db"])
        assert ef.is_excluded("Thumbs.db")
        if sys.platform != "win32":
            # fnmatch is case-sensitive on POSIX, case-insensitive on Windows
            assert not ef.is_excluded("thumbs.db")
        assert not ef.is_excluded("photo.jpg")

    def test_fnmatch_wildcard(self) -> None:
        ef = ExcludeFilter(["*.log"])
        assert ef.is_excluded("debug.log")
        assert ef.is_excluded("app.log")
        assert not ef.is_excluded("app.txt")

    def test_regex_hidden_files(self) -> None:
        ef = ExcludeFilter([r"re:^\..*"])
        assert ef.is_excluded(".gitignore")
        assert ef.is_excluded(".DS_Store")
        assert not ef.is_excluded("readme.md")

    def test_mixed_patterns(self) -> None:
        ef = ExcludeFilter(["Thumbs.db", r"re:^\..+"])
        assert ef.is_excluded("Thumbs.db")
        assert ef.is_excluded(".hidden")
        assert not ef.is_excluded("photo.jpg")

    def test_blank_and_whitespace_lines_ignored(self) -> None:
        ef = ExcludeFilter(["", "  ", "Thumbs.db", "  "])
        assert not ef.is_empty
        assert ef.is_excluded("Thumbs.db")

    def test_is_empty_false_when_patterns_present(self) -> None:
        ef = ExcludeFilter(["*.tmp"])
        assert not ef.is_empty

    def test_default_patterns_available(self) -> None:
        defaults = ExcludeFilter.DEFAULT_PATTERNS
        assert len(defaults) >= 2
        ef = ExcludeFilter(defaults)
        assert ef.is_excluded("Thumbs.db")
        assert ef.is_excluded(".DS_Store")
        assert not ef.is_excluded("readme.md")

    def test_invalid_regex_pattern_skipped_gracefully(self) -> None:
        # Arrange — pattern with unbalanced parenthesis
        ef = ExcludeFilter(["re:(", "*.log"])

        # Assert — valid pattern still works, invalid one is skipped
        assert not ef.is_empty
        assert ef.is_excluded("app.log")
        assert not ef.is_excluded("(")
