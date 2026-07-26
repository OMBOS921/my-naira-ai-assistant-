"""
CapabilityCache — Thread-safe TTL cache for local machine capabilities.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityInfo,
    CapabilityStatus,
)

_LOG = logging.getLogger("naira.capability.cache")

# Default TTL configuration by category (in seconds)
DEFAULT_CATEGORY_TTLS: dict[CapabilityCategory | str, float] = {
    CapabilityCategory.SYSTEM: 30.0,
    CapabilityCategory.NETWORK: 10.0,
    CapabilityCategory.PERIPHERAL: 15.0,
    CapabilityCategory.SOFTWARE: 600.0,
    CapabilityCategory.BROWSER: 300.0,
    CapabilityCategory.RUNTIME: 300.0,
    CapabilityCategory.HARDWARE: 120.0,
    CapabilityCategory.AI: 60.0,
}


class CapabilityCache:
    """Thread-safe TTL cache store for real-time capability information."""

    def __init__(
        self,
        default_ttl: float = 300.0,
        category_ttls: dict[CapabilityCategory | str, float] | None = None,
    ) -> None:
        self._default_ttl = default_ttl
        self._category_ttls = dict(DEFAULT_CATEGORY_TTLS)
        if category_ttls:
            self._category_ttls.update(category_ttls)

        self._lock = threading.RLock()
        self._store: dict[str, CapabilityInfo] = {}

    def get_ttl_for_category(self, category: CapabilityCategory | str) -> float:
        """Return the default TTL for a category."""
        return self._category_ttls.get(category, self._default_ttl)

    def set(self, info: CapabilityInfo) -> None:
        """Store a capability info snapshot in cache."""
        with self._lock:
            self._store[info.name] = info
            _LOG.debug("Cached capability '%s' (status: %s)", info.name, info.status)

    def get(self, name: str, allow_stale: bool = False) -> CapabilityInfo | None:
        """Retrieve capability info if present and non-stale (unless allow_stale=True)."""
        with self._lock:
            info = self._store.get(name)
            if info is None:
                return None
            if not allow_stale and info.is_stale():
                _LOG.debug("Capability '%s' is stale in cache", name)
                return None
            return info

    def has(self, name: str, allow_stale: bool = False) -> bool:
        """Return True if capability is cached and valid."""
        return self.get(name, allow_stale=allow_stale) is not None

    def invalidate(self, name: str) -> bool:
        """Remove a capability from cache."""
        with self._lock:
            if name in self._store:
                del self._store[name]
                _LOG.debug("Invalidated capability '%s'", name)
                return True
            return False

    def clear(self) -> None:
        """Clear all cached capabilities."""
        with self._lock:
            self._store.clear()
            _LOG.debug("Capability cache cleared")

    def get_all(self, allow_stale: bool = False) -> list[CapabilityInfo]:
        """Return snapshot of all cached capability entries."""
        with self._lock:
            if allow_stale:
                return list(self._store.values())
            now = time.time()
            return [info for info in self._store.values() if not info.is_stale(now)]

    def query(
        self,
        *,
        category: CapabilityCategory | str | None = None,
        min_confidence: float = 0.0,
        status: CapabilityStatus | None = None,
        allow_stale: bool = False,
        filter_func: Callable[[CapabilityInfo], bool] | None = None,
    ) -> list[CapabilityInfo]:
        """Query cached capability records matching criteria."""
        category_val = (
            category.value if isinstance(category, CapabilityCategory) else category
        )

        with self._lock:
            results: list[CapabilityInfo] = []
            now = time.time()
            for info in self._store.values():
                if not allow_stale and info.is_stale(now):
                    continue
                if category_val is not None:
                    info_cat = (
                        info.category.value
                        if isinstance(info.category, CapabilityCategory)
                        else info.category
                    )
                    if info_cat != category_val:
                        continue
                if info.confidence < min_confidence:
                    continue
                if status is not None and info.status != status:
                    continue
                if filter_func is not None and not filter_func(info):
                    continue
                results.append(info)
            return results
