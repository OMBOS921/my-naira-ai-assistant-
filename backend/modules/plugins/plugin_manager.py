"""
PluginManager — Manager for discovery, lifecycle, and tool registration of plugins.

Conforms to ``ModuleInterface`` (``backend/types.py``).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.plugins._plugin_base import NairaPlugin
from backend.modules.plugins._plugin_loader import PluginLoader
from backend.modules.tools._definition import ToolDefinition

_LOG = logging.getLogger("naira.plugins")


class PluginManager:
    """Manages the full lifecycle of Naira plugins and registers their tools."""

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        tool_manager: object | None = None,
        plugins_dir: str = "plugins",
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._tool_manager = tool_manager
        self._plugins_dir = plugins_dir
        self._default_timeout = default_timeout

        self._loader = PluginLoader(plugins_dir, logger=self._logger)
        self._loaded_plugins: dict[str, NairaPlugin] = {}
        self._degraded: bool = False
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Discover and load all plugins in plugins_dir."""
        self._ensure_not_degraded()
        plugin_files = self._loader.discover_plugin_files()

        for file_path in plugin_files:
            plugin = await self._loader.load_plugin_from_file(file_path)
            if plugin is not None:
                self._loaded_plugins[plugin.PLUGIN_NAME] = plugin
                self._register_plugin_tools(plugin)

        self._initialized = True
        self._logger.info(
            "PluginManager initialized — loaded %d plugin(s)", len(self._loaded_plugins)
        )

    async def async_shutdown(self) -> None:
        """Unload all plugins gracefully."""
        for name, plugin in list(self._loaded_plugins.items()):
            try:
                await plugin.on_unload()
            except Exception as exc:
                self._logger.warning("Error unloading plugin '%s': %s", name, exc)

        self._loaded_plugins.clear()
        self._degraded = False
        self._initialized = False
        self._logger.info("PluginManager shut down.")

    def degrade(self) -> None:
        """Mark PluginManager as degraded."""
        self._degraded = True
        self._logger.warning("PluginManager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Plugin management API
    # ------------------------------------------------------------------

    def _register_plugin_tools(self, plugin: NairaPlugin) -> None:
        """Register tool definitions exposed by a plugin into ToolManager."""
        register_fn = getattr(self._tool_manager, "register_tool", None)
        if not callable(register_fn):
            self._logger.debug("ToolManager register_tool not available; skipping plugin tool registration")
            return

        tools = plugin.get_tools()
        if not isinstance(tools, list):
            return

        for tool_dict in tools:
            if not isinstance(tool_dict, dict):
                continue

            name = tool_dict.get("name")
            desc = tool_dict.get("description", "")
            params = tool_dict.get("parameters", {})
            category = tool_dict.get("category", "plugin")
            handler = tool_dict.get("handler")

            if not name:
                continue

            if handler is None and hasattr(plugin, f"tool_{name}"):
                handler = getattr(plugin, f"tool_{name}")
            elif handler is None and hasattr(plugin, name):
                handler = getattr(plugin, name)

            if handler is not None and callable(handler):
                try:
                    tool_def = ToolDefinition(
                        name=name,
                        description=desc,
                        parameters=params,
                        category=category,
                    )
                    register_fn(tool_def, handler)
                    self._logger.info(
                        "Registered tool '%s' from plugin '%s'", name, plugin.PLUGIN_NAME
                    )
                except Exception as exc:
                    self._logger.warning(
                        "Failed to register tool '%s' from plugin '%s': %s",
                        name, plugin.PLUGIN_NAME, exc,
                    )

    async def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a specific plugin by name."""
        self._ensure_not_degraded()
        plugin = self._loaded_plugins.get(plugin_name)
        if plugin is not None:
            try:
                await plugin.on_unload()
            except Exception as exc:
                self._logger.warning("Error unloading plugin '%s' during reload: %s", plugin_name, exc)
            self._loaded_plugins.pop(plugin_name, None)

        plugin_files = self._loader.discover_plugin_files()
        for file_path in plugin_files:
            new_plugin = await self._loader.load_plugin_from_file(file_path)
            if new_plugin is not None and new_plugin.PLUGIN_NAME == plugin_name:
                self._loaded_plugins[plugin_name] = new_plugin
                self._register_plugin_tools(new_plugin)
                self._logger.info("Plugin '%s' reloaded successfully", plugin_name)
                return True

        self._logger.warning("Plugin '%s' not found for reload", plugin_name)
        return False

    def list_plugins(self) -> list[dict[str, Any]]:
        """List metadata for all loaded plugins."""
        results: list[dict[str, Any]] = []
        for plugin in self._loaded_plugins.values():
            results.append({
                "name": plugin.PLUGIN_NAME,
                "version": plugin.PLUGIN_VERSION,
                "description": plugin.PLUGIN_DESCRIPTION,
                "author": plugin.PLUGIN_AUTHOR,
                "enabled": plugin.is_enabled,
                "required_permissions": plugin.REQUIRES_PERMISSIONS,
            })
        return results

    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin by name."""
        self._ensure_not_degraded()
        plugin = self._loaded_plugins.get(plugin_name)
        if plugin is None:
            return False
        plugin.disable()
        self._logger.info("Plugin '%s' disabled", plugin_name)
        return True

    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin by name."""
        self._ensure_not_degraded()
        plugin = self._loaded_plugins.get(plugin_name)
        if plugin is None:
            return False
        plugin.enable()
        self._logger.info("Plugin '%s' enabled", plugin_name)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "PluginManager is degraded",
                context={"module": "plugins"},
            )
