"""MultiFileEditorPort — interface for multi-file editing.

Defines the contract for editing multiple files, including
patch generation and diff application.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MultiFileEditorPort(ABC):
    """Port for multi-file editing.

    Manages coordinated edits across multiple files.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the editor is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def create_patch(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> str:
        """Create a unified diff patch.

        Parameters
        ----------
        file_path : str
            Path to the file.
        old_content : str
            Original file content.
        new_content : str
            New file content.

        Returns
        -------
        str
            Unified diff patch.
        """

    @abstractmethod
    async def apply_patch(
        self,
        file_path: str,
        patch: str,
    ) -> str:
        """Apply a patch to a file.

        Parameters
        ----------
        file_path : str
            Path to the file.
        patch : str
            Unified diff patch.

        Returns
        -------
        str
            New file content after patch application.
        """

    @abstractmethod
    async def create_hunk(
        self,
        file_path: str,
        line_start: int,
        line_end: int,
        content: str,
    ) -> dict[str, Any]:
        """Create a code hunk.

        Parameters
        ----------
        file_path : str
            Path to the file.
        line_start : int
            Start line number.
        line_end : int
            End line number.
        content : str
            Content for the hunk.

        Returns
        -------
        dict[str, Any]
            Hunk definition.
        """

    @abstractmethod
    async def edit_multiple(
        self,
        edits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply multiple file edits.

        Parameters
        ----------
        edits : list[dict[str, Any]]
            List of edit definitions with:
            - file_path: str
            - action: str (create, write, delete)
            - content: str (for create/write)
            - line_start: int (for hunk-based)
            - line_end: int
            - content: str

        Returns
        -------
        dict[str, Any]
            Results with:
            - success: list[str]
            - failed: list[str]
            - errors: dict[str, str]
        """

    @abstractmethod
    async def close(self) -> None:
        """Release editor resources."""
