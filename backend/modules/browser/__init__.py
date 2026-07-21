"""
Browser module — web navigation, search, and content extraction.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §15 — Tool contracts.

Public API
----------
- ``BrowserManager`` — central browser manager
- ``BrowserPort`` — abstract port for pluggable browser adapters
- ``BrowserSession`` — tab/window session state manager
- ``BrowserPage`` — immutable page snapshot
- ``BrowserTab`` — immutable tab state
- ``BrowserSearchResult`` — single search result
- ``BrowserSearchResponse`` — search response container
"""

from __future__ import annotations

from backend.modules.browser._playwright_adapter import PlaywrightBrowserAdapter
from backend.modules.browser._session import BrowserSession
from backend.modules.browser._types import (
    BrowserPage,
    BrowserSearchResponse,
    BrowserSearchResult,
    BrowserTab,
)
from backend.modules.browser.browser_module import BrowserManager
from backend.modules.browser.ports.browser_port import BrowserPort

__all__ = [
    "BrowserManager",
    "BrowserPort",
    "BrowserSession",
    "BrowserPage",
    "BrowserTab",
    "BrowserSearchResult",
    "BrowserSearchResponse",
    "PlaywrightBrowserAdapter",
]
