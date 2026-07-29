from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

MAX_JOURNAL_ENTRIES = 100
JOURNAL_DIRECTORY_NAME = "history"
JOURNAL_FILE_NAME = "requests.jsonl"


def request_journal_path(base_dir: Path | None = None) -> Path:
    root = base_dir or Path(
        os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or Path.home()
    )
    return root / "SmartHelper" / JOURNAL_DIRECTORY_NAME / JOURNAL_FILE_NAME


class RequestJournal:
    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        max_entries: int = MAX_JOURNAL_ENTRIES,
    ) -> None:
        if max_entries < 1:
            raise ValueError("Количество записей журнала должно быть положительным")
        self.path = request_journal_path(base_dir)
        self.max_entries = max_entries
        self._lock = threading.Lock()

    def record(
        self,
        *,
        command: str,
        prompt: str,
        model: str,
        duration_ms: int,
        screenshot_path: Path | None = None,
        answer: str | None = None,
        error: Exception | None = None,
        context_chars: int = 0,
    ) -> None:
        entry = {
            "id": uuid4().hex,
            "created_at": datetime.now()
            .astimezone()
            .isoformat(timespec="milliseconds"),
            "status": "error" if error is not None else "success",
            "command": command,
            "prompt": prompt,
            "model": model,
            "duration_ms": max(0, duration_ms),
            "screenshot": self._stored_screenshot_path(screenshot_path),
            "context_chars": max(0, context_chars),
            "answer": answer,
            "error_type": type(error).__name__ if error is not None else None,
            "error_message": str(error)[:4000] if error is not None else None,
        }
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                entries = self._read_entries()
                entries.append(entry)
                entries = entries[-self.max_entries :]
                temporary = self.path.with_suffix(".jsonl.tmp")
                temporary.write_text(
                    "".join(
                        json.dumps(item, ensure_ascii=False) + "\n" for item in entries
                    ),
                    encoding="utf-8",
                )
                temporary.replace(self.path)
        except OSError:
            logger.exception("Не удалось обновить скрытый журнал запросов")

    def _read_entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        entries = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        for line in lines:
            try:
                item = json.loads(line)
            except (TypeError, ValueError):
                continue
            if isinstance(item, dict):
                entries.append(item)
        return entries

    def _stored_screenshot_path(self, screenshot_path: Path | None) -> str | None:
        if screenshot_path is None:
            return None
        app_directory = self.path.parent.parent
        try:
            return str(screenshot_path.resolve().relative_to(app_directory.resolve()))
        except ValueError:
            return str(screenshot_path)
