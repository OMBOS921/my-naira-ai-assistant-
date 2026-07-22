"""
MemoryIntelligence — stores patterns, insights, and key observations with deduplication.

Uses the central SQLiteStore instance for persistence.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.modules.memory.sqlite_store import SQLiteStore


class MemoryIntelligence:
    """Engine for managing intelligent observations, recurring patterns, and key facts.

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

    def record_fact(
        self,
        content: str,
        fact_type: str = "important_fact",
        importance: int = 5,
        tags: list[str] | str | None = None,
    ) -> int | None:
        """Record a new observation or increment trigger_count if an ~80% similar fact exists.

        Parameters
        ----------
        content : str
            Observation/fact content.
        fact_type : str
            Type of fact ('important_fact', 'pattern', 'preference', etc.).
        importance : int
            Importance rating (1-10).
        tags : list[str] | str | None
            Optional tag strings.

        Returns
        -------
        int | None
            Fact ID (inserted or existing triggered row), or None if error.
        """
        now = time.time()
        # Normalize incoming content into word set for overlap checking
        words_new = set(re.findall(r"\w+", content.lower()))

        # Check existing active facts for 80% word overlap match
        active_facts = self.get_active(fact_type=fact_type, min_importance=1, limit=100)
        for fact in active_facts:
            existing_content = fact.get("content", "")
            words_existing = set(re.findall(r"\w+", existing_content.lower()))
            if words_new and words_existing:
                intersection = words_new.intersection(words_existing)
                min_len = min(len(words_new), len(words_existing))
                overlap = len(intersection) / min_len if min_len > 0 else 0.0
                if overlap >= 0.8:
                    # Similar fact exists! Increment trigger count instead of duplicate insertion
                    fact_id = fact["id"]
                    self.increment_trigger(fact_id)
                    return fact_id

        # Serialize tags to JSON string if passed as list
        if tags is not None and not isinstance(tags, str):
            tags_str = json.dumps(tags)
        else:
            tags_str = tags

        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                cursor = conn.execute(
                    """
                    INSERT INTO memory_intelligence (
                        fact_type, content, trigger_count, last_triggered_at,
                        first_seen_at, importance, tags, is_active
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, 1)
                    """,
                    (fact_type, content, now, now, importance, tags_str),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as exc:
            if self._logger:
                self._logger.warning("MemoryIntelligence.record_fact failed: %s", exc)
            return None

    def get_active(
        self,
        fact_type: str | None = None,
        min_importance: int = 1,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve active memory intelligence entries.

        Parameters
        ----------
        fact_type : str | None
            Filter by fact type.
        min_importance : int
            Minimum importance threshold.
        limit : int
            Maximum items.

        Returns
        -------
        list[dict]
            Active fact records ordered by importance and trigger count.
        """
        try:
            conn = self._store._require_conn()
            conditions = ["is_active = 1", "importance >= ?"]
            params: list[Any] = [min_importance]

            if fact_type:
                conditions.append("fact_type = ?")
                params.append(fact_type)

            where_clause = "WHERE " + " AND ".join(conditions)
            sql = f"SELECT * FROM memory_intelligence {where_clause} ORDER BY importance DESC, trigger_count DESC LIMIT ?"
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
                results.append(item)
            return results
        except Exception as exc:
            if self._logger:
                self._logger.warning("MemoryIntelligence.get_active failed: %s", exc)
            return []

    def dismiss(self, fact_id: int) -> bool:
        """Deactivate (soft delete) a fact by setting is_active = 0.

        Parameters
        ----------
        fact_id : int
            ID of the memory intelligence row.

        Returns
        -------
        bool
            True if updated.
        """
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                conn.execute(
                    "UPDATE memory_intelligence SET is_active = 0 WHERE id = ?",
                    (fact_id,),
                )
                conn.commit()
            return True
        except Exception as exc:
            if self._logger:
                self._logger.warning("MemoryIntelligence.dismiss failed for id %s: %s", fact_id, exc)
            return False

    def increment_trigger(self, fact_id: int) -> bool:
        """Increment trigger_count and update last_triggered_at timestamp.

        Parameters
        ----------
        fact_id : int
            ID of the fact record.

        Returns
        -------
        bool
            True if updated successfully.
        """
        now = time.time()
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                conn.execute(
                    """
                    UPDATE memory_intelligence
                    SET trigger_count = trigger_count + 1, last_triggered_at = ?
                    WHERE id = ?
                    """,
                    (now, fact_id),
                )
                conn.commit()
            return True
        except Exception as exc:
            if self._logger:
                self._logger.warning(
                    "MemoryIntelligence.increment_trigger failed for id %s: %s", fact_id, exc
                )
            return False

    def get_patterns(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve top observed patterns ordered by trigger count.

        Parameters
        ----------
        limit : int
            Max patterns.

        Returns
        -------
        list[dict]
            Pattern records.
        """
        return self.get_active(fact_type="pattern", min_importance=1, limit=limit)

    def get_summary_for_prompt(self, limit: int = 5) -> str:
        """Generate formatted key observations section for prompt context.

        Format:
        Key observations:
        • [content] ([type], observed [x] times)

        Parameters
        ----------
        limit : int
            Max items.

        Returns
        -------
        str
            Formatted summary or empty string.
        """
        facts = self.get_active(limit=limit)
        if not facts:
            return ""

        lines = ["Key observations:"]
        for f in facts:
            content = f.get("content", "")
            ftype = f.get("fact_type", "")
            count = f.get("trigger_count", 1)
            lines.append(f"• {content} ({ftype}, observed {count} times)")

        return "\n".join(lines)
