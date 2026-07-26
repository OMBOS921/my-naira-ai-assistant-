"""
Unit tests for Skill Matching — confidence scoring, alias matching, multilingual support, capability checks.
"""

from __future__ import annotations

import pytest

from backend.modules.skills.builtin_skills import get_builtin_skills
from backend.modules.skills.matchers.embedding import EmbeddingSkillMatcher
from backend.modules.skills.matchers.keyword_alias import KeywordAliasSkillMatcher
from backend.modules.skills.matchers.multilingual import MultilingualSkillMatcher
from backend.modules.skills.models import Skill, SkillMatchConfig
from backend.modules.skills.registry import SkillRegistry


@pytest.fixture
def populated_registry() -> SkillRegistry:
    reg = SkillRegistry()
    for skill in get_builtin_skills():
        reg.register_skill(skill)
    return reg


def test_exact_and_alias_matching(populated_registry: SkillRegistry) -> None:
    # Exact intent match
    matches = populated_registry.find_skill_by_intent("Open Website")
    assert len(matches) > 0
    top = matches[0]
    assert top.skill.id == "skill.web.open_website"
    assert top.confidence >= 0.95

    # Alias intent match
    alias_matches = populated_registry.find_skill_by_intent("browse_url")
    assert len(alias_matches) > 0
    assert alias_matches[0].skill.id == "skill.web.open_website"
    assert alias_matches[0].confidence >= 0.95


def test_multilingual_intent_matching(populated_registry: SkillRegistry) -> None:
    # Spanish
    es_matches = populated_registry.find_skill_by_intent("abrir sitio web")
    assert len(es_matches) > 0
    assert es_matches[0].skill.id == "skill.web.open_website"

    # Yoruba
    yo_matches = populated_registry.find_skill_by_intent("sii oju opo webu")
    assert len(yo_matches) > 0
    assert yo_matches[0].skill.id == "skill.web.open_website"

    # French
    fr_matches = populated_registry.find_skill_by_intent("revue de code")
    assert len(fr_matches) > 0
    assert fr_matches[0].skill.id == "skill.coding.code_review"

    # Nigerian Pidgin
    pidgin_matches = populated_registry.find_skill_by_intent("check system")
    assert len(pidgin_matches) > 0
    assert pidgin_matches[0].skill.id == "skill.system.system_diagnostics"


def test_capability_matching_and_filtering(populated_registry: SkillRegistry) -> None:
    # Query with missing required capabilities
    matches_missing = populated_registry.find_skill_by_intent(
        intent="flash android",
        available_capabilities=["network.available"],
    )
    assert len(matches_missing) > 0
    match = matches_missing[0]
    assert match.skill.id == "skill.mobile.android_flashing"
    assert match.is_executable is False
    assert "adb.installed" in match.missing_capabilities

    # Query with satisfied capabilities
    matches_satisfied = populated_registry.find_skill_by_intent(
        intent="flash android",
        available_capabilities=["adb.installed", "network.available"],
    )
    assert len(matches_satisfied) > 0
    sat_match = matches_satisfied[0]
    assert sat_match.skill.id == "skill.mobile.android_flashing"
    assert sat_match.is_executable is True
    assert len(sat_match.missing_capabilities) == 0


def test_confidence_scoring_ranking(populated_registry: SkillRegistry) -> None:
    matches = populated_registry.find_skill_by_intent("review code audit", min_confidence=0.3)
    assert len(matches) >= 1
    # Candidate results should be ordered by confidence descending
    for i in range(len(matches) - 1):
        assert matches[i].confidence >= matches[i + 1].confidence


def test_extensible_embedding_matcher_hook() -> None:
    # Dummy embedding function generator
    def mock_embed(text: str) -> list[float]:
        text_lower = text.lower()
        if "web" in text_lower or "site" in text_lower:
            return [1.0, 0.0, 0.0]
        if "code" in text_lower or "review" in text_lower:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def mock_cosine(v1: list[float], v2: list[float]) -> float:
        return sum(a * b for a, b in zip(v1, v2))

    matcher = EmbeddingSkillMatcher(
        embedding_func=mock_embed,
        cosine_sim_func=mock_cosine,
    )
    assert matcher.is_available() is True

    skills = get_builtin_skills()
    results = matcher.match("web search query", skills, SkillMatchConfig(min_confidence=0.5))

    assert len(results) > 0
    assert "web" in results[0].skill.id
