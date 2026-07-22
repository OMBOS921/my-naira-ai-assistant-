"""
TimelineEngine — tracks temporal events, user actions, and session milestones.

Uses the central SQLiteStore instance for persistence.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.modules.memory.sqlite_store import SQLiteStore


class TimelineEngine:
    """Engine for recording and querying chronological events and milestones.

    Parameters
    ----------
    store : SQLiteStore
        Shared SQLite store instance.
    logger : logging.Logger | None
        Module logger instance.
    """

    def __init__(self, store: SQLiteStore, logger: logging.Logger | None = None) -> None:
        self._store = store
        self._logger = logger

    def record(
        self,
        event_type: str,
        title: str,
        description: str | None = None,
        session_id: str | None = None,
        happened_at: float | None = None,
        tags: list[str] | str | None = None,
        importance: int = 5,
        metadata: dict[str, Any] | str | None = None,
    ) -> int | None:
        """Record a timeline event into the store.

        Parameters
        ----------
        event_type : str
            Category/type of event.
        title : str
            Short title or summary.
        description : str | None
            Detailed description.
        session_id : str | None
            Associated session ID.
        happened_at : float | None
            Timestamp when event occurred (defaults to now).
        tags : list[str] | str | None
            Event tags.
        importance : int
            Event importance (1-10).
        metadata : dict | str | None
            Additional metadata.

        Returns
        -------
        int | None
            Row ID of the inserted event, or None if failed.
        """
        now = time.time()
        event_ts = happened_at if happened_at is not None else now

        # Serialize tags to JSON string if list
        if tags is not None and not isinstance(tags, str):
            tags_str = json.dumps(tags)
        else:
            tags_str = tags

        # Serialize metadata to JSON string if dict
        if metadata is not None and not isinstance(metadata, str):
            meta_str = json.dumps(metadata)
        else:
            meta_str = metadata

        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                cursor = conn.execute(
                    """
                    INSERT INTO timeline_events (
                        event_type, title, description, session_id,
                        happened_at, created_at, tags, importance, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_type,
                        title,
                        description,
                        session_id,
                        event_ts,
                        now,
                        tags_str,
                        importance,
                        meta_str,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as exc:
            if self._logger:
                self._logger.warning("TimelineEngine.record failed: %s", exc)
            return None

    def get_recent(
        self,
        limit: int = 10,
        event_type: str | None = None,
        since_timestamp: float | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve recent timeline events.

        Parameters
        ----------
        limit : int
            Maximum number of events.
        event_type : str | None
            Filter by event type.
        since_timestamp : float | None
            Filter events after this timestamp.

        Returns
        -------
        list[dict]
            List of timeline events ordered by happened_at DESC.
        """
        try:
            conn = self._store._require_conn()
            conditions = []
            params: list[Any] = []

            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            if since_timestamp is not None:
                conditions.append("happened_at >= ?")
                params.append(since_timestamp)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"SELECT * FROM timeline_events {where_clause} ORDER BY happened_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            results = []
            for r in rows:
                item = dict(r)
                if item.get("tags"):
                    try:
                        item["tags"] = json.loads(item["tags"])
                    except Exception:
                        pass
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results
        except Exception as exc:
            if self._logger:
                self._logger.warning("TimelineEngine.get_recent failed: %s", exc)
            return []

    def get_today(self) -> list[dict[str, Any]]:
        """Retrieve all events recorded within the last 24 hours.

        Returns
        -------
        list[dict]
            Events from last 24h.
        """
        since_ts = time.time() - 86400
        return self.get_recent(limit=100, since_timestamp=since_ts)

    def get_by_session(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve events for a specific session ID.

        Parameters
        ----------
        session_id : str
            Session identifier.
        limit : int
            Maximum events.

        Returns
        -------
        list[dict]
            List of events.
        """
        try:
            conn = self._store._require_conn()
            rows = conn.execute(
                """
                SELECT * FROM timeline_events
                WHERE session_id = ?
                ORDER BY happened_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()

            results = []
            for r in rows:
                item = dict(r)
                if item.get("tags"):
                    try:
                        item["tags"] = json.loads(item["tags"])
                    except Exception:
                        pass
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results
        except Exception as exc:
            if self._logger:
                self._logger.warning("TimelineEngine.get_by_session failed: %s", exc)
            return []

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search events by matching title or description using LIKE.

        Parameters
        ----------
        query : str
            Query pattern.
        limit : int
            Max results.

        Returns
        -------
        list[dict]
            Matching events.
        """
        try:
            conn = self._store._require_conn()
            pattern = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM timeline_events
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY happened_at DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()

            results = []
            for r in rows:
                item = dict(r)
                if item.get("tags"):
                    try:
                        item["tags"] = json.loads(item["tags"])
                    except Exception:
                        pass
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results
        except Exception as exc:
            if self._logger:
                self._logger.warning("TimelineEngine.search failed: %s", exc)
            return []

    def get_summary_for_prompt(self, limit: int = 5) -> str:
        """Generate formatted recent activity block for system prompt.

        Format:
        Recent activity:
        • [YYYY-MM-DD HH:MM] [type] — [title]

        Parameters
        ----------
        limit : int
            Maximum items.

        Returns
        -------
        str
            Formatted summary or empty string.
        """
        events = self.get_recent(limit=limit)
        if not events:
            return ""

        lines = ["Recent activity:"]
        for ev in events:
            ts = ev.get("happened_at", time.time())
            dt_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
            e_type = ev.get("event_type", "")
            title = ev.get("title", "")
            lines.append(f"• [{dt_str}] [{e_type}] — {title}")

        return "\n".join(lines)
