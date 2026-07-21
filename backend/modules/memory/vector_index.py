"""
VectorIndex — lightweight JSON-based keyword index.

21_System_Contracts.md §16.1 — Semantic Index (JSON + NumPy).
21_System_Contracts.md §16.5 — No vector server.

Internal module; not exported from ``__init__.py``.

Uses simple keyword overlap scoring.  No NumPy dependency required.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any


class VectorIndex:
    """Lightweight keyword-based semantic index backed by JSON.

    Stores keyword→document mappings in a JSON file.  Search uses
    TF-IDF-style scoring based on keyword overlap.

    Parameters
    ----------
    index_path : Path | str
        Filesystem path to the JSON index file.
    """

    def __init__(self, index_path: Path | str) -> None:
        self._index_path = Path(index_path)
        self._documents: dict[str, dict[str, Any]] = {}
        self._modified: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the index from the JSON file.

        If the file does not exist, starts with an empty index.
        """
        if self._index_path.exists():
            with self._index_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._documents = data.get("documents", {})
        else:
            self._documents = {}
        self._modified = False

    def save(self) -> None:
        """Persist the index to the JSON file."""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "version": 1,
            "documents": self._documents,
        }
        with self._index_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._modified = False

    @property
    def is_loaded(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Index operations
    # ------------------------------------------------------------------

    def index(self, keywords: list[str], source_id: str) -> None:
        """Associate *keywords* with a *source_id*.

        Parameters
        ----------
        keywords : list[str]
            Extracted keywords to index.
        source_id : str
            Unique identifier for the source document.
        """
        existing = self._documents.get(source_id, {})
        existing_keywords = set(existing.get("keywords", []))
        existing_keywords.update(k.lower().strip() for k in keywords if k.strip())

        self._documents[source_id] = {
            "keywords": sorted(existing_keywords),
            "updated_at": time.time(),
        }
        self._modified = True

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the index for documents matching *query*.

        Parameters
        ----------
        query : str
            Natural-language query string.
        top_k : int
            Maximum number of results.

        Returns
        -------
        list[dict[str, Any]]
            Each dict contains ``source_id``, ``score``, and
            ``matched_keywords``.
        """
        if not self._documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        query_counter = Counter(query_tokens)
        results: list[dict[str, Any]] = []

        num_docs = len(self._documents)
        doc_freq: Counter[str] = Counter()
        for doc in self._documents.values():
            for kw in set(doc.get("keywords", [])):
                doc_freq[kw] += 1

        for source_id, doc in self._documents.items():
            doc_keywords = doc.get("keywords", [])
            doc_counter = Counter(doc_keywords)

            overlap = query_counter & doc_counter
            if not overlap:
                continue

            tfidf_score = 0.0
            for term, count in overlap.items():
                tf = count / max(len(doc_keywords), 1)
                idf = math.log((num_docs + 1) / (doc_freq.get(term, 0) + 1)) + 1
                tfidf_score += tf * idf

            results.append({
                "source_id": source_id,
                "score": round(tfidf_score, 4),
                "matched_keywords": list(overlap.keys()),
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    def remove(self, source_id: str) -> bool:
        """Remove a document from the index.

        Returns ``True`` if the document existed.
        """
        if source_id in self._documents:
            del self._documents[source_id]
            self._modified = True
            return True
        return False

    def clear(self) -> None:
        """Remove all entries from the index."""
        self._documents.clear()
        self._modified = True

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def is_modified(self) -> bool:
        return self._modified

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split *text* into lowercase keyword tokens."""
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        return [t for t in tokens if len(t) >= 2]
