"""
ProviderHealthTracker — health, latency, rate limits, and recovery policy.

Requirements:
- Track provider health (0-100 score).
- Track latency (EWMA & min/max/average).
- Track recent failures and error history.
- Track rate limits and cooldown timers.
- Expose health metrics: provider_name, health_score, average_latency, success_rate, last_failure, current_status.
- Circuit breaker state machine (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderStatus(Enum):
    """Current operational status of a provider."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    UNHEALTHY = "UNHEALTHY"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    OFFLINE = "OFFLINE"


@dataclass
class ProviderHealthMetrics:
    """Exposed health metrics for a provider as required by specifications.

    Parameters
    ----------
    provider_name : str
    health_score : float (0.0 to 100.0)
    average_latency : float (in ms)
    success_rate : float (0.0 to 100.0)
    last_failure : str
    current_status : str
    """

    provider_name: str
    health_score: float
    average_latency: float
    success_rate: float
    last_failure: str
    current_status: str


class ProviderHealthTracker:
    """Tracks health metrics, latency EWMA, error window, rate limits, and circuit breaker."""

    def __init__(
        self,
        provider_name: str,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        latency_alpha: float = 0.2,
    ) -> None:
        self.provider_name = provider_name
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._latency_alpha = latency_alpha

        # Request stats
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0

        # Latency stats (ms)
        self.average_latency_ms: float = 0.0
        self.min_latency_ms: float = 0.0
        self.max_latency_ms: float = 0.0

        # Circuit breaker & rate limiting
        self._circuit_open: bool = False
        self._half_open: bool = False
        self._circuit_opened_at: float = 0.0
        self._rate_limited_until: float = 0.0

        # Error tracking
        self.last_failure: str = ""
        self.last_failure_time: float = 0.0
        self.last_failure_category: str = ""
        self.failure_history: list[dict[str, Any]] = []

    @property
    def current_status(self) -> ProviderStatus:
        """Evaluate provider status dynamically based on circuit state, rate limit, and failure count."""
        now = time.time()
        if self._circuit_open:
            if now - self._circuit_opened_at >= self._cooldown_seconds:
                return ProviderStatus.DEGRADED  # HALF_OPEN / probing
            return ProviderStatus.CIRCUIT_OPEN

        if now < self._rate_limited_until:
            return ProviderStatus.RATE_LIMITED

        if self.consecutive_failures >= self._failure_threshold:
            return ProviderStatus.UNHEALTHY

        if self.consecutive_failures > 0:
            return ProviderStatus.DEGRADED

        return ProviderStatus.HEALTHY

    @property
    def is_available(self) -> bool:
        """Check if provider is available for requests or probing."""
        status = self.current_status
        if status in (ProviderStatus.CIRCUIT_OPEN, ProviderStatus.RATE_LIMITED, ProviderStatus.OFFLINE):
            return False
        return True

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is in half-open state ready to probe."""
        now = time.time()
        return self._circuit_open and (now - self._circuit_opened_at >= self._cooldown_seconds)

    @property
    def success_rate(self) -> float:
        """Calculate percentage of successful requests."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0

    @property
    def health_score(self) -> float:
        """Calculate dynamic health score between 0.0 and 100.0."""
        status = self.current_status
        if status == ProviderStatus.CIRCUIT_OPEN:
            return 0.0

        score = self.success_rate

        # Consecutive failure penalty
        score -= min(60.0, self.consecutive_failures * 20.0)

        # Rate limit penalty
        if status == ProviderStatus.RATE_LIMITED:
            score -= 40.0

        # Latency penalty if average latency > 2000ms
        if self.average_latency_ms > 2000.0:
            excess = (self.average_latency_ms - 2000.0) / 100.0
            score -= min(20.0, excess)

        return max(0.0, min(100.0, round(score, 2)))

    def record_success(self, duration_ms: float) -> None:
        """Record a successful request, update latency EWMA, and reset circuit if probing."""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1

        # Reset circuit breaker
        self._circuit_open = False
        self._half_open = False

        # Update latency
        if self.average_latency_ms == 0.0:
            self.average_latency_ms = duration_ms
            self.min_latency_ms = duration_ms
            self.max_latency_ms = duration_ms
        else:
            self.average_latency_ms = (
                self._latency_alpha * duration_ms
                + (1.0 - self._latency_alpha) * self.average_latency_ms
            )
            self.min_latency_ms = min(self.min_latency_ms, duration_ms)
            self.max_latency_ms = max(self.max_latency_ms, duration_ms)

    def record_failure(self, error_message: str, category: str, cooldown: float | None = None) -> None:
        """Record a request failure, increment error counts, and trip circuit if threshold exceeded."""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0

        now = time.time()
        self.last_failure = error_message
        self.last_failure_time = now
        self.last_failure_category = category

        self.failure_history.append({
            "timestamp": now,
            "error": error_message,
            "category": category,
        })
        if len(self.failure_history) > 50:
            self.failure_history.pop(0)

        # Rate limit handling
        if category == "RATE_LIMITED":
            cooldown_time = cooldown if cooldown is not None else self._cooldown_seconds
            self._rate_limited_until = max(self._rate_limited_until, now + cooldown_time)

        # Auth error or consecutive failure threshold -> trip circuit breaker immediately
        if category == "AUTH_ERROR" or self.consecutive_failures >= self._failure_threshold:
            self._circuit_open = True
            self._circuit_opened_at = now

    def reset(self) -> None:
        """Reset health metrics and circuit state."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self._circuit_open = False
        self._half_open = False
        self._rate_limited_until = 0.0

    def get_metrics(self) -> ProviderHealthMetrics:
        """Return exposed health metrics dataclass as required by system spec."""
        return ProviderHealthMetrics(
            provider_name=self.provider_name,
            health_score=self.health_score,
            average_latency=round(self.average_latency_ms, 2),
            success_rate=round(self.success_rate, 2),
            last_failure=self.last_failure or "None",
            current_status=self.current_status.value,
        )
