"""
SQLiteStore — raw SQLite persistence for conversation data.

21_System_Contracts.md §16.4 — SQLite Policy.

Internal module; not exported from ``__init__.py``.

All I/O methods are synchronous.  Callers (or the async adapter) are
responsible for offloading to ``asyncio.to_thread()``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from backend.modules.memory.memory_models import MIGRATIONS
from backend.types import Message


class SQLiteStore:
    """Synchronous SQLite store for conversation history and settings.

    Parameters
    ----------
    db_path : Path | str
        Filesystem path to the SQLite database file.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._write_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the SQLite connection, enable WAL mode, and migrate."""
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._write_lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._migrate()

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def is_open(self) -> bool:
        return self._conn is not None

    # ------------------------------------------------------------------
    # Schema migration
    # ------------------------------------------------------------------

    def _migrate(self) -> None:
        conn = self._conn
        if conn is None:
            raise RuntimeError("SQLiteStore is not open")

        current = self._get_schema_version(conn)

        for version in sorted(MIGRATIONS):
            if version > current:
                conn.executescript(MIGRATIONS[version])
                conn.execute(
                    "INSERT OR REPLACE INTO _schema_version (version) VALUES (?)",
                    (version,),
                )
                conn.commit()

    @staticmethod
    def _get_schema_version(conn: sqlite3.Connection) -> int:
        try:
            row = conn.execute(
                "SELECT version FROM _schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            return row["version"] if row else 0
        except sqlite3.OperationalError:
            return 0

    # ------------------------------------------------------------------
    # Message operations
    # ------------------------------------------------------------------

    def store_message(self, session_id: str, message: Message) -> None:
        """Insert a single message into the conversation store.

        Parameters
        ----------
        session_id : str
            Session identifier.
        message : Message
            The message to persist.
        """
        conn = self._require_conn()
        now = time.time()
        tool_calls_str: str | None = None
        if message.tool_calls:
            tool_calls_str = json.dumps(
                [t.__dict__ if hasattr(t, "__dict__") else t for t in message.tool_calls]
            )

        with self._write_lock:
            conn.execute(
                """INSERT INTO conversations
                   (session_id, role, content, tool_calls, tool_call_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    message.role,
                    message.content,
                    tool_calls_str,
                    message.tool_call_id,
                    now,
                ),
            )

            conn.execute(
                """INSERT INTO session_metadata (session_id, created_at, updated_at, message_count)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(session_id) DO UPDATE SET
                       updated_at = excluded.updated_at,
                       message_count = message_count + 1""",
                (session_id, now, now),
            )

            conn.commit()

    def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[Message]:
        """Retrieve recent messages for a session.

        Parameters
        ----------
        session_id : str
            Session identifier.
        limit : int
            Maximum number of messages to return.

        Returns
        -------
        list[Message]
            Messages ordered by creation time (oldest first).
        """
        conn = self._require_conn()
        rows = conn.execute(
            """SELECT role, content, tool_calls, tool_call_id
               FROM conversations
               WHERE session_id = ? AND archived = 0
               ORDER BY created_at ASC
               LIMIT ?""",
            (session_id, limit),
        ).fetchall()

        messages: list[Message] = []
        for row in rows:
            tool_calls = None
            if row["tool_calls"] is not None:
                raw = json.loads(row["tool_calls"])
                tool_calls = [
                    type(
                        "ToolCall",
                        (),
                        {
                            "id": t.get("id", ""),
                            "name": t.get("name", ""),
                            "arguments": t.get("arguments", {}),
                        },
                    )
                    for t in raw
                ]

            messages.append(
                Message(
                    role=row["role"],
                    content=row["content"],
                    tool_calls=tool_calls,  # type: ignore[arg-type]
                    tool_call_id=row["tool_call_id"],
                )
            )

        return messages

    def get_all_sessions(self) -> list[str]:
        """Return all non-archived session IDs."""
        conn = self._require_conn()
        rows = conn.execute(
            "SELECT DISTINCT session_id FROM conversations WHERE archived = 0 ORDER BY session_id"
        ).fetchall()
        return [row["session_id"] for row in rows]

    def archive_session(self, session_id: str) -> None:
        """Mark all messages and metadata for a session as archived.

        No data is deleted (policy: never delete user data).
        """
        with self._write_lock:
            conn = self._require_conn()
            conn.execute(
                "UPDATE conversations SET archived = 1 WHERE session_id = ?",
                (session_id,),
            )
            conn.execute(
                "UPDATE session_metadata SET archived = 1 WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

    def delete_session(self, session_id: str) -> None:
        """Permanently remove all data for a session.

        Use with caution — this violates the "never delete" policy
        and is intended only for testing and explicit user requests.
        """
        with self._write_lock:
            conn = self._require_conn()
            conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM session_metadata WHERE session_id = ?", (session_id,))
            conn.commit()

    # ------------------------------------------------------------------
    # Settings operations
    # ------------------------------------------------------------------

    def store_setting(self, key: str, value: object) -> None:
        """Persist a key-value setting.

        Parameters
        ----------
        key : str
            Setting key.
        value : Any
            Value to store (serialised as JSON).
        """
        with self._write_lock:
            conn = self._require_conn()
            conn.execute(
                """INSERT INTO settings (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = excluded.updated_at""",
                (key, json.dumps(value), time.time()),
            )
            conn.commit()

    def get_setting(self, key: str) -> object | None:
        """Retrieve a previously stored setting.

        Parameters
        ----------
        key : str
            Setting key.

        Returns
        -------
        Any | None
            The deserialised value, or ``None`` if not found.
        """
        conn = self._require_conn()
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def get_all_settings(self) -> dict[str, object]:
        """Return all stored settings."""
        conn = self._require_conn()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: json.loads(row["value"]) for row in rows}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Return ``True`` if the database is reachable."""
        conn = self._require_conn()
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.OperationalError:
            return False

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def vacuum(self) -> None:
        """Reclaim storage space."""
        with self._write_lock:
            conn = self._require_conn()
            conn.execute("VACUUM")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteStore is not open — call open() first")
        return self._conn
