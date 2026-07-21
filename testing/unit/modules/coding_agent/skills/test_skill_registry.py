"""Tests for SkillRegistry."""

from __future__ import annotations

import pytest

from backend.modules.coding_agent.skills.packs.python_expert import PythonExpertPack
from backend.modules.coding_agent.skills.packs.react_expert import ReactExpertPack
from backend.modules.coding_agent.skills.packs.typescript_expert import TypeScriptExpertPack


@pytest.mark.asyncio
class TestSkillRegistry:
    async def test_register_and_get(self, empty_registry) -> None:
        skill = PythonExpertPack()
        await empty_registry.register("python", skill)
        assert empty_registry.is_registered("python")
        assert empty_registry.get("python") is skill

    async def test_register_overwrite(self, empty_registry) -> None:
        skill1 = PythonExpertPack()
        skill2 = PythonExpertPack()
        await empty_registry.register("python", skill1)
        await empty_registry.register("python", skill2)
        assert empty_registry.get("python") is skill2

    async def test_unregister(self, empty_registry) -> None:
        skill = PythonExpertPack()
        await empty_registry.register("python", skill)
        assert empty_registry.is_registered("python")
        await empty_registry.unregister("python")
        assert not empty_registry.is_registered("python")

    async def test_count(self, empty_registry) -> None:
        assert empty_registry.count() == 0
        await empty_registry.register("python", PythonExpertPack())
        assert empty_registry.count() == 1
        await empty_registry.register("react", ReactExpertPack())
        assert empty_registry.count() == 2

    async def test_registered_names(self, empty_registry) -> None:
        await empty_registry.register("python", PythonExpertPack())
        await empty_registry.register("react", ReactExpertPack())
        names = empty_registry.registered_names
        assert "python" in names
        assert "react" in names

    async def test_active_names(self, empty_registry) -> None:
        skill = PythonExpertPack()
        await empty_registry.register("python", skill)
        assert "python" in empty_registry.active_names

    async def test_get_by_language(self, empty_registry) -> None:
        python_skill = PythonExpertPack()
        ts_skill = TypeScriptExpertPack()
        await empty_registry.register("python", python_skill)
        await empty_registry.register("typescript", ts_skill)
        result = empty_registry.get_by_language("python")
        assert python_skill in result
        assert ts_skill not in result

    async def test_get_by_extension(self, empty_registry) -> None:
        python_skill = PythonExpertPack()
        await empty_registry.register("python", python_skill)
        result = empty_registry.get_by_extension(".py")
        assert python_skill in result

    async def test_get_by_framework(self, empty_registry) -> None:
        react_skill = ReactExpertPack()
        await empty_registry.register("react", react_skill)
        result = empty_registry.get_by_framework("react")
        assert react_skill in result

    async def test_get_prioritized(self, empty_registry) -> None:
        low = PythonExpertPack()
        low._meta = low._meta.__class__(
            name="low", description="", priority=200,
            supported_languages=(), supported_frameworks=(),
            supported_file_extensions=(),
        )
        high = ReactExpertPack()
        high._meta = high._meta.__class__(
            name="high", description="", priority=50,
            supported_languages=(), supported_frameworks=(),
            supported_file_extensions=(),
        )
        await empty_registry.register("low", low)
        await empty_registry.register("high", high)
        prioritized = empty_registry.get_prioritized()
        assert prioritized[0].metadata().name == "high"

    async def test_get_nonexistent(self, empty_registry) -> None:
        assert empty_registry.get("nonexistent") is None

    async def test_all_skills_property(self, empty_registry) -> None:
        py = PythonExpertPack()
        react = ReactExpertPack()
        await empty_registry.register("python", py)
        await empty_registry.register("react", react)
        all_skills = empty_registry.all_skills
        assert all_skills["python"] is py
        assert all_skills["react"] is react

    async def test_health_report_registered(self, empty_registry) -> None:
        skill = PythonExpertPack()
        await empty_registry.register("python", skill)
        report = await empty_registry.health_report("python")
        assert report.is_healthy
        assert report.registered
        assert report.active
        assert report.name == "Python Expert"

    async def test_health_report_unregistered(self, empty_registry) -> None:
        report = await empty_registry.health_report("nonexistent")
        assert not report.is_healthy
        assert not report.active

    async def test_get_metadata(self, empty_registry) -> None:
        skill = PythonExpertPack()
        await empty_registry.register("python", skill)
        meta = empty_registry.get_metadata("python")
        assert meta is not None
        assert meta.name == "Python Expert"

    async def test_get_metadata_nonexistent(self, empty_registry) -> None:
        assert empty_registry.get_metadata("nonexistent") is None
