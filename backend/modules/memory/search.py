"""
SearchAPI — combined search across conversation history and vector index.

21_System_Contracts.md §16 — Memory Contracts.

Internal module; not exported from ``__init__.py``.
"""

from __future__ import annotations

from backend.modules.memory.sqlite_store import SQLiteStore
from backend.modules.memory.vector_index import VectorIndex
from backend.types import SearchResult
class SearchAPI:
    """Combined search across SQLite conversation store and vector index.

    Parameters
    ----------
    sqlite_store : SQLiteStore
        The conversation store instance.
    vector_index : VectorIndex
        The keyword index instance.
    """

    def __init__(self, sqlite_store: SQLiteStore, vector_index: VectorIndex) -> None:
        self._sqlite = sqlite_store
        self._index = vector_index

    def search_conversations(
        self, query: str, session_id: str | None = None, limit: int = 10
    ) -> list[SearchResult]:
        """Search conversation messages by content substring match.

        Parameters
        ----------
        query : str
            Search term (case-insensitive substring match).
        session_id : str | None
            If provided, restricts search to a single session.
        limit : int
            Maximum results.

        Returns
        -------
        list[SearchResult]
            Chronologically ordered results.
        """
        sql = """SELECT session_id, content, created_at, role
                 FROM conversations
                 WHERE LOWER(content) LIKE LOWER(?)
                   AND archived = 0"""
        params: list[str | None] = [f"%{query}%"]

        if session_id is not None:
            sql += " AND session_id = ?"
            params.append(session_id)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(str(limit))

        conn = self._sqlite._require_conn()
        rows = conn.execute(sql, params).fetchall()

        results: list[SearchResult] = []
        for row in rows:
            results.append(
                SearchResult(
                    source_id=row["session_id"],
                    content=row["content"][:500],
                    score=1.0,
                    metadata={
                        "role": row["role"],
                        "timestamp": row["created_at"],
                        "match_type": "substring",
                    },
                )
            )
        return results

    def search_semantic(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search the vector index for semantically similar content.

        Parameters
        ----------
        query : str
            Natural-language query.
        top_k : int
            Maximum results.

        Returns
        -------
        list[SearchResult]
            Ranked by semantic relevance score.
        """
        raw_results = self._index.search(query, top_k=top_k)
        results: list[SearchResult] = []

        for r in raw_results:
            score = r.get("score", 0.0)
            source_id = r.get("source_id", "")

            content = ""
            history = self._sqlite.get_history(source_id, limit=1)
            if history:
                content = history[-1].content[:500]

            results.append(
                SearchResult(
                    source_id=source_id,
                    content=content,
                    score=score,
                    metadata={
                        "matched_keywords": r.get("matched_keywords", []),
                        "match_type": "semantic",
                    },
                )
            )

        return results

    def combined_search(
        self, query: str, top_k: int = 5
    ) -> list[SearchResult]:
        """Run both substring and semantic search, merge by score.

        Parameters
        ----------
        query : str
            Search query.
        top_k : int
            Maximum combined results.

        Returns
        -------
        list[SearchResult]
            Merged and scored results.
        """
        semantic = self.search_semantic(query, top_k=top_k)
        substring = self.search_conversations(query, limit=top_k)

        seen: set[str] = set()
        merged: list[SearchResult] = []
        for result in semantic + substring:
            if result.source_id not in seen:
                seen.add(result.source_id)
                merged.append(result)

        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[:top_k]
