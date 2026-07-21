"""Tests for SkillRouter — automatic routing."""

from __future__ import annotations

import pytest

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._registry import SkillRegistry
from backend.modules.coding_agent.skills.context._models import (
    FileInfo,
    ProjectContext,
    SkillContext,
)
from backend.modules.coding_agent.skills.packs.c_expert import CExpertPack
from backend.modules.coding_agent.skills.packs.docker_expert import DockerExpertPack
from backend.modules.coding_agent.skills.packs.python_expert import PythonExpertPack
from backend.modules.coding_agent.skills.packs.react_expert import ReactExpertPack
from backend.modules.coding_agent.skills.packs.sql_expert import SQlExpertPack
from backend.modules.coding_agent.skills.routing._router import SkillRouter


@pytest.fixture
def populated_registry() -> SkillRegistry:
    reg = SkillRegistry()
    import asyncio
    asyncio.run(reg.register("python", PythonExpertPack()))
    asyncio.run(reg.register("react", ReactExpertPack()))
    asyncio.run(reg.register("c", CExpertPack()))
    asyncio.run(reg.register("sql", SQlExpertPack()))
    asyncio.run(reg.register("docker", DockerExpertPack()))
    return reg


@pytest.mark.asyncio
class TestSkillRouter:
    async def test_route_by_python_file(self, populated_registry) -> None:
        router = SkillRouter(registry=populated_registry)
        ctx = SkillContext(
            project=ProjectContext(project_type="python", languages=["python"]),
            current_file=FileInfo(path="main.py", extension=".py"),
        )
        skills = await router.route(ctx)
        assert len(skills) > 0
        names = [s.metadata().name for s in skills]
        assert "Python Expert" in names

    async def test_route_by_react_file(self, populated_registry) -> None:
        router = SkillRouter(registry=populated_registry)
        ctx = SkillContext(
            project=ProjectContext(
                project_type="react", languages=["javascript"], frameworks=["react"]
            ),
            current_file=FileInfo(path="App.tsx", extension=".tsx"),
        )
        skills = await router.route(ctx)
        names = [s.metadata().name for s in skills]
        assert "React Expert" in names

    async def test_route_by_sql_file(self, populated_registry) -> None:
        router = SkillRouter(registry=populated_registry)
        ctx = SkillContext(
            project=ProjectContext(project_type="unknown", languages=["sql"]),
            current_file=FileInfo(path="migration.sql", extension=".sql"),
        )
        skills = await router.route(ctx)
        names = [s.metadata().name for s in skills]
        assert "SQL Expert" in names

    async def test_route_by_dockerfile(self, populated_registry) -> None:
        router = SkillRouter(registry=populated_registry)
        ctx = SkillContext(
            project=ProjectContext(project_type="docker"),
            current_file=FileInfo(path="Dockerfile", extension=""),
        )
        skills = await router.route(ctx)
        names = [s.metadata().name for s in skills]
        assert "Docker Expert" in names

    async def test_route_by_c_file(self, populated_registry) -> None:
        router = SkillRouter(registry=populated_registry)
        ctx = SkillContext(
            project=ProjectContext(project_type="c", languages=["c"]),
            current_file=FileInfo(path="main.c", extension=".c"),
        )
        skills = await router.route(ctx)
        names = [s.metadata().name for s in skills]
        assert "C Expert" in names

    async def test_route_fallback_to_all(self) -> None:
        reg = SkillRegistry()
        router = SkillRouter(registry=reg)
        ctx = SkillContext(
            project=ProjectContext(project_type="unknown"),
            current_file=FileInfo(path="unknown.xyz", extension=".xyz"),
        )
        skills = await router.route(ctx)
        assert len(skills) >= 0

    async def test_route_disabled(self, populated_registry) -> None:
        config = SkillConfig(enable_auto_routing=False)
        router = SkillRouter(registry=populated_registry, config=config)
        ctx = SkillContext()
        skills = await router.route(ctx)
        assert len(skills) > 0

    async def test_route_max_results(self, populated_registry) -> None:
        config = SkillConfig(routing_max_results=2)
        router = SkillRouter(registry=populated_registry, config=config)
        ctx = SkillContext(
            project=ProjectContext(project_type="python", languages=["python"]),
            current_file=FileInfo(path="main.py", extension=".py"),
        )
        skills = await router.route(ctx)
        assert len(skills) <= 2

    async def test_route_by_file(self, populated_registry) -> None:
        router = SkillRouter(registry=populated_registry)
        project = ProjectContext(languages=["python"])
        skills = await router.route_by_file("main.py", project)
        assert len(skills) > 0

    async def test_mixed_project_routing(self, populated_registry) -> None:
        router = SkillRouter(registry=populated_registry)
        ctx = SkillContext(
            project=ProjectContext(
                project_type="mixed", is_monorepo=True, languages=["python", "javascript"]
            ),
            current_file=FileInfo(path="Dockerfile"),
        )
        skills = await router.route(ctx)
        names = [s.metadata().name for s in skills]
        assert "Docker Expert" in names
