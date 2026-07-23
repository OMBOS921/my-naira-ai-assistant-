"""
Abstract port interface for GitHub operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.modules.integrations._types import GitHubIssueInfo, GitHubRepoInfo


class GitHubPort(ABC):
    """Abstract port defining GitHub integration capabilities."""

    @abstractmethod
    async def authenticate(self, token: str) -> bool:
        """Authenticate using a Personal Access Token or OAuth token."""

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if currently authenticated with GitHub."""

    @abstractmethod
    async def list_repos(self, limit: int = 20) -> list[GitHubRepoInfo]:
        """List repositories accessible by authenticated user."""

    @abstractmethod
    async def get_repo(self, repo_full_name: str) -> GitHubRepoInfo:
        """Get information about a specific repository."""

    @abstractmethod
    async def create_repo(
        self, name: str, private: bool = True, description: str = ""
    ) -> GitHubRepoInfo:
        """Create a new GitHub repository."""

    @abstractmethod
    async def list_issues(
        self, repo_full_name: str, state: str = "open"
    ) -> list[GitHubIssueInfo]:
        """List issues for a repository."""

    @abstractmethod
    async def create_issue(
        self,
        repo_full_name: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> GitHubIssueInfo:
        """Create an issue in a repository."""

    @abstractmethod
    async def push_file(
        self,
        repo_full_name: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        """Create or update a file in a repository."""

    @abstractmethod
    async def get_file_content(
        self, repo_full_name: str, file_path: str, branch: str = "main"
    ) -> str:
        """Get raw text content of a file from a repository."""

    @abstractmethod
    async def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        head_branch: str,
        base_branch: str = "main",
        body: str = "",
    ) -> dict[str, Any]:
        """Create a pull request in a repository."""

    @abstractmethod
    async def get_commit_history(
        self, repo_full_name: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent commit history for a repository."""
