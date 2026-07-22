"""
SQLite store for persistent analytics events.

21_System_Contracts.md §16 — Storage contracts.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from backend.modules.analytics._event_types import AnalyticsEvent, AnalyticsSummary

_LOG = logging.getLogger("naira.analytics.store")


class SQLiteAnalyticsStore:
    """Synchronous SQLite store with WAL mode for analytics events."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        """Connect to SQLite database, configure WAL mode, and initialize schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    duration_ms REAL,
                    success INTEGER,
                    payload TEXT
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_ts ON analytics_events(timestamp)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics_events(event_type)"
            )

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def write_event(self, event: AnalyticsEvent) -> None:
        """Persist a single analytics event to SQLite."""
        if self._conn is None:
            return

        try:
            payload_json = json.dumps(event.payload, default=str)
        except Exception as exc:
            _LOG.warning("Failed to serialize analytics payload: %s", exc)
            payload_json = "{}"

        success_int = None if event.success is None else (1 if event.success else 0)
        ts_str = event.timestamp.isoformat()

        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO analytics_events
                    (event_type, timestamp, duration_ms, success, payload)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_type,
                        ts_str,
                        event.duration_ms,
                        success_int,
                        payload_json,
                    ),
                )
        except Exception as exc:
            _LOG.error("Failed to write analytics event to DB: %s", exc)

    def query_summary_historical(self, period: str) -> AnalyticsSummary:
        """Fall back to SQL GROUP BY for historical query summaries."""
        if self._conn is None:
            return AnalyticsSummary(
                period=period if period in ("today", "week", "all") else "all",  # type: ignore[arg-type]
                total_events=0,
                event_counts={},
                success_rate=0.0,
                top_tools=[],
                avg_duration_ms=0.0,
            )

        cutoff = None
        now = datetime.now()
        if period == "today":
            cutoff = datetime(now.year, now.month, now.day).isoformat()
        elif period == "week":
            cutoff = (now - timedelta(days=7)).isoformat()

        where_clause = "WHERE timestamp >= ?" if cutoff else ""
        params = (cutoff,) if cutoff else ()

        with self._conn:
            # Event counts by type
            q_cnt = (
                f"SELECT event_type, COUNT(*) as cnt FROM analytics_events "
                f"{where_clause} GROUP BY event_type"
            )
            counts_cur = self._conn.execute(q_cnt, params)  # noqa: S608
            event_counts = {row["event_type"]: row["cnt"] for row in counts_cur.fetchall()}

            total_events = sum(event_counts.values())

            # Success rate calculation
            q_succ = (
                f"SELECT COUNT(*) as total, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as succ "
                f"FROM analytics_events {where_clause} AND success IS NOT NULL"
                if where_clause
                else "SELECT COUNT(*) as total, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as succ "
                     "FROM analytics_events WHERE success IS NOT NULL"
            )
            succ_cur = self._conn.execute(q_succ, params)  # noqa: S608
            succ_row = succ_cur.fetchone()
            total_with_status = succ_row["total"] if succ_row else 0
            succ_count = succ_row["succ"] if (succ_row and succ_row["succ"]) else 0
            success_rate = (succ_count / total_with_status) if total_with_status > 0 else 0.0

            # Avg duration
            q_dur = (
                f"SELECT AVG(duration_ms) as avg_dur FROM analytics_events "
                f"{where_clause} AND duration_ms IS NOT NULL"
                if where_clause
                else "SELECT AVG(duration_ms) as avg_dur FROM analytics_events "
                     "WHERE duration_ms IS NOT NULL"
            )
            dur_cur = self._conn.execute(q_dur, params)  # noqa: S608
            dur_row = dur_cur.fetchone()
            avg_dur_val = float(dur_row["avg_dur"]) if (dur_row and dur_row["avg_dur"] is not None) else 0.0

            # Top tools used
            q_tool = (
                f"SELECT payload FROM analytics_events {where_clause} AND event_type = 'TOOL_CALL'"
                if where_clause
                else "SELECT payload FROM analytics_events WHERE event_type = 'TOOL_CALL'"
            )
            tool_cur = self._conn.execute(q_tool, params)  # noqa: S608
            tool_counts: dict[str, int] = {}
            for row in tool_cur.fetchall():
                try:
                    data = json.loads(row["payload"])
                    t_name = data.get("tool_name") or data.get("tool")
                    if t_name:
                        tool_counts[str(t_name)] = tool_counts.get(str(t_name), 0) + 1
                except Exception:
                    pass

            top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        period_literal: Literal["today", "week", "all"] = "all"
        if period in ("today", "week", "all"):
            period_literal = period  # type: ignore[assignment]

        return AnalyticsSummary(
            period=period_literal,
            total_events=total_events,
            event_counts=event_counts,
            success_rate=success_rate,
            top_tools=top_tools,
            avg_duration_ms=avg_dur_val,
        )
