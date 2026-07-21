from __future__ import annotations

import logging
from typing import Any

from backend.modules.coding_agent.ports.task_planner_port import TaskPlannerPort

_LOG = logging.getLogger("naira.coding_agent.planner")


class DefaultTaskPlannerProvider(TaskPlannerPort):
    """Default provider for the Task Planner port.

    Provides basic task planning, decomposition, and prioritization.
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
        return "default_planner"

    async def plan_tasks(
        self,
        goal: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._logger.debug("Planning tasks for goal: %s", goal[:50])
        return {
            "goal": goal,
            "tasks": [
                {"id": "task_1", "description": f"Analyze: {goal}", "complexity": "medium"},
                {"id": "task_2", "description": f"Implement: {goal}", "complexity": "high"},
                {"id": "task_3", "description": "Verify implementation", "complexity": "low"},
            ],
            "task_dependencies": {"task_2": ["task_1"], "task_3": ["task_2"]},
            "estimated_complexity": "medium",
            "required_resources": ["file_system", "git"],
        }

    async def decompose_task(
        self,
        task_id: str,
        task_description: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._logger.debug("Decomposing task %s", task_id)
        return {
            "task_id": task_id,
            "subtasks": [
                {"id": f"{task_id}_sub_1", "description": f"Sub-task 1 of {task_description}"},
                {"id": f"{task_id}_sub_2", "description": f"Sub-task 2 of {task_description}"},
            ],
            "dependencies": {},
        }

    async def prioritize_tasks(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        def _complexity_key(t: dict[str, Any]) -> int:
            return {"high": 0, "medium": 1, "low": 2}.get(t.get("complexity", "medium"), 1)
        ordered = sorted(tasks, key=_complexity_key)
        return ordered

    async def close(self) -> None:
        self._available = False
        self._logger.info("Task planner provider closed")
