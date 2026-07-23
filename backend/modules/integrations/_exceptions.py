"""
Custom exceptions for the integrations module.
"""

from __future__ import annotations

from typing import Any


class IntegrationError(Exception):
    """Base exception for all integration errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class IntegrationNotConnectedError(IntegrationError):
    """Raised when an integration is accessed before authentication."""


class IntegrationAuthError(IntegrationError):
    """Raised when authentication fails for an integration service."""


class IntegrationAPIError(IntegrationError):
    """Raised when an external API call fails."""


class IntegrationTimeoutError(IntegrationError):
    """Raised when an integration request times out."""
