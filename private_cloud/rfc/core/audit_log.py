"""Append-only JSON Lines audit log of MCP tool calls, one file per local day."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


MAX_TEXT_LENGTH = 1000
READ_BACK_DAYS = 31


def _sanitize(value: Any, redact: Callable[[str], str]) -> Any:
    """Make a value JSON-compatible, redact secrets and cap long strings."""
    if isinstance(value, str):
        value = redact(value)
        if len(value) > MAX_TEXT_LENGTH:
            return value[:MAX_TEXT_LENGTH] + "...[truncated]"
        return value
    if isinstance(value, dict):
        return {str(key): _sanitize(item, redact) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, redact) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _sanitize(str(value), redact)


class ToolCallAuditLog:
    """Write and read logs/tool_calls_YYYY-MM-DD.jsonl."""

    def __init__(self, directory: Path, redact: Callable[[str], str]) -> None:
        self._directory = directory
        self._redact = redact
        self._lock = threading.Lock()

    @property
    def directory(self) -> Path:
        return self._directory

    def _path(self, day: date) -> Path:
        return self._directory / f"tool_calls_{day.isoformat()}.jsonl"

    def record(self, entry: dict[str, Any]) -> None:
        now = datetime.now().astimezone()
        line = json.dumps(
            {"timestamp": now.isoformat(timespec="milliseconds"), **_sanitize(entry, self._redact)},
            ensure_ascii=False,
        )
        with self._lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            # One write per line keeps entries intact when several MCP server
            # processes append to the same daily file.
            with self._path(now.date()).open("a", encoding="utf-8") as file:
                file.write(line + "\n")

    def read_recent(self, limit: int, tool: str = "", status: str = "") -> list[dict[str, Any]]:
        """Return up to limit entries, newest first, from the last READ_BACK_DAYS days."""
        entries: list[dict[str, Any]] = []
        today = datetime.now().astimezone().date()
        for days_back in range(READ_BACK_DAYS):
            path = self._path(today - timedelta(days=days_back))
            if not path.is_file():
                continue
            for raw_line in reversed(path.read_text(encoding="utf-8").splitlines()):
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if tool and entry.get("tool") != tool:
                    continue
                if status and entry.get("status") != status:
                    continue
                entries.append(entry)
                if len(entries) >= limit:
                    return entries
        return entries
