"""RetryEngine — configurable retry policies for agent operations."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.retry")


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for agent operations.

    Parameters
    ----------
    max_retries : int
        Maximum number of retry attempts (default 3).
    base_delay : float
        Initial delay in seconds before first retry (default 1.0).
    max_delay : float
        Maximum delay between retries in seconds (default 30.0).
    backoff_multiplier : float
        Exponential backoff multiplier (default 2.0).
    retryable_exceptions : tuple[type[Exception], ...]
        Exception types that trigger a retry (default catches all).
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


class RetryEngine:
    """Executes operations with configurable retry policies.

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
        self._metrics: dict[str, dict[str, Any]] = {}

    async def execute(
        self,
        operation: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        policy: RetryPolicy | None = None,
    ) -> tuple[bool, Any, str]:
        """Execute an operation with retry logic.

        Parameters
        ----------
        operation : str
            Operation name for logging and metrics.
        coro_factory : callable
            Zero-argument callable returning an awaitable.
        policy : RetryPolicy | None
            Retry policy. Uses defaults if None.

        Returns
        -------
        tuple[bool, Any, str]
            (success, result, error_message)
        """
        policy = policy or RetryPolicy()
        attempts = 0
        last_error = ""

        for attempt in range(policy.max_retries + 1):
            attempts = attempt + 1
            try:
                result = await coro_factory()
                self._record_metrics(operation, attempts, True)
                return (True, result, "")
            except Exception as exc:
                last_error = str(exc)
                if not isinstance(exc, policy.retryable_exceptions):
                    self._logger.debug(
                        "Non-retryable exception for '%s': %s", operation, exc,
                    )
                    self._record_metrics(operation, attempts, False)
                    return (False, None, last_error)
                if attempt < policy.max_retries:
                    delay = min(
                        policy.base_delay * (policy.backoff_multiplier ** attempt),
                        policy.max_delay,
                    )
                    self._logger.debug(
                        "Retry %d/%d for '%s' in %.1fs",
                        attempt + 1, policy.max_retries, operation, delay,
                    )
                    await asyncio.sleep(delay)

        self._record_metrics(operation, attempts, False)
        return (False, None, last_error)

    def _record_metrics(self, operation: str, attempts: int, success: bool) -> None:
        if operation not in self._metrics:
            self._metrics[operation] = {
                "total_attempts": 0,
                "successes": 0,
                "failures": 0,
                "last_attempts": 0,
            }
        self._metrics[operation]["total_attempts"] += 1
        self._metrics[operation]["last_attempts"] = attempts
        if success:
            self._metrics[operation]["successes"] += 1
        else:
            self._metrics[operation]["failures"] += 1

    def get_metrics(self) -> dict[str, Any]:
        """Return retry metrics for all operations."""
        return dict(self._metrics)
