"""Context Statistics — tracks and reports statistics about context usage.

Collects and analyses usage data including context builds, token counts,
compression ratios, cache performance, and search patterns.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from backend.modules.context_intelligence._types import ContextStatistics

_LOG = logging.getLogger("naira.context_intelligence.context_statistics")

_MAX_HISTORY = 1000


class ContextStatisticsTracker:
    """Tracks context usage statistics for analysis and monitoring.

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
        self._total_contexts_built = 0
        self._total_tokens_processed = 0
        self._total_compressions = 0
        self._total_chunks_created = 0
        self._total_searches = 0
        self._total_cache_hits = 0
        self._total_cache_misses = 0
        self._total_navigations = 0
        self._build_times: deque[float] = deque(maxlen=_MAX_HISTORY)
        self._search_times: deque[float] = deque(maxlen=_MAX_HISTORY)
        self._compression_ratios: deque[float] = deque(maxlen=_MAX_HISTORY)
        self._token_counts: deque[int] = deque(maxlen=_MAX_HISTORY)

    def record_context_built(self, token_count: int, duration_ms: float) -> None:
        """Record a context build event.

        Parameters
        ----------
        token_count : int
            Number of tokens in the built context.
        duration_ms : float
            Build duration in milliseconds.
        """
        self._total_contexts_built += 1
        self._total_tokens_processed += token_count
        self._build_times.append(duration_ms)
        self._token_counts.append(token_count)

    def record_compression(self, original_tokens: int, compressed_tokens: int) -> None:
        """Record a compression event.

        Parameters
        ----------
        original_tokens : int
            Token count before compression.
        compressed_tokens : int
            Token count after compression.
        """
        self._total_compressions += 1
        ratio = compressed_tokens / max(original_tokens, 1)
        self._compression_ratios.append(ratio)

    def record_chunks_created(self, count: int) -> None:
        """Record chunk creation.

        Parameters
        ----------
        count : int
            Number of chunks created.
        """
        self._total_chunks_created += count

    def record_search(self, duration_ms: float) -> None:
        """Record a search event.

        Parameters
        ----------
        duration_ms : float
            Search duration in milliseconds.
        """
        self._total_searches += 1
        self._search_times.append(duration_ms)

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self._total_cache_hits += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self._total_cache_misses += 1

    def record_navigation(self) -> None:
        """Record a cross-file navigation event."""
        self._total_navigations += 1

    def snapshot(self) -> ContextStatistics:
        """Return a snapshot of current statistics.

        Returns
        -------
        ContextStatistics
            Current statistics snapshot.
        """
        avg_build = (
            sum(self._build_times) / len(self._build_times)
            if self._build_times else 0.0
        )
        avg_search = (
            sum(self._search_times) / len(self._search_times)
            if self._search_times else 0.0
        )
        avg_ratio = (
            sum(self._compression_ratios) / len(self._compression_ratios)
            if self._compression_ratios else 1.0
        )

        return ContextStatistics(
            total_contexts_built=self._total_contexts_built,
            total_tokens_processed=self._total_tokens_processed,
            total_compressions=self._total_compressions,
            total_chunks_created=self._total_chunks_created,
            total_searches=self._total_searches,
            total_cache_hits=self._total_cache_hits,
            total_cache_misses=self._total_cache_misses,
            total_navigations=self._total_navigations,
            avg_build_time_ms=round(avg_build, 2),
            avg_search_time_ms=round(avg_search, 2),
            compression_ratio=round(avg_ratio, 4),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return statistics as a dictionary.

        Returns
        -------
        dict[str, Any]
            Statistics dictionary for serialisation.
        """
        stats = self.snapshot()
        return {
            "total_contexts_built": stats.total_contexts_built,
            "total_tokens_processed": stats.total_tokens_processed,
            "total_compressions": stats.total_compressions,
            "total_chunks_created": stats.total_chunks_created,
            "total_searches": stats.total_searches,
            "total_cache_hits": stats.total_cache_hits,
            "total_cache_misses": stats.total_cache_misses,
            "total_navigations": stats.total_navigations,
            "avg_build_time_ms": stats.avg_build_time_ms,
            "avg_search_time_ms": stats.avg_search_time_ms,
            "compression_ratio": stats.compression_ratio,
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self._total_contexts_built = 0
        self._total_tokens_processed = 0
        self._total_compressions = 0
        self._total_chunks_created = 0
        self._total_searches = 0
        self._total_cache_hits = 0
        self._total_cache_misses = 0
        self._total_navigations = 0
        self._build_times.clear()
        self._search_times.clear()
        self._compression_ratios.clear()
        self._token_counts.clear()

    async def health_check(self) -> bool:
        return True
