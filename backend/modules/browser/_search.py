"""
BrowserSearch — web search abstraction.

Encapsulates the strategy for querying a search engine (Google, Bing,
DuckDuckGo, etc.) and normalising results into ``BrowserSearchResponse``.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request

from backend.modules.browser._types import (
    BrowserSearchResponse,
    BrowserSearchResult,
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
        """Execute a web search using DuckDuckGo API and HTML fallback.

        Parameters
        ----------
        query : str
            The search query.
        max_results : int
            Maximum number of results to include.

        Returns
        -------
        BrowserSearchResponse
            Search results populated with real items.
        """
        start_t = time.monotonic()
        results_list: list[BrowserSearchResult] = []

        # 1. DuckDuckGo Instant Answer API
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(ddg_url, headers={"User-Agent": "Naira-OS/2.0 Omniscience Engine"})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                data = json.loads(response.read().decode("utf-8"))
                heading = data.get("Heading") or query
                abstract = data.get("AbstractText", "").strip()
                abs_url = data.get("AbstractURL", "")
                if abstract:
                    results_list.append(BrowserSearchResult(title=heading, url=abs_url or f"https://duckduckgo.com/?q={urllib.parse.quote(query)}", snippet=abstract))

                related = data.get("RelatedTopics", [])
                for item in related:
                    if len(results_list) >= max_results:
                        break
                    if isinstance(item, dict) and item.get("Text"):
                        results_list.append(BrowserSearchResult(title=item.get("Text")[:60], url=item.get("FirstURL", ""), snippet=item.get("Text")))
        except Exception as exc:
            self._logger.debug("DuckDuckGo API search error: %s", exc)

        # 2. Fallback HTML fetch if API gave few results
        if len(results_list) < max_results:
            try:
                html_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
                req = urllib.request.Request(html_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    html = response.read().decode("utf-8", errors="ignore")
                    snippets = re.findall(r'<a class="result__snippet[^">]*>(.*?)</a>', html, re.DOTALL)
                    titles = re.findall(r'<a class="result__title[^">]*>(.*?)</a>', html, re.DOTALL)
                    urls = re.findall(r'<a class="result__url[^">]*href="([^"]+)"', html, re.DOTALL)

                    for i in range(min(len(snippets), max_results - len(results_list))):
                        snip_txt = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                        title_txt = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else f"Result {i+1}"
                        url_txt = urls[i].strip() if i < len(urls) else ""
                        if snip_txt:
                            results_list.append(BrowserSearchResult(title=title_txt, url=url_txt, snippet=snip_txt))
            except Exception as exc:
                self._logger.debug("DuckDuckGo HTML search error: %s", exc)

        duration = (time.monotonic() - start_t) * 1000
        return BrowserSearchResponse(
            query=query,
            results=tuple(results_list[:max_results]),
            total_estimate=len(results_list),
            duration_ms=duration,
        )
