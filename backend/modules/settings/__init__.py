"""
Settings module — configuration, environment, and feature flags.

07_Module_Design.md §1.B.
18_Boot_Sequence.md §2 Steps 1-2, Step 8.

Public API
----------
- ``SettingsManager`` — central configuration manager
- ``AppConfig``       — immutable application configuration tree
- ``EnvironmentSnapshot`` — validated environment variables
- ``FeatureFlagManager``  — feature flag loader and query
- ``FeatureFlags``        — immutable feature flag set
"""

from __future__ import annotations

from backend.modules.settings._config import AppConfig, build_app_config
from backend.modules.settings._env import EnvironmentSnapshot
from backend.modules.settings._features import FeatureFlagManager, FeatureFlags
from backend.modules.settings.settings_module import SettingsManager

__all__ = [
    "SettingsManager",
    "AppConfig",
    "EnvironmentSnapshot",
    "FeatureFlagManager",
    "FeatureFlags",
    "build_app_config",
]
