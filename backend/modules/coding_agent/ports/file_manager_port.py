"""FileManagerPort — interface for file operations.

Defines the contract for safe file operations including read,
write, create, delete, and multi-file editing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class FileManagerPort(ABC):
    """Port for file operations.

    Provides safe file operations with proper validation.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the file manager is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def read_file(
        self,
        path: str,
        encoding: str = "utf-8",
    ) -> str:
        """Read a file.

        Parameters
        ----------
        path : str
            Path to the file.
        encoding : str
            File encoding.

        Returns
        -------
        str
            File contents.

        Raises
        ------
        FileOperationError
            If file read fails.
        """

    @abstractmethod
    async def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        """Write to a file.

        Parameters
        ----------
        path : str
            Path to the file.
        content : str
            Content to write.
        encoding : str
            File encoding.

        Raises
        ------
        FileOperationError
            If file write fails.
        """

    @abstractmethod
    async def create_file(
        self,
        path: str,
        content: str = "",
        encoding: str = "utf-8",
    ) -> None:
        """Create a new file.

        Parameters
        ----------
        path : str
            Path to the file.
        content : str
            Initial content.
        encoding : str
            File encoding.

        Raises
        ------
        FileOperationError
            If file creation fails.
        """

    @abstractmethod
    async def delete_file(
        self,
        path: str,
    ) -> None:
        """Delete a file.

        Parameters
        ----------
        path : str
            Path to the file.

        Raises
        ------
        FileOperationError
            If file deletion fails.
        """

    @abstractmethod
    async def list_directory(
        self,
        path: str,
        recursive: bool = False,
    ) -> list[str]:
        """List directory contents.

        Parameters
        ----------
        path : str
            Path to the directory.
        recursive : bool
            Whether to list recursively.

        Returns
        -------
        list[str]
            List of file and directory paths.
        """

    @abstractmethod
    async def file_exists(
        self,
        path: str,
    ) -> bool:
        """Check if a file exists.

        Parameters
        ----------
        path : str
            Path to the file.

        Returns
        -------
        bool
            True if file exists.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release file manager resources."""
