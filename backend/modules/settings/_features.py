"""
Feature flags — load, store, and query capability toggles.

07_Module_Design.md §1.B.
18_Boot_Sequence.md §2 Step 8.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("naira.features")

# Known feature flag key names mapped to their default (disabled) value.
_FLAG_DEFAULTS: dict[str, bool] = {
    "vision": False,
    "voice": False,
    "browser": False,
    "avatar_3d": False,
    "file_manager": False,
    "pc_control": False,
    "security": False,
    "coding_agent": False,
}


@dataclass(frozen=True)
class FeatureFlags:
    """Immutable set of feature capability flags.

    Every flag defaults to ``False`` — the safest default for the
    low-resource target hardware and for first-boot scenarios.
    """

    vision: bool = False
    voice: bool = False
    browser: bool = False
    avatar_3d: bool = False
    file_manager: bool = False
    pc_control: bool = False
    security: bool = False
    coding_agent: bool = False


class FeatureFlagManager:
    """Loads, stores, and exposes feature flags.

    Feature flags control which dynamic modules are loaded and
    made available to the orchestrator.  Flags are loaded from
    ``config/features.json`` (or ``.yaml``) during boot Step 8.

    Corrupt or missing flag files are handled gracefully: all
    flags default to ``False`` and a warning is logged.
    """

    def __init__(self, flags: FeatureFlags) -> None:
        self._flags = flags

    @property
    def flags(self) -> FeatureFlags:
        return self._flags

    def is_enabled(self, name: str) -> bool:
        """Check whether a named feature flag is enabled.

        Parameters
        ----------
        name : str
            Flag name, e.g. ``"vision"``, ``"voice"``.

        Returns
        -------
        bool
        """
        return getattr(self._flags, name, False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, config_dir: Path) -> FeatureFlagManager:
        """Load feature flags from ``config/``.

        Searches for ``features.json`` or ``features.yaml`` (in that
        order).  If neither exists or both are malformed every flag
        defaults to ``False``.

        Parameters
        ----------
        config_dir : Path
            Path to the ``config/`` directory.

        Returns
        -------
        FeatureFlagManager
        """
        data = cls._try_load_as_json(config_dir) or cls._try_load_as_yaml(config_dir) or {}

        if not isinstance(data, dict):
            _LOG.warning("Feature flags root is not a mapping — all flags disabled")
            return cls(FeatureFlags())

        validated: dict[str, bool] = {}
        for key, default in _FLAG_DEFAULTS.items():
            value = data.get(key)
            if isinstance(value, bool):
                validated[key] = value
            elif key in data:
                _LOG.warning(
                    "Invalid type for flag '%s': expected bool, got %s — using default (%s)",
                    key,
                    type(value).__name__,
                    default,
                )

        return cls(FeatureFlags(**validated))

    @staticmethod
    def _try_load_as_json(config_dir: Path) -> dict[str, Any] | None:
        path = config_dir / "features.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            _LOG.warning("features.json is not a JSON object")
            return None
        except (json.JSONDecodeError, OSError) as exc:
            _LOG.warning("Failed to parse features.json: %s", exc)
            return None

    @staticmethod
    def _try_load_as_yaml(config_dir: Path) -> dict[str, Any] | None:
        path = config_dir / "features.yaml"
        if not path.is_file():
            path = config_dir / "features.yml"
            if not path.is_file():
                return None
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            _LOG.debug("PyYAML not installed — skipping YAML feature flag file: %s", path)
            return None
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            _LOG.warning("Feature flag YAML file is not a mapping: %s", path)
            return None
        except Exception as exc:
            _LOG.warning("Failed to parse feature flag file %s: %s", path, exc)
            return None
