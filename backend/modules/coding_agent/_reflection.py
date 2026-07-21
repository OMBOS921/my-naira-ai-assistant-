"""ReflectionEngine — analyzes task execution results for insights."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.reflection")


class ReflectionEngine:
    """Analyzes execution results to extract insights and improvements.

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
        self._reflection_history: list[dict[str, Any]] = []

    async def reflect(
        self,
        task_id: str,
        result: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform reflection on a task execution.

        Parameters
        ----------
        task_id : str
            Task identifier.
        result : dict[str, Any]
            Execution result.
        context : dict[str, Any]
            Execution context.

        Returns
        -------
        dict[str, Any]
            Reflection result with insights and recommendations.
        """
        status = result.get("status", "unknown")
        result.get("output", "")
        duration = result.get("duration_ms", 0)

        insights: list[str] = []
        if status == "completed":
            insights.append("Task completed successfully")
            if duration > 0:
                insights.append(f"Duration: {duration}ms")
        elif status == "failed":
            error = result.get("error", "Unknown error")
            insights.append(f"Task failed: {error}")

        improvements: list[str] = []
        if duration > 5000:
            improvements.append("Task took longer than expected — consider optimization")
        if status == "failed":
            improvements.append("Add error handling and retry logic")

        reflection = {
            "task_id": task_id,
            "success": status == "completed",
            "insights": insights,
            "improvements": improvements,
            "context_size": len(str(context)),
        }

        self._reflection_history.append(reflection)
        if len(self._reflection_history) > 100:
            self._reflection_history.pop(0)

        return reflection

    def get_history(self, max_items: int = 10) -> list[dict[str, Any]]:
        """Return recent reflection history."""
        return self._reflection_history[-max_items:]

    def clear_history(self) -> None:
        self._reflection_history.clear()
        self._logger.debug("Reflection history cleared")
