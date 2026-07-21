"""
BrowserContentExtractor — HTML-to-text extraction and content analysis.

Provides basic content extraction heuristics (strip tags, extract
headings, compute reading time) that work without a full DOM engine.
When a real browser adapter (Playwright) is wired, richer extraction
becomes available.
"""

from __future__ import annotations

import logging
import re

_LOG = logging.getLogger("naira.browser.content")


class BrowserContentExtractor:
    """Content extraction and analysis utility.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    # Regex to strip HTML tags
    _TAG_RE = re.compile(r"<[^>]+>")

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    def extract_text(self, html: str) -> str:
        """Strip HTML tags and return clean text.

        Collapses whitespace and removes script/style content.

        Parameters
        ----------
        html : str
            Raw HTML source.

        Returns
        -------
        str
            Plain text extracted from the HTML.
        """
        # Remove script and style blocks
        cleaned = re.sub(
            r"<(script|style)[^>]*>.*?</\1>", "", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Strip remaining tags
        cleaned = self._TAG_RE.sub("", cleaned)
        # Decode common entities
        cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&")
        cleaned = cleaned.replace("&lt;", "<").replace("&gt;", ">")
        # Collapse whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def word_count(text: str) -> int:
        """Return the number of words in *text*."""
        return len(text.split())

    @staticmethod
    def reading_time_minutes(text: str, words_per_minute: int = 200) -> float:
        """Estimate reading time in minutes."""
        return max(0.1, BrowserContentExtractor.word_count(text) / words_per_minute)

    @staticmethod
    def extract_links(html: str) -> list[dict[str, str]]:
        """Extract ``<a href=\"...\">`` links from raw HTML.

        Returns
        -------
        list[dict[str, str]]
            Each entry has ``href`` and ``text`` keys.
        """
        links: list[dict[str, str]] = []
        pattern = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
        for match in pattern.finditer(html):
            href = match.group(1)
            text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            if href and not href.startswith(("#", "javascript:")):
                links.append({"href": href, "text": text or href})
        return links
