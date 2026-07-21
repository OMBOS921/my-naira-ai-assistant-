"""CommandExecutorPort — interface for command execution.

Defines the contract for executing shell commands with proper
sandboxing, timeout, and output capture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CommandExecutorPort(ABC):
    """Port for command execution.

    Executes shell commands safely with proper sandboxing.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the executor is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def execute(
        self,
        command: str | list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Execute a command.

        Parameters
        ----------
        command : str | list[str]
            Command to execute.
        cwd : str | None
            Working directory for command execution.
        env : dict[str, str] | None
            Environment variables for the process.
        timeout : float
            Command timeout in seconds.

        Returns
        -------
        dict[str, Any]
            Execution result with:
            - success: bool
            - output: str
            - error: str
            - return_code: int
            - duration_ms: float
        """

    @abstractmethod
    async def close(self) -> None:
        """Release executor resources."""
