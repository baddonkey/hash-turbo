"""Tests for ``hash_turbo.core.path_key``."""

from __future__ import annotations

from hash_turbo.core.path_key import normalize_path_key


class TestNormalizePathKey:
    def test_backslashes_become_forward_slashes(self) -> None:
        assert normalize_path_key("foo\\bar\\baz") == "foo/bar/baz"

    def test_dot_slash_prefix_is_stripped(self) -> None:
        assert normalize_path_key("./foo/bar") == "foo/bar"

    def test_case_is_folded(self) -> None:
        assert normalize_path_key("Foo/Bar") == normalize_path_key("foo/BAR")

    def test_empty_string_round_trips(self) -> None:
        assert normalize_path_key("") == ""

    def test_already_normalized_is_unchanged(self) -> None:
        assert normalize_path_key("foo/bar") == "foo/bar"
