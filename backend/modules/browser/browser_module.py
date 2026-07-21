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

    async def _handle_navigate_tool(self, url: str, timeout: float | None = None, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_navigate``."""
        import webbrowser
        try:
            full_url = url if url.startswith(("http://", "https://")) else "https://" + url
            webbrowser.open(full_url)
        except Exception:
            pass
        return await self.navigate(url, timeout=timeout)

    async def _handle_search_tool(self, query: str, max_results: int = 10, **kwargs: object) -> ToolResult:
        """Tool handler for ``browser_search``."""
        import webbrowser
        import urllib.parse
        try:
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(search_url)
        except Exception:
            pass
        return await self.search(query, max_results=max_results)

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
