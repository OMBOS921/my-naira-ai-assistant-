from __future__ import annotations

from backend.exceptions import SecurityError


class SecurityExecutionError(SecurityError):
    """A security operation failed."""


class SecurityPermissionError(SecurityError):
    """Permission denied by the security module."""


class SecurityTimeoutError(SecurityError):
    """Security operation timed out (e.g. HITL approval)."""


class SecurityNotImplementedError(SecurityError):
    """The security adapter does not support this operation."""


class SecurityConfigError(SecurityError):
    """Security configuration error."""
