"""
BrowserManager — the single public class for the browser module.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §15 — Tool contracts.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.browser._content_extractor import BrowserContentExtractor
from backend.modules.browser._executor import BrowserExecutor
from backend.modules.browser._local_adapter import LocalBrowserAdapter
from backend.modules.browser._navigation import BrowserNavigation
from backend.modules.browser._playwright_adapter import (
    _HAS_PLAYWRIGHT,
    PlaywrightBrowserAdapter,
)
from backend.modules.browser._search import BrowserSearch
from backend.modules.browser._session import BrowserSession
from backend.modules.browser.ports.browser_port import BrowserPort
from backend.types import ToolResult
_LOG = logging.getLogger("naira.browser")


class BrowserManager:
    """Central browser manager — navigation, search, content extraction.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        ``EventBus`` instance for event emission.
    capability_manager : object | None
        ``CapabilityManager`` instance for capability registration.
    tool_manager : object | None
        ``ToolManager`` instance for tool registration.
    adapter : BrowserPort | None
        Browser adapter to use.  Defaults to ``LocalBrowserAdapter``
        (placeholder mode).
    default_timeout : float
        Default timeout for browser operations (default 30.0).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        tool_manager: object | None = None,
        security_manager: object | None = None,
        adapter: BrowserPort | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._security_manager = security_manager
        self._degraded: bool = False
        self._default_timeout = default_timeout

        browser_cfg = getattr(config, "browser", None) if config else None
        user_data_dir = getattr(browser_cfg, "user_data_dir", None) if browser_cfg else None
        browser_engine = getattr(browser_cfg, "browser_engine", "chromium") if browser_cfg else "chromium"

        # Internal components
        if adapter is not None:
            self._adapter = adapter
            self._logger.info(
                "Browser adapter explicitly provided: %s",
                type(adapter).__name__,
            )
        elif _HAS_PLAYWRIGHT:
            self._adapter = PlaywrightBrowserAdapter(
                logger=logger,
                user_data_dir=user_data_dir,
                browser_engine=browser_engine,
            )
            self._logger.info(
                "Browser adapter selected: PlaywrightBrowserAdapter (playwright available)",
            )
        else:
            self._adapter = LocalBrowserAdapter(logger=logger)
            self._logger.info(
                "Browser adapter selected: LocalBrowserAdapter (playwright not installed)",
            )
        self._session = BrowserSession(logger=logger)
        self._navigation = BrowserNavigation(logger=logger)
        self._search = BrowserSearch(logger=logger)
        self._extractor = BrowserContentExtractor(logger=logger)
        self._executor = BrowserExecutor(
            adapter=self._adapter,
            default_timeout=default_timeout,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the browser module.

        Registers the ``browser`` capability and system tools for
        navigation, search, and content extraction.
        """
        self._register_capability()
        self._register_tools()
        adapter_name = type(self._adapter).__name__
        available = self._executor.is_available
        self._logger.info(
            "Browser manager initialised — adapter=%s adapter_available=%s",
            adapter_name,
            available,
        )

    async def async_shutdown(self) -> None:
        """Release browser adapter resources and clear session state."""
        try:
            await self._adapter.close()
        except Exception as exc:
            self._logger.warning("Error closing browser adapter: %s", exc)
        self._session.clear()
        self._degraded = False
        self._logger.info("Browser manager shut down.")

    def degrade(self) -> None:
        """Mark the module as degraded and release adapter resources."""
        self._degraded = True
        self._session.clear()
        self._logger.warning("Browser manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Navigation API
    # ------------------------------------------------------------------

    async def navigate(
        self,
        url: str,
        timeout: float | None = None,
        extract_content: bool = True,
    ) -> ToolResult:
        """Navigate to a URL and return the result.

        Parameters
        ----------
        url : str
            The URL to navigate to.
        timeout : float | None
            Per-operation timeout (defaults to module default).
        extract_content : bool
            Whether to extract text content after load.

        Returns
        -------
        ToolResult
            The navigation result.
        """
        self._ensure_not_degraded()
        # Validate the URL first
        try:
            validated_url = self._navigation.validate_url(url)
        except Exception as exc:
            return ToolResult(
                status="error",
                error=f"Invalid URL: {exc}",
            )

        await self._emit_event_async("browser.navigate_start", {
            "url": validated_url,
        })
        result = await self._executor.navigate(
            validated_url,
            timeout=timeout,
            extract_content=extract_content,
        )
        await self._emit_event_async("browser.navigate_complete", {
            "url": validated_url,
            "status": result.status,
        })
        return result

    async def search(
        self,
        query: str,
        max_results: int = 10,
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute a web search.

        Parameters
        ----------
        query : str
            Search query.
        max_results : int
            Maximum number of results.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            The search result.
        """
        self._ensure_not_degraded()
        await self._emit_event_async("browser.search_start", {
            "query": query,
        })
        result = await self._executor.search(query, max_results=max_results, timeout=timeout)
        await self._emit_event_async("browser.search_complete", {
            "query": query,
            "status": result.status,
        })
        return result

    async def extract(
        self,
        url: str,
        timeout: float | None = None,
    ) -> ToolResult:
        """Extract content from a URL.

        Parameters
        ----------
        url : str
            The URL to extract content from.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            The extraction result.
        """
        self._ensure_not_degraded()
        try:
            validated_url = self._navigation.validate_url(url)
        except Exception as exc:
            return ToolResult(
                status="error",
                error=f"Invalid URL: {exc}",
            )

        await self._emit_event_async("browser.extract_start", {
            "url": validated_url,
        })
        result = await self._executor.extract(validated_url, timeout=timeout)
        await self._emit_event_async("browser.extract_complete", {
            "url": validated_url,
            "status": result.status,
        })
        return result

    async def click(
        self,
        selector: str,
        timeout: float | None = None,
    ) -> ToolResult:
        """Click an element matching the CSS selector.

        Parameters
        ----------
        selector : str
            CSS selector for the target element.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            Execution result.
        """
        self._ensure_not_degraded()
        effective_timeout = timeout if timeout is not None else self._default_timeout
        await self._emit_event_async("browser.click_start", {"selector": selector})
        try:
            adapter = getattr(self._executor, "_adapter", self._adapter)
            if not adapter.is_available or not hasattr(adapter, "click"):
                res = ToolResult(
                    status="error",
                    error="Browser adapter not configured — no Playwright/Selenium driver available",
                )
                await self._emit_event_async("browser.click_complete", {"selector": selector, "status": res.status})
                return res
            await asyncio.wait_for(
                adapter.click(selector, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            res = ToolResult(
                status="success",
                output=f"Successfully clicked element with selector '{selector}'",
            )
        except asyncio.TimeoutError:
            res = ToolResult(
                status="timeout",
                error=f"Click on '{selector}' timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Click on '%s' failed: %s", selector, exc)
            res = ToolResult(
                status="error",
                error=f"Click on '{selector}' failed: {exc}",
            )
        await self._emit_event_async("browser.click_complete", {"selector": selector, "status": res.status})
        return res

    async def fill(
        self,
        selector: str,
        text: str,
        timeout: float | None = None,
    ) -> ToolResult:
        """Fill an input field matching the CSS selector with text.

        Parameters
        ----------
        selector : str
            CSS selector for the target element.
        text : str
            Text value to input.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            Execution result.
        """
        self._ensure_not_degraded()
        effective_timeout = timeout if timeout is not None else self._default_timeout
        await self._emit_event_async("browser.fill_start", {"selector": selector})
        try:
            adapter = getattr(self._executor, "_adapter", self._adapter)
            if not adapter.is_available or not hasattr(adapter, "fill"):
                res = ToolResult(
                    status="error",
                    error="Browser adapter not configured — no Playwright/Selenium driver available",
                )
                await self._emit_event_async("browser.fill_complete", {"selector": selector, "status": res.status})
                return res
            await asyncio.wait_for(
                adapter.fill(selector, text, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            res = ToolResult(
                status="success",
                output=f"Successfully filled element '{selector}' with provided text",
            )
        except asyncio.TimeoutError:
            res = ToolResult(
                status="timeout",
                error=f"Fill on '{selector}' timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Fill on '%s' failed: %s", selector, exc)
            res = ToolResult(
                status="error",
                error=f"Fill on '{selector}' failed: {exc}",
            )
        await self._emit_event_async("browser.fill_complete", {"selector": selector, "status": res.status})
        return res

    async def scroll(
        self,
        delta_x: int = 0,
        delta_y: int = 500,
        timeout: float | None = None,
    ) -> ToolResult:
        """Scroll the active page by horizontal and vertical pixel deltas.

        Parameters
        ----------
        delta_x : int
            Horizontal scroll pixel delta (default 0).
        delta_y : int
            Vertical scroll pixel delta (default 500).
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            Execution result.
        """
        self._ensure_not_degraded()
        effective_timeout = timeout if timeout is not None else self._default_timeout
        await self._emit_event_async("browser.scroll_start", {"delta_x": delta_x, "delta_y": delta_y})
        try:
            adapter = getattr(self._executor, "_adapter", self._adapter)
            if not adapter.is_available or not hasattr(adapter, "scroll"):
                res = ToolResult(
                    status="error",
                    error="Browser adapter not configured — no Playwright/Selenium driver available",
                )
                await self._emit_event_async("browser.scroll_complete", {"status": res.status})
                return res
            await asyncio.wait_for(
                adapter.scroll(delta_x=delta_x, delta_y=delta_y),
                timeout=effective_timeout + 1.0,
            )
            res = ToolResult(
                status="success",
                output=f"Successfully scrolled page by delta_x={delta_x}, delta_y={delta_y}",
            )
        except asyncio.TimeoutError:
            res = ToolResult(
                status="timeout",
                error=f"Scroll action timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Scroll action failed: %s", exc)
            res = ToolResult(
                status="error",
                error=f"Scroll action failed: {exc}",
            )
        await self._emit_event_async("browser.scroll_complete", {"status": res.status})
        return res

    async def extract_text(
        self,
        selector: str | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        """Extract visible text from active page or specific CSS selector.

        Parameters
        ----------
        selector : str | None
            Optional CSS selector targeting specific element.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            Execution result containing extracted text.
        """
        self._ensure_not_degraded()
        effective_timeout = timeout if timeout is not None else self._default_timeout
        await self._emit_event_async("browser.extract_text_start", {"selector": selector})
        try:
            import json
            adapter = getattr(self._executor, "_adapter", self._adapter)
            if not adapter.is_available:
                res = ToolResult(
                    status="error",
                    error="Browser adapter not configured — no Playwright/Selenium driver available",
                )
                await self._emit_event_async("browser.extract_text_complete", {"status": res.status})
                return res

            if selector and hasattr(adapter, "execute_js"):
                script = f"document.querySelector({json.dumps(selector)})?.innerText || ''"
                text = await asyncio.wait_for(
                    adapter.execute_js(script),
                    timeout=effective_timeout,
                )
            elif hasattr(adapter, "get_visible_text"):
                text = await asyncio.wait_for(
                    adapter.get_visible_text(),
                    timeout=effective_timeout,
                )
            else:
                res = ToolResult(
                    status="error",
                    error="Browser adapter does not support text extraction",
                )
                await self._emit_event_async("browser.extract_text_complete", {"status": res.status})
                return res

            res = ToolResult(
                status="success",
                output=text if text else "(no visible text found)",
            )
        except asyncio.TimeoutError:
            res = ToolResult(
                status="timeout",
                error=f"Extract text timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Extract text failed: %s", exc)
            res = ToolResult(
                status="error",
                error=f"Extract text failed: {exc}",
            )
        await self._emit_event_async("browser.extract_text_complete", {"status": res.status})
        return res

    async def screenshot(
        self,
        url: str = "",
        save_path: str | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        """Capture a screenshot of active page or given URL."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.screenshot_start", {"url": url})
        result = await self._executor.screenshot(url=url, save_path=save_path, timeout=timeout)
        await self._emit_event_async("browser.screenshot_complete", {"status": result.status})
        return result

    async def back(self, timeout: float | None = None) -> ToolResult:
        """Navigate back in browser history."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.back_start", {})
        result = await self._executor.back(timeout=timeout)
        await self._emit_event_async("browser.back_complete", {"status": result.status})
        return result

    async def forward(self, timeout: float | None = None) -> ToolResult:
        """Navigate forward in browser history."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.forward_start", {})
        result = await self._executor.forward(timeout=timeout)
        await self._emit_event_async("browser.forward_complete", {"status": result.status})
        return result

    async def reload(self, timeout: float | None = None) -> ToolResult:
        """Reload current page."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.reload_start", {})
        result = await self._executor.reload(timeout=timeout)
        await self._emit_event_async("browser.reload_complete", {"status": result.status})
        return result

    async def new_tab(self, url: str = "about:blank") -> ToolResult:
        """Open a new browser tab."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.new_tab_start", {"url": url})
        result = await self._executor.new_tab(url=url)
        await self._emit_event_async("browser.new_tab_complete", {"status": result.status})
        return result

    async def close_tab(self, tab_id: str | None = None) -> ToolResult:
        """Close a browser tab."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.close_tab_start", {"tab_id": tab_id})
        result = await self._executor.close_tab(page_id=tab_id)
        await self._emit_event_async("browser.close_tab_complete", {"status": result.status})
        return result

    async def list_tabs(self) -> ToolResult:
        """List open browser tabs."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.list_tabs_start", {})
        result = await self._executor.list_tabs()
        await self._emit_event_async("browser.list_tabs_complete", {"status": result.status})
        return result

    async def switch_tab(self, tab_id: str) -> ToolResult:
        """Switch active browser tab."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.switch_tab_start", {"tab_id": tab_id})
        result = await self._executor.switch_tab(page_id=tab_id)
        await self._emit_event_async("browser.switch_tab_complete", {"status": result.status})
        return result

    async def get_cookies(self, urls: list[str] | None = None) -> ToolResult:
        """Get browser cookies."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.get_cookies_start", {})
        result = await self._executor.get_cookies(urls=urls)
        await self._emit_event_async("browser.get_cookies_complete", {"status": result.status})
        return result

    async def set_cookies(self, cookies: list[dict[str, Any]]) -> ToolResult:
        """Set browser cookies."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.set_cookies_start", {})
        result = await self._executor.set_cookies(cookies=cookies)
        await self._emit_event_async("browser.set_cookies_complete", {"status": result.status})
        return result

    async def clear_cookies(self) -> ToolResult:
        """Clear browser cookies."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.clear_cookies_start", {})
        result = await self._executor.clear_cookies()
        await self._emit_event_async("browser.clear_cookies_complete", {"status": result.status})
        return result

    async def upload_file(self, selector: str, file_paths: str | list[str]) -> ToolResult:
        """Upload file(s) into file input element."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.upload_file_start", {"selector": selector})
        result = await self._executor.upload_file(selector=selector, file_paths=file_paths)
        await self._emit_event_async("browser.upload_file_complete", {"status": result.status})
        return result

    async def press_key(self, key: str, selector: str | None = None) -> ToolResult:
        """Press keyboard key on element or page."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.press_key_start", {"key": key, "selector": selector})
        result = await self._executor.press_key(key=key, selector=selector)
        await self._emit_event_async("browser.press_key_complete", {"status": result.status})
        return result

    async def _check_security_gate(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult | None:
        """Evaluate security gate for high-risk browser tools."""
        if self._security_manager is None:
            return None
        check_fn = getattr(self._security_manager, "check_tool_execution", None)
        if check_fn is None:
            return None
        check = await check_fn(tool_name, arguments)
        if getattr(check, "denied", False):
            reason = getattr(check, "reason", "Action denied by security policy")
            return ToolResult(status="error", error=f"Security denied: {reason}")
        if getattr(check, "requires_confirmation", False):
            reason = getattr(check, "reason", "Requires explicit confirmation")
            return ToolResult(status="error", error=f"Security confirmation required: {reason}")
        return None

    async def wait_for_selector(
        self, selector: str, state: str = "visible", timeout: float | None = None
    ) -> ToolResult:
        """Wait for element matching selector."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.wait_for_selector_start", {"selector": selector})
        result = await self._executor.wait_for_selector(selector=selector, state=state, timeout=timeout)
        await self._emit_event_async("browser.wait_for_selector_complete", {"status": result.status})
        return result

    async def select_option(
        self, selector: str, value: str | list[str], timeout: float | None = None
    ) -> ToolResult:
        """Select dropdown option."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.select_option_start", {"selector": selector})
        result = await self._executor.select_option(selector=selector, value=value, timeout=timeout)
        await self._emit_event_async("browser.select_option_complete", {"status": result.status})
        return result

    async def hover(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Hover cursor over element."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.hover_start", {"selector": selector})
        result = await self._executor.hover(selector=selector, timeout=timeout)
        await self._emit_event_async("browser.hover_complete", {"status": result.status})
        return result

    async def right_click(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Right-click element."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.right_click_start", {"selector": selector})
        result = await self._executor.right_click(selector=selector, timeout=timeout)
        await self._emit_event_async("browser.right_click_complete", {"status": result.status})
        return result

    async def drag_and_drop(
        self, source_selector: str, target_selector: str, timeout: float | None = None
    ) -> ToolResult:
        """Drag and drop element."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.drag_and_drop_start", {"source": source_selector, "target": target_selector})
        result = await self._executor.drag_and_drop(source_selector=source_selector, target_selector=target_selector, timeout=timeout)
        await self._emit_event_async("browser.drag_and_drop_complete", {"status": result.status})
        return result

    async def check(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Check checkbox/radio element."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.check_start", {"selector": selector})
        result = await self._executor.check(selector=selector, timeout=timeout)
        await self._emit_event_async("browser.check_complete", {"status": result.status})
        return result

    async def uncheck(self, selector: str, timeout: float | None = None) -> ToolResult:
        """Uncheck checkbox element."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.uncheck_start", {"selector": selector})
        result = await self._executor.uncheck(selector=selector, timeout=timeout)
        await self._emit_event_async("browser.uncheck_complete", {"status": result.status})
        return result

    async def export_pdf(self, save_path: str = "", timeout: float | None = None) -> ToolResult:
        """Export page to PDF file."""
        self._ensure_not_degraded()
        await self._emit_event_async("browser.export_pdf_start", {})
        result = await self._executor.export_pdf(save_path=save_path, timeout=timeout)
        await self._emit_event_async("browser.export_pdf_complete", {"status": result.status})
        return result

    async def download_file(self, timeout: float | None = None) -> ToolResult:
        """Wait for file download event (security-gated)."""
        self._ensure_not_degraded()
        gate_res = await self._check_security_gate("browser_download_file", {})
        if gate_res:
            return gate_res
        await self._emit_event_async("browser.download_file_start", {})
        result = await self._executor.download_file(timeout=timeout)
        await self._emit_event_async("browser.download_file_complete", {"status": result.status})
        return result

    async def execute_js(self, script: str, *args: Any, timeout: float | None = None) -> ToolResult:
        """Execute arbitrary JavaScript in browser (security-gated)."""
        self._ensure_not_degraded()
        gate_res = await self._check_security_gate("browser_execute_js", {"script": script})
        if gate_res:
            return gate_res
        await self._emit_event_async("browser.execute_js_start", {"script": script[:50]})
        result = await self._executor.execute_js(script, *args, timeout=timeout)
        await self._emit_event_async("browser.execute_js_complete", {"status": result.status})
        return result

    async def get_local_storage(self, key: str | None = None) -> ToolResult:
        """Get local storage content."""
        self._ensure_not_degraded()
        return await self._executor.get_local_storage(key=key)

    async def set_local_storage(self, key: str, value: str) -> ToolResult:
        """Set local storage key (security-gated)."""
        self._ensure_not_degraded()
        gate_res = await self._check_security_gate("browser_set_local_storage", {"key": key})
        if gate_res:
            return gate_res
        return await self._executor.set_local_storage(key=key, value=value)

    async def clear_local_storage(self) -> ToolResult:
        """Clear local storage (security-gated)."""
        self._ensure_not_degraded()
        gate_res = await self._check_security_gate("browser_clear_local_storage", {})
        if gate_res:
            return gate_res
        return await self._executor.clear_local_storage()

    async def get_session_storage(self, key: str | None = None) -> ToolResult:
        """Get session storage content."""
        self._ensure_not_degraded()
        return await self._executor.get_session_storage(key=key)

    async def set_session_storage(self, key: str, value: str) -> ToolResult:
        """Set session storage key (security-gated)."""
        self._ensure_not_degraded()
        gate_res = await self._check_security_gate("browser_set_session_storage", {"key": key})
        if gate_res:
            return gate_res
        return await self._executor.set_session_storage(key=key, value=value)

    async def clear_session_storage(self) -> ToolResult:
        """Clear session storage (security-gated)."""
        self._ensure_not_degraded()
        gate_res = await self._check_security_gate("browser_clear_session_storage", {})
        if gate_res:
            return gate_res
        return await self._executor.clear_session_storage()

    # ------------------------------------------------------------------
    # Session API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Return ``True`` if a real browser adapter is wired."""
        return self._executor.is_available

    @property
    def session(self) -> BrowserSession:
        """Expose the underlying session for tab management."""
        return self._session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_capability(self) -> None:
        """Register the ``browser`` capability if a manager is available."""
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register", None)
            if register_cap is not None:
                from backend.modules.capability.capability import Capability
                register_cap(Capability(name="browser", version="0.1.0", dependencies=("llm",)))

    def _register_tools(self) -> None:
        """Register browser tools with the ToolManager."""
        if self._tool_manager is not None:
            register = getattr(self._tool_manager, "register_tool", None)
            if register is not None:
                from backend.modules.tools import ToolDefinition

                register(
                    ToolDefinition(
                        name="browser_navigate",
                        description="Navigate to a URL and return the page content",
                        parameters={
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "The URL to navigate to"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["url"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_navigate_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_search",
                        description="Search the web for a query",
                        parameters={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "max_results": {"type": "integer", "description": "Max results"},
                            },
                            "required": ["query"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_search_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_click",
                        description="Click an element matching the CSS selector on the active browser page",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector of the element to click"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_click_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_fill",
                        description="Fill an input field matching the CSS selector with text on the active browser page",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector of the input field"},
                                "text": {"type": "string", "description": "Text value to fill into the input field"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector", "text"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_fill_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_scroll",
                        description="Scroll the active browser page by given horizontal and vertical pixel deltas",
                        parameters={
                            "type": "object",
                            "properties": {
                                "delta_x": {"type": "integer", "description": "Horizontal scroll offset in pixels (default 0)"},
                                "delta_y": {"type": "integer", "description": "Vertical scroll offset in pixels (default 500)"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_scroll_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_extract_text",
                        description="Extract visible text content from the active page or a specific CSS selector",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "Optional CSS selector to extract text from"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_extract_text_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_screenshot",
                        description="Capture a screenshot of the active browser page or a specific URL",
                        parameters={
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "Optional URL to capture screenshot of"},
                                "save_path": {"type": "string", "description": "Optional file path to save screenshot"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_screenshot_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_new_tab",
                        description="Open a new browser tab with an optional URL",
                        parameters={
                            "type": "object",
                            "properties": {
                                "url": {"type": "string", "description": "Initial URL for new tab"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_new_tab_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_close_tab",
                        description="Close a browser tab by tab ID",
                        parameters={
                            "type": "object",
                            "properties": {
                                "tab_id": {"type": "string", "description": "ID of tab to close"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_close_tab_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_list_tabs",
                        description="List all open browser tabs",
                        parameters={"type": "object", "properties": {}},
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_list_tabs_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_switch_tab",
                        description="Switch active browser tab",
                        parameters={
                            "type": "object",
                            "properties": {
                                "tab_id": {"type": "string", "description": "ID of tab to switch to"},
                            },
                            "required": ["tab_id"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_switch_tab_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_back",
                        description="Navigate back in browser history",
                        parameters={
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_back_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_forward",
                        description="Navigate forward in browser history",
                        parameters={
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_forward_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_reload",
                        description="Reload the current browser page",
                        parameters={
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_reload_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_get_cookies",
                        description="Get browser cookies",
                        parameters={
                            "type": "object",
                            "properties": {
                                "urls": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Optional list of URLs",
                                },
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_get_cookies_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_set_cookies",
                        description="Set browser cookies",
                        parameters={
                            "type": "object",
                            "properties": {
                                "cookies": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                    "description": "List of cookie objects",
                                },
                            },
                            "required": ["cookies"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_set_cookies_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_clear_cookies",
                        description="Clear all browser cookies",
                        parameters={"type": "object", "properties": {}},
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_clear_cookies_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_upload_file",
                        description="Upload a file into a input element matching CSS selector",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector of file input"},
                                "file_paths": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "File path(s) to upload",
                                },
                            },
                            "required": ["selector", "file_paths"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_upload_file_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_press_key",
                        description="Press a key on the active page or element",
                        parameters={
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "Key name to press"},
                                "selector": {"type": "string", "description": "Optional CSS selector"},
                            },
                            "required": ["key"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_press_key_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_wait_for_selector",
                        description="Wait for an element matching CSS selector to reach target state",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector to wait for"},
                                "state": {"type": "string", "description": "State: visible, hidden, attached, detached"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_wait_for_selector_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_select_option",
                        description="Select option(s) in a dropdown element",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector of dropdown"},
                                "value": {"type": "string", "description": "Value to select"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector", "value"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_select_option_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_hover",
                        description="Hover mouse cursor over an element",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_hover_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_right_click",
                        description="Right-click an element matching CSS selector",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_right_click_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_drag_and_drop",
                        description="Drag source element and drop onto target element",
                        parameters={
                            "type": "object",
                            "properties": {
                                "source_selector": {"type": "string", "description": "Source CSS selector"},
                                "target_selector": {"type": "string", "description": "Target CSS selector"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["source_selector", "target_selector"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_drag_and_drop_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_check",
                        description="Check a checkbox or radio element",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_check_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_uncheck",
                        description="Uncheck a checkbox element",
                        parameters={
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string", "description": "CSS selector"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                            "required": ["selector"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_uncheck_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_export_pdf",
                        description="Export the active browser page to a PDF file",
                        parameters={
                            "type": "object",
                            "properties": {
                                "save_path": {"type": "string", "description": "Optional file path to save PDF"},
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_export_pdf_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_download_file",
                        description="Trigger or wait for a file download in the browser (security-gated)",
                        parameters={
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "number", "description": "Timeout in seconds"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_download_file_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_execute_js",
                        description="Execute arbitrary JavaScript on the active browser page (security-gated)",
                        parameters={
                            "type": "object",
                            "properties": {
                                "script": {"type": "string", "description": "JavaScript code to execute"},
                            },
                            "required": ["script"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_execute_js_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_get_local_storage",
                        description="Get browser local storage content",
                        parameters={
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "Optional storage key"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_get_local_storage_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_set_local_storage",
                        description="Set a key-value pair in browser local storage (security-gated)",
                        parameters={
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "Storage key"},
                                "value": {"type": "string", "description": "Storage value"},
                            },
                            "required": ["key", "value"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_set_local_storage_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_clear_local_storage",
                        description="Clear all local storage (security-gated)",
                        parameters={"type": "object", "properties": {}},
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_clear_local_storage_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_get_session_storage",
                        description="Get browser session storage content",
                        parameters={
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "Optional storage key"},
                            },
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_get_session_storage_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_set_session_storage",
                        description="Set a key-value pair in browser session storage (security-gated)",
                        parameters={
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "Storage key"},
                                "value": {"type": "string", "description": "Storage value"},
                            },
                            "required": ["key", "value"],
                        },
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_set_session_storage_tool,
                )

                register(
                    ToolDefinition(
                        name="browser_clear_session_storage",
                        description="Clear all session storage (security-gated)",
                        parameters={"type": "object", "properties": {}},
                        category="browser",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_clear_session_storage_tool,
                )

    async def _handle_navigate_tool(self, url: str, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_navigate``."""
        return await self.navigate(url, timeout=timeout)

    async def _handle_search_tool(self, query: str, max_results: int = 10, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_search``."""
        return await self.search(query, max_results=max_results)

    async def _handle_click_tool(self, selector: str, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_click``."""
        return await self.click(selector, timeout=timeout)

    async def _handle_fill_tool(self, selector: str, text: str = "", value: str = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_fill``."""
        target_text = text if text else value
        return await self.fill(selector, target_text, timeout=timeout)

    async def _handle_scroll_tool(self, delta_x: int = 0, delta_y: int = 500, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_scroll``."""
        return await self.scroll(delta_x=delta_x, delta_y=delta_y, timeout=timeout)

    async def _handle_extract_text_tool(self, selector: str | None = None, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_extract_text``."""
        return await self.extract_text(selector=selector, timeout=timeout)

    async def _handle_screenshot_tool(self, url: str = "", save_path: str | None = None, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_screenshot``."""
        return await self.screenshot(url=url, save_path=save_path, timeout=timeout)

    async def _handle_new_tab_tool(self, url: str = "about:blank", **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_new_tab``."""
        return await self.new_tab(url=url)

    async def _handle_close_tab_tool(self, tab_id: str | None = None, page_id: str | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_close_tab``."""
        target = tab_id or page_id
        return await self.close_tab(tab_id=target)

    async def _handle_list_tabs_tool(self, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_list_tabs``."""
        return await self.list_tabs()

    async def _handle_switch_tab_tool(self, tab_id: str = "", page_id: str = "", **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_switch_tab``."""
        target = tab_id or page_id
        return await self.switch_tab(tab_id=target)

    async def _handle_back_tool(self, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_back``."""
        return await self.back(timeout=timeout)

    async def _handle_forward_tool(self, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_forward``."""
        return await self.forward(timeout=timeout)

    async def _handle_reload_tool(self, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_reload``."""
        return await self.reload(timeout=timeout)

    async def _handle_get_cookies_tool(self, urls: list[str] | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_get_cookies``."""
        return await self.get_cookies(urls=urls)

    async def _handle_set_cookies_tool(self, cookies: list[dict[str, Any]] | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_set_cookies``."""
        return await self.set_cookies(cookies=cookies or [])

    async def _handle_clear_cookies_tool(self, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_clear_cookies``."""
        return await self.clear_cookies()

    async def _handle_upload_file_tool(self, selector: str = "", file_paths: str | list[str] | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_upload_file``."""
        return await self.upload_file(selector=selector, file_paths=file_paths or [])

    async def _handle_press_key_tool(self, key: str = "", selector: str | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_press_key``."""
        return await self.press_key(key=key, selector=selector)

    async def _handle_wait_for_selector_tool(self, selector: str = "", state: str = "visible", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_wait_for_selector``."""
        return await self.wait_for_selector(selector=selector, state=state, timeout=timeout)

    async def _handle_select_option_tool(self, selector: str = "", value: str | list[str] = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_select_option``."""
        return await self.select_option(selector=selector, value=value, timeout=timeout)

    async def _handle_hover_tool(self, selector: str = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_hover``."""
        return await self.hover(selector=selector, timeout=timeout)

    async def _handle_right_click_tool(self, selector: str = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_right_click``."""
        return await self.right_click(selector=selector, timeout=timeout)

    async def _handle_drag_and_drop_tool(self, source_selector: str = "", target_selector: str = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_drag_and_drop``."""
        return await self.drag_and_drop(source_selector=source_selector, target_selector=target_selector, timeout=timeout)

    async def _handle_check_tool(self, selector: str = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_check``."""
        return await self.check(selector=selector, timeout=timeout)

    async def _handle_uncheck_tool(self, selector: str = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_uncheck``."""
        return await self.uncheck(selector=selector, timeout=timeout)

    async def _handle_export_pdf_tool(self, save_path: str = "", timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_export_pdf``."""
        return await self.export_pdf(save_path=save_path, timeout=timeout)

    async def _handle_download_file_tool(self, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_download_file``."""
        return await self.download_file(timeout=timeout)

    async def _handle_execute_js_tool(self, script: str = "", **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_execute_js``."""
        return await self.execute_js(script)

    async def _handle_get_local_storage_tool(self, key: str | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_get_local_storage``."""
        return await self.get_local_storage(key=key)

    async def _handle_set_local_storage_tool(self, key: str = "", value: str = "", **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_set_local_storage``."""
        return await self.set_local_storage(key=key, value=value)

    async def _handle_clear_local_storage_tool(self, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_clear_local_storage``."""
        return await self.clear_local_storage()

    async def _handle_get_session_storage_tool(self, key: str | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_get_session_storage``."""
        return await self.get_session_storage(key=key)

    async def _handle_set_session_storage_tool(self, key: str = "", value: str = "", **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_set_session_storage``."""
        return await self.set_session_storage(key=key, value=value)

    async def _handle_clear_session_storage_tool(self, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_clear_session_storage``."""
        return await self.clear_session_storage()



    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "BrowserManager is degraded",
                context={"module": "browser"},
            )

    def _emit_event_sync(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event from a synchronous context."""
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(event_type, data))
            except RuntimeError:
                self._logger.debug("No running loop — event not emitted: %s", event_type)

    async def _emit_event_async(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event from an async context."""
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)

