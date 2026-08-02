"""
Browser exception hierarchy.

21_System_Contracts.md §3 — All application exceptions inherit from
``NairaError`` and carry a ``context`` dict.
"""

from __future__ import annotations

from typing import Any

from backend.exceptions import NairaError


class BrowserError(NairaError):
    """Base for all browser-module errors."""


class BrowserTimeoutError(BrowserError):
    """A browser operation exceeded its timeout."""


class BrowserNavigationError(BrowserError):
    """Navigation to a URL failed (unreachable, DNS, TLS, etc.)."""


class BrowserContentError(BrowserError):
    """Content extraction or parsing failed."""


class BrowserSearchError(BrowserError):
    """Web search failed (engine unavailable, rate limited, etc.)."""


class BrowserSessionError(BrowserError):
    """Session-level error (tab not found, already closed, etc.)."""


class BrowserNotImplementedError(BrowserError):
    """The operation is not supported by the current adapter.

    Raised by placeholder adapters (e.g. ``LocalBrowserAdapter``)
    to signal that the real implementation has not been wired yet.
    """

    def __init__(
        self,
        message: str = "Browser adapter not available — no Playwright/Selenium driver configured",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            context=context,
        )


class BrowserDownloadError(BrowserError):
    """A browser file download operation failed."""


class BrowserPermissionError(BrowserError):
    """Operation denied by browser security/sandbox policy."""

