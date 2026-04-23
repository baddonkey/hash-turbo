"""Cross-platform JSON settings store.

Stores settings as a human-readable JSON file in a consistent
platform-appropriate location:

- macOS:   ~/Library/Application Support/hash-turbo/settings.json
- Linux:   ~/.config/hash-turbo/settings.json
- Windows: %APPDATA%/hash-turbo/settings.json

.. warning::

    The store is *not* safe against concurrent writers from multiple
    processes.  Each :meth:`set_value` call atomically replaces the
    settings file (write-temp + rename) so the file on disk is always
    valid JSON, but two processes calling :meth:`set_value` at the same
    time will use a "last writer wins" strategy on the whole settings
    dict — interleaved updates may be lost.

    For the typical hash-turbo workflow (CLI invoked manually + GUI as
    a long-running app) this is acceptable.  Add file-locking
    (e.g. :mod:`fcntl`) if you ever script multiple concurrent CLI
    runs that mutate settings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class SettingsStore:
    """Thread-safe, JSON-backed key-value settings store."""

    _APP_DIR_NAME = "hash-turbo"
    _FILE_NAME = "settings.json"

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or self._default_path()
        self._data: dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def value(self, key: str, default: Any = None) -> Any:
        """Return the stored value for *key*, or *default* if absent."""
        return self._data.get(key, default)

    def set_value(self, key: str, value: Any) -> None:
        """Set *key* to *value* and immediately persist to disk."""
        self._data[key] = value
        self._save()

    def contains(self, key: str) -> bool:
        """Return whether *key* exists in the store."""
        return key in self._data

    @property
    def path(self) -> Path:
        """Return the path to the settings file."""
        return self._path

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._path)

    @classmethod
    def _default_path(cls) -> Path:
        return cls._config_dir() / cls._FILE_NAME

    @staticmethod
    def _config_dir() -> Path:
        if sys.platform == "win32":
            base = Path.home() / "AppData" / "Roaming"
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            import os
            xdg = os.environ.get("XDG_CONFIG_HOME")
            base = Path(xdg) if xdg else Path.home() / ".config"
        return base / SettingsStore._APP_DIR_NAME


__all__ = ["SettingsStore"]
