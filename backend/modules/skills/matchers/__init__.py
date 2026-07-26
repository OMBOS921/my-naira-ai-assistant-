"""
Skill Matchers Package — Intent matching strategy implementations.
"""

from __future__ import annotations

from backend.modules.skills.matchers.base import BaseSkillMatcher
from backend.modules.skills.matchers.embedding import EmbeddingSkillMatcher
from backend.modules.skills.matchers.keyword_alias import KeywordAliasSkillMatcher
from backend.modules.skills.matchers.multilingual import MultilingualSkillMatcher

__all__ = [
    "BaseSkillMatcher",
    "KeywordAliasSkillMatcher",
    "MultilingualSkillMatcher",
    "EmbeddingSkillMatcher",
]
