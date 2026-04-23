"""Settings model — QML-compatible settings backend."""

from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from hash_turbo.core.exclude_filter import ExcludeFilter
from hash_turbo.core.models import Algorithm
from hash_turbo.i18n import available_languages, current_language, set_language
from hash_turbo.infra.settings_store import SettingsStore


class SettingsModel(QObject):
    """Exposes persistent settings as QML-bindable properties."""

    default_algorithm_changed = Signal()
    path_mode_changed = Signal()
    output_format_changed = Signal()
    theme_changed = Signal()
    language_changed = Signal()
    retranslate_requested = Signal()
    exclude_patterns_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = SettingsStore()
        self._default_algorithm = str(
            self._settings.value("default_algorithm", Algorithm.default().value)
        )
        self._path_mode = str(self._settings.value("path_mode", "relative"))
        self._output_format = str(self._settings.value("output_format", "gnu"))
        self._theme = str(self._settings.value("theme", "system"))
        self._language = current_language()
        default_text = "\n".join(ExcludeFilter.USER_DEFAULT_PATTERNS)
        self._exclude_patterns = str(
            self._settings.value("exclude_patterns", default_text)
        )

    # -- defaultAlgorithm ------------------------------------------------

    def _get_default_algorithm(self) -> str:
        return self._default_algorithm

    def _set_default_algorithm(self, value: str) -> None:
        if self._default_algorithm != value:
            self._default_algorithm = value
            self._settings.set_value("default_algorithm", value)
            self.default_algorithm_changed.emit()

    defaultAlgorithm = Property(  # noqa: N815
        str, _get_default_algorithm, _set_default_algorithm,
        notify=default_algorithm_changed,
    )

    # -- pathMode --------------------------------------------------------

    def _get_path_mode(self) -> str:
        return self._path_mode

    def _set_path_mode(self, value: str) -> None:
        if self._path_mode != value:
            self._path_mode = value
            self._settings.set_value("path_mode", value)
            self.path_mode_changed.emit()

    pathMode = Property(  # noqa: N815
        str, _get_path_mode, _set_path_mode, notify=path_mode_changed,
    )

    # -- outputFormat ----------------------------------------------------

    def _get_output_format(self) -> str:
        return self._output_format

    def _set_output_format(self, value: str) -> None:
        if self._output_format != value:
            self._output_format = value
            self._settings.set_value("output_format", value)
            self.output_format_changed.emit()

    outputFormat = Property(  # noqa: N815
        str, _get_output_format, _set_output_format, notify=output_format_changed,
    )

    # -- theme -----------------------------------------------------------

    def _get_theme(self) -> str:
        return self._theme

    def _set_theme(self, value: str) -> None:
        if self._theme != value:
            self._theme = value
            self._settings.set_value("theme", value)
            self.theme_changed.emit()

    theme = Property(str, _get_theme, _set_theme, notify=theme_changed)

    # -- language --------------------------------------------------------

    def _get_language(self) -> str:
        return self._language

    def _set_language(self, value: str) -> None:
        if self._language != value:
            self._language = value
            set_language(value)
            self.language_changed.emit()
            self.retranslate_requested.emit()

    language = Property(str, _get_language, _set_language, notify=language_changed)

    # -- excludePatterns -------------------------------------------------

    def _get_exclude_patterns(self) -> str:
        return self._exclude_patterns

    def _set_exclude_patterns(self, value: str) -> None:
        if self._exclude_patterns != value:
            self._exclude_patterns = value
            self._settings.set_value("exclude_patterns", value)
            self.exclude_patterns_changed.emit()

    excludePatterns = Property(  # noqa: N815
        str, _get_exclude_patterns, _set_exclude_patterns,
        notify=exclude_patterns_changed,
    )

    # -- constant lists --------------------------------------------------

    def _get_language_names(self) -> list[str]:
        return [name for _, name in available_languages()]

    def _get_language_codes(self) -> list[str]:
        return [code for code, _ in available_languages()]

    languageNames = Property("QVariantList", _get_language_names, constant=True)  # noqa: N815
    languageCodes = Property("QVariantList", _get_language_codes, constant=True)  # noqa: N815

    # -- static utility --------------------------------------------------

    @staticmethod
    def load_exclude_patterns() -> list[str]:
        """Read exclude patterns from persisted settings.

        The persisted value contains the *user-visible* patterns only;
        the internal hash-file extensions (``*.md5``, ``*.sha256`` …)
        are appended here so they are always excluded regardless of
        what the user keeps or removes.
        """
        store = SettingsStore()
        default_text = "\n".join(ExcludeFilter.USER_DEFAULT_PATTERNS)
        text = str(store.value("exclude_patterns", default_text))
        user_patterns = [line for line in text.splitlines() if line.strip()]
        return [*user_patterns, *ExcludeFilter.INTERNAL_HASH_EXTENSIONS]


__all__ = ["SettingsModel"]
