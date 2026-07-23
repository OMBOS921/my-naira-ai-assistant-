"""Email integration package."""

from backend.modules.integrations.email.email_provider import GmailProvider
from backend.modules.integrations.email.ports.email_port import EmailPort

__all__ = ["EmailPort", "GmailProvider"]
