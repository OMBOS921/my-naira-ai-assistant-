"""CodingAgentExecutor — timeout-managed execution for agent operations."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from backend.types import ToolResult

_LOG = logging.getLogger("naira.coding_agent.executor")


class CodingAgentExecutor:
    """Wraps provider calls with timeout handling and graceful degradation.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    default_timeout : float
        Default timeout in seconds for operations (default 60.0).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        default_timeout: float = 60.0,
    ) -> None:
        self._logger = logger or _LOG
        self._default_timeout = default_timeout
        self._degraded: bool = False

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True

    async def execute(
        self,
        operation: str,
        coro: asyncio.Future | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute an async operation with timeout handling.

        Parameters
        ----------
        operation : str
            Operation name for logging.
        coro : asyncio.Future | None
            Awaitable coroutine to execute.
        timeout : float | None
            Timeout in seconds. Falls back to default.

        Returns
        -------
        ToolResult
        """
        if self._degraded:
            return ToolResult(
                status="error",
                error=f"CodingAgentExecutor is degraded — cannot execute '{operation}'",
            )
        if coro is None:
            return ToolResult(
                status="error",
                error=f"No coroutine provided for '{operation}'",
            )
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            result = await asyncio.wait_for(coro, timeout=effective_timeout)
            if isinstance(result, ToolResult):
                return result
            return ToolResult(status="success", output=str(result))
        except asyncio.TimeoutError:
            self._logger.warning("Operation '%s' timed out after %ss", operation, effective_timeout)
            return ToolResult(
                status="timeout",
                error=f"Operation '{operation}' timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.error("Operation '%s' failed: %s", operation, exc)
            return ToolResult(
                status="error",
                error=f"Operation '{operation}' failed: {exc}",
            )

    async def execute_with_retry(
        self,
        operation: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        timeout: float | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> ToolResult:
        """Execute with retry logic and exponential backoff.

        Parameters
        ----------
        operation : str
            Operation name for logging.
        coro_factory : callable
            Zero-argument callable that returns an awaitable.
        timeout : float | None
            Timeout per attempt.
        max_retries : int
            Maximum retry count.
        base_delay : float
            Base delay in seconds.
        max_delay : float
            Maximum delay in seconds.

        Returns
        -------
        ToolResult
        """
        last_error: str = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                self._logger.debug(
                    "Retry %d/%d for '%s' after %.1fs",
                    attempt, max_retries, operation, delay,
                )
                await asyncio.sleep(delay)
            try:
                coro = coro_factory()
                result = await self.execute(operation, coro, timeout)
                if result.status == "success":
                    return result
                last_error = result.error or ""
                if attempt < max_retries:
                    self._logger.debug("Retrying '%s' (attempt %d failed)", operation, attempt)
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    self._logger.debug("Retrying '%s' after error: %s", operation, exc)
        return ToolResult(
            status="error",
            error=f"Operation '{operation}' failed after {max_retries} retries: {last_error}",
        )
