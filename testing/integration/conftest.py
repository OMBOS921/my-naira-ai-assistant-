"""
Integration test fixtures — full boot with isolated directories.

21_System_Contracts.md §23.5.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.modules.settings import AppConfig, EnvironmentSnapshot
from backend.modules.utils.di import DIContainer
from backend.orchestrator import EventBus, Orchestrator


@pytest.fixture
def boot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a minimal environment for boot tests."""
    monkeypatch.setenv("NAIRA_API_KEY", "test-boot-key")


@pytest.fixture
def boot_root(tmp_path: Path) -> Path:
    """Create an isolated project root with minimal config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    prompts_dir = tmp_path / "backend" / "modules" / "prompt" / "templates"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    system_j2 = prompts_dir / "system.j2"
    system_j2.write_text(
        "You are a helpful assistant.\n"
        "Date: {{ date }}\n"
        "{% if capabilities %}Capabilities: {{ capabilities }}{% endif %}\n"
    )

    return tmp_path


@pytest.fixture
def boot_features(boot_root: Path) -> Path:
    """Create a features.json that enables a subset of capabilities."""
    features = {
        "vision": True,
        "voice": False,
        "browser": True,
        "avatar_3d": False,
        "file_manager": True,
        "pc_control": False,
    }
    config_dir = boot_root / "config"
    features_path = config_dir / "features.json"
    features_path.write_text(json.dumps(features), encoding="utf-8")
    return boot_root


@pytest.fixture
def boot_config() -> AppConfig:
    """Provide a default AppConfig for boot tests."""
    return AppConfig()


@pytest.fixture
def boot_env_snapshot() -> EnvironmentSnapshot:
    """Provide an EnvironmentSnapshot for boot tests."""
    return EnvironmentSnapshot(naira_api_key="test-boot-key")


@pytest.fixture
def di_container() -> DIContainer:
    """Provide a fresh DIContainer."""
    return DIContainer()


@pytest.fixture
def event_bus() -> EventBus:
    """Provide a fresh EventBus."""
    return EventBus()


@pytest.fixture
def orchestrator(
    event_bus: EventBus,
    boot_config: AppConfig,
    boot_env_snapshot: EnvironmentSnapshot,
) -> Orchestrator:
    """Provide an Orchestrator in BOOTING state."""
    return Orchestrator(event_bus=event_bus, config=boot_config, env=boot_env_snapshot)
