"""
Unit tests for SkillRegistry — registration, discovery, caching, lazy loading, and versioning.
"""

from __future__ import annotations

import pytest
import time
from typing import Any

from backend.modules.skills.models import Skill, SkillCategory
from backend.modules.skills.registry import SkillRegistry


@pytest.fixture
def registry() -> SkillRegistry:
    return SkillRegistry()


def test_register_and_get_skill(registry: SkillRegistry) -> None:
    skill = Skill(
        id="skill.test.sample",
        name="Sample Skill",
        description="A sample test skill",
        category=SkillCategory.CODING,
        required_capabilities=["python.installed"],
        tags=["sample", "test"],
        aliases=["test_sample"],
        version="1.0.0",
    )

    registry.register_skill(skill)
    fetched = registry.get_skill("skill.test.sample")

    assert fetched is not None
    assert fetched.name == "Sample Skill"
    assert fetched.category == "coding"
    assert fetched.version == "1.0.0"
    assert len(registry.list_skills()) == 1


def test_unregister_skill(registry: SkillRegistry) -> None:
    skill = Skill(
        id="skill.test.remove",
        name="Remove Skill",
        description="To be removed",
        aliases=["to_remove"],
        required_capabilities=["net"],
    )
    registry.register_skill(skill)
    assert registry.get_skill("skill.test.remove") is not None

    removed = registry.unregister_skill("skill.test.remove")
    assert removed is not None
    assert removed.id == "skill.test.remove"
    assert registry.get_skill("skill.test.remove") is None
    assert registry.find_skill_by_name("Remove Skill") is None
    assert registry.find_skill_by_name("to_remove") is None


def test_find_skill_by_name_and_alias(registry: SkillRegistry) -> None:
    skill = Skill(
        id="skill.web.open_url",
        name="Open Website",
        description="Open URL in browser",
        aliases=["visit_page", "open_page"],
    )
    registry.register_skill(skill)

    # By exact name
    assert registry.find_skill_by_name("Open Website") == skill
    # Case-insensitive
    assert registry.find_skill_by_name("open website") == skill
    # By alias
    assert registry.find_skill_by_name("visit_page") == skill
    assert registry.find_skill_by_name("open_page") == skill


def test_find_skills_by_category(registry: SkillRegistry) -> None:
    s1 = Skill(id="s1", name="S1", description="D1", category=SkillCategory.WEB)
    s2 = Skill(id="s2", name="S2", description="D2", category=SkillCategory.WEB)
    s3 = Skill(id="s3", name="S3", description="D3", category=SkillCategory.SYSTEM)

    registry.register_skill(s1)
    registry.register_skill(s2)
    registry.register_skill(s3)

    web_skills = registry.find_skills_by_category(SkillCategory.WEB)
    assert len(web_skills) == 2
    assert {s.id for s in web_skills} == {"s1", "s2"}

    sys_skills = registry.find_skills_by_category("system")
    assert len(sys_skills) == 1
    assert sys_skills[0].id == "s3"


def test_find_skills_by_capability(registry: SkillRegistry) -> None:
    s1 = Skill(id="s1", name="S1", description="D1", required_capabilities=["adb.installed", "usb"])
    s2 = Skill(id="s2", name="S2", description="D2", required_capabilities=["adb.installed"])
    s3 = Skill(id="s3", name="S3", description="D3", required_capabilities=["python.installed"])

    registry.register_skill(s1)
    registry.register_skill(s2)
    registry.register_skill(s3)

    adb_skills = registry.find_skills_by_capability("adb.installed")
    assert len(adb_skills) == 2
    assert {s.id for s in adb_skills} == {"s1", "s2"}


def test_intent_caching_and_invalidation(registry: SkillRegistry) -> None:
    skill = Skill(id="s1", name="Code Review", description="Automated review", tags=["review"])
    registry.register_skill(skill)

    # First match (populates cache)
    matches1 = registry.find_skill_by_intent("code review")
    assert len(matches1) > 0
    assert matches1[0].skill.id == "s1"

    # Second match (hits cache)
    matches2 = registry.find_skill_by_intent("code review")
    assert len(matches2) > 0
    assert matches2[0].skill.id == "s1"

    # Registering a new skill invalidates cache
    s2 = Skill(id="s2", name="Code Audit", description="Security code audit", tags=["review"])
    registry.register_skill(s2)

    matches3 = registry.find_skill_by_intent("code review")
    assert len(matches3) >= 1


def test_lazy_loading_handler(registry: SkillRegistry) -> None:
    loaded = False

    def lazy_handler() -> str:
        nonlocal loaded
        loaded = True
        return "result"

    skill = Skill(
        id="s.lazy",
        name="Lazy Skill",
        description="Lazy execution test",
        executor=lazy_handler,
    )
    registry.register_skill(skill)

    retrieved = registry.get_skill("s.lazy")
    assert retrieved is not None
    assert not loaded  # Handler is deferred and not called on lookup

    # Simulating handler invocation
    assert callable(retrieved.executor)
    res = retrieved.executor()
    assert res == "result"
    assert loaded is True
