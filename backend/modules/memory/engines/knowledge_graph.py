"""
KnowledgeGraph — stores subject-predicate-object semantic triples.

Uses the central SQLiteStore instance for persistence.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.modules.memory.sqlite_store import SQLiteStore


class KnowledgeGraph:
    """Engine for storing and querying subject-predicate-object knowledge triples.

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
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
        source: str = "stated",
    ) -> bool:
        """Insert a triple or update confidence and updated_at timestamp on conflict.

        Parameters
        ----------
        subject : str
            Triple subject.
        predicate : str
            Triple predicate.
        object_ : str
            Triple object value.
        confidence : float
            Confidence score (0.0 - 1.0).
        source : str
            Source of knowledge.

        Returns
        -------
        bool
            True if operation succeeded.
        """
        now = time.time()
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                conn.execute(
                    """
                    INSERT INTO knowledge_graph (
                        subject, predicate, object, confidence, source, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(subject, predicate, object) DO UPDATE SET
                        confidence = excluded.confidence,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    (subject, predicate, object_, confidence, source, now, now),
                )
                conn.commit()
            return True
        except Exception as exc:
            if self._logger:
                self._logger.warning("KnowledgeGraph.upsert failed: %s", exc)
            return False

    def query(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        object_: str | None = None,
        min_confidence: float = 0.5,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query knowledge graph triples based on optional filters.

        Parameters
        ----------
        subject : str | None
            Subject filter.
        predicate : str | None
            Predicate filter.
        object_ : str | None
            Object filter.
        min_confidence : float
            Minimum confidence threshold.
        limit : int
            Max triples to return.

        Returns
        -------
        list[dict]
            List of matching triple records.
        """
        try:
            conn = self._store._require_conn()
            conditions = ["confidence >= ?"]
            params: list[Any] = [min_confidence]

            if subject:
                conditions.append("subject = ?")
                params.append(subject)
            if predicate:
                conditions.append("predicate = ?")
                params.append(predicate)
            if object_:
                conditions.append("object = ?")
                params.append(object_)

            where_clause = "WHERE " + " AND ".join(conditions)
            sql = f"SELECT * FROM knowledge_graph {where_clause} ORDER BY confidence DESC, updated_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            if self._logger:
                self._logger.warning("KnowledgeGraph.query failed: %s", exc)
            return []

    def get_about(self, subject: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch all facts where entity is either subject or object.

        Parameters
        ----------
        subject : str
            Entity name.
        limit : int
            Max records.

        Returns
        -------
        list[dict]
            List of matching triples.
        """
        try:
            conn = self._store._require_conn()
            pattern = f"%{subject}%"
            rows = conn.execute(
                """
                SELECT * FROM knowledge_graph
                WHERE (subject LIKE ? OR object LIKE ?) AND confidence >= 0.5
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            if self._logger:
                self._logger.warning("KnowledgeGraph.get_about failed: %s", exc)
            return []

    def delete(self, subject: str, predicate: str, object_: str) -> bool:
        """Delete a triple from the knowledge graph.

        Parameters
        ----------
        subject : str
            Triple subject.
        predicate : str
            Triple predicate.
        object_ : str
            Triple object.

        Returns
        -------
        bool
            True if deleted successfully.
        """
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                conn.execute(
                    "DELETE FROM knowledge_graph WHERE subject = ? AND predicate = ? AND object = ?",
                    (subject, predicate, object_),
                )
                conn.commit()
            return True
        except Exception as exc:
            if self._logger:
                self._logger.warning("KnowledgeGraph.delete failed: %s", exc)
            return False

    def upsert_bulk(self, triples: list[tuple[Any, ...]]) -> int:
        """Upsert a list of triple tuples into the knowledge graph.

        Parameters
        ----------
        triples : list[tuple]
            List of (subject, predicate, object) or (subject, predicate, object, confidence, source) tuples.

        Returns
        -------
        int
            Count of successfully upserted triples.
        """
        count = 0
        for item in triples:
            if len(item) == 3:
                s, p, o = item
                conf, src = 1.0, "stated"
            elif len(item) == 4:
                s, p, o, conf = item
                src = "stated"
            elif len(item) >= 5:
                s, p, o, conf, src = item[:5]
            else:
                continue

            if self.upsert(str(s), str(p), str(o), float(conf), str(src)):
                count += 1
        return count

    def get_summary_for_prompt(self, subject: str = "Om", limit: int = 10) -> str:
        """Generate formatted knowledge section for prompt context.

        Format:
        What I know about [subject]:
        • [subject] [predicate] [object] ([source])

        Parameters
        ----------
        subject : str
            Target subject entity.
        limit : int
            Max triples to format.

        Returns
        -------
        str
            Formatted summary or empty string.
        """
        facts = self.get_about(subject, limit=limit)
        if not facts:
            # Fallback to general triples if subject has no specific facts
            facts = self.query(min_confidence=0.5, limit=limit)

        if not facts:
            return ""

        lines = [f"What I know about {subject}:"]
        for f in facts:
            s = f.get("subject", "")
            p = f.get("predicate", "")
            o = f.get("object", "")
            src = f.get("source", "stated")
            lines.append(f"• {s} {p} {o} ({src})")

        return "\n".join(lines)
