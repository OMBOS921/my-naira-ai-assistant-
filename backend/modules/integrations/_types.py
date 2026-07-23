"""
Shared dataclasses for the integrations module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationStatus:
    """Status of an external service integration."""

    name: str
    connected: bool
    account_identifier: str = ""
    last_checked_at: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class GitHubRepoInfo:
    """Information about a GitHub repository."""

    name: str
    full_name: str
    description: str = ""
    private: bool = False
    default_branch: str = "main"
    open_issues_count: int = 0
    url: str = ""


@dataclass(frozen=True)
class GitHubIssueInfo:
    """Information about a GitHub issue."""

    number: int
    title: str
    body: str = ""
    state: str = "open"
    url: str = ""
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class CalendarEventInfo:
    """Information about a calendar event."""

    event_id: str
    title: str
    start_time: str
    end_time: str
    description: str = ""
    location: str = ""
    attendees: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmailInfo:
    """Information about an email message."""

    message_id: str
    subject: str
    sender: str
    snippet: str = ""
    received_at: str = ""
    is_unread: bool = False
    labels: tuple[str, ...] = ()
