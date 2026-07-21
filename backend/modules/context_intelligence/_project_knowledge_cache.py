"""Project Knowledge Cache — caches project analysis results for reuse.

Maintains an in-memory cache of project-level knowledge with optional
persistence, enabling fast retrieval of previously computed results.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("naira.context_intelligence.project_knowledge_cache")


class ProjectKnowledgeCache:
    """Caches project knowledge with TTL-based expiry.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    ttl_seconds : int
        Time-to-live for cache entries in seconds (default 300).
    max_entries : int
        Maximum number of cache entries (default 1000).
    persist_path : Path | str | None
        Optional path for persisting cache to disk.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        ttl_seconds: int = 300,
        max_entries: int = 1000,
        persist_path: Path | str | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._persist_path = Path(persist_path) if persist_path else None
        self._cache: dict[str, tuple[float, Any]] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Retrieve a value from the cache.

        Parameters
        ----------
        key : str
            Cache key.

        Returns
        -------
        Any | None
            Cached value if found and not expired, else None.
        """
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        timestamp, value = entry
        if time.monotonic() - timestamp > self._ttl:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache.

        Parameters
        ----------
        key : str
            Cache key.
        value : Any
            Value to cache.
        """
        if len(self._cache) >= self._max_entries:
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest]

        self._cache[key] = (time.monotonic(), value)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry from the cache.

        Parameters
        ----------
        key : str
            Cache key to invalidate.
        """
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    async def persist(self) -> None:
        """Persist cache to disk if a path is configured."""
        if self._persist_path is None:
            return
        try:
            serializable: dict[str, Any] = {}
            for key, (ts, value) in self._cache.items():
                try:
                    json.dumps(value)
                    serializable[key] = {"ts": ts, "value": value}
                except (TypeError, ValueError):
                    pass
            self._persist_path.write_text(
                json.dumps(serializable, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            self._logger.warning("Failed to persist cache: %s", exc)

    async def load_persisted(self) -> None:
        """Load cache from disk if a path is configured."""
        if self._persist_path is None or not self._persist_path.exists():
            return
        try:
            raw = self._persist_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            now = time.monotonic()
            for key, entry in data.items():
                ts = entry.get("ts", now)
                if now - ts <= self._ttl:
                    self._cache[key] = (ts, entry["value"])
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            self._logger.warning("Failed to load persisted cache: %s", exc)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": self.size,
            "hit_rate": round(self._hits / max(total, 1) * 100, 1),
            "ttl_seconds": self._ttl,
            "max_entries": self._max_entries,
        }

    async def health_check(self) -> bool:
        return True
