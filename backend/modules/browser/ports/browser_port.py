"""
BrowserPort — abstract port for pluggable browser adapters.

20_Dependency_Rules.md §2 — Port/Adapter pattern.

Concrete adapters (Playwright, Selenium, etc.) implement this ABC
so ``BrowserManager`` remains agnostic of the underlying driver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.browser._types import BrowserPage

from backend.modules.browser._types import BrowserSearchResponse


class BrowserPort(ABC):
    """Abstract browser port.

    Each method corresponds to a high-level browser capability.
    Implementations manage their own driver lifecycle internally.
    """

    @abstractmethod
    async def navigate(
        self,
        url: str,
        timeout: float = 30.0,
        extract_content: bool = True,
    ) -> BrowserPage:
        """Navigate to *url* and return the resulting page.

        Parameters
        ----------
        url : str
            Fully qualified URL to navigate to.
        timeout : float
            Maximum wait time in seconds.
        extract_content : bool
            Whether to extract text content after load.

        Returns
        -------
        BrowserPage
            Immutable snapshot of the loaded page.

        Raises
        ------
        BrowserNavigationError
            If the URL is unreachable or navigation fails.
        BrowserTimeoutError
            If the operation exceeds *timeout*.
        """

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: float = 30.0,
    ) -> BrowserSearchResponse:
        """Execute a web search.

        Parameters
        ----------
        query : str
            Search query string.
        max_results : int
            Maximum number of results to return.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        BrowserSearchResponse
            Search results.

        Raises
        ------
        BrowserSearchError
            If the search engine is unavailable.
        BrowserTimeoutError
            If the operation exceeds *timeout*.
        """

    @abstractmethod
    async def extract(
        self,
        url: str,
        timeout: float = 30.0,
    ) -> BrowserPage:
        """Extract content from *url* without executing JavaScript.

        Useful for static content extraction where full page rendering
        is unnecessary.

        Parameters
        ----------
        url : str
            Fully qualified URL.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        BrowserPage
            The extracted page content.

        Raises
        ------
        BrowserNavigationError
            If the URL is unreachable.
        BrowserTimeoutError
            If the operation exceeds *timeout*.
        """

    @abstractmethod
    async def screenshot(
        self,
        url: str,
        timeout: float = 30.0,
    ) -> bytes:
        """Capture a screenshot of the page at *url*.

        Parameters
        ----------
        url : str
            Fully qualified URL.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        bytes
            PNG-encoded screenshot bytes.

        Raises
        ------
        BrowserNavigationError
            If the URL is unreachable.
        BrowserTimeoutError
            If the operation exceeds *timeout*.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release all driver resources.

        Called during ``BrowserManager.async_shutdown()``.
        Implementations must be idempotent.
        """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the adapter can be used.

        A placeholder adapter (e.g. ``LocalBrowserAdapter``) returns
        ``False``; a fully-initialised Playwright adapter returns
        ``True``.
        """
