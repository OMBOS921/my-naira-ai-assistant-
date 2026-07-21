"""
BrowserNavigation — URL navigation abstraction.

Handles URL validation, normalisation, and delegates the actual
navigation to the configured ``BrowserPort`` adapter.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from backend.modules.browser._exceptions import BrowserNavigationError

_LOG = logging.getLogger("naira.browser.navigation")


class BrowserNavigation:
    """URL navigation helper.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    @staticmethod
    def validate_url(url: str) -> str:
        """Validate and normalise a URL.

        Parameters
        ----------
        url : str
            The URL to validate.

        Returns
        -------
        str
            The normalised URL (with scheme if missing).

        Raises
        ------
        BrowserNavigationError
            If the URL is malformed or uses an unsupported scheme.
        """
        if not url or not url.strip():
            raise BrowserNavigationError(
                "URL must not be empty",
                context={"url": url},
            )

        url = url.strip()
        parsed = urlparse(url)

        if not parsed.scheme:
            # Default to HTTPS
            url = "https://" + url
            parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise BrowserNavigationError(
                f"Unsupported URL scheme: '{parsed.scheme}'",
                context={"url": url, "scheme": parsed.scheme},
            )

        if not parsed.netloc:
            raise BrowserNavigationError(
                f"URL missing hostname: '{url}'",
                context={"url": url},
            )

        return url

    @staticmethod
    def is_same_origin(url_a: str, url_b: str) -> bool:
        """Return ``True`` if both URLs share the same origin."""
        a = urlparse(url_a)
        b = urlparse(url_b)
        return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)
