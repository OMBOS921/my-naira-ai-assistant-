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
        extra_http_headers: dict[str, str] | None = None,
        http_credentials: tuple[str, str] | None = None,
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
        url: str = "",
        timeout: float = 30.0,
    ) -> bytes:
        raise BrowserNotImplementedError(context={"operation": "screenshot", "url": url})

    async def back(self, timeout: float | None = None) -> BrowserPage:
        raise BrowserNotImplementedError(context={"operation": "back"})

    async def forward(self, timeout: float | None = None) -> BrowserPage:
        raise BrowserNotImplementedError(context={"operation": "forward"})

    async def reload(self, timeout: float | None = None) -> BrowserPage:
        raise BrowserNotImplementedError(context={"operation": "reload"})

    async def new_tab(self, url: str = "about:blank") -> str:
        raise BrowserNotImplementedError(context={"operation": "new_tab", "url": url})

    async def close_tab(self, page_id: str | None = None) -> None:
        raise BrowserNotImplementedError(context={"operation": "close_tab", "page_id": page_id})

    async def list_tabs(self) -> list[object]:
        raise BrowserNotImplementedError(context={"operation": "list_tabs"})

    async def switch_tab(self, page_id: str) -> None:
        raise BrowserNotImplementedError(context={"operation": "switch_tab", "page_id": page_id})

    async def get_cookies(self, urls: list[str] | None = None) -> list[dict[str, object]]:
        raise BrowserNotImplementedError(context={"operation": "get_cookies"})

    async def set_cookies(self, cookies: list[dict[str, object]]) -> None:
        raise BrowserNotImplementedError(context={"operation": "set_cookies"})

    async def clear_cookies(self) -> None:
        raise BrowserNotImplementedError(context={"operation": "clear_cookies"})

    async def upload_file(self, selector: str, file_paths: str | list[str]) -> None:
        raise BrowserNotImplementedError(context={"operation": "upload_file", "selector": selector})

    async def press_key(self, key: str, selector: str | None = None) -> None:
        raise BrowserNotImplementedError(context={"operation": "press_key", "key": key})

    async def wait_for_selector(self, selector: str, state: str = "visible", timeout: float = 30.0) -> None:
        raise BrowserNotImplementedError(context={"operation": "wait_for_selector", "selector": selector})

    async def select_option(self, selector: str, value: str | list[str], timeout: float = 30.0) -> None:
        raise BrowserNotImplementedError(context={"operation": "select_option", "selector": selector})

    async def hover(self, selector: str, timeout: float = 30.0) -> None:
        raise BrowserNotImplementedError(context={"operation": "hover", "selector": selector})

    async def right_click(self, selector: str, timeout: float = 30.0) -> None:
        raise BrowserNotImplementedError(context={"operation": "right_click", "selector": selector})

    async def drag_and_drop(self, source_selector: str, target_selector: str, timeout: float = 30.0) -> None:
        raise BrowserNotImplementedError(context={"operation": "drag_and_drop", "source": source_selector})

    async def check(self, selector: str, timeout: float = 30.0) -> None:
        raise BrowserNotImplementedError(context={"operation": "check", "selector": selector})

    async def uncheck(self, selector: str, timeout: float = 30.0) -> None:
        raise BrowserNotImplementedError(context={"operation": "uncheck", "selector": selector})

    async def export_pdf(self, save_path: str = "", timeout: float = 30.0) -> str:
        raise BrowserNotImplementedError(context={"operation": "export_pdf"})

    async def wait_for_download(self, timeout: float = 30.0) -> Any:
        raise BrowserNotImplementedError(context={"operation": "wait_for_download"})

    async def get_local_storage(self, key: str | None = None) -> str:
        raise BrowserNotImplementedError(context={"operation": "get_local_storage"})

    async def set_local_storage(self, key: str, value: str) -> None:
        raise BrowserNotImplementedError(context={"operation": "set_local_storage"})

    async def clear_local_storage(self) -> None:
        raise BrowserNotImplementedError(context={"operation": "clear_local_storage"})

    async def get_session_storage(self, key: str | None = None) -> str:
        raise BrowserNotImplementedError(context={"operation": "get_session_storage"})

    async def set_session_storage(self, key: str, value: str) -> None:
        raise BrowserNotImplementedError(context={"operation": "set_session_storage"})

    async def clear_session_storage(self) -> None:
        raise BrowserNotImplementedError(context={"operation": "clear_session_storage"})

    async def close(self) -> None:
        self._logger.debug("LocalBrowserAdapter.close() — no-op")


