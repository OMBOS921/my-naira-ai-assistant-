"""
SkillManager — Top-level ModuleInterface implementation for Skill System.

Coordinates SkillRegistry, SkillEngine, built-in skills pre-loading,
and EventBus wiring.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from backend.modules.skills.builtin_skills import get_builtin_skills
from backend.modules.skills.engine import SkillEngine
from backend.modules.skills.models import Skill, SkillMatch
from backend.modules.skills.registry import SkillRegistry

_LOG = logging.getLogger("naira.skills.manager")


class SkillManager:
    """Central Skill System Manager for Naira OS.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration.
    logger : logging.Logger | None
        Module logger.
    event_bus : object | None
        Global EventBus instance.
    capability_registry : object | None
        CapabilityRegistry instance for capability readiness checks.
    task_engine : object | None
        AutonomousTaskEngine instance for execution handoff.
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_registry: object | None = None,
        task_engine: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_registry = capability_registry
        self._task_engine = task_engine

        self._registry = SkillRegistry(event_bus=event_bus)
        self._engine = SkillEngine(
            registry=self._registry,
            capability_registry=capability_registry,
            task_engine=task_engine,
            event_bus=event_bus,
        )
        self._initialized = False
        self._degraded = False

    # ------------------------------------------------------------------
    # ModuleInterface Protocol
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "skills"

    @property
    def status(self) -> str:
        if self._degraded:
            return "degraded"
        return "healthy" if self._initialized else "uninitialized"

    def health(self) -> Dict[str, Any]:
        """Module health assessment."""
        skill_count = len(self._registry.list_skills())
        return {
            "name": self.name,
            "status": self.status,
            "skills_registered": skill_count,
            "engine_active": self._engine is not None,
            "capability_registry_attached": self._capability_registry is not None,
            "task_engine_attached": self._task_engine is not None,
        }

    async def initialize(self, container: Any | None = None) -> None:
        """Initialize Skill module and register default built-in skills."""
        if self._initialized:
            return

        self._logger.info("Initializing SkillManager...")

        # Pre-register standard built-in skills
        for skill in get_builtin_skills():
            self._registry.register_skill(skill)

        self._initialized = True
        self._logger.info("SkillManager initialized with %d skills.", len(self._registry.list_skills()))

    async def async_init(self) -> None:
        """Async initialization alias for system boot sequence."""
        await self.initialize()

    async def shutdown(self) -> None:
        """Clean up module resources."""
        self._logger.info("Shutting down SkillManager...")
        self._initialized = False

    # ------------------------------------------------------------------
    # Public Facade APIs
    # ------------------------------------------------------------------

    @property
    def registry(self) -> SkillRegistry:
        return self._registry

    @property
    def engine(self) -> SkillEngine:
        return self._engine

    def register_skill(self, skill: Skill) -> None:
        """Register a custom or external skill."""
        self._registry.register_skill(skill)

    def unregister_skill(self, skill_id: str) -> Optional[Skill]:
        """Unregister a skill by ID."""
        return self._registry.unregister_skill(skill_id)

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Retrieve skill by ID."""
        return self._registry.get_skill(skill_id)

    def find_skill_by_name(self, name: str) -> Optional[Skill]:
        """Discovery API: find skill by name."""
        return self._registry.find_skill_by_name(name)

    def find_skills_by_category(self, category: str) -> List[Skill]:
        """Discovery API: find skills by category."""
        return self._registry.find_skills_by_category(category)

    def find_skills_by_capability(self, capability: str) -> List[Skill]:
        """Discovery API: find skills requiring capability."""
        return self._registry.find_skills_by_capability(capability)

    def find_skill_by_intent(self, intent: str, min_confidence: float = 0.4) -> List[SkillMatch]:
        """Discovery API: find matching skills for user intent query."""
        return self._engine.match_intent(intent, min_confidence)

    def find_best_skill(self, intent: str) -> Optional[Skill]:
        """Discovery API: find single best executable skill for user intent."""
        return self._registry.find_best_skill(intent)

    def dispatch_skill(self, skill_or_id: Union[Skill, str], context_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Hand skill execution over to TaskEngine."""
        return self._engine.dispatch_skill_execution(skill_or_id, context_data)
