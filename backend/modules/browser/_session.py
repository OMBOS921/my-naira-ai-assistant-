"""
BrowserSession — tab/window state management.

Manages a collection of open tabs, their navigation history,
and the currently active tab.  All state is held in-memory.
"""

from __future__ import annotations

import logging
import time
import uuid

from backend.modules.browser._types import BrowserTab

_LOG = logging.getLogger("naira.browser.session")


class BrowserSession:
    """In-memory session manager for browser tabs.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG
        self._tabs: dict[str, BrowserTab] = {}
        self._active_tab_id: str | None = None

    # ------------------------------------------------------------------
    # Tab lifecycle
    # ------------------------------------------------------------------

    def create_tab(self, url: str = "", title: str = "") -> BrowserTab:
        """Create a new tab and make it active.

        Parameters
        ----------
        url : str
            Initial URL (may be empty for a blank tab).
        title : str
            Initial page title.

        Returns
        -------
        BrowserTab
            The newly created tab.
        """
        now = time.monotonic()
        tab_id = uuid.uuid4().hex[:12]
        tab = BrowserTab(
            id=tab_id,
            url=url,
            title=title,
            created_at=now,
            last_active_at=now,
        )
        self._tabs[tab_id] = tab
        self._active_tab_id = tab_id
        self._logger.debug("Tab created: %s (%s)", tab_id, url)
        return tab

    def close_tab(self, tab_id: str) -> bool:
        """Close a tab by its identifier.

        If the closed tab was the active tab, the most recently
        created remaining tab becomes active (or ``None``).

        Returns ``True`` if the tab existed.
        """
        if tab_id not in self._tabs:
            return False
        del self._tabs[tab_id]
        self._logger.debug("Tab closed: %s", tab_id)
        if self._active_tab_id == tab_id:
            self._active_tab_id = next(iter(self._tabs)) if self._tabs else None
        return True

    # ------------------------------------------------------------------
    # Tab access
    # ------------------------------------------------------------------

    def get_tab(self, tab_id: str) -> BrowserTab | None:
        """Retrieve a tab by identifier.

        Returns ``None`` if not found.
        """
        return self._tabs.get(tab_id)

    @property
    def active_tab(self) -> BrowserTab | None:
        """Return the currently active tab, or ``None``."""
        if self._active_tab_id is None:
            return None
        return self._tabs.get(self._active_tab_id)

    @property
    def active_tab_id(self) -> str | None:
        """Return the active tab's identifier."""
        return self._active_tab_id

    def list_tabs(self) -> list[BrowserTab]:
        """Return all open tabs."""
        return list(self._tabs.values())

    @property
    def tab_count(self) -> int:
        """Return the number of open tabs."""
        return len(self._tabs)

    # ------------------------------------------------------------------
    # Tab state updates
    # ------------------------------------------------------------------

    def update_tab(
        self,
        tab_id: str,
        url: str | None = None,
        title: str | None = None,
    ) -> bool:
        """Update the URL and/or title of an existing tab.

        Appends the new URL to the tab's navigation history.

        Returns ``True`` if the tab was found and updated.
        """
        tab = self._tabs.get(tab_id)
        if tab is None:
            return False

        new_url = url if url is not None else tab.url
        new_title = title if title is not None else tab.title
        new_history = list(tab.history)
        if url is not None and (not new_history or new_history[-1] != url):
            new_history.append(url)

        updated = BrowserTab(
            id=tab.id,
            url=new_url,
            title=new_title,
            created_at=tab.created_at,
            last_active_at=time.monotonic(),
            history=tuple(new_history),
        )
        self._tabs[tab_id] = updated
        return True

    def switch_to_tab(self, tab_id: str) -> bool:
        """Switch the active tab to *tab_id*.

        Returns ``True`` if the tab exists.
        """
        if tab_id not in self._tabs:
            return False
        self._active_tab_id = tab_id
        tab = self._tabs[tab_id]
        self._tabs[tab_id] = BrowserTab(
            id=tab.id,
            url=tab.url,
            title=tab.title,
            created_at=tab.created_at,
            last_active_at=time.monotonic(),
            history=tab.history,
        )
        return True

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Close all tabs and reset session state."""
        self._tabs.clear()
        self._active_tab_id = None
        self._logger.info("Browser session cleared")
