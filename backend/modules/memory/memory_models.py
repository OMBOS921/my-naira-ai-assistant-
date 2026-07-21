"""
Memory models — SQLite schema definitions and migration logic.

21_System_Contracts.md §16.4 — SQLite Policy.

Internal module; not exported from ``__init__.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

SCHEMA_VERSION: int = 1

SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    tool_call_id TEXT,
    created_at REAL NOT NULL,
    archived INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_conversations_session
    ON conversations(session_id, created_at);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS session_metadata (
    session_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    message_count INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0
);
"""

MIGRATIONS: dict[int, str] = {
    1: SCHEMA_SQL,
}


@dataclass
class ConversationRow:
    """Internal representation of a row in the ``conversations`` table.

    Not a public API type; used internally by ``SQLiteStore``.
    """

    id: int | None = None
    session_id: str = ""
    role: str = ""
    content: str = ""
    tool_calls: str | None = None
    tool_call_id: str | None = None
    created_at: float = 0.0
    archived: bool = False

    @property
    def     tool_calls_parsed(self) -> list[dict[str, object]] | None:
        if self.tool_calls is None:
            return None
        try:
            return json.loads(self.tool_calls)
        except json.JSONDecodeError:
            return None


@dataclass
class SettingRow:
    """Internal representation of a row in the ``settings`` table."""

    key: str = ""
    value: str = ""
    updated_at: float = 0.0


@dataclass
class SessionMetadataRow:
    """Internal representation of a row in the ``session_metadata`` table."""

    session_id: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    message_count: int = 0
    archived: bool = False
