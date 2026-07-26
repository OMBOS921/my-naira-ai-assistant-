"""
Application exception hierarchy.

21_System_Contracts.md §3 — all application exceptions inherit from
``NairaError`` and carry a ``context`` dict with debugging information.
"""

from __future__ import annotations

from typing import Any


class NairaError(Exception):
    """Base exception for all Naira-OS application errors.

    Every ``NairaError`` must carry a ``context`` dict with debugging
    information (module name, request ID, operation, duration, etc.).

    Parameters
    ----------
    message : str
        Human-readable error description.
    context : dict[str, Any] | None
        Structured debugging metadata.
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.context: dict[str, Any] = context or {}
        super().__init__(message)


class ConfigurationError(NairaError):
    """Configuration validation failure."""


class ModuleError(NairaError):
    """Base for module-level errors."""


class ModuleLoadError(ModuleError):
    """Module construction or async_init failure."""


class ModuleTimeoutError(ModuleError):
    """Module operation exceeded its deadline."""


class ModuleDegradedError(ModuleError):
    """Module is operating in a degraded state."""


class SecurityError(NairaError):
    """Base for security violations."""


class InputRejectedError(SecurityError):
    """Payload failed security validation."""


class PermissionDeniedError(SecurityError):
    """User denied permission or no active session."""


class AuditLogError(SecurityError):
    """Audit log write failure."""


class LLMError(NairaError):
    """Base for LLM provider errors."""


class ProviderTimeoutError(LLMError):
    """LLM provider request timed out."""


class ProviderRateLimitError(LLMError):
    """LLM provider rate limit exceeded."""


class ProviderAuthError(LLMError):
    """LLM provider authentication failure."""


class ProviderInvalidRequestError(LLMError):
    """LLM provider invalid request error (400/422/bad payload). Non-retryable."""


class ProviderAPIError(LLMError):
    """LLM provider internal API/server error (500/502/503/504)."""


class ProviderNetworkError(LLMError):
    """LLM provider network connection or socket error."""


class ProviderUnavailableError(LLMError):
    """LLM provider unavailable or circuit open."""


class MemoryError(NairaError):
    """Base for database and cache errors."""


class IntegrityError(MemoryError):
    """Database constraint violation (e.g. SQLite UNIQUE)."""


class NotFoundError(MemoryError):
    """Requested key or record was not found."""


class ToolExecutionError(NairaError):
    """Error during tool or module execution."""


class ToolTimeoutError(ToolExecutionError):
    """Tool execution exceeded its timeout."""


class ToolRejectedError(ToolExecutionError):
    """Tool execution rejected by the permission gatekeeper."""
