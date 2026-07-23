from __future__ import annotations

import threading
from dataclasses import dataclass

DEFAULT_MAX_CONTEXT_CHARS = 120_000
MIN_DEDUPLICATED_LINE_LENGTH = 20


@dataclass(frozen=True)
class ReadingContextUpdate:
    added_chars: int
    total_chars: int
    fragments: int
    duplicate: bool
    truncated: bool


class ReadingContext:
    def __init__(self, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS) -> None:
        if max_chars < 1:
            raise ValueError("Размер контекста должен быть положительным")
        self.max_chars = max_chars
        self._fragments: list[list[str]] = []
        self._lock = threading.Lock()

    def add(self, text: str) -> ReadingContextUpdate:
        lines = self._clean_lines(text)
        if not lines:
            return self.stats(duplicate=True)

        with self._lock:
            known_lines = self._known_lines()
            unique_lines: list[str] = []
            for line in lines:
                key = self._line_key(line)
                if len(key) >= MIN_DEDUPLICATED_LINE_LENGTH and key in known_lines:
                    continue
                unique_lines.append(line)
                if len(key) >= MIN_DEDUPLICATED_LINE_LENGTH:
                    known_lines.add(key)

            if not unique_lines:
                return self._stats_unlocked(duplicate=True)

            self._fragments.append(unique_lines)
            added_chars = len("\n".join(unique_lines))
            truncated = self._trim()
            return self._stats_unlocked(
                added_chars=added_chars,
                truncated=truncated,
            )

    def clear(self) -> ReadingContextUpdate:
        with self._lock:
            self._fragments.clear()
            return self._stats_unlocked()

    @property
    def text(self) -> str:
        with self._lock:
            return self._text_unlocked()

    def stats(self, duplicate: bool = False) -> ReadingContextUpdate:
        with self._lock:
            return self._stats_unlocked(duplicate=duplicate)

    def _trim(self) -> bool:
        truncated = False
        while len(self._text_unlocked()) > self.max_chars and self._fragments:
            truncated = True
            overflow = len(self._text_unlocked()) - self.max_chars
            first = self._fragments[0]
            if len(self._fragments) == 1 and len(first) == 1:
                first[0] = first[0][-self.max_chars :]
                break
            while first and overflow > 0:
                overflow -= len(first.pop(0)) + 1
            if not first:
                self._fragments.pop(0)
        return truncated

    def _known_lines(self) -> set[str]:
        return {
            self._line_key(line)
            for fragment in self._fragments
            for line in fragment
            if len(self._line_key(line)) >= MIN_DEDUPLICATED_LINE_LENGTH
        }

    def _stats_unlocked(
        self,
        added_chars: int = 0,
        duplicate: bool = False,
        truncated: bool = False,
    ) -> ReadingContextUpdate:
        return ReadingContextUpdate(
            added_chars=added_chars,
            total_chars=len(self._text_unlocked()),
            fragments=len(self._fragments),
            duplicate=duplicate,
            truncated=truncated,
        )

    def _text_unlocked(self) -> str:
        return "\n\n".join("\n".join(fragment) for fragment in self._fragments)

    @staticmethod
    def _clean_lines(text: str) -> list[str]:
        return [" ".join(line.split()) for line in text.splitlines() if line.strip()]

    @staticmethod
    def _line_key(line: str) -> str:
        return " ".join(line.casefold().split())
