from __future__ import annotations

import logging
from typing import Any

from backend.modules.coding_agent.ports.agent_runtime_port import AgentRuntimePort

_LOG = logging.getLogger("naira.coding_agent.runtime")


class DefaultAgentRuntimeProvider(AgentRuntimePort):
    """Default provider for the Agent Runtime port.

    Manages the agent's execution lifecycle, including task execution,
    error recovery, and reflection.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "default_runtime"

    async def execute_task(
        self,
        task_id: str,
        task_description: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._logger.debug("Executing task %s: %s", task_id, task_description[:50])
        return {
            "task_id": task_id,
            "status": "completed",
            "output": f"Executed: {task_description}",
        }

    async def handle_error(
        self,
        task_id: str,
        error: Exception,
        retries: int,
    ) -> tuple[bool, str]:
        self._logger.warning("Error handling task %s (retry %d): %s", task_id, retries, error)
        if retries < 3:
            return (True, "retry")
        return (False, "abort")

    async def reflect_on_execution(
        self,
        task_id: str,
        result: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "success": result.get("status") == "completed",
            "insights": [],
            "improvements": [],
        }

    async def close(self) -> None:
        self._available = False
        self._logger.info("Agent runtime provider closed")
