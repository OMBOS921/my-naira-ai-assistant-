"""
PlaywrightBrowserAdapter — real Playwright-based browser adapter.

Replaces ``LocalBrowserAdapter`` with a full Playwright implementation.
Lazily launches the browser on first use, manages contexts and pages,
and provides comprehensive browser automation.

BrowserPort methods
-------------------
- navigate, search, extract, screenshot, close, is_available

Additional public API
---------------------
- launch, ensure_initialized, back, forward, reload
- get_current_url, get_title, execute_js
- click, fill, press_key, scroll, upload_file
- get_html, get_visible_text, get_cookies, set_cookies, clear_cookies
- get_local_storage, set_local_storage, clear_local_storage
- get_session_storage, clear_session_storage
- new_tab, close_tab, list_tabs, switch_tab
- set_default_timeout, wait_for_navigation
"""

# ruff: noqa: N806, ANN401

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import re
import time
import urllib.parse
from typing import Any

from backend.modules.browser._downloads import BrowserDownloader
from backend.modules.browser._exceptions import (
    BrowserContentError,
    BrowserDownloadError,
    BrowserError,
    BrowserNavigationError,
    BrowserNotImplementedError,
    BrowserPermissionError,
    BrowserSearchError,
    BrowserSessionError,
    BrowserTimeoutError,
)
from backend.modules.browser._types import (
    BrowserPage,
    BrowserSearchResponse,
    BrowserSearchResult,
    DownloadResult,
)
from backend.modules.browser.ports.browser_port import BrowserPort

_LOG = logging.getLogger("naira.browser.playwright")

# Lazily-imported Playwright types — populated on first successful import
_PW_ERROR: type[Exception] | None = None
_PW_TIMEOUT_ERROR: type[Exception] | None = None
_PW_ASYNC_PLAYWRIGHT: Any = None
_PW_RESPONSE: type | None = None
_HAS_PLAYWRIGHT = False

try:
    from playwright.async_api import (
        Error as _PW_Error,
    )
    from playwright.async_api import (
        Response as _PW_Response,
    )
    from playwright.async_api import (
        TimeoutError as _PW_TimeoutError,
    )
    from playwright.async_api import (
        async_playwright as _async_playwright,
    )
    _HAS_PLAYWRIGHT = True
    _PW_ERROR = _PW_Error
    _PW_TIMEOUT_ERROR = _PW_TimeoutError
    _PW_ASYNC_PLAYWRIGHT = _async_playwright
    _PW_RESPONSE = _PW_Response
except ImportError:
    pass

type _PWTypes = tuple[type[Exception], type[Exception], Any, type]


class PlaywrightBrowserAdapter(BrowserPort):
    """Playwright-based browser adapter.

    Lazily launches a Chromium/Firefox/WebKit browser on the first operation.
    Manages a single browser context and multiple pages (tabs).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        headless: bool = True,
        slow_mo: int = 0,
        launch_args: list[str] | None = None,
        default_timeout: float = 30.0,
        user_data_dir: str | None = None,
        browser_engine: str = "chromium",
    ) -> None:
        self._logger = logger or _LOG
        self._headless = headless
        self._slow_mo = slow_mo
        self._launch_args = launch_args or []
        self._default_timeout_ms = int(default_timeout * 1000)
        self._user_data_dir = user_data_dir
        self._browser_engine = browser_engine.lower()
        self._downloader = BrowserDownloader(logger=logger)

        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._pages: dict[str, Any] = {}
        self._active_page_id: str | None = None
        self._closed: bool = False
        self._initialized: bool = False
        self._init_lock = asyncio.Lock()
        self._page_counter: int = 0

    # ------------------------------------------------------------------
    # Public helpers (beyond BrowserPort)
    # ------------------------------------------------------------------

    async def launch(self) -> None:
        """Explicitly launch the Playwright browser.  Idempotent."""
        if self._closed:
            raise BrowserError("Adapter is closed", context={"operation": "launch"})
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await self._do_launch()

    async def ensure_initialized(self) -> None:
        """Ensure the browser is launched (lazy init)."""
        if not self._initialized:
            await self.launch()

    async def back(self, timeout: float | None = None) -> BrowserPage:
        """Navigate back in history."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.go_back(timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                "Back navigation timed out", context={"timeout": timeout}
            ) from exc
        except PW_Error as exc:
            raise BrowserNavigationError(
                f"Back navigation failed: {exc}",
                context={"operation": "back"},
            ) from exc
        return await self._snapshot(page)

    async def forward(self, timeout: float | None = None) -> BrowserPage:
        """Navigate forward in history."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.go_forward(timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                "Forward navigation timed out", context={"timeout": timeout}
            ) from exc
        except PW_Error as exc:
            raise BrowserNavigationError(
                f"Forward navigation failed: {exc}",
                context={"operation": "forward"},
            ) from exc
        return await self._snapshot(page)

    async def reload(self, timeout: float | None = None) -> BrowserPage:
        """Reload the current page."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.reload(timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                "Reload timed out", context={"timeout": timeout}
            ) from exc
        except PW_Error as exc:
            raise BrowserNavigationError(
                f"Reload failed: {exc}", context={"operation": "reload"}
            ) from exc
        return await self._snapshot(page)

    async def get_current_url(self) -> str:
        """Return the URL of the active page."""
        return self._require_active_page().url

    async def get_title(self) -> str:
        """Return the title of the active page."""
        page = self._require_active_page()
        return await page.title()

    async def execute_js(self, script: str, *args: Any) -> Any:
        """Execute JavaScript in the active page context."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            return await page.evaluate(script, *args)
        except PW_Error as exc:
            raise BrowserError(
                f"JavaScript execution failed: {exc}",
                context={"script": script[:100]},
            ) from exc

    async def click(self, selector: str, timeout: float | None = None) -> None:
        """Click an element matching the CSS selector."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.click(selector, timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Click on '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Click on '{selector}' failed: {exc}",
                context={"selector": selector},
            ) from exc

    async def wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: float | None = None,
    ) -> None:
        """Wait for an element matching *selector* to reach *state*."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        page = self._require_active_page()
        effective_ms = _to_ms(timeout, self._default_timeout_ms)
        try:
            res = page.wait_for_selector(selector, state=state, timeout=effective_ms)
            if inspect.isawaitable(res):
                await res
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Element '{selector}' not {state} after {effective_ms / 1000.0}s",
                context={"selector": selector, "state": state},
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Wait for selector '{selector}' failed: {exc}",
                context={"selector": selector},
            ) from exc

    async def click(self, selector: str, timeout: float | None = None) -> None:
        """Click an element matching the CSS selector."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.click(selector, timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Click on '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Click on '{selector}' failed: {exc}",
                context={"selector": selector},
            ) from exc

    async def fill(self, selector: str, value: str, timeout: float | None = None) -> None:
        """Fill an input field with text."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.fill(selector, value, timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Fill '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Fill '{selector}' failed: {exc}",
                context={"selector": selector},
            ) from exc

    async def select_option(
        self, selector: str, value: str | list[str], timeout: float | None = None
    ) -> None:
        """Select option(s) in a dropdown element matching *selector*."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.select_option(selector, value, timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Select option on '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Select option on '{selector}' failed: {exc}", context={"selector": selector}
            ) from exc

    async def hover(self, selector: str, timeout: float | None = None) -> None:
        """Hover cursor over element matching *selector*."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.hover(selector, timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Hover on '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Hover on '{selector}' failed: {exc}", context={"selector": selector}
            ) from exc

    async def right_click(self, selector: str, timeout: float | None = None) -> None:
        """Right-click element matching *selector*."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.click(selector, button="right", timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Right-click on '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Right-click on '{selector}' failed: {exc}", context={"selector": selector}
            ) from exc

    async def drag_and_drop(
        self, source_selector: str, target_selector: str, timeout: float | None = None
    ) -> None:
        """Drag element from *source_selector* and drop onto *target_selector*."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(source_selector, state="visible", timeout=effective_timeout)
        await self.wait_for_selector(target_selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.drag_and_drop(
                source_selector, target_selector, timeout=_to_ms(timeout, self._default_timeout_ms)
            )
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                "Drag and drop timed out",
                context={"source": source_selector, "target": target_selector},
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Drag and drop failed: {exc}",
                context={"source": source_selector, "target": target_selector},
            ) from exc

    async def check(self, selector: str, timeout: float | None = None) -> None:
        """Check checkbox/radio element matching *selector*."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.check(selector, timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Check on '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Check on '{selector}' failed: {exc}", context={"selector": selector}
            ) from exc

    async def uncheck(self, selector: str, timeout: float | None = None) -> None:
        """Uncheck checkbox element matching *selector*."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        effective_timeout = timeout if timeout is not None else (self._default_timeout_ms / 1000.0)
        await self.wait_for_selector(selector, state="visible", timeout=effective_timeout)
        page = self._require_active_page()
        try:
            await page.uncheck(selector, timeout=_to_ms(timeout, self._default_timeout_ms))
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Uncheck on '{selector}' timed out", context={"selector": selector}
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"Uncheck on '{selector}' failed: {exc}", context={"selector": selector}
            ) from exc

    async def export_pdf(self, save_path: str = "", timeout: float | None = None) -> str:
        """Export current page as PDF (Chromium headless mode only)."""
        if not self._headless or self._browser_engine != "chromium":
            raise BrowserNotImplementedError(
                "PDF export is only supported in headless Chromium mode",
                context={
                    "operation": "export_pdf",
                    "reason": "PDF export is only supported in headless Chromium mode",
                    "headless": self._headless,
                    "engine": self._browser_engine,
                },
            )
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        self._check_playwright_available()
        await self.ensure_initialized()
        page = self._require_active_page()
        effective_ms = _to_ms(timeout, self._default_timeout_ms)
        out_path = save_path or str((Path.cwd() / "data" / "exports" / f"page_{int(time.time())}.pdf").resolve())
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            await page.pdf(path=out_path, timeout=effective_ms)
            return out_path
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError("PDF export timed out", context={"timeout": timeout}) from exc
        except PW_Error as exc:
            raise BrowserError(f"PDF export failed: {exc}") from exc

    async def wait_for_download(self, timeout: float | None = None) -> DownloadResult:
        """Wait for a download event and save the downloaded file to sandboxed dir."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        self._check_playwright_available()
        await self.ensure_initialized()
        page = self._require_active_page()
        effective_ms = _to_ms(timeout, self._default_timeout_ms)
        try:
            async with page.expect_download(timeout=effective_ms) as download_info:
                download = await download_info.value
            filename = download.suggested_filename
            target = self._downloader.prepare_target_file(filename)
            await self._downloader.validate_path(str(target))
            await download.save_as(str(target))
            size = target.stat().st_size if target.exists() else 0
            return DownloadResult(
                path=str(target),
                suggested_filename=filename,
                size_bytes=size,
                url=download.url,
            )
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError("Download timed out", context={"timeout": timeout}) from exc
        except PW_Error as exc:
            raise BrowserDownloadError(f"Download failed: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, (BrowserTimeoutError, BrowserDownloadError, BrowserPermissionError)):
                raise
            raise BrowserDownloadError(f"Download failed: {exc}") from exc

    async def get_local_storage(self, key: str | None = None) -> str:
        """Get local storage content or specific key."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            if key:
                val = await page.evaluate(f"window.localStorage.getItem({json.dumps(key)})")
                return str(val) if val is not None else ""
            res = await page.evaluate("JSON.stringify(window.localStorage)")
            return str(res or "{}")
        except PW_Error as exc:
            raise BrowserError(f"Get local storage failed: {exc}") from exc

    async def set_local_storage(self, key: str, value: str) -> None:
        """Set key in local storage."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.evaluate(f"window.localStorage.setItem({json.dumps(key)}, {json.dumps(value)})")
        except PW_Error as exc:
            raise BrowserError(f"Set local storage failed: {exc}") from exc

    async def clear_local_storage(self) -> None:
        """Clear local storage."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.evaluate("window.localStorage.clear()")
        except PW_Error as exc:
            raise BrowserError(f"Clear local storage failed: {exc}") from exc

    async def get_session_storage(self, key: str | None = None) -> str:
        """Get session storage content or specific key."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            if key:
                val = await page.evaluate(f"window.sessionStorage.getItem({json.dumps(key)})")
                return str(val) if val is not None else ""
            res = await page.evaluate("JSON.stringify(window.sessionStorage)")
            return str(res or "{}")
        except PW_Error as exc:
            raise BrowserError(f"Get session storage failed: {exc}") from exc

    async def set_session_storage(self, key: str, value: str) -> None:
        """Set key in session storage."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.evaluate(f"window.sessionStorage.setItem({json.dumps(key)}, {json.dumps(value)})")
        except PW_Error as exc:
            raise BrowserError(f"Set session storage failed: {exc}") from exc

    async def clear_session_storage(self) -> None:
        """Clear session storage."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.evaluate("window.sessionStorage.clear()")
        except PW_Error as exc:
            raise BrowserError(f"Clear session storage failed: {exc}") from exc

    async def press_key(self, key: str, selector: str | None = None) -> None:
        """Press a keyboard key on active page or element."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        target = selector or "body"
        try:
            await page.press(target, key)
        except PW_Error as exc:
            raise BrowserError(
                f"Key press '{key}' failed: {exc}", context={"key": key}
            ) from exc


    async def scroll(self, delta_x: int = 0, delta_y: int = 500) -> None:
        """Scroll the page by the given delta."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            await page.evaluate(f"window.scrollBy({delta_x}, {delta_y})")
        except PW_Error as exc:
            raise BrowserError(
                f"Scroll failed: {exc}",
                context={"delta_x": delta_x, "delta_y": delta_y},
            ) from exc

    async def upload_file(
        self, selector: str, file_paths: str | list[str], timeout: float | None = None
    ) -> None:
        """Upload a file via a file input element."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        page = self._require_active_page()
        files = [file_paths] if isinstance(file_paths, str) else file_paths
        try:
            await page.set_input_files(
                selector, files, timeout=_to_ms(timeout, self._default_timeout_ms)
            )
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"File upload '{selector}' timed out",
                context={"selector": selector},
            ) from exc
        except PW_Error as exc:
            raise BrowserError(
                f"File upload '{selector}' failed: {exc}",
                context={"selector": selector},
            ) from exc

    async def get_html(self) -> str:
        """Return the raw HTML of the active page."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            return await page.content()
        except PW_Error as exc:
            raise BrowserContentError(
                f"Failed to get page HTML: {exc}",
                context={"operation": "get_html"},
            ) from exc

    async def get_visible_text(self) -> str:
        """Return the visible text content of the active page."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            text = await page.inner_text("body")
        except PW_Error as exc:
            raise BrowserContentError(
                f"Failed to get visible text: {exc}",
                context={"operation": "get_visible_text"},
            ) from exc
        return re.sub(r"\s+", " ", text).strip()

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Return all cookies for the current context."""
        await self.ensure_initialized()
        if self._context is None:
            return []
        PW_Error, _, _, _ = self._pw_types()
        try:
            return await self._context.cookies()
        except PW_Error as exc:
            raise BrowserError(
                f"Failed to get cookies: {exc}", context={"operation": "get_cookies"}
            ) from exc

    async def set_cookies(self, cookies: list[dict[str, Any]]) -> None:
        """Set cookies in the current context."""
        await self.ensure_initialized()
        if self._context is None:
            return
        PW_Error, _, _, _ = self._pw_types()
        try:
            await self._context.add_cookies(cookies)
        except PW_Error as exc:
            raise BrowserError(
                f"Failed to set cookies: {exc}", context={"operation": "set_cookies"}
            ) from exc

    async def clear_cookies(self) -> None:
        """Clear all cookies in the current context."""
        await self.ensure_initialized()
        if self._context is None:
            return
        PW_Error, _, _, _ = self._pw_types()
        try:
            await self._context.clear_cookies()
        except PW_Error as exc:
            raise BrowserError(
                f"Failed to clear cookies: {exc}",
                context={"operation": "clear_cookies"},
            ) from exc

    async def get_local_storage(self) -> str:
        """Return all local storage entries as JSON string."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            return await page.evaluate("JSON.stringify(window.localStorage)")
        except PW_Error as exc:
            raise BrowserError(
                f"Failed to get local storage: {exc}",
                context={"operation": "get_local_storage"},
            ) from exc

    async def set_local_storage(self, key: str, value: str) -> None:
        """Set a local storage entry."""
        page = self._require_active_page()
        try:
            await page.evaluate(f"window.localStorage.setItem('{key}', '{value}')")
        except Exception as exc:
            raise BrowserError(
                f"Failed to set local storage: {exc}", context={"key": key}
            ) from exc

    async def clear_local_storage(self) -> None:
        """Clear all local storage entries."""
        page = self._require_active_page()
        try:
            await page.evaluate("window.localStorage.clear()")
        except Exception as exc:
            raise BrowserError(
                f"Failed to clear local storage: {exc}",
                context={"operation": "clear_local_storage"},
            ) from exc

    async def get_session_storage(self) -> str:
        """Return all session storage entries as JSON string."""
        PW_Error, _, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            return await page.evaluate("JSON.stringify(window.sessionStorage)")
        except PW_Error as exc:
            raise BrowserError(
                f"Failed to get session storage: {exc}",
                context={"operation": "get_session_storage"},
            ) from exc

    async def clear_session_storage(self) -> None:
        """Clear all session storage entries."""
        page = self._require_active_page()
        try:
            await page.evaluate("window.sessionStorage.clear()")
        except Exception as exc:
            raise BrowserError(
                f"Failed to clear session storage: {exc}",
                context={"operation": "clear_session_storage"},
            ) from exc

    async def new_tab(self, url: str = "about:blank") -> str:
        """Open a new tab (page) in the current context.

        Returns the page identifier.
        """
        PW_Error, _, _, _ = self._pw_types()
        await self.ensure_initialized()
        if self._context is None:
            raise BrowserError(
                "No browser context available", context={"operation": "new_tab"}
            )
        try:
            page = await self._context.new_page()
            if url and url != "about:blank":
                await page.goto(url, timeout=min(self._default_timeout_ms, 30000))
            page_id = self._next_page_id()
            self._pages[page_id] = page
            self._active_page_id = page_id
            return page_id
        except PW_Error as exc:
            raise BrowserSessionError(
                f"Failed to open new tab: {exc}", context={"url": url}
            ) from exc

    async def close_tab(self, page_id: str | None = None) -> None:
        """Close a tab by its identifier.

        If *page_id* is ``None``, closes the active tab.
        If it's the last tab, a new blank tab is created.
        """
        if page_id is None:
            page_id = self._active_page_id
        if page_id is None or page_id not in self._pages:
            raise BrowserSessionError(
                f"Tab '{page_id}' not found",
                context={"operation": "close_tab", "page_id": page_id},
            )
        page = self._pages.pop(page_id)
        with contextlib.suppress(Exception):
            await page.close()
        if self._active_page_id == page_id:
            self._active_page_id = next(iter(self._pages)) if self._pages else None
        if not self._pages:
            blank_id = await self.new_tab("about:blank")
            self._active_page_id = blank_id

    def list_tabs(self) -> list[dict[str, Any]]:
        """Return metadata for all open tabs."""
        return [
            {"id": pid, "url": p.url}
            for pid, p in self._pages.items()
        ]

    def switch_tab(self, page_id: str) -> bool:
        """Switch the active tab.  Returns ``True`` if successful."""
        if page_id in self._pages:
            self._active_page_id = page_id
            return True
        return False

    def set_default_timeout(self, timeout: float) -> None:
        """Set the default timeout in seconds for all operations."""
        self._default_timeout_ms = int(timeout * 1000)

    async def wait_for_navigation(
        self, timeout: float | None = None, url: str | None = None
    ) -> BrowserPage:
        """Wait for the active page to complete navigation."""
        PW_Error, PW_TimeoutError, _, _ = self._pw_types()
        page = self._require_active_page()
        try:
            if url:
                await page.wait_for_url(url, timeout=_to_ms(timeout, self._default_timeout_ms))
            else:
                await page.wait_for_load_state(
                    "networkidle", timeout=_to_ms(timeout, self._default_timeout_ms)
                )
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                "Navigation wait timed out", context={"timeout": timeout}
            ) from exc
        except PW_Error as exc:
            raise BrowserNavigationError(
                f"Navigation wait failed: {exc}",
                context={"operation": "wait_for_navigation"},
            ) from exc
        return await self._snapshot(page)

    # ------------------------------------------------------------------
    # BrowserPort implementation
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self._initialized and (self._browser is not None or self._context is not None)

    async def navigate(
        self,
        url: str,
        timeout: float = 30.0,
        extract_content: bool = True,
        extra_http_headers: dict[str, str] | None = None,
        http_credentials: tuple[str, str] | None = None,
    ) -> BrowserPage:
        """Navigate to *url* and return the resulting page."""
        PW_Error, PW_TimeoutError, PW_async_playwright, PW_Response = self._pw_types()
        self._check_playwright_available()
        await self.ensure_initialized()
        if extra_http_headers and self._context:
            with contextlib.suppress(Exception):
                await self._context.set_extra_http_headers(extra_http_headers)
        page = self._require_active_page()
        effective_ms = _to_ms(timeout, self._default_timeout_ms)

        try:
            resp = await page.goto(url, timeout=effective_ms, wait_until="load")
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Navigation to '{url}' timed out after {timeout}s",
                context={"url": url, "timeout": timeout},
            ) from exc
        except PW_Error as exc:
            raise BrowserNavigationError(
                f"Navigation to '{url}' failed: {exc}",
                context={"url": url},
            ) from exc

        if isinstance(resp, PW_Response):
            status_code = resp.status
            headers = dict(resp.headers)
        else:
            status_code = 0
            headers = {}

        title = await page.title()
        html = await page.content() if extract_content else None
        text = self._extract_text(html) if html else None

        return BrowserPage(
            url=page.url,
            title=title,
            content=text,
            html=html,
            status_code=status_code,
            headers=headers,
            duration_ms=time.monotonic(),
        )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: float = 30.0,
    ) -> BrowserSearchResponse:
        """Execute a web search via DuckDuckGo HTML search."""
        PW_Error, PW_TimeoutError, PW_async_playwright, PW_Response = self._pw_types()
        self._check_playwright_available()
        await self.ensure_initialized()
        page = self._require_active_page()
        effective_ms = _to_ms(timeout, self._default_timeout_ms)

        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query, safe='')}"
        start_time = time.monotonic()

        try:
            await page.goto(search_url, timeout=effective_ms, wait_until="domcontentloaded")
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Search timed out after {timeout}s",
                context={"query": query, "timeout": timeout},
            ) from exc
        except PW_Error as exc:
            raise BrowserSearchError(
                f"Search failed: {exc}", context={"query": query}
            ) from exc

        duration = time.monotonic() - start_time
        results: list[BrowserSearchResult] = []

        try:
            links = await page.query_selector_all("a.result__a")
            snippets = await page.query_selector_all(".result__snippet")
            if not links:
                links = await page.query_selector_all("a.result__url")
                snippets = await page.query_selector_all(".result__snippet")
            if not links:
                links = await page.query_selector_all(".result__title a")
                snippets = await page.query_selector_all(".result__snippet")

            for i, link in enumerate(links):
                if len(results) >= max_results:
                    break
                href = await link.get_attribute("href") or ""
                title_text = await link.inner_text()
                snippet_text = ""
                if i < len(snippets):
                    snippet_text = await snippets[i].inner_text()
                results.append(
                    BrowserSearchResult(
                        title=title_text.strip(),
                        url=_clean_search_url(href),
                        snippet=snippet_text.strip(),
                    )
                )
        except Exception:
            pass

        return BrowserSearchResponse(
            query=query,
            results=tuple(results),
            total_estimate=len(results),
            duration_ms=duration * 1000,
        )

    async def extract(
        self,
        url: str,
        timeout: float = 30.0,
    ) -> BrowserPage:
        """Extract content from *url* without executing JavaScript."""
        PW_Error, PW_TimeoutError, PW_async_playwright, PW_Response = self._pw_types()
        self._check_playwright_available()
        await self.ensure_initialized()
        page = self._require_active_page()
        effective_ms = _to_ms(timeout, self._default_timeout_ms)

        try:
            resp = await page.goto(url, timeout=effective_ms, wait_until="domcontentloaded")
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Extraction from '{url}' timed out after {timeout}s",
                context={"url": url, "timeout": timeout},
            ) from exc
        except PW_Error as exc:
            raise BrowserNavigationError(
                f"Extraction from '{url}' failed: {exc}",
                context={"url": url},
            ) from exc

        if isinstance(resp, PW_Response):
            status_code = resp.status
            headers = dict(resp.headers)
        else:
            status_code = 0
            headers = {}

        title = await page.title()
        html = await page.content()
        text = self._extract_text(html)

        return BrowserPage(
            url=page.url,
            title=title,
            content=text,
            html=html,
            status_code=status_code,
            headers=headers,
            duration_ms=time.monotonic(),
        )

    async def screenshot(
        self,
        url: str,
        timeout: float = 30.0,
    ) -> bytes:
        """Capture a screenshot of *url*."""
        PW_Error, PW_TimeoutError, PW_async_playwright, PW_Response = self._pw_types()
        self._check_playwright_available()
        await self.ensure_initialized()
        page = self._require_active_page()
        effective_ms = _to_ms(timeout, self._default_timeout_ms)

        try:
            await page.goto(url, timeout=effective_ms, wait_until="load")
        except PW_TimeoutError as exc:
            raise BrowserTimeoutError(
                f"Screenshot navigation to '{url}' timed out after {timeout}s",
                context={"url": url, "timeout": timeout},
            ) from exc
        except PW_Error as exc:
            raise BrowserNavigationError(
                f"Screenshot navigation to '{url}' failed: {exc}",
                context={"url": url},
            ) from exc

        try:
            return await page.screenshot(full_page=True, type="png")
        except PW_Error as exc:
            raise BrowserError(
                f"Screenshot capture failed: {exc}", context={"url": url}
            ) from exc

    async def close(self) -> None:
        """Release all Playwright resources.  Idempotent."""
        if self._closed:
            return
        self._closed = True
        errors: list[str] = []

        for pid, p in list(self._pages.items()):
            try:
                await p.close()
            except Exception as exc:
                errors.append(f"page '{pid}': {exc}")
        self._pages.clear()
        self._active_page_id = None

        if self._context is not None:
            try:
                await self._context.close()
            except Exception as exc:
                errors.append(f"context: {exc}")
            self._context = None

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as exc:
                errors.append(f"browser: {exc}")
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as exc:
                errors.append(f"playwright: {exc}")
            self._playwright = None

        self._initialized = False

        if errors:
            self._logger.warning(
                "close() completed with %d error(s): %s", len(errors), "; ".join(errors)
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pw_types() -> _PWTypes:
        """Return (Error, TimeoutError, async_playwright, Response) or raise."""
        if not _HAS_PLAYWRIGHT:
            raise BrowserNotImplementedError(
                context={"error": "playwright package is not installed"},
            )
        return (
            _PW_ERROR,
            _PW_TIMEOUT_ERROR,
            _PW_ASYNC_PLAYWRIGHT,
            _PW_RESPONSE,
        )  # type: ignore[return-value]

    @staticmethod
    def _check_playwright_available() -> None:
        """Raise ``BrowserNotImplementedError`` if Playwright is not installed."""
        if not _HAS_PLAYWRIGHT:
            raise BrowserNotImplementedError(
                context={"error": "playwright package is not installed"},
            )

    async def _do_launch(self) -> None:
        _, _, PW_async_playwright, _ = self._pw_types()
        engine_type = self._browser_engine.lower()
        self._logger.info("Launching Playwright browser engine=%s (headless=%s) ...", engine_type, self._headless)
        try:
            pw = await PW_async_playwright().start()
            if engine_type == "firefox":
                engine = pw.firefox
            elif engine_type == "webkit":
                engine = pw.webkit
            else:
                engine = pw.chromium

            browser_args = self._launch_args if engine_type == "chromium" else []
            viewport = {"width": 1280, "height": 720}
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

            if self._user_data_dir:
                context = await engine.launch_persistent_context(
                    self._user_data_dir,
                    headless=self._headless,
                    slow_mo=self._slow_mo,
                    args=browser_args,
                    viewport=viewport,
                    user_agent=user_agent,
                )
                browser = None
                page = context.pages[0] if context.pages else await context.new_page()
            else:
                browser = await engine.launch(
                    headless=self._headless,
                    slow_mo=self._slow_mo,
                    args=browser_args,
                )
                context = await browser.new_context(
                    viewport=viewport,
                    user_agent=user_agent,
                )
                page = await context.new_page()

            page_id = self._next_page_id()
            self._playwright = pw
            self._browser = browser
            self._context = context
            self._pages[page_id] = page
            self._active_page_id = page_id
            self._initialized = True
            self._logger.info("Playwright browser launched successfully")
        except Exception:
            self._initialized = False
            await self._cleanup_partial()
            raise

    async def _cleanup_partial(self) -> None:
        for p in list(self._pages.values()):
            with contextlib.suppress(Exception):
                await p.close()
        self._pages.clear()
        if self._context is not None:
            with contextlib.suppress(Exception):
                await self._context.close()
            self._context = None
        if self._browser is not None:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
            self._playwright = None

    def _require_active_page(self) -> Any:
        if not self._initialized:
            raise BrowserError(
                "Browser not initialized — call launch() or ensure_initialized() first",
            )
        if self._active_page_id is None or self._active_page_id not in self._pages:
            raise BrowserSessionError("No active tab available")
        return self._pages[self._active_page_id]

    def _next_page_id(self) -> str:
        self._page_counter += 1
        return f"page_{self._page_counter:04d}"

    async def _snapshot(self, page: Any) -> BrowserPage:
        html = await page.content()
        return BrowserPage(
            url=page.url,
            title=await page.title(),
            content=self._extract_text(html),
            html=html,
            status_code=0,
        )

    @staticmethod
    def _extract_text(html: str) -> str:
        cleaned = re.sub(
            r"<(script|style)[^>]*>.*?</\1>", "", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&")
        cleaned = cleaned.replace("&lt;", "<").replace("&gt;", ">")
        return re.sub(r"\s+", " ", cleaned).strip()


def _to_ms(timeout: float | None, default_ms: int) -> int:
    if timeout is None or timeout <= 0:
        return default_ms
    return int(timeout * 1000)


def _clean_search_url(url: str) -> str:
    if "uddg=" in url:
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        redirect = params.get("uddg", [None])[0]
        if redirect:
            return redirect
    return url
