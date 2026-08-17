from __future__ import annotations
from typing import Any
"""
JSONVectorIndexAdapter — implements ``VectorIndexPort`` for JSON keyword index.

21_System_Contracts.md §16.3 — VectorIndexPort interface.
21_System_Contracts.md §16.5 — No vector server.

This adapter is instantiated at boot time (Step 9) and injected into
the Any Manager or consumed directly.
"""



import asyncio

from backend.modules.memory.ports.vector_index_port import VectorIndexPort
from backend.modules.memory.vector_index import VectorIndex
from backend.types import SearchResult
class JSONVectorIndexAdapter(VectorIndexPort):
    """Adapter that exposes a ``VectorIndex`` through the ``VectorIndexPort`` interface.

    All public methods are async; synchronous operations are offloaded
    via ``asyncio.to_thread()``.

    Parameters
    ----------
    index : VectorIndex
        The underlying synchronous keyword index.
    """

    def __init__(self, index: VectorIndex) -> None:
        self._index = index

    async def index(self, keywords: list[str], source_id: str) -> None:
        await asyncio.to_thread(self._index.index, keywords, source_id)

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        raw = await asyncio.to_thread(self._index.search, query, top_k)
        results: list[SearchResult] = []
        for r in raw:
            results.append(
                SearchResult(
                    source_id=r.get("source_id", ""),
                    content="",
                    score=r.get("score", 0.0),
                    metadata={"matched_keywords": r.get("matched_keywords", [])},
                )
            )
        return results
