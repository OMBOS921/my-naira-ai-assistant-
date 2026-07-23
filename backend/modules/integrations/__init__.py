"""Integrations module package."""

from backend.modules.integrations._credential_store import CredentialStore
from backend.modules.integrations._exceptions import (
    IntegrationAPIError,
    IntegrationAuthError,
    IntegrationError,
    IntegrationNotConnectedError,
    IntegrationTimeoutError,
)
from backend.modules.integrations._types import (
    CalendarEventInfo,
    EmailInfo,
    GitHubIssueInfo,
    GitHubRepoInfo,
    IntegrationStatus,
)
from backend.modules.integrations.integrations_module import IntegrationsManager

__all__ = [
    "IntegrationsManager",
    "CredentialStore",
    "IntegrationStatus",
    "GitHubRepoInfo",
    "GitHubIssueInfo",
    "CalendarEventInfo",
    "EmailInfo",
    "IntegrationError",
    "IntegrationNotConnectedError",
    "IntegrationAuthError",
    "IntegrationAPIError",
    "IntegrationTimeoutError",
]
