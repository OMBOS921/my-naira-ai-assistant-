"""ErrorRecovery — handles non-fatal errors with recovery strategies."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.recovery")


class ErrorRecovery:
    """Manages recovery strategies for non-fatal agent errors.

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
        self._recovery_attempts: dict[str, int] = {}

    async def attempt_recovery(
        self,
        task_id: str,
        error: Exception,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Attempt to recover from an error.

        Parameters
        ----------
        task_id : str
            Task identifier.
        error : Exception
            The exception that occurred.
        context : dict[str, Any]
            Execution context.

        Returns
        -------
        dict[str, Any]
            Recovery plan with:
            - recoverable: bool
            - strategy: str
            - actions: list[str]
            - retry_count: int
        """
        error_type = type(error).__name__
        error_msg = str(error)
        attempts = self._recovery_attempts.get(task_id, 0) + 1
        self._recovery_attempts[task_id] = attempts

        recovery_strategies: list[tuple[str, list[str]]] = []

        if "timeout" in error_type.lower() or "timeout" in error_msg.lower():
            recovery_strategies.append((
                "increase_timeout",
                ["Retry with increased timeout", "Consider splitting the task"],
            ))

        if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
            recovery_strategies.append((
                "create_resource",
                ["Create the missing resource", "Verify the path exists"],
            ))

        if "permission" in error_msg.lower() or "denied" in error_msg.lower():
            recovery_strategies.append((
                "request_permission",
                ["Request elevated permissions", "Use an alternative approach"],
            ))

        if "connection" in error_msg.lower() or "network" in error_msg.lower():
            recovery_strategies.append((
                "retry_network",
                ["Retry the network operation", "Check network connectivity"],
            ))

        recovery_strategies.append((
            "abort",
            [f"Cannot recover from {error_type}: {error_msg}"],
        ))

        strategy, actions = recovery_strategies[0]
        recoverable = strategy != "abort" and attempts <= 3

        return {
            "recoverable": recoverable,
            "strategy": strategy,
            "actions": actions,
            "retry_count": attempts,
            "error_type": error_type,
        }

    def reset(self, task_id: str) -> None:
        self._recovery_attempts.pop(task_id, None)
