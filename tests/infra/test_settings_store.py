"""Tests for SettingsStore — JSON-backed cross-platform settings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hash_turbo.infra.settings_store import SettingsStore


@pytest.fixture()
def settings_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


@pytest.fixture()
def store(settings_path: Path) -> SettingsStore:
    return SettingsStore(path=settings_path)


class TestSettingsStore:
    """Unit tests for SettingsStore."""

    def test_value_missing_key_returns_default(self, store: SettingsStore) -> None:
        assert store.value("nonexistent", "fallback") == "fallback"

    def test_value_missing_key_returns_none_by_default(self, store: SettingsStore) -> None:
        assert store.value("nonexistent") is None

    def test_set_value_persists_to_disk(self, settings_path: Path) -> None:
        # Arrange
        store = SettingsStore(path=settings_path)

        # Act
        store.set_value("theme", "dark")

        # Assert — read raw JSON to verify persistence
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["theme"] == "dark"

    def test_set_value_readable_after_reload(self, settings_path: Path) -> None:
        # Arrange
        store = SettingsStore(path=settings_path)
        store.set_value("theme", "dark")

        # Act — fresh instance reads from disk
        reloaded = SettingsStore(path=settings_path)

        # Assert
        assert reloaded.value("theme") == "dark"

    def test_contains_returns_true_for_existing_key(self, store: SettingsStore) -> None:
        store.set_value("algo", "sha256")
        assert store.contains("algo") is True

    def test_contains_returns_false_for_missing_key(self, store: SettingsStore) -> None:
        assert store.contains("missing") is False

    def test_set_value_overwrites_existing(self, store: SettingsStore) -> None:
        store.set_value("theme", "light")
        store.set_value("theme", "dark")
        assert store.value("theme") == "dark"

    def test_multiple_keys_persist_independently(self, settings_path: Path) -> None:
        # Arrange
        store = SettingsStore(path=settings_path)
        store.set_value("theme", "dark")
        store.set_value("language", "de")

        # Act
        reloaded = SettingsStore(path=settings_path)

        # Assert
        assert reloaded.value("theme") == "dark"
        assert reloaded.value("language") == "de"

    def test_load_ignores_corrupt_json(self, settings_path: Path) -> None:
        # Arrange
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("{corrupt", encoding="utf-8")

        # Act
        store = SettingsStore(path=settings_path)

        # Assert — falls back to empty
        assert store.value("anything") is None

    def test_load_ignores_non_dict_json(self, settings_path: Path) -> None:
        # Arrange
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("[1, 2, 3]", encoding="utf-8")

        # Act
        store = SettingsStore(path=settings_path)

        # Assert
        assert store.value("anything") is None

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        # Arrange
        deep_path = tmp_path / "a" / "b" / "c" / "settings.json"
        store = SettingsStore(path=deep_path)

        # Act
        store.set_value("key", "value")

        # Assert
        assert deep_path.exists()
        assert store.value("key") == "value"

    def test_path_property_returns_configured_path(self, settings_path: Path) -> None:
        store = SettingsStore(path=settings_path)
        assert store.path == settings_path
