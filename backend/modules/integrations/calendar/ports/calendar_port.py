"""
Abstract port interface for Calendar operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.modules.integrations._types import CalendarEventInfo


class CalendarPort(ABC):
    """Abstract port defining Calendar integration capabilities."""

    @abstractmethod
    async def authenticate(self, credentials_json_path: str) -> bool:
        """Authenticate using Google OAuth client secrets file."""

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if currently authenticated with Calendar service."""

    @abstractmethod
    async def list_upcoming_events(
        self, max_results: int = 10, calendar_id: str = "primary"
    ) -> list[CalendarEventInfo]:
        """List upcoming calendar events from now onwards."""

    @abstractmethod
    async def get_events_for_date(
        self, date_iso: str, calendar_id: str = "primary"
    ) -> list[CalendarEventInfo]:
        """List calendar events for a specific date (YYYY-MM-DD)."""

    @abstractmethod
    async def create_event(
        self,
        title: str,
        start_time_iso: str,
        end_time_iso: str,
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
    ) -> CalendarEventInfo:
        """Create a new event on the calendar."""

    @abstractmethod
    async def update_event(
        self, event_id: str, updates: dict[str, Any], calendar_id: str = "primary"
    ) -> CalendarEventInfo:
        """Update an existing event by ID."""

    @abstractmethod
    async def delete_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> bool:
        """Delete an event from the calendar by ID."""

    @abstractmethod
    async def check_free_busy(
        self, start_time_iso: str, end_time_iso: str, calendar_id: str = "primary"
    ) -> bool:
        """Check if time slot is free (True) or busy (False)."""
