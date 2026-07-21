"""
BrowserExecutor — async execution layer with timeout and error isolation.

Wraps port/adapter operations so that ``BrowserManager`` never deals
with raw exceptions or hanging calls.
"""

from __future__ import annotations

import asyncio
import logging

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
