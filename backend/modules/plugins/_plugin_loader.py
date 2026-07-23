"""
PluginLoader — Dynamic module discovery and loading for Naira plugins.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
import sys
import traceback
from typing import Any

from backend.modules.plugins._plugin_base import NairaPlugin

_LOG = logging.getLogger("naira.plugins.loader")


class PluginLoader:
    """Discovers, validates, and dynamically loads plugin files."""

    def __init__(
        self,
        plugins_dir: str = "plugins",
        logger: logging.Logger | None = None,
    ) -> None:
        self._plugins_dir = Path(plugins_dir)
        self._logger = logger or _LOG

    def discover_plugin_files(self) -> list[Path]:
        """Scan plugins_dir for .py files (excluding __init__.py, files starting with _ or test_)."""
        if not self._plugins_dir.exists() or not self._plugins_dir.is_dir():
            self._logger.debug("Plugins directory does not exist: %s", self._plugins_dir)
            return []

        plugin_files: list[Path] = []
        for path in self._plugins_dir.glob("*.py"):
            filename = path.name
            if (
                filename == "__init__.py"
                or filename.startswith("_")
            ):
                continue
            plugin_files.append(path)

        return sorted(plugin_files)

    def validate_plugin_metadata(self, plugin_target: Any) -> bool:
        """Check PLUGIN_NAME is set and non-default, PLUGIN_DESCRIPTION is non-empty."""
        name = getattr(plugin_target, "PLUGIN_NAME", None)
        desc = getattr(plugin_target, "PLUGIN_DESCRIPTION", None)

        if not name or not isinstance(name, str) or name == "unnamed_plugin":
            self._logger.warning("Plugin validation failed: invalid or default PLUGIN_NAME")
            return False

        if not desc or not isinstance(desc, str) or not desc.strip():
            self._logger.warning(
                "Plugin validation failed for '%s': empty PLUGIN_DESCRIPTION", name
            )
            return False

        return True

    async def load_plugin_from_file(self, file_path: Path) -> NairaPlugin | None:
        """Dynamically load and instantiate a NairaPlugin from a Python file.

        Wrap EVERYTHING in try/except — a broken plugin file must NEVER crash Naira.
        """
        try:
            import uuid
            self._logger.info("Attempting to load plugin file: %s", file_path)
            unique_id = uuid.uuid4().hex[:8]
            module_name = f"naira_plugin_{file_path.stem}_{unique_id}"

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                self._logger.error("Could not create module spec for file: %s", file_path)
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(module_name, None)
                raise

            plugin_class: type[NairaPlugin] | None = None
            for _name, cls in inspect.getmembers(module, inspect.isclass):
                if issubclass(cls, NairaPlugin) and cls is not NairaPlugin:
                    plugin_class = cls
                    break

            if plugin_class is None:
                self._logger.warning("No subclass of NairaPlugin found in %s", file_path)
                return None

            if not self.validate_plugin_metadata(plugin_class):
                self._logger.warning(
                    "Plugin class metadata invalid in file %s", file_path
                )
                return None

            instance = plugin_class(logger=self._logger)

            if not self.validate_plugin_metadata(instance):
                return None

            loaded = await instance.on_load()
            if not loaded:
                self._logger.warning(
                    "Plugin %s on_load() returned False", instance.PLUGIN_NAME
                )
                return None

            self._logger.info(
                "Successfully loaded plugin '%s' v%s from %s",
                instance.PLUGIN_NAME,
                instance.PLUGIN_VERSION,
                file_path,
            )
            return instance

        except Exception as exc:
            self._logger.error(
                "Failed to load plugin from file %s: %s\n%s",
                file_path,
                exc,
                traceback.format_exc(),
            )
            return None
