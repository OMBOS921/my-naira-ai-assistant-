"""
ToolRegistry — central store for tool definitions and their handlers.

07_Module_Design.md §2 — Registry pattern.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from backend.modules.tools._definition import ToolDefinition
from backend.types import ToolResult

type ToolHandler = Callable[..., Coroutine[Any, Any, ToolResult]]
"""Signature for a tool execution handler.

Handler receives keyword arguments matching the tool's parameter schema
and must return a ``ToolResult``.
"""

_LOG = logging.getLogger("naira.tools")


class ToolRegistry:
    """Central registry for tool definitions and their async handlers.

    Manages:
    - Registration and unregistration of tools.
    - Enable/disable state per tool.
    - Category-based organisation and discovery.
    - Handler storage for execution.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self._categories: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def register(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        """Register a tool definition and its async handler.

        Parameters
        ----------
        definition : ToolDefinition
            The tool descriptor.
        handler : ToolHandler
            Async callable that executes the tool.

        Raises
        ------
        ValueError
            If a tool with the same name is already registered.
        """
        name = definition.name
        if name in self._definitions:
            raise ValueError(f"Tool already registered: '{name}'")

        self._definitions[name] = definition
        self._handlers[name] = handler

        cat = definition.category
        if cat not in self._categories:
            self._categories[cat] = set()
        self._categories[cat].add(name)

        self._logger.info("Tool registered: '%s' (category=%s)", name, cat)

    def unregister(self, name: str) -> None:
        """Unregister a tool by name.

        Silently ignores unknown names.
        """
        definition = self._definitions.pop(name, None)
        self._handlers.pop(name, None)
        if definition is not None:
            cat = definition.category
            if cat in self._categories:
                self._categories[cat].discard(name)
                if not self._categories[cat]:
                    del self._categories[cat]
            self._logger.info("Tool unregistered: '%s'", name)

    # ------------------------------------------------------------------
    # Lookup API
    # ------------------------------------------------------------------

    def get(self, name: str) -> ToolDefinition | None:
        """Retrieve a tool definition by name.

        Returns ``None`` if not found.
        """
        return self._definitions.get(name)

    def get_handler(self, name: str) -> ToolHandler | None:
        """Retrieve a tool's async handler by name.

        Returns ``None`` if not found.
        """
        return self._handlers.get(name)

    def has(self, name: str) -> bool:
        """Return ``True`` if a tool with *name* is registered."""
        return name in self._definitions

    # ------------------------------------------------------------------
    # Discovery API
    # ------------------------------------------------------------------

    def list(
        self,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> list[ToolDefinition]:
        """List registered tool definitions, optionally filtered.

        Parameters
        ----------
        category : str | None
            If set, only tools in this category are returned.
        enabled_only : bool
            If ``True`` (default), only enabled tools are returned.

        Returns
        -------
        list[ToolDefinition]
            Matching tool definitions.
        """
        results: list[ToolDefinition] = []
        for _name, definition in self._definitions.items():
            if category is not None and definition.category != category:
                continue
            if enabled_only and not definition.enabled:
                continue
            results.append(definition)
        return results

    def list_enabled(self) -> list[ToolDefinition]:
        """Return all enabled tool definitions."""
        return self.list(enabled_only=True)

    def list_by_category(self, category: str) -> list[ToolDefinition]:
        """Return all tool definitions in a given category."""
        return self.list(category=category, enabled_only=False)

    # ------------------------------------------------------------------
    # Enable / Disable
    # ------------------------------------------------------------------

    def enable(self, name: str) -> bool:
        """Enable a tool by name.

        Returns ``True`` if the tool was found and enabled.
        """
        definition = self._definitions.get(name)
        if definition is None:
            return False
        if not definition.enabled:
            object.__setattr__(definition, "enabled", True)  # frozen workaround
            self._logger.info("Tool enabled: '%s'", name)
        return True

    def disable(self, name: str) -> bool:
        """Disable a tool by name.

        Returns ``True`` if the tool was found and disabled.
        """
        definition = self._definitions.get(name)
        if definition is None:
            return False
        if definition.enabled:
            object.__setattr__(definition, "enabled", False)  # frozen workaround
            self._logger.info("Tool disabled: '%s'", name)
        return True

    def is_enabled(self, name: str) -> bool:
        """Return ``True`` if the tool exists and is enabled."""
        definition = self._definitions.get(name)
        if definition is None:
            return False
        return definition.enabled

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    @property
    def categories(self) -> list[str]:
        """Return sorted list of all known category names."""
        return sorted(self._categories)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    @property
    def tool_count(self) -> int:
        """Return the total number of registered tools."""
        return len(self._definitions)

    def clear(self) -> None:
        """Remove all registered tools and categories."""
        self._definitions.clear()
        self._handlers.clear()
        self._categories.clear()
        self._logger.info("Tool registry cleared")
