"""
GoogleCalendarProvider — Google Calendar integration implementation.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any

from backend.modules.integrations._credential_store import CredentialStore
from backend.modules.integrations._exceptions import (
    IntegrationAPIError,
    IntegrationAuthError,
    IntegrationNotConnectedError,
)
from backend.modules.integrations._types import CalendarEventInfo
from backend.modules.integrations.calendar.ports.calendar_port import CalendarPort

_LOG = logging.getLogger("naira.integrations.calendar")
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarProvider(CalendarPort):
    """Concrete implementation of CalendarPort using Google Calendar API."""

    def __init__(
        self,
        *,
        credential_store: CredentialStore,
        client_secrets_path: str = "config/google_client_secret.json",
        logger: logging.Logger | None = None,
    ) -> None:
        self._credential_store = credential_store
        self._client_secrets_path = client_secrets_path
        self._logger = logger or _LOG
        self._service: Any = None
        self._creds: Any = None

    async def authenticate(self, credentials_json_path: str | None = None) -> bool:
        """Authenticate using Google OAuth flow."""
        secret_path = credentials_json_path or self._client_secrets_path

        def _auth() -> tuple[Any, Any]:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            service = build("calendar", "v3", credentials=creds)
            return creds, service

        try:
            creds, service = await asyncio.to_thread(_auth)
            self._creds = creds
            self._service = service
            creds_json = json.loads(creds.to_json())
            self._credential_store.save_token("calendar", creds_json)
            self._logger.info("Google Calendar authenticated successfully")
            return True
        except Exception as exc:
            self._creds = None
            self._service = None
            raise IntegrationAuthError(
                f"Google Calendar authentication failed: {exc}",
                context={"service": "calendar"},
            ) from exc

    async def is_authenticated(self) -> bool:
        """Check if authenticated. Restores cached tokens without browser flow."""
        if self._service is not None:
            return True

        saved = self._credential_store.load_token("calendar")
        if not saved:
            return False

        def _verify() -> tuple[Any, Any] | None:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_info(saved, SCOPES)
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    return None
            if creds and creds.valid:
                service = build("calendar", "v3", credentials=creds)
                return creds, service
            return None

        try:
            res = await asyncio.to_thread(_verify)
            if res is not None:
                creds, service = res
                self._creds = creds
                self._service = service
                self._credential_store.save_token("calendar", json.loads(creds.to_json()))
                return True
            return False
        except Exception:
            return False

    async def _ensure_authenticated(self) -> None:
        if not await self.is_authenticated():
            raise IntegrationNotConnectedError(
                "Calendar integration is not connected", context={"service": "calendar"}
            )

    async def list_upcoming_events(
        self, max_results: int = 10, calendar_id: str = "primary"
    ) -> list[CalendarEventInfo]:
        await self._ensure_authenticated()
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"

        def _fetch() -> list[CalendarEventInfo]:
            events_result = (
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now_iso,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            items = events_result.get("items", [])
            return [self._parse_event_item(item) for item in items]

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to list upcoming calendar events: {exc}",
                context={"service": "calendar"},
            ) from exc

    async def get_events_for_date(
        self, date_iso: str, calendar_id: str = "primary"
    ) -> list[CalendarEventInfo]:
        await self._ensure_authenticated()

        def _fetch() -> list[CalendarEventInfo]:
            parsed = datetime.datetime.fromisoformat(date_iso.replace("Z", ""))
            start_of_day = datetime.datetime(
                parsed.year, parsed.month, parsed.day, 0, 0, 0
            ).isoformat() + "Z"
            end_of_day = datetime.datetime(
                parsed.year, parsed.month, parsed.day, 23, 59, 59
            ).isoformat() + "Z"

            events_result = (
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_of_day,
                    timeMax=end_of_day,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            items = events_result.get("items", [])
            return [self._parse_event_item(item) for item in items]

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to fetch calendar events for date '{date_iso}': {exc}",
                context={"service": "calendar", "date": date_iso},
            ) from exc

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
        await self._ensure_authenticated()

        def _create() -> CalendarEventInfo:
            body: dict[str, Any] = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {"dateTime": start_time_iso},
                "end": {"dateTime": end_time_iso},
            }
            if attendees:
                body["attendees"] = [{"email": email} for email in attendees]

            item = (
                self._service.events()
                .insert(calendarId=calendar_id, body=body)
                .execute()
            )
            return self._parse_event_item(item)

        try:
            return await asyncio.to_thread(_create)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to create calendar event '{title}': {exc}",
                context={"service": "calendar", "title": title},
            ) from exc

    async def update_event(
        self, event_id: str, updates: dict[str, Any], calendar_id: str = "primary"
    ) -> CalendarEventInfo:
        await self._ensure_authenticated()

        def _update() -> CalendarEventInfo:
            existing = (
                self._service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
            if "title" in updates:
                existing["summary"] = updates["title"]
            if "description" in updates:
                existing["description"] = updates["description"]
            if "location" in updates:
                existing["location"] = updates["location"]
            if "start_time" in updates:
                existing["start"] = {"dateTime": updates["start_time"]}
            if "end_time" in updates:
                existing["end"] = {"dateTime": updates["end_time"]}

            item = (
                self._service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=existing)
                .execute()
            )
            return self._parse_event_item(item)

        try:
            return await asyncio.to_thread(_update)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to update calendar event '{event_id}': {exc}",
                context={"service": "calendar", "event_id": event_id},
            ) from exc

    async def delete_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> bool:
        await self._ensure_authenticated()

        def _delete() -> bool:
            self._service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
            return True

        try:
            return await asyncio.to_thread(_delete)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to delete calendar event '{event_id}': {exc}",
                context={"service": "calendar", "event_id": event_id},
            ) from exc

    async def check_free_busy(
        self, start_time_iso: str, end_time_iso: str, calendar_id: str = "primary"
    ) -> bool:
        await self._ensure_authenticated()

        def _check() -> bool:
            body = {
                "timeMin": start_time_iso,
                "timeMax": end_time_iso,
                "items": [{"id": calendar_id}],
            }
            res = self._service.freebusy().query(body=body).execute()
            busy = res.get("calendars", {}).get(calendar_id, {}).get("busy", [])
            return len(busy) == 0

        try:
            return await asyncio.to_thread(_check)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to check free/busy status: {exc}",
                context={"service": "calendar"},
            ) from exc

    def _parse_event_item(self, item: dict[str, Any]) -> CalendarEventInfo:
        start = item.get("start", {})
        end = item.get("end", {})
        start_str = start.get("dateTime") or start.get("date") or ""
        end_str = end.get("dateTime") or end.get("date") or ""

        att_list = item.get("attendees", [])
        attendees = tuple(
            a.get("email", "") for a in att_list if isinstance(a, dict) and "email" in a
        )

        return CalendarEventInfo(
            event_id=item.get("id", ""),
            title=item.get("summary", "(No Title)"),
            start_time=start_str,
            end_time=end_str,
            description=item.get("description", ""),
            location=item.get("location", ""),
            attendees=attendees,
        )
