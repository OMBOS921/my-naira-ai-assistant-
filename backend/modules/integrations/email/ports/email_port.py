"""
Abstract port interface for Email operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.modules.integrations._types import EmailInfo


class EmailPort(ABC):
    """Abstract port defining Email integration capabilities."""

    @abstractmethod
    async def authenticate(self, credentials_json_path: str) -> bool:
        """Authenticate using Google OAuth client secrets file."""

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if currently authenticated with Email service."""

    @abstractmethod
    async def list_recent_emails(
        self, max_results: int = 10, unread_only: bool = False
    ) -> list[EmailInfo]:
        """List recent emails from inbox."""

    @abstractmethod
    async def get_email_content(self, message_id: str) -> EmailInfo:
        """Get full details of a specific email by message ID."""

    @abstractmethod
    async def search_emails(
        self, query: str, max_results: int = 10
    ) -> list[EmailInfo]:
        """Search emails matching search query string."""

    @abstractmethod
    async def send_email(
        self, to: str, subject: str, body: str, cc: str = "", bcc: str = ""
    ) -> dict[str, Any]:
        """Send an email message."""

    @abstractmethod
    async def mark_as_read(self, message_id: str) -> bool:
        """Mark an email message as read."""

    @abstractmethod
    async def get_unread_count(self) -> int:
        """Get total number of unread emails in inbox."""
