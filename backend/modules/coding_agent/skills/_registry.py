"""
SkillRegistry — central registry for all Skill Packs.

Manages registration, lookup, and lifecycle of Skill Pack instances.
"""

from __future__ import annotations

import logging

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._health import SkillHealthReport
from backend.modules.coding_agent.skills._skill_port import SkillPort
from backend.modules.coding_agent.skills._types import SkillMetadata

_LOG = logging.getLogger("naira.coding_agent.skills.registry")


class SkillRegistry:
    """Registry that owns all registered Skill Pack instances."""

    def __init__(
        self,
        *,
        config: SkillConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config or SkillConfig()
        self._logger = logger or _LOG
        self._skills: dict[str, SkillPort] = {}
        self._active_skills: set[str] = set()

    # ── Registration ──────────────────────────────────────────────────

    async def register(self, name: str, skill: SkillPort) -> None:
        """Register a Skill Pack by name.

        Parameters
        ----------
        name : str
            Unique skill name.
        skill : SkillPort
            Skill Pack instance implementing ``SkillPort``.
        """
        if name in self._skills:
            self._logger.warning("Skill '%s' already registered — overwriting", name)
        self._skills[name] = skill
        self._active_skills.add(name)
        self._logger.info(
            "Skill registered: %s (priority=%d)",
            name,
            skill.metadata().priority,
        )

    async def unregister(self, name: str) -> None:
        """Unregister a previously registered Skill Pack."""
        self._skills.pop(name, None)
        self._active_skills.discard(name)
        self._logger.info("Skill unregistered: %s", name)

    def is_registered(self, name: str) -> bool:
        return name in self._skills

    def is_active(self, name: str) -> bool:
        return name in self._active_skills

    # ── Lookup ────────────────────────────────────────────────────────

    def get(self, name: str) -> SkillPort | None:
        return self._skills.get(name)

    def get_by_language(self, language: str) -> list[SkillPort]:
        result: list[SkillPort] = []
        for skill in self._skills.values():
            meta = skill.metadata()
            if language.lower() in [lang.lower() for lang in meta.supported_languages]:
                result.append(skill)
        return result

    def get_by_extension(self, extension: str) -> list[SkillPort]:
        result: list[SkillPort] = []
        ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for skill in self._skills.values():
            meta = skill.metadata()
            if ext in [e.lower() for e in meta.supported_file_extensions]:
                result.append(skill)
        return result

    def get_by_framework(self, framework: str) -> list[SkillPort]:
        result: list[SkillPort] = []
        fw = framework.lower()
        for skill in self._skills.values():
            meta = skill.metadata()
            if fw in [f.lower() for f in meta.supported_frameworks]:
                result.append(skill)
        return result

    def get_prioritized(self) -> list[SkillPort]:
        return sorted(
            self._skills.values(),
            key=lambda s: s.metadata().priority,
        )

    # ── Bulk Queries ──────────────────────────────────────────────────

    @property
    def all_skills(self) -> dict[str, SkillPort]:
        return dict(self._skills)

    @property
    def registered_names(self) -> list[str]:
        return list(self._skills.keys())

    @property
    def active_names(self) -> list[str]:
        return list(self._active_skills)

    def count(self) -> int:
        return len(self._skills)

    # ── Health ────────────────────────────────────────────────────────

    async def health_report(self, name: str) -> SkillHealthReport:
        skill = self._skills.get(name)
        if skill is None:
            return SkillHealthReport.unhealthy(
                name, reason="not_registered"
            )
        try:
            return await skill.health()
        except Exception as exc:
            return SkillHealthReport.unhealthy(
                name, reason=str(exc)
            )

    # ── Metadata ──────────────────────────────────────────────────────

    def get_metadata(self, name: str) -> SkillMetadata | None:
        skill = self._skills.get(name)
        if skill is None:
            return None
        return skill.metadata()
