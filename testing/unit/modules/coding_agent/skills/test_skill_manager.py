"""Tests for SkillManager."""

from __future__ import annotations

import pytest

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._manager import SkillManager
from backend.modules.coding_agent.skills.context._models import SkillContext
from backend.modules.coding_agent.skills.packs.python_expert import PythonExpertPack


@pytest.mark.asyncio
class TestSkillManager:
    async def test_initialise_empty(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        assert mgr.initialized
        assert mgr.degraded

    async def test_initialise_with_skills(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=True))
        await mgr.async_init()
        assert mgr.initialized

    async def test_register_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        assert mgr.get_skill("python") is skill
        assert "python" in mgr.list_skills()

    async def test_unregister_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        await mgr.unregister_skill("python")
        assert mgr.get_skill("python") is None

    async def test_list_skills(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=True))
        await mgr.async_init()
        skills = mgr.list_skills()
        assert len(skills) > 0
        assert "python" in skills

    async def test_list_active_skills(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=True))
        await mgr.async_init()
        active = mgr.list_active_skills()
        assert len(active) > 0

    async def test_shutdown(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        await mgr.async_shutdown()
        assert not mgr.initialized

    async def test_degrade(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded

    async def test_health(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=True))
        await mgr.async_init()
        health = mgr.health()
        assert "subsystem" in health
        assert health["subsystem"]["subsystem"] == "skills"
        assert "per_skill" in health

    async def test_metrics(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        metrics = mgr.metrics()
        assert metrics["total_requests"] == 0

    async def test_analyse_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        ctx = SkillContext()
        result = await mgr.analyse("python", ctx)
        assert result.success

    async def test_plan_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        ctx = SkillContext()
        result = await mgr.plan("python", ctx)
        assert result.success

    async def test_review_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        ctx = SkillContext()
        result = await mgr.review("python", ctx)
        assert result.success

    async def test_generate_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        ctx = SkillContext()
        result = await mgr.generate("python", ctx)
        assert result.success

    async def test_refactor_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        ctx = SkillContext()
        result = await mgr.refactor("python", ctx)
        assert result.success

    async def test_debug_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        ctx = SkillContext()
        result = await mgr.debug("python", ctx)
        assert result.success

    async def test_explain_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        skill = PythonExpertPack()
        await mgr.register_skill("python", skill)
        ctx = SkillContext()
        result = await mgr.explain("python", ctx)
        assert result.success

    async def test_analyse_nonexistent_skill(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        ctx = SkillContext()
        result = await mgr.analyse("nonexistent", ctx)
        assert not result.success

    async def test_detect_project(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        ctx = await mgr.detect_project(".")
        assert ctx.root_path != ""

    async def test_detect_capabilities(self) -> None:
        mgr = SkillManager(config=SkillConfig(auto_register_builtin_packs=False))
        await mgr.async_init()
        caps = await mgr.detect_capabilities(".")
        assert isinstance(caps, dict)
