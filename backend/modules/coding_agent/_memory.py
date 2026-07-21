"""AgentMemory — in-memory agent context and state management."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.memory")


class AgentMemory:
    """Ephemeral agent-specific memory for context and state tracking.

    Stores task results, conversation context, and agent state.
    Uses an LRU-style eviction policy.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    max_entries : int
        Maximum number of memory entries (default 1000).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        max_entries: int = 1000,
    ) -> None:
        self._logger = logger or _LOG
        self._max_entries = max_entries
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._degraded: bool = False

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def size(self) -> int:
        return len(self._store)

    def store(self, key: str, value: dict[str, Any]) -> None:
        if self._degraded:
            self._logger.warning("AgentMemory is degraded — skipping store for '%s'", key)
            return
        if len(self._store) >= self._max_entries:
            self._store.popitem(last=False)
        value["_timestamp"] = time.time()
        self._store[key] = value
        self._logger.debug("Stored memory: %s", key)

    def retrieve(self, key: str) -> dict[str, Any] | None:
        if key in self._store:
            self._store.move_to_end(key)
            return dict(self._store[key])
        return None

    def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        query_lower = query.lower()
        results: list[dict[str, Any]] = []
        for key, value in reversed(list(self._store.items())):
            if len(results) >= max_results:
                break
            content = f"{key} {value}".lower()
            if query_lower in content:
                entry = dict(value)
                entry["_key"] = key
                results.append(entry)
        return results

    def clear(self) -> None:
        self._store.clear()
        self._logger.debug("Agent memory cleared")

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("AgentMemory marked degraded")

    def metrics(self) -> dict[str, Any]:
        return {
            "size": len(self._store),
            "max_entries": self._max_entries,
            "usage_pct": round(len(self._store) / max(self._max_entries, 1) * 100, 1),
            "degraded": self._degraded,
        }
