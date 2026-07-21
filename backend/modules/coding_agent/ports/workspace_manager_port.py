"""WorkspaceManagerPort — interface for workspace management.

Defines the contract for managing agent workspaces,
including creation, cleanup, and state persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WorkspaceManagerPort(ABC):
    """Port for workspace management.

    Manages agent workspace lifecycle.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the workspace manager is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def create_workspace(
        self,
        session_id: str,
        project_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a new workspace.

        Parameters
        ----------
        session_id : str
            Session identifier.
        project_path : str | None
            Path to project (optional).

        Returns
        -------
        dict[str, Any]
            Workspace info with:
            - path: str
            - session_id: str
            - created_at: float
        """

    @abstractmethod
    async def get_workspace(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Get workspace for a session.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        dict[str, Any]
            Workspace info.
        """

    @abstractmethod
    async def cleanup_workspace(
        self,
        session_id: str,
    ) -> None:
        """Clean up workspace resources.

        Parameters
        ----------
        session_id : str
            Session identifier.
        """

    @abstractmethod
    async def save_state(
        self,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        """Save agent state.

        Parameters
        ----------
        session_id : str
            Session identifier.
        state : dict[str, Any]
            State to save.
        """

    @abstractmethod
    async def load_state(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Load agent state.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        dict[str, Any]
            Loaded state.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release workspace manager resources."""
