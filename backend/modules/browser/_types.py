"""
Browser types — immutable result dataclasses for web page data.

21_System_Contracts.md §15 — Tool contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class BrowserPage:
    """Immutable snapshot of a web page after navigation or extraction.

    Parameters
    ----------
    url : str
        The final URL after any redirects.
    title : str
        The page title (``<title>`` tag).
    content : str | None
        Extracted text/markdown content.  ``None`` if extraction
        was skipped or failed.
    html : str | None
        Raw HTML source.  ``None`` if not captured.
    status_code : int
        HTTP status code (0 if unknown/unreachable).
    headers : dict[str, str]
        Response headers.
    duration_ms : float
        Wall-clock time for the navigation + extraction.
    """

    url: str
    title: str
    content: str | None = None
    html: str | None = None
    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass(frozen=True)
class BrowserTab:
    """State of a single browser tab/window.

    Parameters
    ----------
    id : str
        Unique tab identifier.
    url : str
        Current URL.
    title : str
        Current page title.
    created_at : float
        Monotonic timestamp when the tab was opened.
    last_active_at : float
        Monotonic timestamp of the last navigation.
    history : tuple[str, ...]
        Navigation history (URLs) for this tab.
    """

    id: str
    url: str
    title: str
    created_at: float
    last_active_at: float
    history: tuple[str, ...] = ()


@dataclass(frozen=True)
class BrowserSearchResult:
    """A single search result from a web search engine.

    Parameters
    ----------
    title : str
        Result title.
    url : str
        Result URL.
    snippet : str
        Text snippet / description.
    """

    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class BrowserSearchResponse:
    """Complete search response.

    Parameters
    ----------
    query : str
        The original search query.
    results : tuple[BrowserSearchResult, ...]
        Individual result items.
    total_estimate : int
        Estimated total number of results (0 if unknown).
    duration_ms : float
        Wall-clock time for the search.
    """

    query: str
    results: tuple[BrowserSearchResult, ...] = ()
    total_estimate: int = 0
    duration_ms: float = 0.0


@dataclass(frozen=True)
class DownloadResult:
    """Result of a browser file download operation.

    Parameters
    ----------
    path : str
        Local filesystem path where the file was saved.
    suggested_filename : str
        Suggested filename from response header or download event.
    size_bytes : int
        Size of the downloaded file in bytes.
    url : str
        Source URL of the downloaded file.
    """

    path: str
    suggested_filename: str
    size_bytes: int = 0
    url: str = ""


type BrowserAction = Literal["navigate", "search", "extract", "screenshot"]
"""Types of browser actions tracked by the module."""

