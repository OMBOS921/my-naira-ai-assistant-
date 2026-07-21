"""
LocalBrowserAdapter — placeholder browser adapter.

Returns ``is_available=False`` and raises ``BrowserNotImplementedError``
on every operation.  This adapter is used when no real browser driver
(Playwright / Selenium) has been configured.

When a real adapter is wired in, ``BrowserManager`` will use it
in place of this placeholder with zero code changes.
"""

from __future__ import annotations

import logging

from backend.modules.browser._exceptions import BrowserNotImplementedError
from backend.modules.browser._types import BrowserPage, BrowserSearchResponse
from backend.modules.browser.ports.browser_port import BrowserPort

_LOG = logging.getLogger("naira.browser.adapter")


class LocalBrowserAdapter(BrowserPort):
    """Placeholder adapter that signals that no real browser driver
    is available.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    @property
    def is_available(self) -> bool:
        return False

    async def navigate(
        self,
        url: str,
        timeout: float = 30.0,
        extract_content: bool = True,
    ) -> BrowserPage:
        raise BrowserNotImplementedError(context={"operation": "navigate", "url": url})

    async def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: float = 30.0,
    ) -> BrowserSearchResponse:
        raise BrowserNotImplementedError(context={"operation": "search", "query": query})

    async def extract(
        self,
        url: str,
        timeout: float = 30.0,
    ) -> BrowserPage:
        raise BrowserNotImplementedError(context={"operation": "extract", "url": url})

    async def screenshot(
        self,
        url: str,
        timeout: float = 30.0,
    ) -> bytes:
        raise BrowserNotImplementedError(context={"operation": "screenshot", "url": url})

    async def close(self) -> None:
        self._logger.debug("LocalBrowserAdapter.close() — no-op")
