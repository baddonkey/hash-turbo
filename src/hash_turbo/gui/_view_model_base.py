"""Common base for QML view models.

Centralises the boilerplate shared between the Hash, Verify, and
Sanitize view models — most notably the change-tracked property setter
(``_set_prop``) and the rolling log appender (``_append_log``).
"""

from __future__ import annotations

from typing import TypeVar

from PySide6.QtCore import QObject, Signal

T = TypeVar("T")


class ViewModelBase(QObject):
    """Base class for QML-bound view models.

    Provides:

    * :meth:`_set_prop` — assigns *value* to ``self.<attr>`` and emits
      *signal* only when the value actually changes.  ``hasattr`` is
      checked once during development to catch typos in attribute names.
    * :meth:`_append_log` — appends a line to ``self._log_text`` and
      emits ``self.log_text_changed``.  Subclasses must declare both.
    """

    def _set_prop(self, attr: str, value: T, signal: Signal) -> None:
        if not hasattr(self, attr):  # defensive — catches typos at runtime
            raise AttributeError(f"No attribute {attr!r} on {type(self).__name__}")
        if getattr(self, attr) != value:
            setattr(self, attr, value)
            signal.emit()

    def _append_log(self, text: str) -> None:
        current = getattr(self, "_log_text", "")
        new_value = (current + "\n" + text).lstrip("\n")
        setattr(self, "_log_text", new_value)
        signal = getattr(self, "log_text_changed", None)
        if signal is not None:
            signal.emit()


__all__ = ["ViewModelBase"]
