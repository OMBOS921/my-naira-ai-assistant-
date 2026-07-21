"""
ToolProvider — abstract port for pluggable tool implementations.

20_Dependency_Rules.md §2 — Port/Adapter pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.modules.tools._definition import ToolDefinition

from backend.types import ToolResult


class ToolProvider(ABC):
    """Abstract port that concrete tool adapters must implement.

    Each tool registered in the system must have an associated
    ``ToolProvider`` that knows how to execute it.

    Parameters
    ----------
    definition : ToolDefinition
        The tool's static descriptor (name, schema, category, etc.).
    """

    def __init__(self, definition: object) -> None:
        self._definition: ToolDefinition = definition  # type: ignore[assignment]

    @property
    def definition(self) -> object:
        """Return the tool's static descriptor."""
        return self._definition

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given *arguments*.

        Parameters
        ----------
        arguments : dict[str, Any]
            Validated and sanitized input arguments.

        Returns
        -------
        ToolResult
            The result of the execution.
        """
        ...
