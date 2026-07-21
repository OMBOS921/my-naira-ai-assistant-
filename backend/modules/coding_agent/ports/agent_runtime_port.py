"""AgentRuntimePort — interface for the agent runtime engine.

Defines the contract for managing the agent's execution lifecycle,
including task execution, error recovery, and reflection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentRuntimePort(ABC):
    """Port for the agent runtime engine.

    Manages agent lifecycle, task execution, and error recovery.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the runtime is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def execute_task(
        self,
        task_id: str,
        task_description: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single task.

        Parameters
        ----------
        task_id : str
            Unique task identifier.
        task_description : str
            Description of the task to execute.
        context : dict[str, Any]
            Execution context including variables, tools, etc.

        Returns
        -------
        dict[str, Any]
            Task execution results.

        Raises
        ------
        AgentTimeoutError
            If task execution exceeds timeout.
        AgentRuntimeError
            If task execution fails.
        """

    @abstractmethod
    async def handle_error(
        self,
        task_id: str,
        error: Exception,
        retries: int,
    ) -> tuple[bool, str]:
        """Handle an error during task execution.

        Parameters
        ----------
        task_id : str
            Task identifier where error occurred.
        error : Exception
            The exception that occurred.
        retries : int
            Current retry count.

        Returns
        -------
        tuple[bool, str]
            (retry, action) - whether to retry and what action to take.
        """

    @abstractmethod
    async def reflect_on_execution(
        self,
        task_id: str,
        result: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Perform reflection on task execution.

        Parameters
        ----------
        task_id : str
            Task identifier that was executed.
        result : dict[str, Any]
            Result of the task execution.
        context : dict[str, Any]
            Execution context.

        Returns
        -------
        dict[str, Any]
            Reflection results including insights, learnings.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release runtime resources."""
