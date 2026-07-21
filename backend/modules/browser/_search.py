"""
BrowserSearch — web search abstraction.

Encapsulates the strategy for querying a search engine (Google, Bing,
DuckDuckGo, etc.) and normalising results into ``BrowserSearchResponse``.

Currently provides a no-op placeholder; real search backends will be
injected via the port/adapter layer.
"""

from __future__ import annotations

import logging

from backend.modules.browser._types import (
    BrowserSearchResponse,
)

_LOG = logging.getLogger("naira.browser.search")


class BrowserSearch:
    """Web search executor.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> BrowserSearchResponse:
        """Execute a web search.

        .. caution::
            Currently a placeholder.  Real search backends
            (DuckDuckGo, Google Custom Search, Bing Web Search)
            are injected by the adapter layer.  Without a backend
            this method returns an empty response.

        Parameters
        ----------
        query : str
            The search query.
        max_results : int
            Maximum number of results to include.

        Returns
        -------
        BrowserSearchResponse
            Search results (empty in placeholder mode).
        """
        self._logger.debug(
            "Search placeholder for query=%r max_results=%d",
            query,
            max_results,
        )
        return BrowserSearchResponse(query=query)
