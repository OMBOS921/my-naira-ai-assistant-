"""ToolSelectionPort — interface for tool selection.

Defines the contract for selecting appropriate tools
for task execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolSelectionPort(ABC):
    """Port for tool selection.

    Selects appropriate tools for agent tasks.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the tool selector is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def select_tools(
        self,
        task_description: str,
        available_tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Select tools for a task.

        Parameters
        ----------
        task_description : str
            Task description.
        available_tools : list[dict[str, Any]]
            List of available tool definitions.

        Returns
        -------
        list[dict[str, Any]]
            Selected tools with confidence scores.
        """

    @abstractmethod
    async def rank_tools(
        self,
        task_description: str,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Rank tools by suitability.

        Parameters
        ----------
        task_description : str
            Task description.
        tools : list[dict[str, Any]]
            List of tool definitions.

        Returns
        -------
        list[dict[str, Any]]
            Ranked tool list with scores.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release tool selector resources."""
