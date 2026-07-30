"""
Settings module — central configuration manager.

07_Module_Design.md §1.B.
18_Boot_Sequence.md §2 Steps 1-2, Step 8.

The ``SettingsManager`` is the single public entry-point for the
settings module.  It loads and owns the application configuration
tree, environment snapshot, and feature flags.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from backend.modules.settings._config import AppConfig, build_app_config
from backend.modules.settings._env import EnvironmentSnapshot
from backend.modules.settings._features import FeatureFlagManager
from backend.modules.settings._loader import load_config, validate_config

_LOG = logging.getLogger("naira.settings")

_ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent


class SettingsManager:
    """Central configuration manager.

    Owns the ``AppConfig``, ``EnvironmentSnapshot``, and
    ``FeatureFlagManager``.  Modules receive a reference to the
    manager or to the config / env snapshots directly via
    constructor injection.

    Module lifecycle follows the ``ModuleInterface`` protocol
    defined in ``backend/types.py``.
    """

    def __init__(
        self,
        config_dir: Path | None = None,
        env_file: Path | None = None,
        schema_dir: Path | None = None,
        event_bus: object | None = None,
    ) -> None:
        self._config_dir = config_dir or _ROOT_DIR / "config"
        self._env_file = env_file or _ROOT_DIR / ".env"
        self._schema_dir = schema_dir
        self._event_bus = event_bus

        self._config: AppConfig | None = None
        self._raw_config: dict[str, Any] = {}
        self._env: EnvironmentSnapshot | None = None
        self._features: FeatureFlagManager | None = None
        self._degraded: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Load all configuration sources.

        Equivalent to boot Steps 1, 2, and 8.  Must be called once
        before accessing ``config``, ``env``, or ``features``.
        """
        self._load_env()
        self._load_config()
        self._load_features()

    async def async_shutdown(self) -> None:
        """Release held configuration references."""
        self._config = None
        self._raw_config = {}
        self._env = None
        self._features = None
        self._degraded = False
        _LOG.info("Settings manager shut down.")

    def degrade(self) -> None:
        """Mark the manager as degraded."""
        self._degraded = True
        _LOG.warning("Settings manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def config(self) -> AppConfig:
        self._require_initialised()
        return self._config  # type: ignore[return-value]

    @property
    def env(self) -> EnvironmentSnapshot:
        self._require_initialised()
        return self._env  # type: ignore[return-value]

    @property
    def features(self) -> FeatureFlagManager:
        self._require_initialised()
        return self._features  # type: ignore[return-value]

    def get(self, key_path: str, default: Any = None) -> Any:
        """Retrieve nested configuration setting using dot-notation (e.g. 'api_keys.groq')."""
        if not key_path:
            return default

        parts = key_path.split(".")

        # 1. Check raw merged config tree
        if self._raw_config:
            val: Any = self._raw_config
            found = True
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    found = False
                    break
            if found and val is not None and val != "":
                return val

        # 2. Check env snapshot for matching property or env var
        if self._env:
            last_part = parts[-1]
            if hasattr(self._env, last_part):
                val = getattr(self._env, last_part)
                if val:
                    return val
            if hasattr(self._env, f"{last_part.lower()}_api_key"):
                val = getattr(self._env, f"{last_part.lower()}_api_key")
                if val:
                    return val

        # 3. Check AppConfig dataclass
        if self._config:
            section = parts[0]
            if hasattr(self._config, section):
                val = getattr(self._config, section)
                for part in parts[1:]:
                    if hasattr(val, part):
                        val = getattr(val, part)
                    else:
                        val = None
                        break
                if val is not None and val != "":
                    return val

        return default

    def get_api_key(self, provider: str) -> str:
        """Retrieve API key for provider (e.g. 'groq', 'gemini') from vault/config/env."""
        provider_lower = provider.lower()
        val = (
            self.get(f"api_keys.{provider_lower}")
            or self.get(f"{provider_lower}_api_key")
            or self.get(f"api_keys.{provider_lower}.key")
        )
        if val and isinstance(val, str) and val.strip():
            return val.strip()

        env_var = f"{provider_lower.upper()}_API_KEY"
        if self._env and hasattr(self._env, f"{provider_lower}_api_key"):
            env_val = getattr(self._env, f"{provider_lower}_api_key")
            if env_val:
                return str(env_val).strip()

        return os.environ.get(env_var, "").strip()

    # ------------------------------------------------------------------
    # Internal loaders
    # ------------------------------------------------------------------

    def _load_env(self) -> None:
        self._env = EnvironmentSnapshot.load(env_file=self._env_file)

    def _load_config(self) -> None:
        raw = load_config(self._config_dir)
        errors = validate_config(raw, schema_dir=self._schema_dir)
        if errors:
            for err in errors:
                _LOG.error("Config schema violation: %s", err)
            _LOG.critical("Configuration validation failed — cannot continue")
            sys.exit(1)
        self._raw_config = raw
        self._config = build_app_config(raw)
        _LOG.info("Configuration loaded from %s", self._config_dir)

    def _load_features(self) -> None:
        self._features = FeatureFlagManager.load(self._config_dir)

    def _require_initialised(self) -> None:
        if self._config is None:
            raise RuntimeError(
                "SettingsManager not initialised — call async_init() before access"
            )

