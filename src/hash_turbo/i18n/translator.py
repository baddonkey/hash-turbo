"""Translator — gettext wrapper with runtime language switching."""

from __future__ import annotations

import gettext
import logging
from pathlib import Path
from typing import Sequence

from hash_turbo.infra.settings_store import SettingsStore

_log = logging.getLogger(__name__)

_DOMAIN = "hash_turbo"
_LOCALES_DIR = Path(__file__).parent / "locales"

# Language code -> display name (shown in the Settings combo box).
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "rm": "Rumantsch",
}


class Translator:
    """Loads gettext translations and exposes a switchable ``gettext`` callable.

    The constructor accepts an optional :class:`SettingsStore` so tests
    (and embedders) can avoid touching the real on-disk settings file.
    Pass ``settings=None`` to skip persistence entirely — useful in
    pure unit tests where you only want in-memory language switching.
    """

    def __init__(self, settings: SettingsStore | None | object = ...) -> None:
        # Sentinel ``...`` means "use the default SettingsStore".
        # Explicit ``None`` means "no persistence at all".
        if settings is ...:
            self._settings: SettingsStore | None = SettingsStore()
        else:
            self._settings = settings  # type: ignore[assignment]
        self._lang: str = "en"
        self._gt: gettext.GNUTranslations | gettext.NullTranslations = gettext.NullTranslations()
        self._load_saved_language()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def gettext(self, message: str) -> str:
        """Translate *message* using the active language."""
        return self._gt.gettext(message)

    def set_language(self, lang: str) -> None:
        """Switch the active language and persist the choice."""
        self._apply_language(lang)
        if self._settings is not None:
            self._settings.set_value("language", lang)

    def apply_language(self, lang: str) -> None:
        """Switch the active language **without** persisting."""
        self._apply_language(lang)

    def current_language(self) -> str:
        """Return the active language code (e.g. ``'de'``)."""
        return self._lang

    @staticmethod
    def available_languages() -> Sequence[tuple[str, str]]:
        """Return ``(code, display_name)`` pairs for all supported languages."""
        return list(LANGUAGE_NAMES.items())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_language(self, lang: str) -> None:
        """Set the runtime language without persisting."""
        self._lang = lang
        self._gt = self._load(lang)

    def _load_saved_language(self) -> None:
        if self._settings is None:
            self._apply_language("en")
            return
        lang = str(self._settings.value("language", "en"))
        self._apply_language(lang)

    @staticmethod
    def _load(lang: str) -> gettext.GNUTranslations | gettext.NullTranslations:
        """Load the ``.mo`` file for *lang*, falling back to NullTranslations."""
        try:
            return gettext.translation(
                _DOMAIN,
                localedir=str(_LOCALES_DIR),
                languages=[lang],
            )
        except FileNotFoundError:
            return gettext.NullTranslations()


__all__ = ["Translator"]
