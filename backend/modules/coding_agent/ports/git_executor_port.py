"""GitExecutorPort — interface for Git operations.

Defines the contract for Git operations including commit, push,
pull, and diff generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GitExecutorPort(ABC):
    """Port for Git operations.

    Executes Git commands with proper repository context.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the Git executor is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def execute(
        self,
        args: list[str],
        *,
        cwd: str | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Execute a Git command.

        Parameters
        ----------
        args : list[str]
            Git command arguments.
        cwd : str | None
            Repository directory.
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
        """

    @abstractmethod
    async def commit(
        self,
        message: str,
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Commit changes to the repository.

        Parameters
        ----------
        message : str
            Commit message.
        cwd : str | None
            Repository directory.

        Returns
        -------
        dict[str, Any]
            Commit result.
        """

    @abstractmethod
    async def push(
        self,
        remote: str = "origin",
        branch: str = "main",
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Push changes to remote.

        Parameters
        ----------
        remote : str
            Remote repository name.
        branch : str
            Branch name.
        cwd : str | None
            Repository directory.

        Returns
        -------
        dict[str, Any]
            Push result.
        """

    @abstractmethod
    async def pull(
        self,
        remote: str = "origin",
        branch: str = "main",
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Pull changes from remote.

        Parameters
        ----------
        remote : str
            Remote repository name.
        branch : str
            Branch name.
        cwd : str | None
            Repository directory.

        Returns
        -------
        dict[str, Any]
            Pull result.
        """

    @abstractmethod
    async def diff(
        self,
        *,
        cwd: str | None = None,
    ) -> str:
        """Generate diff for current changes.

        Parameters
        ----------
        cwd : str | None
            Repository directory.

        Returns
        -------
        str
            Diff output in unified format.
        """

    @abstractmethod
    async def status(
        self,
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Get repository status.

        Parameters
        ----------
        cwd : str | None
            Repository directory.

        Returns
        -------
        dict[str, Any]
            Status with:
            - modified: list[str]
            - staged: list[str]
            - untracked: list[str]
        """

    @abstractmethod
    async def close(self) -> None:
        """Release Git executor resources."""
