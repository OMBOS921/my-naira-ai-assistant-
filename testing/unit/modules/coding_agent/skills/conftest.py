"""Shared fixtures for skills tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._registry import SkillRegistry
from backend.modules.coding_agent.skills._statistics import AggregatedStatistics
from backend.modules.coding_agent.skills.context._models import (
    FileInfo,
    ProjectContext,
    SkillContext,
)
from backend.modules.coding_agent.skills.packs.c_expert import CExpertPack
from backend.modules.coding_agent.skills.packs.cpp_expert import CppExpertPack
from backend.modules.coding_agent.skills.packs.python_expert import PythonExpertPack


@pytest.fixture
def skill_config() -> SkillConfig:
    return SkillConfig()


@pytest.fixture
def empty_registry() -> SkillRegistry:
    return SkillRegistry()


@pytest.fixture
def sample_context() -> SkillContext:
    return SkillContext(
        project=ProjectContext(
            root_path="/test/project",
            project_type="python",
            languages=["python"],
            frameworks=["fastapi"],
        ),
        current_file=FileInfo(
            path="/test/project/main.py",
            content="print('hello')",
            language="python",
            extension=".py",
        ),
        query="Analyse this code",
    )


@pytest.fixture
def c_skill() -> CExpertPack:
    return CExpertPack()


@pytest.fixture
def cpp_skill() -> CppExpertPack:
    return CppExpertPack()


@pytest.fixture
def python_skill() -> PythonExpertPack:
    return PythonExpertPack()


@pytest.fixture
def multi_skill_registry(
    c_skill: CExpertPack, cpp_skill: CppExpertPack, python_skill: PythonExpertPack
) -> SkillRegistry:
    reg = SkillRegistry()
    import asyncio
    asyncio.run(reg.register("c", c_skill))
    asyncio.run(reg.register("cpp", cpp_skill))
    asyncio.run(reg.register("python", python_skill))
    return reg


@pytest.fixture
def sample_stats() -> AggregatedStatistics:
    stats = AggregatedStatistics()
    stats.record_skill("python", 100.0, True)
    stats.record_skill("python", 150.0, True)
    stats.record_skill("c", 50.0, False)
    stats.record_routing()
    return stats


@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    return tmp_path
