from __future__ import annotations

import io
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE_NAME = "smarthelper.log"
MAX_LOG_SIZE = 2 * 1024 * 1024
BACKUP_COUNT = 5


class _LogStream(io.TextIOBase):
    def __init__(self, logger: logging.Logger, level: int) -> None:
        self._logger = logger
        self._level = level

    def write(self, text: str) -> int:
        for line in text.rstrip().splitlines():
            if line.strip():
                self._logger.log(self._level, line)
        return len(text)

    def flush(self) -> None:
        return None


def desktop_log_path() -> Path:
    base_dir = Path(os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or Path.home())
    return base_dir / "SmartHelper" / "logs" / LOG_FILE_NAME


def configure_desktop_logging() -> Path:
    log_path = desktop_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    resolved_log_path = str(log_path.resolve())
    has_handler = any(
        isinstance(handler, RotatingFileHandler)
        and handler.baseFilename == resolved_log_path
        for handler in root_logger.handlers
    )
    if not has_handler:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(process)d | %(threadName)s | "
                "%(name)s | %(message)s"
            )
        )
        root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    logging.captureWarnings(True)

    if sys.stdout is None:
        sys.stdout = _LogStream(logging.getLogger("smarthelper.stdout"), logging.INFO)
    if sys.stderr is None:
        sys.stderr = _LogStream(logging.getLogger("smarthelper.stderr"), logging.ERROR)
    return log_path
