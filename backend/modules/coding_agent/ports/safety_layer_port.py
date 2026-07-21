"""SafetyLayerPort — interface for the safety layer.

Defines the contract for security validation and sandboxing
of agent operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SafetyLayerPort(ABC):
    """Port for the safety layer.

    Validates operations for security and sandboxing.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the safety layer is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def validate_command(
        self,
        command: str,
        args: list[str],
    ) -> tuple[bool, str | None]:
        """Validate a command for safety.

        Parameters
        ----------
        command : str
            Command to execute.
        args : list[str]
            Command arguments.

        Returns
        -------
        tuple[bool, str | None]
            (allowed, reason) - whether command is allowed.
        """

    @abstractmethod
    async def validate_file_operation(
        self,
        operation: str,
        path: str,
    ) -> tuple[bool, str | None]:
        """Validate a file operation.

        Parameters
        ----------
        operation : str
            Operation type (read, write, delete).
        path : str
            File path.

        Returns
        -------
        tuple[bool, str | None]
            (allowed, reason) - whether operation is allowed.
        """

    @abstractmethod
    async def validate_git_operation(
        self,
        operation: str,
        args: list[str],
    ) -> tuple[bool, str | None]:
        """Validate a Git operation.

        Parameters
        ----------
        operation : str
            Git operation (commit, push, pull).
        args : list[str]
            Operation arguments.

        Returns
        -------
        tuple[bool, str | None]
            (allowed, reason) - whether operation is allowed.
        """

    @abstractmethod
    async def validate_network_access(
        self,
        url: str,
    ) -> tuple[bool, str | None]:
        """Validate network access request.

        Parameters
        ----------
        url : str
            URL to access.

        Returns
        -------
        tuple[bool, str | None]
            (allowed, reason) - whether access is allowed.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release safety layer resources."""
