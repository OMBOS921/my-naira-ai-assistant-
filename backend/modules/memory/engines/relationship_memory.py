"""
RelationshipMemory — manages entities, relationship types, and importance scores.

Uses the central SQLiteStore instance for persistence.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.modules.memory.sqlite_store import SQLiteStore


class RelationshipMemory:
    """Engine for tracking entity relationships, interaction counts, and importance.

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

    def upsert(
        self,
        entity_name: str,
        entity_type: str,
        relationship_type: str,
        description: str,
        importance: int = 5,
        metadata: dict[str, Any] | list[Any] | str | None = None,
    ) -> bool:
        """Insert a new relationship or update description/interaction details on conflict.

        Parameters
        ----------
        entity_name : str
            Name of the entity.
        entity_type : str
            Category/type of the entity.
        relationship_type : str
            Type of relationship (e.g., 'friend', 'colleague', 'tool').
        description : str
            Detailed description of the relationship.
        importance : int
            Importance score from 1 to 10.
        metadata : dict | list | str | None
            Optional metadata object.

        Returns
        -------
        bool
            True if operation succeeded, False otherwise.
        """
        now = time.time()
        # Serialize metadata to JSON string if provided as dict or list
        if metadata is not None and not isinstance(metadata, str):
            metadata_str = json.dumps(metadata)
        else:
            metadata_str = metadata

        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                conn.execute(
                    """
                    INSERT INTO relationships (
                        entity_name, entity_type, relationship_type, description,
                        importance, interaction_count, last_seen_at, first_seen_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    ON CONFLICT(entity_name, entity_type) DO UPDATE SET
                        relationship_type = excluded.relationship_type,
                        description = excluded.description,
                        importance = excluded.importance,
                        interaction_count = relationships.interaction_count + 1,
                        last_seen_at = excluded.last_seen_at,
                        metadata = excluded.metadata
                    """,
                    (
                        entity_name,
                        entity_type,
                        relationship_type,
                        description,
                        importance,
                        now,
                        now,
                        metadata_str,
                    ),
                )
                conn.commit()
            return True
        except Exception as exc:
            # Catch DB error safely to avoid breaking execution
            if self._logger:
                self._logger.warning("RelationshipMemory.upsert failed: %s", exc)
            return False

    def get(self, entity_name: str, entity_type: str | None = None) -> dict[str, Any] | None:
        """Fetch a specific relationship record by entity name and optional type.

        Parameters
        ----------
        entity_name : str
            Name of the entity.
        entity_type : str | None
            Optional entity type filter.

        Returns
        -------
        dict | None
            Dictionary representing the row, or None if not found.
        """
        try:
            conn = self._store._require_conn()
            if entity_type:
                row = conn.execute(
                    "SELECT * FROM relationships WHERE entity_name = ? AND entity_type = ?",
                    (entity_name, entity_type),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM relationships WHERE entity_name = ? LIMIT 1",
                    (entity_name,),
                ).fetchone()

            if not row:
                return None

            result = dict(row)
            # Parse JSON metadata if available
            if result.get("metadata"):
                try:
                    result["metadata"] = json.loads(result["metadata"])
                except Exception:
                    pass
            return result
        except Exception as exc:
            if self._logger:
                self._logger.warning("RelationshipMemory.get failed: %s", exc)
            return None

    def get_all(
        self, entity_type: str | None = None, min_importance: int = 1, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Retrieve relationship records ordered by importance.

        Parameters
        ----------
        entity_type : str | None
            Filter by entity type.
        min_importance : int
            Minimum importance threshold.
        limit : int
            Maximum records to return.

        Returns
        -------
        list[dict]
            List of matching relationship records.
        """
        try:
            conn = self._store._require_conn()
            if entity_type:
                rows = conn.execute(
                    """
                    SELECT * FROM relationships
                    WHERE entity_type = ? AND importance >= ?
                    ORDER BY importance DESC, last_seen_at DESC
                    LIMIT ?
                    """,
                    (entity_type, min_importance, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM relationships
                    WHERE importance >= ?
                    ORDER BY importance DESC, last_seen_at DESC
                    LIMIT ?
                    """,
                    (min_importance, limit),
                ).fetchall()

            results = []
            for r in rows:
                item = dict(r)
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results
        except Exception as exc:
            if self._logger:
                self._logger.warning("RelationshipMemory.get_all failed: %s", exc)
            return []

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search entity relationships using LIKE matching on name or description.

        Parameters
        ----------
        query : str
            Search query string.
        limit : int
            Maximum number of matches.

        Returns
        -------
        list[dict]
            List of matching records.
        """
        try:
            conn = self._store._require_conn()
            pattern = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM relationships
                WHERE entity_name LIKE ? OR description LIKE ?
                ORDER BY importance DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()

            results = []
            for r in rows:
                item = dict(r)
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results
        except Exception as exc:
            if self._logger:
                self._logger.warning("RelationshipMemory.search failed: %s", exc)
            return []

    def increment_interaction(self, entity_name: str, entity_type: str | None = None) -> bool:
        """Increment interaction count and update last_seen_at timestamp.

        Parameters
        ----------
        entity_name : str
            Entity name.
        entity_type : str | None
            Optional entity type.

        Returns
        -------
        bool
            True if updated successfully.
        """
        now = time.time()
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                if entity_type:
                    conn.execute(
                        """
                        UPDATE relationships
                        SET interaction_count = interaction_count + 1, last_seen_at = ?
                        WHERE entity_name = ? AND entity_type = ?
                        """,
                        (now, entity_name, entity_type),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE relationships
                        SET interaction_count = interaction_count + 1, last_seen_at = ?
                        WHERE entity_name = ?
                        """,
                        (now, entity_name),
                    )
                conn.commit()
            return True
        except Exception as exc:
            if self._logger:
                self._logger.warning("RelationshipMemory.increment_interaction failed: %s", exc)
            return False

    def get_summary_for_prompt(self, limit: int = 8) -> str:
        """Generate formatted summary string for system prompts.

        Format:
        Known entities:
        • [name] [[type]] — [desc] (importance: [x])

        Parameters
        ----------
        limit : int
            Maximum number of relationships to include.

        Returns
        -------
        str
            Formatted summary text or empty string if no records exist.
        """
        items = self.get_all(min_importance=1, limit=limit)
        if not items:
            return ""

        lines = ["Known entities:"]
        for item in items:
            name = item.get("entity_name", "")
            e_type = item.get("entity_type", "")
            desc = item.get("description", "")
            imp = item.get("importance", 5)
            lines.append(f"• {name} [{e_type}] — {desc} (importance: {imp})")

        return "\n".join(lines)
