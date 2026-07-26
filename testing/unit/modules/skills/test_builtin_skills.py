"""
Unit tests for Built-in Skills schema & specification.
"""

from __future__ import annotations

import pytest

from backend.modules.skills.builtin_skills import get_builtin_skills
from backend.modules.skills.models import SkillCategory


def test_builtin_skills_schema() -> None:
    skills = get_builtin_skills()
    assert len(skills) == 10

    expected_ids = {
        "skill.web.open_website",
        "skill.web.search_web",
        "skill.coding.code_review",
        "skill.vcs.git_ops",
        "skill.mobile.android_flashing",
        "skill.coding.repository_analysis",
        "skill.devops.project_build",
        "skill.document.pdf_analysis",
        "skill.system.system_diagnostics",
        "skill.system.software_installation",
    }

    actual_ids = {s.id for s in skills}
    assert actual_ids == expected_ids

    for skill in skills:
        assert isinstance(skill.id, str) and len(skill.id) > 0
        assert isinstance(skill.name, str) and len(skill.name) > 0
        assert isinstance(skill.description, str) and len(skill.description) > 0
        assert isinstance(skill.category, str) and len(skill.category) > 0
        assert isinstance(skill.required_capabilities, list)
        assert isinstance(skill.optional_capabilities, list)
        assert isinstance(skill.supported_platforms, list)
        assert isinstance(skill.required_permissions, list)
        assert 0.0 <= skill.complexity_score <= 1.0
        assert skill.estimated_duration > 0.0
        assert isinstance(skill.rollback_support, bool)
        assert isinstance(skill.tags, list) and len(skill.tags) > 0
        assert isinstance(skill.aliases, list)
        assert isinstance(skill.version, str)
