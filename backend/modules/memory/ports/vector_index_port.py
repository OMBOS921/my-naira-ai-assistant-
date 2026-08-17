"""
VectorIndexPort — abstract interface for keyword-based semantic search.

21_System_Contracts.md §16.3 — VectorIndexPort interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.types import SearchResult
class VectorIndexPort(ABC):
    """Port for keyword-based semantic indexing and search.

    Implemented by ``memory.adapters.json_vector_index_adapter.JSONVectorIndexAdapter``
    (Layer 5 — Infrastructure).
    """

    @abstractmethod
    async def index(self, keywords: list[str], source_id: str) -> None:
        """Index a set of *keywords* for a given *source_id*.

        Parameters
        ----------
        keywords : list[str]
            Extracted keywords to associate with the source.
        source_id : str
            Unique identifier for the source document or conversation.
        """
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search the index for documents matching *query*.

        Parameters
        ----------
        query : str
            Natural-language query string.
        top_k : int
            Maximum number of results to return.

        Returns
        -------
        list[SearchResult]
            Ranked results ordered by relevance score.
        """
        ...
