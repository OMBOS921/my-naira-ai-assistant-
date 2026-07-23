"""
PyGithubProvider — GitHub integration implementation using PyGithub.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.modules.integrations._credential_store import CredentialStore
from backend.modules.integrations._exceptions import (
    IntegrationAPIError,
    IntegrationAuthError,
    IntegrationNotConnectedError,
)
from backend.modules.integrations._types import GitHubIssueInfo, GitHubRepoInfo
from backend.modules.integrations.github.ports.github_port import GitHubPort

_LOG = logging.getLogger("naira.integrations.github")


class PyGithubProvider(GitHubPort):
    """Concrete implementation of GitHubPort using PyGithub."""

    def __init__(
        self,
        *,
        credential_store: CredentialStore,
        logger: logging.Logger | None = None,
    ) -> None:
        self._credential_store = credential_store
        self._logger = logger or _LOG
        self._client: Any = None
        self._authenticated = False
        self._user_login = ""

    async def authenticate(self, token: str) -> bool:
        """Authenticate with GitHub using Personal Access Token."""
        def _auth() -> str:
            from github import Github
            gh = Github(token)
            user = gh.get_user()
            return user.login

        try:
            user_login = await asyncio.to_thread(_auth)
            from github import Github
            self._client = Github(token)
            self._authenticated = True
            self._user_login = user_login
            self._credential_store.save_token(
                "github", {"token": token, "user": user_login}
            )
            self._logger.info("GitHub authenticated as %s", user_login)
            return True
        except Exception as exc:
            self._authenticated = False
            self._client = None
            raise IntegrationAuthError(
                f"GitHub authentication failed: {exc}", context={"service": "github"}
            ) from exc

    async def is_authenticated(self) -> bool:
        """Check if authenticated with GitHub, restoring session if cached."""
        if self._authenticated and self._client is not None:
            return True

        saved = self._credential_store.load_token("github")
        if not saved or "token" not in saved:
            return False

        token = saved["token"]

        def _verify() -> str:
            from github import Github
            gh = Github(token)
            return gh.get_user().login

        try:
            user_login = await asyncio.to_thread(_verify)
            from github import Github
            self._client = Github(token)
            self._authenticated = True
            self._user_login = user_login
            return True
        except Exception:
            self._authenticated = False
            self._client = None
            return False

    async def _ensure_authenticated(self) -> None:
        if not await self.is_authenticated():
            raise IntegrationNotConnectedError(
                "GitHub integration is not connected", context={"service": "github"}
            )

    async def list_repos(self, limit: int = 20) -> list[GitHubRepoInfo]:
        await self._ensure_authenticated()

        def _fetch() -> list[GitHubRepoInfo]:
            user = self._client.get_user()
            results: list[GitHubRepoInfo] = []
            for repo in user.get_repos():
                if len(results) >= limit:
                    break
                results.append(
                    GitHubRepoInfo(
                        name=repo.name,
                        full_name=repo.full_name,
                        description=repo.description or "",
                        private=repo.private,
                        default_branch=repo.default_branch or "main",
                        open_issues_count=repo.open_issues_count,
                        url=repo.html_url,
                    )
                )
            return results

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to list GitHub repos: {exc}", context={"service": "github"}
            ) from exc

    async def get_repo(self, repo_full_name: str) -> GitHubRepoInfo:
        await self._ensure_authenticated()

        def _fetch() -> GitHubRepoInfo:
            repo = self._client.get_repo(repo_full_name)
            return GitHubRepoInfo(
                name=repo.name,
                full_name=repo.full_name,
                description=repo.description or "",
                private=repo.private,
                default_branch=repo.default_branch or "main",
                open_issues_count=repo.open_issues_count,
                url=repo.html_url,
            )

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to get repo '{repo_full_name}': {exc}",
                context={"service": "github", "repo": repo_full_name},
            ) from exc

    async def create_repo(
        self, name: str, private: bool = True, description: str = ""
    ) -> GitHubRepoInfo:
        await self._ensure_authenticated()

        def _create() -> GitHubRepoInfo:
            user = self._client.get_user()
            repo = user.create_repo(
                name=name, private=private, description=description
            )
            return GitHubRepoInfo(
                name=repo.name,
                full_name=repo.full_name,
                description=repo.description or "",
                private=repo.private,
                default_branch=repo.default_branch or "main",
                open_issues_count=repo.open_issues_count,
                url=repo.html_url,
            )

        try:
            return await asyncio.to_thread(_create)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to create repo '{name}': {exc}",
                context={"service": "github", "repo_name": name},
            ) from exc

    async def list_issues(
        self, repo_full_name: str, state: str = "open"
    ) -> list[GitHubIssueInfo]:
        await self._ensure_authenticated()

        def _fetch() -> list[GitHubIssueInfo]:
            repo = self._client.get_repo(repo_full_name)
            issues = repo.get_issues(state=state)
            results: list[GitHubIssueInfo] = []
            for issue in issues:
                labels = tuple(lbl.name for lbl in issue.labels)
                results.append(
                    GitHubIssueInfo(
                        number=issue.number,
                        title=issue.title,
                        body=issue.body or "",
                        state=issue.state,
                        url=issue.html_url,
                        labels=labels,
                    )
                )
            return results

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to list issues for '{repo_full_name}': {exc}",
                context={"service": "github", "repo": repo_full_name},
            ) from exc

    async def create_issue(
        self,
        repo_full_name: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> GitHubIssueInfo:
        await self._ensure_authenticated()

        def _create() -> GitHubIssueInfo:
            repo = self._client.get_repo(repo_full_name)
            kwargs: dict[str, Any] = {"title": title, "body": body}
            if labels:
                kwargs["labels"] = labels
            issue = repo.create_issue(**kwargs)
            lbl_tuple = tuple(lbl.name for lbl in issue.labels)
            return GitHubIssueInfo(
                number=issue.number,
                title=issue.title,
                body=issue.body or "",
                state=issue.state,
                url=issue.html_url,
                labels=lbl_tuple,
            )

        try:
            return await asyncio.to_thread(_create)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to create issue in '{repo_full_name}': {exc}",
                context={"service": "github", "repo": repo_full_name},
            ) from exc

    async def push_file(
        self,
        repo_full_name: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        await self._ensure_authenticated()

        def _push() -> dict[str, Any]:
            from github import GithubException
            repo = self._client.get_repo(repo_full_name)
            try:
                contents = repo.get_contents(file_path, ref=branch)
                res = repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=contents.sha,
                    branch=branch,
                )
            except GithubException:
                res = repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    branch=branch,
                )
            return {
                "commit_sha": res["commit"].sha,
                "content_path": res["content"].path,
                "html_url": res["content"].html_url,
            }

        try:
            return await asyncio.to_thread(_push)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to push file '{file_path}' to '{repo_full_name}': {exc}",
                context={"service": "github", "repo": repo_full_name, "path": file_path},
            ) from exc

    async def get_file_content(
        self, repo_full_name: str, file_path: str, branch: str = "main"
    ) -> str:
        await self._ensure_authenticated()

        def _read() -> str:
            repo = self._client.get_repo(repo_full_name)
            contents = repo.get_contents(file_path, ref=branch)
            return contents.decoded_content.decode("utf-8")

        try:
            return await asyncio.to_thread(_read)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to read file '{file_path}' from '{repo_full_name}': {exc}",
                context={"service": "github", "repo": repo_full_name, "path": file_path},
            ) from exc

    async def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        head_branch: str,
        base_branch: str = "main",
        body: str = "",
    ) -> dict[str, Any]:
        await self._ensure_authenticated()

        def _pr() -> dict[str, Any]:
            repo = self._client.get_repo(repo_full_name)
            pr = repo.create_pull(
                title=title, body=body, head=head_branch, base=base_branch
            )
            return {
                "number": pr.number,
                "title": pr.title,
                "url": pr.html_url,
                "state": pr.state,
            }

        try:
            return await asyncio.to_thread(_pr)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to create pull request in '{repo_full_name}': {exc}",
                context={"service": "github", "repo": repo_full_name},
            ) from exc

    async def get_commit_history(
        self, repo_full_name: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        await self._ensure_authenticated()

        def _history() -> list[dict[str, Any]]:
            repo = self._client.get_repo(repo_full_name)
            commits = repo.get_commits()
            results: list[dict[str, Any]] = []
            for commit in commits:
                if len(results) >= limit:
                    break
                results.append(
                    {
                        "sha": commit.sha,
                        "message": commit.commit.message,
                        "author": commit.commit.author.name if commit.commit.author else "",
                        "date": commit.commit.author.date.isoformat() if commit.commit.author else "",
                        "url": commit.html_url,
                    }
                )
            return results

        try:
            return await asyncio.to_thread(_history)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to get commit history for '{repo_full_name}': {exc}",
                context={"service": "github", "repo": repo_full_name},
            ) from exc
