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
import sys
from pathlib import Path

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
        self._config = build_app_config(raw)
        _LOG.info("Configuration loaded from %s", self._config_dir)

    def _load_features(self) -> None:
        self._features = FeatureFlagManager.load(self._config_dir)

    def _require_initialised(self) -> None:
        if self._config is None:
            raise RuntimeError(
                "SettingsManager not initialised — call async_init() before access"
            )
