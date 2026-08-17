"""
BrowserExecutor — async execution layer with timeout and error isolation.

Wraps port/adapter operations so that ``BrowserManager`` never deals
with raw exceptions or hanging calls.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

from backend.modules.browser._exceptions import (
    BrowserNotImplementedError,
    BrowserTimeoutError,
)
from backend.modules.browser._types import BrowserSearchResponse
from backend.modules.browser.ports.browser_port import BrowserPort
from backend.types import ToolResult
_LOG = logging.getLogger("naira.browser.executor")


class BrowserExecutor:
    """Safe execution wrapper for browser operations.

    Parameters
    ----------
    adapter : BrowserPort
        The active browser adapter (placeholder or real).
    default_timeout : float
        Default timeout for all operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        adapter: BrowserPort,
        default_timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._adapter = adapter
        self._default_timeout = default_timeout
        self._logger = logger or _LOG

    async def navigate(
        self,
        url: str,
        timeout: float | None = None,
        extract_content: bool = True,
    ) -> ToolResult:
        """Navigate to *url* and return the result.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            page = await asyncio.wait_for(
                self._adapter.navigate(
                    url,
                    timeout=effective_timeout,
                    extract_content=extract_content,
                ),
                timeout=effective_timeout + 1.0,
            )
            return ToolResult(
                status="success",
                output=f"Navigated to {page.url} ({page.title})",
            )
        except BrowserNotImplementedError:
            return ToolResult(
                status="error",
                error="Browser adapter not configured — no Playwright/Selenium driver available",
            )
        except BrowserTimeoutError as exc:
            return ToolResult(
                status="timeout",
                error=f"Navigation to '{url}' timed out: {exc}",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Navigation to '{url}' timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Navigation to '%s' failed: %s", url, exc)
            return ToolResult(
                status="error",
                error=f"Navigation to '{url}' failed: {exc}",
            )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute a web search and return the result.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            response = await asyncio.wait_for(
                self._adapter.search(query, max_results=max_results, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            if not response.results:
                return ToolResult(
                    status="error",
                    error="No search results returned",
                )
            output = _format_search_results(response)
            return ToolResult(status="success", output=output)
        except BrowserNotImplementedError:
            return ToolResult(
                status="error",
                error="Browser adapter not configured — no Playwright/Selenium driver available",
            )
        except BrowserTimeoutError as exc:
            return ToolResult(
                status="timeout",
                error=f"Search timed out: {exc}",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Search timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Search failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Search failed: {exc}",
            )

    async def extract(
        self,
        url: str,
        timeout: float | None = None,
    ) -> ToolResult:
        """Extract content from *url* and return the result.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            page = await asyncio.wait_for(
                self._adapter.extract(url, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            content = page.content or "(no content extracted)"
            return ToolResult(status="success", output=content)
        except BrowserNotImplementedError:
            return ToolResult(
                status="error",
                error="Browser adapter not configured — no Playwright/Selenium driver available",
            )
        except BrowserTimeoutError as exc:
            return ToolResult(
                status="timeout",
                error=f"Content extraction timed out: {exc}",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Content extraction from '{url}' timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Content extraction from '%s' failed: %s", url, exc)
            return ToolResult(
                status="error",
                error=f"Content extraction from '{url}' failed: {exc}",
            )

    async def screenshot(
        self,
        url: str = "",
        save_path: str | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        """Capture a screenshot of *url* (or active page if empty) and return the result."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            raw_bytes = await asyncio.wait_for(
                self._adapter.screenshot(url=url, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            if save_path:
                p = Path(save_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(raw_bytes)
                return ToolResult(status="success", output=f"Screenshot saved to {p}")
            base64_data = base64.b64encode(raw_bytes).decode("ascii")
            return ToolResult(status="success", output=f"data:image/png;base64,{base64_data}")
        except BrowserNotImplementedError:
            return ToolResult(
                status="error",
                error="Browser adapter not configured — no Playwright/Selenium driver available",
            )
        except BrowserTimeoutError as exc:
            return ToolResult(status="timeout", error=f"Screenshot timed out: {exc}")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Screenshot timed out after {effective_timeout}s")
        except Exception as exc:
            self._logger.warning("Screenshot failed: %s", exc)
            return ToolResult(status="error", error=f"Screenshot failed: {exc}")

    async def back(self, timeout: float | None = None) -> ToolResult:
        """Navigate back in browser history."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "back"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            page = await asyncio.wait_for(adapter.back(timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Navigated back to {page.url} ({page.title})")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Back navigation timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Back navigation failed: {exc}")

    async def forward(self, timeout: float | None = None) -> ToolResult:
        """Navigate forward in browser history."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "forward"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            page = await asyncio.wait_for(adapter.forward(timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Navigated forward to {page.url} ({page.title})")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Forward navigation timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Forward navigation failed: {exc}")

    async def reload(self, timeout: float | None = None) -> ToolResult:
        """Reload the current page."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "reload"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            page = await asyncio.wait_for(adapter.reload(timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Reloaded {page.url} ({page.title})")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Reload timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Reload failed: {exc}")

    async def new_tab(self, url: str = "about:blank") -> ToolResult:
        """Open a new browser tab."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "new_tab"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            tab_id = await adapter.new_tab(url=url)
            return ToolResult(status="success", output=f"Opened new tab '{tab_id}' ({url})")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"New tab failed: {exc}")

    async def close_tab(self, page_id: str | None = None) -> ToolResult:
        """Close a browser tab."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "close_tab"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.close_tab(page_id=page_id)
            target = page_id or "active tab"
            return ToolResult(status="success", output=f"Closed tab '{target}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Close tab failed: {exc}")

    async def list_tabs(self) -> ToolResult:
        """List all open browser tabs."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "list_tabs"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            tabs = await adapter.list_tabs()
            output = "\n".join(f"- {getattr(t, 'id', str(t))}: {getattr(t, 'title', '')} ({getattr(t, 'url', '')})" for t in tabs)
            return ToolResult(status="success", output=output or "No open tabs")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"List tabs failed: {exc}")

    async def switch_tab(self, page_id: str) -> ToolResult:
        """Switch active tab."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "switch_tab"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.switch_tab(page_id=page_id)
            return ToolResult(status="success", output=f"Switched to tab '{page_id}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Switch tab failed: {exc}")

    async def get_cookies(self, urls: list[str] | None = None) -> ToolResult:
        """Get browser cookies."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "get_cookies"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            cookies = await adapter.get_cookies(urls=urls)
            return ToolResult(status="success", output=json.dumps(cookies, indent=2))
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Get cookies failed: {exc}")

    async def set_cookies(self, cookies: list[dict[str, Any]]) -> ToolResult:
        """Set browser cookies."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "set_cookies"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.set_cookies(cookies=cookies)
            return ToolResult(status="success", output=f"Successfully set {len(cookies)} cookies")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Set cookies failed: {exc}")

    async def clear_cookies(self) -> ToolResult:
        """Clear browser cookies."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "clear_cookies"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.clear_cookies()
            return ToolResult(status="success", output="Browser cookies cleared")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Clear cookies failed: {exc}")

    async def upload_file(self, selector: str, file_paths: str | list[str]) -> ToolResult:
        """Upload file(s) into file input element."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "upload_file"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.upload_file(selector, file_paths)
            return ToolResult(status="success", output=f"Uploaded file(s) to '{selector}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Upload file failed: {exc}")

    async def press_key(self, key: str, selector: str | None = None) -> ToolResult:
        """Press key on element or active page."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "press_key"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.press_key(key, selector=selector)
            return ToolResult(status="success", output=f"Pressed key '{key}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Press key failed: {exc}")

    async def wait_for_selector(self, selector: str, state: str = "visible", timeout: float | None = None) -> ToolResult:
        """Wait for element matching selector."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "wait_for_selector"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await asyncio.wait_for(adapter.wait_for_selector(selector, state=state, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Element '{selector}' is now {state}")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Wait for selector '{selector}' timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Wait for selector failed: {exc}")

    async def select_option(self, selector: str, value: str | list[str], timeout: float | None = None) -> ToolResult:
        """Select option in dropdown."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "select_option"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await asyncio.wait_for(adapter.select_option(selector, value, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Selected option on '{selector}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Select option timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Select option failed: {exc}")

    async def hover(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Hover over element."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "hover"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await asyncio.wait_for(adapter.hover(selector, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Hovered over '{selector}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Hover timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Hover failed: {exc}")

    async def right_click(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Right-click element."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "right_click"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await asyncio.wait_for(adapter.right_click(selector, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Right-clicked on '{selector}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Right-click timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Right-click failed: {exc}")

    async def drag_and_drop(self, source_selector: str, target_selector: str, timeout: float | None = None) -> ToolResult:
        """Drag and drop element."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "drag_and_drop"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await asyncio.wait_for(adapter.drag_and_drop(source_selector, target_selector, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Dragged '{source_selector}' to '{target_selector}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Drag and drop timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Drag and drop failed: {exc}")

    async def check(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Check checkbox/radio element."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "check"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await asyncio.wait_for(adapter.check(selector, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Checked '{selector}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Check timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Check failed: {exc}")

    async def uncheck(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Uncheck checkbox element."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "uncheck"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await asyncio.wait_for(adapter.uncheck(selector, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Unchecked '{selector}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Uncheck timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Uncheck failed: {exc}")

    async def export_pdf(self, save_path: str = "", timeout: float | None = None) -> ToolResult:
        """Export page as PDF."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "export_pdf"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            out = await asyncio.wait_for(adapter.export_pdf(save_path=save_path, timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Exported PDF to '{out}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="PDF export is only supported in headless Chromium mode")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"PDF export timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"PDF export failed: {exc}")

    async def download_file(self, timeout: float | None = None) -> ToolResult:
        """Wait for download."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "wait_for_download"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            res = await asyncio.wait_for(adapter.wait_for_download(timeout=effective_timeout), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=f"Downloaded file '{getattr(res, 'suggested_filename', '')}' to '{getattr(res, 'path', '')}' ({getattr(res, 'size_bytes', 0)} bytes)")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Download timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Download failed: {exc}")

    async def get_local_storage(self, key: str | None = None) -> ToolResult:
        """Get local storage."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "get_local_storage"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            res = await adapter.get_local_storage(key=key) if hasattr(adapter, "get_local_storage") else ""
            return ToolResult(status="success", output=str(res))
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Get local storage failed: {exc}")

    async def set_local_storage(self, key: str, value: str) -> ToolResult:
        """Set local storage key."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "set_local_storage"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.set_local_storage(key, value)
            return ToolResult(status="success", output=f"Set local storage '{key}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Set local storage failed: {exc}")

    async def clear_local_storage(self) -> ToolResult:
        """Clear local storage."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "clear_local_storage"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.clear_local_storage()
            return ToolResult(status="success", output="Cleared local storage")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Clear local storage failed: {exc}")

    async def get_session_storage(self, key: str | None = None) -> ToolResult:
        """Get session storage."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "get_session_storage"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            res = await adapter.get_session_storage(key=key) if hasattr(adapter, "get_session_storage") else ""
            return ToolResult(status="success", output=str(res))
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Get session storage failed: {exc}")

    async def set_session_storage(self, key: str, value: str) -> ToolResult:
        """Set session storage key."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "set_session_storage"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.set_session_storage(key, value)
            return ToolResult(status="success", output=f"Set session storage '{key}'")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Set session storage failed: {exc}")

    async def clear_session_storage(self) -> ToolResult:
        """Clear session storage."""
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "clear_session_storage"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            await adapter.clear_session_storage()
            return ToolResult(status="success", output="Cleared session storage")
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except Exception as exc:
            return ToolResult(status="error", error=f"Clear session storage failed: {exc}")

    async def execute_js(self, script: str, *args: Any, timeout: float | None = None) -> ToolResult:
        """Execute arbitrary JavaScript in active page context."""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            adapter = getattr(self, "_adapter", None)
            if not adapter or not adapter.is_available or not hasattr(adapter, "execute_js"):
                return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
            res = await asyncio.wait_for(adapter.execute_js(script, *args), timeout=effective_timeout + 1.0)
            return ToolResult(status="success", output=json.dumps(res) if not isinstance(res, str) else res)
        except BrowserNotImplementedError:
            return ToolResult(status="error", error="Browser adapter not configured — no Playwright/Selenium driver available")
        except asyncio.TimeoutError:
            return ToolResult(status="timeout", error=f"Execute JS timed out after {effective_timeout}s")
        except Exception as exc:
            return ToolResult(status="error", error=f"Execute JS failed: {exc}")


    @property
    def is_available(self) -> bool:
        """Return ``True`` if the underlying adapter is usable."""
        return self._adapter.is_available


def _format_search_results(response: BrowserSearchResponse) -> str:
    """Format search results as a plain-text string."""
    lines: list[str] = [f"Search results for '{response.query}':", ""]
    for i, result in enumerate(response.results, 1):
        lines.append(f"{i}. {result.title}")
        lines.append(f"   URL: {result.url}")
        lines.append(f"   {result.snippet}")
        lines.append("")
    return "\n".join(lines).strip()
