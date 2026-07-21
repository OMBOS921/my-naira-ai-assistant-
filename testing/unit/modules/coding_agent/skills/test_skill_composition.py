"""Tests for SkillComposer — multi-skill composition."""

from __future__ import annotations

import pytest

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills.composition._composer import SkillComposer
from backend.modules.coding_agent.skills.context._models import SkillContext
from backend.modules.coding_agent.skills.packs.docker_expert import DockerExpertPack
from backend.modules.coding_agent.skills.packs.git_expert import GitExpertPack
from backend.modules.coding_agent.skills.packs.python_expert import PythonExpertPack
from backend.modules.coding_agent.skills.packs.react_expert import ReactExpertPack
from backend.modules.coding_agent.skills.packs.typescript_expert import TypeScriptExpertPack


@pytest.mark.asyncio
class TestSkillComposer:
    async def test_compose_empty_skills(self) -> None:
        composer = SkillComposer()
        ctx = SkillContext()
        result = await composer.compose_plan([], ctx, "test")
        assert not result.success

    async def test_compose_single_skill(self) -> None:
        composer = SkillComposer()
        ctx = SkillContext()
        skill = PythonExpertPack()
        result = await composer.compose_plan([skill], ctx, "analyse code")
        assert result.success
        assert "Python Execution Plan" in result.content

    async def test_compose_multiple_skills_merge(self) -> None:
        composer = SkillComposer(config=SkillConfig(composition_strategy="merge"))
        ctx = SkillContext()
        skills = [PythonExpertPack(), ReactExpertPack()]
        result = await composer.compose_plan(skills, ctx, "analyse project")
        assert result.success
        assert "Python Expert" in result.content
        assert "React Expert" in result.content

    async def test_compose_sequential(self) -> None:
        composer = SkillComposer(config=SkillConfig(composition_strategy="sequential"))
        ctx = SkillContext()
        skills = [PythonExpertPack(), GitExpertPack()]
        result = await composer.compose_plan(skills, ctx, "plan")
        assert result.success

    async def test_compose_priority_based(self) -> None:
        composer = SkillComposer(config=SkillConfig(composition_strategy="priority"))
        ctx = SkillContext()
        skills = [DockerExpertPack(), GitExpertPack()]
        result = await composer.compose_plan(skills, ctx, "plan")
        assert result.success

    async def test_compose_react_typescript_node_docker_git(self) -> None:
        """React + TypeScript + Node + Docker + Git should produce one combined plan."""
        composer = SkillComposer()
        ctx = SkillContext()
        skills = [
            ReactExpertPack(),
            TypeScriptExpertPack(),
            DockerExpertPack(),
            GitExpertPack(),
        ]
        result = await composer.compose_plan(skills, ctx, "full stack project")
        assert result.success
        assert "React Expert" in result.content
        assert "TypeScript Expert" in result.content
        assert "Docker Expert" in result.content
        assert "Git Expert" in result.content

    async def test_compose_review(self) -> None:
        composer = SkillComposer()
        ctx = SkillContext()
        skills = [PythonExpertPack(), DockerExpertPack()]
        result = await composer.compose_review(skills, ctx)
        assert result.success

    async def test_compose_max_skills_limit(self) -> None:
        composer = SkillComposer(config=SkillConfig(composition_max_skills=2))
        ctx = SkillContext()
        skills = [PythonExpertPack(), ReactExpertPack(), DockerExpertPack(), GitExpertPack()]
        result = await composer.compose_plan(skills, ctx, "plan")
        assert result.success

    async def test_compose_with_failing_skill(self) -> None:
        composer = SkillComposer()
        ctx = SkillContext()

        class FailingSkill(PythonExpertPack):
            async def _execute_plan(self, context: SkillContext) -> None:
                raise RuntimeError("Simulated failure")

        skills = [PythonExpertPack(), FailingSkill()]
        result = await composer.compose_plan(skills, ctx, "plan")
        assert not result.success  # One skill failed, so overall fails
