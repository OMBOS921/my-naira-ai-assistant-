"""
ProviderErrorClassifier — standard error taxonomy and classification for LLM providers.

Requirement 10 — Distinguish:
- API error
- Authentication error
- Rate limit
- Timeout
- Invalid request
- Network failure
- Provider unavailable
"""

from __future__ import annotations

import socket

from enum import Enum
from typing import Any

from backend.exceptions import (
    LLMError,
    ProviderAPIError,
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class ProviderErrorCategory(Enum):
    """Normalized categories for provider execution errors."""

    API_ERROR = "API_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    INVALID_REQUEST = "INVALID_REQUEST"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


def classify_provider_error(
    exc: Exception, status_code: int | None = None
) -> tuple[ProviderErrorCategory, bool]:
    """Classify an exception and determine whether it is retryable.

    Returns
    -------
    tuple[ProviderErrorCategory, bool]
        Category enum and boolean indicating if request/provider can be retried.
    """
    if isinstance(exc, ProviderInvalidRequestError) or status_code in (400, 422):
        return ProviderErrorCategory.INVALID_REQUEST, False  # Never retry invalid requests!

    if isinstance(exc, ProviderAuthError) or status_code in (401, 403):
        return ProviderErrorCategory.AUTH_ERROR, False  # Fail provider immediately, failover allowed

    if isinstance(exc, ProviderRateLimitError) or status_code == 429:
        return ProviderErrorCategory.RATE_LIMIT, True  # Retryable with backoff or failover

    if isinstance(exc, ProviderTimeoutError) or isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout):
        return ProviderErrorCategory.TIMEOUT, True  # Retryable

    if isinstance(exc, ProviderNetworkError) or isinstance(exc, (ConnectionError, socket.error)):
        return ProviderErrorCategory.NETWORK_FAILURE, True  # Retryable

    if isinstance(exc, ProviderUnavailableError) or status_code in (503, 504):
        return ProviderErrorCategory.PROVIDER_UNAVAILABLE, True  # Failover

    if isinstance(exc, ProviderAPIError) or (status_code is not None and status_code >= 500):
        return ProviderErrorCategory.API_ERROR, True  # Retryable

    # Check error message keywords if status code / exception type wasn't explicit
    err_str = str(exc).lower()
    if "invalid" in err_str or "bad request" in err_str or "unsupported" in err_str:
        return ProviderErrorCategory.INVALID_REQUEST, False
    if "auth" in err_str or "unauthorized" in err_str or "api key" in err_str:
        return ProviderErrorCategory.AUTH_ERROR, False
    if "rate limit" in err_str or "429" in err_str or "quota" in err_str:
        return ProviderErrorCategory.RATE_LIMIT, True
    if "timeout" in err_str or "timed out" in err_str:
        return ProviderErrorCategory.TIMEOUT, True
    if "connection" in err_str or "socket" in err_str or "network" in err_str:
        return ProviderErrorCategory.NETWORK_FAILURE, True

    return ProviderErrorCategory.UNKNOWN, True
