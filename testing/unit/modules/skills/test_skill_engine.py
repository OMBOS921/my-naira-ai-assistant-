"""
Unit tests for SkillEngine — orchestration, intent selection, capability checks, and non-direct execution delegation.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.modules.skills.builtin_skills import get_builtin_skills
from backend.modules.skills.engine import SkillEngine
from backend.modules.skills.models import Skill
from backend.modules.skills.registry import SkillRegistry
from backend.modules.skills.skills_module import SkillManager


@pytest.fixture
def mock_capability_registry() -> MagicMock:
    mock_reg = MagicMock()
    # Simulate return of active capabilities
    cap1 = MagicMock()
    cap1.name = "browser.installed"
    cap2 = MagicMock()
    cap2.name = "network.available"
    mock_reg.list_active_capabilities.return_value = [cap1, cap2]
    return mock_reg


@pytest.fixture
def mock_task_engine() -> MagicMock:
    mock_te = MagicMock()
    return mock_te


@pytest.fixture
def mock_event_bus() -> MagicMock:
    return MagicMock()


@pytest.fixture
def skill_engine(
    mock_capability_registry: MagicMock,
    mock_task_engine: MagicMock,
    mock_event_bus: MagicMock,
) -> SkillEngine:
    registry = SkillRegistry(event_bus=mock_event_bus)
    for skill in get_builtin_skills():
        registry.register_skill(skill)
    return SkillEngine(
        registry=registry,
        capability_registry=mock_capability_registry,
        task_engine=mock_task_engine,
        event_bus=mock_event_bus,
    )


def test_select_best_skill(skill_engine: SkillEngine) -> None:
    match, candidates = skill_engine.select_best_skill("open website URL")
    assert match is not None
    assert match.skill.id == "skill.web.open_website"
    assert match.is_executable is True


def test_non_direct_execution_delegation(
    skill_engine: SkillEngine,
    mock_task_engine: MagicMock,
    mock_event_bus: MagicMock,
) -> None:
    # Critical test: Verify SkillEngine does NOT execute the skill directly, but hands off to TaskEngine
    dispatch_res = skill_engine.dispatch_skill_execution(
        skill_or_id="skill.web.open_website",
        context_data={"url": "https://example.com"},
    )

    assert dispatch_res["status"] == "HANDED_OFF"
    assert dispatch_res["skill_id"] == "skill.web.open_website"
    assert dispatch_res["context"]["url"] == "https://example.com"

    # Verify Task Engine submit_task was called
    mock_task_engine.submit_task.assert_called_once()
    call_args = mock_task_engine.submit_task.call_args[1]
    assert call_args["action_type"] == "skill.web.open_website"

    # Verify EventBus published SKILL_DISPATCHED
    mock_event_bus.publish.assert_called_with(
        "SKILL_DISPATCHED",
        {
            "task_id": dispatch_res["task_id"],
            "skill_id": "skill.web.open_website",
            "status": "HANDED_OFF",
        },
    )


@pytest.mark.asyncio
async def test_skill_manager_facade() -> None:
    mgr = SkillManager()
    await mgr.initialize()

    assert mgr.status == "healthy"
    assert len(mgr.registry.list_skills()) == 10

    # Discovery API tests via SkillManager facade
    found_by_name = mgr.find_skill_by_name("Code Review")
    assert found_by_name is not None
    assert found_by_name.id == "skill.coding.code_review"

    best_skill = mgr.find_best_skill("check hardware cpu health")
    assert best_skill is not None
    assert best_skill.id == "skill.system.system_diagnostics"

    skills_by_cap = mgr.find_skills_by_capability("git.installed")
    assert len(skills_by_cap) == 1
    assert skills_by_cap[0].id == "skill.vcs.git_ops"

    await mgr.shutdown()
    assert mgr.status == "uninitialized"
