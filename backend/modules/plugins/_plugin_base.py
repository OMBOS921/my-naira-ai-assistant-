"""
NairaPlugin — Abstract Base Class for Naira Plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any


class NairaPlugin(ABC):
    """Base class for all Naira plugins."""

    # Class-level metadata every plugin must define
    PLUGIN_NAME: str = "unnamed_plugin"
    PLUGIN_VERSION: str = "1.0.0"
    PLUGIN_DESCRIPTION: str = ""
    PLUGIN_AUTHOR: str = "unknown"
    REQUIRES_PERMISSIONS: list[str] = []

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger("naira.plugins")
        self._event_bus = event_bus
        self._enabled: bool = True

    @abstractmethod
    async def on_load(self) -> bool:
        """Lifecycle hook called when the plugin is loaded."""
        ...

    @abstractmethod
    async def on_unload(self) -> None:
        """Lifecycle hook called when the plugin is unloaded."""
        ...

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Return list of tool definitions/handlers exposed by this plugin."""
        ...

    @property
    def is_enabled(self) -> bool:
        """Return whether the plugin is currently enabled."""
        return self._enabled

    def disable(self) -> None:
        """Disable the plugin."""
        self._enabled = False

    def enable(self) -> None:
        """Enable the plugin."""
        self._enabled = True
