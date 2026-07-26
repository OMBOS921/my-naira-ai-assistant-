"""
In-memory LRU Response Cache with TTL expiration for LLM Manager.

Provides cost & latency optimization by serving duplicate queries instantly (<50ms).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any

from backend.types import LLMResponse, Message, ToolDef

_LOG = logging.getLogger("naira.llm.cache")


class LLMResponseCache:
    """Fast, in-memory LRU cache with TTL for LLM provider responses.

    Parameters
    ----------
    max_size : int
        Maximum number of cached entries (default 128).
    ttl_seconds : float
        Time-to-live for cache entries in seconds (default 60.0).
    logger : logging.Logger | None
        Optional logger instance.
    """

    def __init__(
        self,
        max_size: int = 128,
        ttl_seconds: float = 60.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._logger = logger or _LOG
        # Stores key -> (expiry_time, LLMResponse)
        self._cache: OrderedDict[str, tuple[float, LLMResponse]] = OrderedDict()

    def _make_key(
        self,
        prompt: str,
        context: list[Message] | None = None,
        tools: list[ToolDef] | None = None,
    ) -> str:
        """Create a deterministic SHA-256 cache key from request parameters."""
        ctx_list = []
        if context:
            for m in context:
                ctx_list.append(f"{m.role}:{m.content}")
        
        tool_list = []
        if tools:
            for t in tools:
                tool_list.append(t.name)

        raw = json.dumps({
            "prompt": prompt.strip().lower(),
            "context": ctx_list,
            "tools": sorted(tool_list),
        }, sort_keys=True)

        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        prompt: str,
        context: list[Message] | None = None,
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse | None:
        """Retrieve a cached response if valid and not expired."""
        key = self._make_key(prompt, context, tools)
        if key not in self._cache:
            return None

        expiry, response = self._cache[key]
        now = time.time()
        if now > expiry:
            self._logger.debug("[CACHE EXPIRED] Evicting stale entry for key %s", key[:8])
            del self._cache[key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._logger.info("[CACHE HIT] Serving cached LLM response for query (key=%s)", key[:8])

        # Return cached response with updated latency & provider tag
        return LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls,
            finish_reason=response.finish_reason,
            token_usage=response.token_usage,
            provider="cache",
            duration_ms=2.0,
        )

    def put(
        self,
        prompt: str,
        context: list[Message] | None,
        tools: list[ToolDef] | None,
        response: LLMResponse,
    ) -> None:
        """Store an LLM response in the cache."""
        if not response or not response.text or response.provider == "cache":
            return

        key = self._make_key(prompt, context, tools)
        now = time.time()
        expiry = now + self._ttl_seconds

        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (expiry, response)

        # Evict oldest if exceeding max_size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

        self._logger.debug("[CACHE PUT] Cached response for key %s (ttl=%.0fs)", key[:8], self._ttl_seconds)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)
