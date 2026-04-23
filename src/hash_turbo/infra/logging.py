"""Application-wide logging configuration."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MiB
_BACKUP_COUNT = 1


class LoggingSetup:
    """Configures the root ``hash_turbo`` logger.

    By default — i.e. CLI invocations — only a stderr handler at
    ``WARNING`` is installed; nothing is written to disk.  GUI sessions
    (and explicit ``--log-file`` opt-ins from the CLI) get the rotating
    file handler in addition.
    """

    @staticmethod
    def configure(
        *,
        level: int = logging.WARNING,
        file_logging: bool = False,
        log_path: Path | None = None,
    ) -> Path | None:
        """Set up logging and return the log file path (or ``None``).

        :param level: Threshold for the stderr handler.
        :param file_logging: When True, also install a rotating file
            handler at ``DEBUG``.  GUI mode passes ``True``.
        :param log_path: Override the default log location.
        """
        root = logging.getLogger("hash_turbo")
        root.setLevel(min(level, logging.DEBUG) if file_logging else level)

        # Avoid duplicate handlers on repeated calls — but do refresh
        # the stderr handler's level so verbosity flags take effect even
        # when configure() is called twice in the same process.
        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

        existing_stream = next(
            (h for h in root.handlers if isinstance(h, logging.StreamHandler)
             and not isinstance(h, RotatingFileHandler)),
            None,
        )
        if existing_stream is None:
            sh = logging.StreamHandler(sys.stderr)
            sh.setFormatter(formatter)
            root.addHandler(sh)
            existing_stream = sh
        existing_stream.setLevel(level)

        resolved_path: Path | None = None
        if file_logging:
            resolved_path = log_path or LoggingSetup._default_log_path()
            existing_file = next(
                (h for h in root.handlers if isinstance(h, RotatingFileHandler)),
                None,
            )
            if existing_file is None:
                resolved_path.parent.mkdir(parents=True, exist_ok=True)
                fh = RotatingFileHandler(
                    resolved_path,
                    maxBytes=_MAX_LOG_BYTES,
                    backupCount=_BACKUP_COUNT,
                    encoding="utf-8",
                )
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(formatter)
                root.addHandler(fh)

        return resolved_path

    @staticmethod
    def _default_log_path() -> Path:
        return LoggingSetup._log_directory() / "hash-turbo.log"

    @staticmethod
    def _log_directory() -> Path:
        """Return the directory for the log file."""
        if getattr(sys, "frozen", False):
            # PyInstaller bundle — use platform-appropriate writable location.
            if sys.platform == "win32":
                base = Path(os.environ.get("LOCALAPPDATA", "~")).expanduser()
            elif sys.platform == "darwin":
                base = Path.home() / "Library" / "Logs"
            else:
                base = Path(
                    os.environ.get(
                        "XDG_DATA_HOME", str(Path.home() / ".local" / "share")
                    )
                )
            return base / "hash-turbo"
        return Path.cwd()


__all__ = ["LoggingSetup"]
