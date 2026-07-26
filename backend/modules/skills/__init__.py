"""
Skills Module — Central Skill Registry and Skill Engine for Naira OS.

Public API
----------
- ``SkillManager`` — Top-level module manager
- ``SkillRegistry`` — Central catalog of executable intelligence
- ``SkillEngine`` — Intent matching & execution handoff orchestrator
- ``Skill`` — Central skill descriptor model
- ``SkillCategory`` — Skill domain categories enum
- ``SkillMatch`` — Result container for intent matching
- ``SkillMatchConfig`` — Matching threshold configuration
- ``get_builtin_skills`` — Factory for default standard built-in skills
"""

from __future__ import annotations

from backend.modules.skills.builtin_skills import get_builtin_skills
from backend.modules.skills.engine import SkillEngine
from backend.modules.skills.models import (
    Skill,
    SkillCategory,
    SkillMatch,
    SkillMatchConfig,
)
from backend.modules.skills.registry import SkillRegistry
from backend.modules.skills.skills_module import SkillManager

__all__ = [
    "SkillManager",
    "SkillRegistry",
    "SkillEngine",
    "Skill",
    "SkillCategory",
    "SkillMatch",
    "SkillMatchConfig",
    "get_builtin_skills",
]
