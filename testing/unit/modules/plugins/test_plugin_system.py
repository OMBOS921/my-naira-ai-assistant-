"""
Unit tests for Plugin System (NairaPlugin, PluginLoader, PluginManager).
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import pytest

from backend.modules.plugins._plugin_base import NairaPlugin
from backend.modules.plugins._plugin_loader import PluginLoader
from backend.modules.plugins.plugin_manager import PluginManager
from backend.types import ToolResult


class DummyPlugin(NairaPlugin):
    PLUGIN_NAME = "dummy_plugin"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "A dummy plugin for unit tests"
    PLUGIN_AUTHOR = "Tester"

    async def on_load(self) -> bool:
        return True

    async def on_unload(self) -> None:
        pass

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "dummy_tool",
                "description": "Dummy tool description",
                "handler": self.dummy_tool,
            }
        ]

    async def dummy_tool(self) -> ToolResult:
        return ToolResult(status="success", result="dummy")


@pytest.mark.asyncio
async def test_plugin_base_lifecycle():
    plugin = DummyPlugin()
    assert plugin.PLUGIN_NAME == "dummy_plugin"
    assert plugin.is_enabled is True

    plugin.disable()
    assert plugin.is_enabled is False

    plugin.enable()
    assert plugin.is_enabled is True

    assert await plugin.on_load() is True
    await plugin.on_unload()


@pytest.mark.asyncio
async def test_plugin_loader_validation():
    loader = PluginLoader(plugins_dir="non_existent_dir")
    assert loader.discover_plugin_files() == []

    # Valid metadata
    assert loader.validate_plugin_metadata(DummyPlugin) is True

    # Invalid name
    class BadNamePlugin(DummyPlugin):
        PLUGIN_NAME = "unnamed_plugin"

    assert loader.validate_plugin_metadata(BadNamePlugin) is False

    # Empty description
    class BadDescPlugin(DummyPlugin):
        PLUGIN_DESCRIPTION = ""

    assert loader.validate_plugin_metadata(BadDescPlugin) is False


@pytest.mark.asyncio
async def test_plugin_manager_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_file = Path(tmpdir) / "test_plugin.py"
        plugin_file.write_text(
            """
from backend.modules.plugins._plugin_base import NairaPlugin
from backend.types import ToolResult

class CustomPlugin(NairaPlugin):
    PLUGIN_NAME = "custom_test_plugin"
    PLUGIN_VERSION = "2.0.0"
    PLUGIN_DESCRIPTION = "Custom plugin description"

    async def on_load(self) -> bool:
        return True

    async def on_unload(self) -> None:
        pass

    def get_tools(self) -> list[dict]:
        return []
"""
        )

        mgr = PluginManager(plugins_dir=tmpdir)
        await mgr.async_init()
        assert mgr.initialized is True
        assert mgr.degraded is False

        plugins = mgr.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "custom_test_plugin"

        mgr.disable_plugin("custom_test_plugin")
        plugins_after_disable = mgr.list_plugins()
        assert plugins_after_disable[0]["enabled"] is False

        await mgr.async_shutdown()
        assert mgr.initialized is False
