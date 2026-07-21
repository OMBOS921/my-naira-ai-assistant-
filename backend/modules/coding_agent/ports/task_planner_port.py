"""TaskPlannerPort — interface for task planning.

Defines the contract for planning tasks, creating task graphs,
and managing task dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TaskPlannerPort(ABC):
    """Port for task planning.

    Plans and organizes agent tasks.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the planner is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def plan_tasks(
        self,
        goal: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Plan tasks for a goal.

        Parameters
        ----------
        goal : str
            The goal to achieve.
        context : dict[str, Any]
            Execution context.

        Returns
        -------
        dict[str, Any]
            Plan with:
            - tasks: list[dict[str, Any]]
            - task_dependencies: dict[str, list[str]]
            - estimated_complexity: str
            - required_resources: list[str]
        """

    @abstractmethod
    async def decompose_task(
        self,
        task_id: str,
        task_description: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Decompose a task into subtasks.

        Parameters
        ----------
        task_id : str
            Task identifier.
        task_description : str
            Task description.
        context : dict[str, Any]
            Execution context.

        Returns
        -------
        dict[str, Any]
            Decomposition with:
            - subtasks: list[dict[str, Any]]
            - dependencies: dict[str, list[str]]
        """

    @abstractmethod
    async def prioritize_tasks(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Prioritize tasks by importance.

        Parameters
        ----------
        tasks : list[dict[str, Any]]
            List of task definitions.

        Returns
        -------
        list[dict[str, Any]]
            Prioritized task list.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release planner resources."""
