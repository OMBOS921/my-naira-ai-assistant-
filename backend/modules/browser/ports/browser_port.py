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
        extra_http_headers: dict[str, str] | None = None,
        http_credentials: tuple[str, str] | None = None,
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
        url: str = "",
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
    async def wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: float = 30.0,
    ) -> None:
        """Wait for an element matching *selector* to reach *state*."""

    @abstractmethod
    async def select_option(
        self,
        selector: str,
        value: str | list[str],
        timeout: float = 30.0,
    ) -> None:
        """Select option(s) in a dropdown element matching *selector*."""

    @abstractmethod
    async def hover(
        self,
        selector: str,
        timeout: float = 30.0,
    ) -> None:
        """Hover cursor over element matching *selector*."""

    @abstractmethod
    async def right_click(
        self,
        selector: str,
        timeout: float = 30.0,
    ) -> None:
        """Right-click element matching *selector*."""

    @abstractmethod
    async def drag_and_drop(
        self,
        source_selector: str,
        target_selector: str,
        timeout: float = 30.0,
    ) -> None:
        """Drag element from *source_selector* and drop onto *target_selector*."""

    @abstractmethod
    async def check(
        self,
        selector: str,
        timeout: float = 30.0,
    ) -> None:
        """Check a checkbox or radio element matching *selector*."""

    @abstractmethod
    async def uncheck(
        self,
        selector: str,
        timeout: float = 30.0,
    ) -> None:
        """Uncheck a checkbox element matching *selector*."""

    @abstractmethod
    async def export_pdf(
        self,
        save_path: str = "",
        timeout: float = 30.0,
    ) -> str:
        """Export current page as a PDF file."""

    @abstractmethod
    async def wait_for_download(
        self,
        timeout: float = 30.0,
    ) -> DownloadResult:
        """Wait for a file download event to complete."""

    @abstractmethod
    async def get_local_storage(self, key: str | None = None) -> str:
        """Get local storage content or specific key."""

    @abstractmethod
    async def set_local_storage(self, key: str, value: str) -> None:
        """Set key in local storage."""

    @abstractmethod
    async def clear_local_storage(self) -> None:
        """Clear local storage."""

    @abstractmethod
    async def get_session_storage(self, key: str | None = None) -> str:
        """Get session storage content or specific key."""

    @abstractmethod
    async def set_session_storage(self, key: str, value: str) -> None:
        """Set key in session storage."""

    @abstractmethod
    async def clear_session_storage(self) -> None:
        """Clear session storage."""

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
