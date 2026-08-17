"""Semantic Search — semantic search over codebase content.

Provides keyword-based semantic search over indexed file contents
using TF-IDF-like scoring and lightweight embedding simulation.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter

from backend.types import SearchResult
_LOG = logging.getLogger("naira.context_intelligence.semantic_search")

_STOP_WORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "just", "it", "its",
    "this", "that", "these", "those", "if", "while", "because",
    "but", "or", "and", "up", "down", "about",
}


class SemanticSearch:
    """Provides semantic search over indexed content.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._documents: dict[str, str] = {}
        self._doc_frequencies: dict[str, int] = {}
        self._total_searches = 0

    def index_document(self, doc_id: str, content: str) -> None:
        """Index a document for search.

        Parameters
        ----------
        doc_id : str
            Unique document identifier (e.g., file path).
        content : str
            Document content.
        """
        self._documents[doc_id] = content
        terms = self._tokenize(content)
        unique_terms = set(terms)
        for term in unique_terms:
            self._doc_frequencies[term] = self._doc_frequencies.get(term, 0) + 1

    def remove_document(self, doc_id: str) -> None:
        """Remove a document from the index.

        Parameters
        ----------
        doc_id : str
            Document identifier.
        """
        content = self._documents.pop(doc_id, "")
        if content:
            terms = set(self._tokenize(content))
            for term in terms:
                self._doc_frequencies[term] = max(
                    0, self._doc_frequencies.get(term, 1) - 1
                )

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.1,
    ) -> list[SearchResult]:
        """Search indexed documents for relevance to a query.

        Uses TF-IDF scoring.

        Parameters
        ----------
        query : str
            Search query.
        top_k : int
            Maximum results.
        min_score : float
            Minimum relevance score threshold.

        Returns
        -------
        list[SearchResult]
            Ranked search results.
        """
        self._total_searches += 1
        if not self._documents:
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        query_counts = Counter(query_terms)
        num_docs = len(self._documents)

        results: list[tuple[float, str, str]] = []

        for doc_id, content in self._documents.items():
            doc_terms = self._tokenize(content)
            doc_counts = Counter(doc_terms)
            doc_length = len(doc_terms) or 1

            score = 0.0
            matched_terms: list[str] = []

            for term, qty in query_counts.items():
                tf = doc_counts.get(term, 0) / doc_length
                idf = math.log(
                    (num_docs + 1) / (self._doc_frequencies.get(term, 1) + 1)
                ) + 1
                score += tf * idf * qty
                if tf > 0:
                    matched_terms.append(term)

            if score >= min_score:
                snippet = self._extract_snippet(content, matched_terms)
                results.append((score, doc_id, snippet))

        results.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchResult(
                source_id=doc_id,
                content=snippet[:500],
                score=round(score, 4),
                metadata={"matched_terms": matched_terms},
            )
            for score, doc_id, snippet in results[:top_k]
        ]

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase terms.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        list[str]
            Tokenized terms.
        """
        text = text.lower()
        tokens = re.findall(r"[a-zA-Z_]\w*", text)
        return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]

    def _extract_snippet(
        self, content: str, matched_terms: list[str]
    ) -> str:
        """Extract a relevant snippet from content.

        Parameters
        ----------
        content : str
            Full document content.
        matched_terms : list[str]
            Terms that matched.

        Returns
        -------
        str
            Relevant snippet up to 300 chars.
        """
        if not matched_terms:
            return content[:300]

        lower_content = content.lower()
        best_pos = 0
        best_count = 0

        for term in matched_terms:
            pos = lower_content.find(term.lower())
            if pos >= 0:
                count = sum(
                    1 for t in matched_terms
                    if t.lower() in lower_content[max(0, pos - 100):pos + 200]
                )
                if count > best_count:
                    best_count = count
                    best_pos = pos

        start = max(0, best_pos - 100)
        end = min(len(content), best_pos + 200)
        snippet = content[start:end]

        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet[:500]

    def clear(self) -> None:
        """Clear all indexed documents."""
        self._documents.clear()
        self._doc_frequencies.clear()

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def total_searches(self) -> int:
        return self._total_searches

    async def health_check(self) -> bool:
        return True
