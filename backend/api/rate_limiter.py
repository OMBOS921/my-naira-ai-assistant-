"""
Rate Limiter using Token Bucket Algorithm.

Protects API endpoints and WebSockets from abuse.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Token bucket rate limiter per IP address."""

    def __init__(self, capacity: int = 100, refill_rate: float = 1.0) -> None:
        """
        :param capacity: Maximum burst capacity (tokens)
        :param refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        # Structure: IP -> {"tokens": float, "last_refill": float, "blocked_until": float}
        self._buckets: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"tokens": self.capacity, "last_refill": time.time(), "blocked_until": 0.0}
        )

    def consume(self, client_ip: str, tokens: int = 1) -> bool:
        """Attempt to consume tokens. Return True if allowed."""
        now = time.time()
        bucket = self._buckets[client_ip]

        # Check if blocked
        if bucket["blocked_until"] > now:
            return False

        # Refill tokens based on elapsed time
        elapsed = now - bucket["last_refill"]
        new_tokens = elapsed * self.refill_rate
        bucket["tokens"] = min(self.capacity, bucket["tokens"] + new_tokens)
        bucket["last_refill"] = now

        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            return True
        
        # Rate limit exceeded — block for 60 seconds if deeply exhausted
        if bucket["tokens"] < -10:
            bucket["blocked_until"] = now + 60.0
            
        return False


# Global instance
api_rate_limiter = RateLimiter(capacity=100, refill_rate=2.0)
ws_rate_limiter = RateLimiter(capacity=500, refill_rate=5.0)


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency to apply rate limiting to routes."""
    client_ip = request.client.host if request.client else "unknown"
    if not api_rate_limiter.consume(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down.",
        )
