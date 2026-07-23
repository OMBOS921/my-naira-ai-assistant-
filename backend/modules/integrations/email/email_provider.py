"""
GmailProvider — Gmail integration implementation using google-api-python-client.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import json
import logging
from email.mime.text import MIMEText
from typing import Any

from backend.modules.integrations._credential_store import CredentialStore
from backend.modules.integrations._exceptions import (
    IntegrationAPIError,
    IntegrationAuthError,
    IntegrationNotConnectedError,
)
from backend.modules.integrations._types import EmailInfo
from backend.modules.integrations.email.ports.email_port import EmailPort

_LOG = logging.getLogger("naira.integrations.email")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


class GmailProvider(EmailPort):
    """Concrete implementation of EmailPort using Gmail API."""

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
            service = build("gmail", "v1", credentials=creds)
            return creds, service

        try:
            creds, service = await asyncio.to_thread(_auth)
            self._creds = creds
            self._service = service
            creds_json = json.loads(creds.to_json())
            self._credential_store.save_token("email", creds_json)
            self._logger.info("Gmail authenticated successfully")
            return True
        except Exception as exc:
            self._creds = None
            self._service = None
            raise IntegrationAuthError(
                f"Gmail authentication failed: {exc}", context={"service": "email"}
            ) from exc

    async def is_authenticated(self) -> bool:
        """Check if authenticated. Restores cached tokens without browser flow."""
        if self._service is not None:
            return True

        saved = self._credential_store.load_token("email")
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
                service = build("gmail", "v1", credentials=creds)
                return creds, service
            return None

        try:
            res = await asyncio.to_thread(_verify)
            if res is not None:
                creds, service = res
                self._creds = creds
                self._service = service
                self._credential_store.save_token("email", json.loads(creds.to_json()))
                return True
            return False
        except Exception:
            return False

    async def _ensure_authenticated(self) -> None:
        if not await self.is_authenticated():
            raise IntegrationNotConnectedError(
                "Email integration is not connected", context={"service": "email"}
            )

    async def list_recent_emails(
        self, max_results: int = 10, unread_only: bool = False
    ) -> list[EmailInfo]:
        await self._ensure_authenticated()

        def _list_ids() -> list[str]:
            q = "is:unread" if unread_only else ""
            res = (
                self._service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=q)
                .execute()
            )
            messages = res.get("messages", [])
            return [m["id"] for m in messages if isinstance(m, dict) and "id" in m]

        try:
            msg_ids = await asyncio.to_thread(_list_ids)
            if not msg_ids:
                return []
            tasks = [self.get_email_content(msg_id) for msg_id in msg_ids]
            return await asyncio.gather(*tasks)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to list recent emails: {exc}", context={"service": "email"}
            ) from exc

    async def get_email_content(self, message_id: str) -> EmailInfo:
        await self._ensure_authenticated()

        def _fetch() -> EmailInfo:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])

            subject = ""
            sender = ""
            date_str = ""
            for h in headers:
                name = h.get("name", "").lower()
                if name == "subject":
                    subject = h.get("value", "")
                elif name == "from":
                    sender = h.get("value", "")
                elif name == "date":
                    date_str = h.get("value", "")

            labels = tuple(msg.get("labelIds", []))
            is_unread = "UNREAD" in labels

            return EmailInfo(
                message_id=message_id,
                subject=subject or "(No Subject)",
                sender=sender,
                snippet=msg.get("snippet", ""),
                received_at=date_str,
                is_unread=is_unread,
                labels=labels,
            )

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to get email content for '{message_id}': {exc}",
                context={"service": "email", "message_id": message_id},
            ) from exc

    async def search_emails(
        self, query: str, max_results: int = 10
    ) -> list[EmailInfo]:
        await self._ensure_authenticated()

        def _search_ids() -> list[str]:
            res = (
                self._service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=query)
                .execute()
            )
            messages = res.get("messages", [])
            return [m["id"] for m in messages if isinstance(m, dict) and "id" in m]

        try:
            msg_ids = await asyncio.to_thread(_search_ids)
            if not msg_ids:
                return []
            tasks = [self.get_email_content(msg_id) for msg_id in msg_ids]
            return await asyncio.gather(*tasks)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to search emails for query '{query}': {exc}",
                context={"service": "email", "query": query},
            ) from exc

    async def send_email(
        self, to: str, subject: str, body: str, cc: str = "", bcc: str = ""
    ) -> dict[str, Any]:
        await self._ensure_authenticated()

        def _send() -> dict[str, Any]:
            mime_msg = MIMEText(body)
            mime_msg["to"] = to
            mime_msg["subject"] = subject
            if cc:
                mime_msg["cc"] = cc
            if bcc:
                mime_msg["bcc"] = bcc

            raw_bytes = mime_msg.as_bytes()
            raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

            res = (
                self._service.users()
                .messages()
                .send(userId="me", body={"raw": raw_b64})
                .execute()
            )
            return {"message_id": res.get("id", ""), "thread_id": res.get("threadId", "")}

        try:
            return await asyncio.to_thread(_send)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to send email to '{to}': {exc}",
                context={"service": "email", "to": to},
            ) from exc

    async def mark_as_read(self, message_id: str) -> bool:
        await self._ensure_authenticated()

        def _mark() -> bool:
            body = {"removeLabelIds": ["UNREAD"]}
            self._service.users().messages().modify(
                userId="me", id=message_id, body=body
            ).execute()
            return True

        try:
            return await asyncio.to_thread(_mark)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to mark email '{message_id}' as read: {exc}",
                context={"service": "email", "message_id": message_id},
            ) from exc

    async def get_unread_count(self) -> int:
        await self._ensure_authenticated()

        def _count() -> int:
            res = (
                self._service.users()
                .labels()
                .get(userId="me", id="UNREAD")
                .execute()
            )
            return res.get("messagesUnread", 0)

        try:
            return await asyncio.to_thread(_count)
        except Exception as exc:
            raise IntegrationAPIError(
                f"Failed to get unread email count: {exc}",
                context={"service": "email"},
            ) from exc
