from __future__ import annotations


class ValidationError(Exception):
    """Base exception for all validation agent errors."""


class TestExecutionError(ValidationError):
    """A test suite failed to execute."""


class LeakDetectedError(ValidationError):
    """A resource leak was detected during validation."""


class AsyncViolationError(ValidationError):
    """An async programming violation was detected."""


class CoverageThresholdError(ValidationError):
    """Coverage fell below the configured threshold."""


class AutoFixFailedError(ValidationError):
    """An automatic fix attempt did not resolve the issue."""


class ValidationAbortedError(ValidationError):
    """Validation was aborted (timeout, user interrupt, etc)."""
