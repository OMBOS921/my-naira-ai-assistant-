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
        adapter: BrowserPort | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._degraded: bool = False
        self._default_timeout = default_timeout

        # Internal components
        if adapter is not None:
            self._adapter = adapter
            self._logger.info(
                "Browser adapter explicitly provided: %s",
                type(adapter).__name__,
            )
        elif _HAS_PLAYWRIGHT:
            self._adapter = PlaywrightBrowserAdapter(logger=logger)
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

