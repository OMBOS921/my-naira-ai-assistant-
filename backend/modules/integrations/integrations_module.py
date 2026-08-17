"""
IntegrationsManager — main manager class for external service integrations.

Follows Port/Adapter clean architecture pattern and ModuleInterface lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.integrations._credential_store import CredentialStore
from backend.modules.integrations._types import IntegrationStatus
from backend.modules.integrations.calendar.calendar_provider import GoogleCalendarProvider
from backend.modules.integrations.calendar.ports.calendar_port import CalendarPort
from backend.modules.integrations.email.email_provider import GmailProvider
from backend.modules.integrations.email.ports.email_port import EmailPort
from backend.modules.integrations.github.github_provider import PyGithubProvider
from backend.modules.integrations.github.ports.github_port import GitHubPort
from backend.types import ToolResult
_LOG = logging.getLogger("naira.integrations")


class IntegrationsManager:
    """Central manager for GitHub, Google Calendar, and Gmail integrations."""

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        tool_manager: object | None = None,
        credential_store: CredentialStore | None = None,
        github_provider: GitHubPort | None = None,
        calendar_provider: CalendarPort | None = None,
        email_provider: EmailPort | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._degraded = False
        self._default_timeout = default_timeout

        self._credential_store = credential_store or CredentialStore(logger=self._logger)
        self._github = github_provider or PyGithubProvider(
            credential_store=self._credential_store, logger=self._logger
        )
        self._calendar = calendar_provider or GoogleCalendarProvider(
            credential_store=self._credential_store, logger=self._logger
        )
        self._email = email_provider or GmailProvider(
            credential_store=self._credential_store, logger=self._logger
        )

    @property
    def is_available(self) -> bool:
        """Return True if manager is not degraded."""
        return not self._degraded

    @property
    def credential_store(self) -> CredentialStore:
        """Return the credential store instance."""
        return self._credential_store

    async def async_init(self) -> None:
        """Initialise integrations module and silently restore sessions if cached."""
        services = [
            ("github", self._github),
            ("calendar", self._calendar),
            ("email", self._email),
        ]
        for name, provider in services:
            if self._credential_store.has_token(name):
                try:
                    await provider.is_authenticated()
                except Exception as exc:
                    self._logger.warning("Auto-authentication failed for '%s': %s", name, exc)

        self._register_capability()
        self._register_tools()
        self._logger.info("IntegrationsManager initialised successfully.")

    async def async_shutdown(self) -> None:
        """Shutdown integrations module."""
        self._degraded = False
        self._logger.info("IntegrationsManager shut down.")

    def degrade(self) -> None:
        """Mark manager as degraded."""
        self._degraded = True
        self._logger.warning("IntegrationsManager marked degraded.")

    async def get_status(self) -> list[IntegrationStatus]:
        """Return connectivity status for all registered integrations."""
        self._ensure_not_degraded()
        services = [
            ("github", self._github),
            ("calendar", self._calendar),
            ("email", self._email),
        ]
        statuses: list[IntegrationStatus] = []
        now = time.time()
        for name, provider in services:
            try:
                is_auth = await provider.is_authenticated()
                statuses.append(
                    IntegrationStatus(
                        name=name,
                        connected=is_auth,
                        last_checked_at=now,
                    )
                )
            except Exception as exc:
                statuses.append(
                    IntegrationStatus(
                        name=name,
                        connected=False,
                        last_checked_at=now,
                        error=str(exc),
                    )
                )
        return statuses

    # ── GitHub Methods ──────────────────────────────────────────────────

    async def github_connect(self, token: str) -> dict[str, Any]:
        """Authenticate with GitHub using a personal access token."""
        self._ensure_not_degraded()
        try:
            success = await self._github.authenticate(token)
            return {"success": success, "service": "github"}
        except Exception as exc:
            return {"success": False, "service": "github", "error": str(exc)}

    async def github_list_repos(self, limit: int = 20) -> ToolResult:
        """List GitHub repositories."""
        self._ensure_not_degraded()
        try:
            repos = await self._github.list_repos(limit=limit)
            out = "\n".join(f"- {r.full_name} ({'private' if r.private else 'public'}): {r.url}" for r in repos)
            return ToolResult(status="success", output=out or "No repositories found.")
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def github_create_issue(
        self, repo_full_name: str, title: str, body: str = ""
    ) -> ToolResult:
        """Create a new GitHub issue."""
        self._ensure_not_degraded()
        try:
            issue = await self._github.create_issue(repo_full_name, title, body=body)
            return ToolResult(
                status="success",
                output=f"Created Issue #{issue.number}: '{issue.title}' in {repo_full_name} ({issue.url})",
            )
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def github_push_file(
        self, repo_full_name: str, file_path: str, content: str, commit_message: str
    ) -> ToolResult:
        """Push/update a file in a GitHub repository."""
        self._ensure_not_degraded()
        try:
            res = await self._github.push_file(
                repo_full_name, file_path, content, commit_message
            )
            return ToolResult(
                status="success",
                output=f"Pushed file '{file_path}' to {repo_full_name} (Commit SHA: {res.get('commit_sha')})",
            )
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    # ── Calendar Methods ────────────────────────────────────────────────

    async def calendar_connect(
        self, credentials_json_path: str = ""
    ) -> dict[str, Any]:
        """Authenticate with Google Calendar."""
        self._ensure_not_degraded()
        try:
            success = await self._calendar.authenticate(credentials_json_path)
            return {"success": success, "service": "calendar"}
        except Exception as exc:
            return {"success": False, "service": "calendar", "error": str(exc)}

    async def calendar_upcoming_events(self, max_results: int = 10) -> ToolResult:
        """List upcoming Google Calendar events."""
        self._ensure_not_degraded()
        try:
            events = await self._calendar.list_upcoming_events(max_results=max_results)
            out = "\n".join(f"- [{e.start_time} - {e.end_time}] {e.title} (ID: {e.event_id})" for e in events)
            return ToolResult(status="success", output=out or "No upcoming events found.")
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def calendar_create_event(
        self,
        title: str,
        start_time_iso: str,
        end_time_iso: str,
        description: str = "",
    ) -> ToolResult:
        """Create a new Google Calendar event."""
        self._ensure_not_degraded()
        try:
            ev = await self._calendar.create_event(
                title, start_time_iso, end_time_iso, description=description
            )
            return ToolResult(
                status="success",
                output=f"Created event '{ev.title}' starting at {ev.start_time} (ID: {ev.event_id})",
            )
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    # ── Email Methods ───────────────────────────────────────────────────

    async def email_connect(self, credentials_json_path: str = "") -> dict[str, Any]:
        """Authenticate with Gmail."""
        self._ensure_not_degraded()
        try:
            success = await self._email.authenticate(credentials_json_path)
            return {"success": success, "service": "email"}
        except Exception as exc:
            return {"success": False, "service": "email", "error": str(exc)}

    async def email_recent(self, max_results: int = 10) -> ToolResult:
        """List recent emails from Gmail inbox."""
        self._ensure_not_degraded()
        try:
            emails = await self._email.list_recent_emails(max_results=max_results)
            out = "\n".join(f"- From: {e.sender} | Subject: {e.subject} (ID: {e.message_id})" for e in emails)
            return ToolResult(status="success", output=out or "No recent emails found.")
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def email_send(self, to: str, subject: str, body: str) -> ToolResult:
        """Send an email using Gmail."""
        self._ensure_not_degraded()
        try:
            res = await self._email.send_email(to, subject, body)
            return ToolResult(
                status="success",
                output=f"Sent email to {to} with Subject '{subject}' (Message ID: {res.get('message_id')})",
            )
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def email_unread_count(self) -> ToolResult:
        """Get count of unread emails in Gmail inbox."""
        self._ensure_not_degraded()
        try:
            count = await self._email.get_unread_count()
            return ToolResult(status="success", output=f"Unread emails: {count}")
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    # ── Tool & Capability Registration ──────────────────────────────────

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "IntegrationsManager is degraded", context={"module": "integrations"}
            )

    def _register_capability(self) -> None:
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register_capability", None)
            if register_cap is not None:
                from backend.modules.capabilities import Capability
                register_cap(
                    Capability(
                        name="integrations",
                        version="0.1.0",
                        description="External service integrations (GitHub, Calendar, Email)",
                    )
                )

    def _register_tools(self) -> None:
        if self._tool_manager is not None:
            register = getattr(self._tool_manager, "register_tool", None)
            if register is not None:
                from backend.modules.tools import ToolDefinition

                register(
                    ToolDefinition(
                        name="github_list_repos",
                        description="List repositories accessible by authenticated GitHub user",
                        parameters={
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Max repositories to return"},
                            },
                            "required": [],
                        },
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_github_list_repos_tool,
                )

                register(
                    ToolDefinition(
                        name="github_create_issue",
                        description="Create an issue in a GitHub repository",
                        parameters={
                            "type": "object",
                            "properties": {
                                "repo_full_name": {"type": "string", "description": "Full repo name (e.g. owner/repo)"},
                                "title": {"type": "string", "description": "Issue title"},
                                "body": {"type": "string", "description": "Issue body markdown"},
                            },
                            "required": ["repo_full_name", "title"],
                        },
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_github_create_issue_tool,
                )

                register(
                    ToolDefinition(
                        name="github_push_file",
                        description="Push or update a file in a GitHub repository",
                        parameters={
                            "type": "object",
                            "properties": {
                                "repo_full_name": {"type": "string", "description": "Full repo name (e.g. owner/repo)"},
                                "file_path": {"type": "string", "description": "Relative file path in repo"},
                                "content": {"type": "string", "description": "File text content"},
                                "commit_message": {"type": "string", "description": "Commit message"},
                            },
                            "required": ["repo_full_name", "file_path", "content", "commit_message"],
                        },
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_github_push_file_tool,
                )

                register(
                    ToolDefinition(
                        name="calendar_upcoming_events",
                        description="List upcoming events from Google Calendar",
                        parameters={
                            "type": "object",
                            "properties": {
                                "max_results": {"type": "integer", "description": "Max events to list"},
                            },
                            "required": [],
                        },
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_calendar_upcoming_events_tool,
                )

                register(
                    ToolDefinition(
                        name="calendar_create_event",
                        description="Create an event on Google Calendar",
                        parameters={
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Event title"},
                                "start_time_iso": {"type": "string", "description": "Start ISO datetime string"},
                                "end_time_iso": {"type": "string", "description": "End ISO datetime string"},
                                "description": {"type": "string", "description": "Event description"},
                            },
                            "required": ["title", "start_time_iso", "end_time_iso"],
                        },
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_calendar_create_event_tool,
                )

                register(
                    ToolDefinition(
                        name="email_recent",
                        description="List recent emails from Gmail inbox",
                        parameters={
                            "type": "object",
                            "properties": {
                                "max_results": {"type": "integer", "description": "Max emails to list"},
                            },
                            "required": [],
                        },
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_email_recent_tool,
                )

                register(
                    ToolDefinition(
                        name="email_send",
                        description="Send an email via Gmail",
                        parameters={
                            "type": "object",
                            "properties": {
                                "to": {"type": "string", "description": "Recipient email address"},
                                "subject": {"type": "string", "description": "Email subject line"},
                                "body": {"type": "string", "description": "Email message body"},
                            },
                            "required": ["to", "subject", "body"],
                        },
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_email_send_tool,
                )

                register(
                    ToolDefinition(
                        name="email_unread_count",
                        description="Get the total count of unread emails in Gmail",
                        parameters={"type": "object", "properties": {}, "required": []},
                        category="integrations",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_email_unread_count_tool,
                )

    # ── Tool Handlers ───────────────────────────────────────────────────

    async def _handle_github_list_repos_tool(self, limit: int = 20) -> ToolResult:
        return await self.github_list_repos(limit=limit)

    async def _handle_github_create_issue_tool(
        self, repo_full_name: str, title: str, body: str = ""
    ) -> ToolResult:
        return await self.github_create_issue(repo_full_name, title, body=body)

    async def _handle_github_push_file_tool(
        self, repo_full_name: str, file_path: str, content: str, commit_message: str
    ) -> ToolResult:
        return await self.github_push_file(
            repo_full_name, file_path, content, commit_message
        )

    async def _handle_calendar_upcoming_events_tool(
        self, max_results: int = 10
    ) -> ToolResult:
        return await self.calendar_upcoming_events(max_results=max_results)

    async def _handle_calendar_create_event_tool(
        self,
        title: str,
        start_time_iso: str,
        end_time_iso: str,
        description: str = "",
    ) -> ToolResult:
        return await self.calendar_create_event(
            title, start_time_iso, end_time_iso, description=description
        )

    async def _handle_email_recent_tool(self, max_results: int = 10) -> ToolResult:
        return await self.email_recent(max_results=max_results)

    async def _handle_email_send_tool(
        self, to: str, subject: str, body: str
    ) -> ToolResult:
        return await self.email_send(to, subject, body)

    async def _handle_email_unread_count_tool(self) -> ToolResult:
        return await self.email_unread_count()
