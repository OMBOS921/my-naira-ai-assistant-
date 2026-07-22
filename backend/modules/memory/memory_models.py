"""
Memory models — SQLite schema definitions and migration logic.

21_System_Contracts.md §16.4 — SQLite Policy.

Internal module; not exported from ``__init__.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

SCHEMA_VERSION: int = 2

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

SCHEMA_V2_SQL: str = """
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    description TEXT NOT NULL,
    importance INTEGER DEFAULT 5,
    interaction_count INTEGER DEFAULT 1,
    last_seen_at REAL NOT NULL,
    first_seen_at REAL NOT NULL,
    metadata TEXT,
    UNIQUE(entity_name, entity_type)
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    session_id TEXT,
    happened_at REAL NOT NULL,
    created_at REAL NOT NULL,
    tags TEXT,
    importance INTEGER DEFAULT 5,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(subject, predicate, object)
);

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key TEXT NOT NULL UNIQUE,
    profile_value TEXT NOT NULL,
    data_type TEXT DEFAULT 'string',
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'stated',
    updated_at REAL NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_intelligence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_type TEXT NOT NULL,
    content TEXT NOT NULL,
    trigger_count INTEGER DEFAULT 1,
    last_triggered_at REAL NOT NULL,
    first_seen_at REAL NOT NULL,
    importance INTEGER DEFAULT 5,
    tags TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS context_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    content TEXT NOT NULL,
    token_estimate INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_timeline_happened ON timeline_events(happened_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_session ON timeline_events(session_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_subject ON knowledge_graph(subject);
CREATE INDEX IF NOT EXISTS idx_knowledge_predicate ON knowledge_graph(predicate);
CREATE INDEX IF NOT EXISTS idx_memory_intel_type ON memory_intelligence(fact_type, is_active);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(entity_type, importance DESC);
CREATE INDEX IF NOT EXISTS idx_context_session ON context_snapshots(session_id, created_at DESC);
"""

MIGRATIONS: dict[int, str] = {
    1: SCHEMA_SQL,
    2: SCHEMA_V2_SQL,
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
    def tool_calls_parsed(self) -> list[dict[str, object]] | None:
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
