"""Tests for i18n.translator — language switching and config persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from hash_turbo.i18n.translator import Translator
from hash_turbo.infra.settings_store import SettingsStore


class TestTranslator:
    def test_default_language_is_english(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "settings.json"
        monkeypatch.setattr(
            SettingsStore, "_default_path", classmethod(lambda cls: config_file),
        )
        t = Translator()
        assert t.current_language() == "en"

    def test_set_language_changes_current(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Point config to tmp_path so we don't pollute real settings
        config_file = tmp_path / "settings.json"
        monkeypatch.setattr(
            SettingsStore, "_default_path", classmethod(lambda cls: config_file),
        )
        t = Translator()
        t.set_language("de")
        assert t.current_language() == "de"

    def test_apply_language_does_not_persist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "settings.json"
        monkeypatch.setattr(
            SettingsStore, "_default_path", classmethod(lambda cls: config_file),
        )
        t = Translator()
        t.apply_language("fr")
        assert t.current_language() == "fr"
        assert not config_file.exists()

    def test_set_language_persists_to_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import json

        config_file = tmp_path / "settings.json"
        monkeypatch.setattr(
            SettingsStore, "_default_path", classmethod(lambda cls: config_file),
        )
        t = Translator()
        t.set_language("it")
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert data["language"] == "it"

    def test_available_languages_returns_all(self) -> None:
        langs = Translator.available_languages()
        codes = [code for code, _ in langs]
        assert "en" in codes
        assert "de" in codes
        assert len(langs) >= 2

    def test_gettext_returns_string(self) -> None:
        t = Translator()
        result = t.gettext("anything")
        assert isinstance(result, str)

    def test_unknown_language_falls_back(self) -> None:
        t = Translator()
        t.apply_language("xx")
        assert t.current_language() == "xx"
        # NullTranslations returns the source string unchanged
        assert t.gettext("hello") == "hello"
