"""
SkillManager — central manager for the skills subsystem.

CodingAgentManager asks SkillManager when domain expertise is required.
Follows the same architecture as LLMManager, VoiceManager, VisionManager.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._health import SkillHealthReportBuilder
from backend.modules.coding_agent.skills._registry import SkillRegistry
from backend.modules.coding_agent.skills._skill_port import SkillPort
from backend.modules.coding_agent.skills._statistics import AggregatedStatistics
from backend.modules.coding_agent.skills._types import (
    SkillResult,
)
from backend.modules.coding_agent.skills._watcher import SkillWatcher
from backend.modules.coding_agent.skills.composition._composer import SkillComposer
from backend.modules.coding_agent.skills.context._models import (
    ProjectContext,
    SkillContext,
)
from backend.modules.coding_agent.skills.detection._capability import CapabilityDetector
from backend.modules.coding_agent.skills.detection._project import ProjectDetector
from backend.modules.coding_agent.skills.routing._router import SkillRouter

_LOG = logging.getLogger("naira.coding_agent.skills.manager")


class SkillManager:
    """Central manager for the skills subsystem.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : SkillConfig | None
        Skills subsystem configuration.
    logger : logging.Logger | None
        Module-scoped logger.
    registry : SkillRegistry | None
        Skill registry instance.
    router : SkillRouter | None
        Auto-routing engine.
    composer : SkillComposer | None
        Skill composition engine.
    project_detector : ProjectDetector | None
        Project type detector.
    capability_detector : CapabilityDetector | None
        Capability detector.
    event_bus : object | None
        Event bus for emitting events.
    """

    def __init__(
        self,
        *,
        config: SkillConfig | None = None,
        logger: logging.Logger | None = None,
        registry: SkillRegistry | None = None,
        router: SkillRouter | None = None,
        composer: SkillComposer | None = None,
        project_detector: ProjectDetector | None = None,
        capability_detector: CapabilityDetector | None = None,
        event_bus: object | None = None,
        watcher: SkillWatcher | None = None,
    ) -> None:
        self._config = config or SkillConfig()
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._watcher = watcher or SkillWatcher(logger=self._logger)

        # Core subsystem components
        self._registry = registry or SkillRegistry(
            config=self._config,
            logger=self._logger,
        )
        self._router = router or SkillRouter(
            registry=self._registry,
            config=self._config,
            logger=self._logger,
        )
        self._composer = composer or SkillComposer(
            config=self._config,
            logger=self._logger,
        )
        self._project_detector = project_detector or ProjectDetector(
            config=self._config,
            logger=self._logger,
        )
        self._capability_detector = capability_detector or CapabilityDetector(
            config=self._config,
            logger=self._logger,
        )

        # Statistics
        self._statistics = AggregatedStatistics()

        # State
        self._degraded: bool = False
        self._initialized: bool = False
        self._builtin_registered: bool = False
        self._cached_health: dict[str, Any] = {
            "subsystem": {"healthy": False, "degraded": True},
            "per_skill": {},
        }

    # ── Module lifecycle ──────────────────────────────────────────────

    async def async_init(self) -> None:
        """Initialise the skills subsystem."""
        if not self._config.enable_skills:
            self._logger.info("Skills subsystem disabled by config")
            self._degraded = True
            self._initialized = True
            return

        if self._config.auto_register_builtin_packs and not self._builtin_registered:
            await self._register_builtin_packs()

        if self._registry.count() == 0:
            self._logger.warning(
                "No Skill Packs registered — skills subsystem degraded"
            )
            self._degraded = True
        else:
            self._degraded = False

        self._initialized = True

        if self._config.enable_skills and self._config.auto_register_builtin_packs:
            self._watcher.enable()

        self._refresh_health_cache()

        await self._emit_event("skills.initialised", {
            "skill_count": self._registry.count(),
            "degraded": self._degraded,
            "skills": self._registry.registered_names,
        })

        self._logger.info(
            "SkillManager initialised — %d skill(s) registered, degraded=%s",
            self._registry.count(),
            self._degraded,
        )

    async def async_shutdown(self) -> None:
        """Shut down the skills subsystem."""
        await self._emit_event("skills.shutdown", {
            "skill_count": self._registry.count(),
        })
        self._degraded = False
        self._initialized = False
        self._logger.info("SkillManager shut down.")

    def degrade(self) -> None:
        """Mark the manager as degraded."""
        self._degraded = True
        self._refresh_health_cache()
        self._logger.warning("SkillManager marked degraded")
        import asyncio
        import contextlib
        with contextlib.suppress(Exception):
            asyncio.ensure_future(self._emit_event("skills.degraded", {}))

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ── Registration ──────────────────────────────────────────────────

    async def register_skill(self, name: str, skill: SkillPort) -> None:
        """Register a Skill Pack."""
        await self._registry.register(name, skill)
        await self._emit_event("skills.skill_registered", {
            "name": name,
            "display_name": skill.metadata().name,
        })

    async def unregister_skill(self, name: str) -> None:
        """Unregister a Skill Pack."""
        await self._registry.unregister(name)

    def get_skill(self, name: str) -> SkillPort | None:
        return self._registry.get(name)

    def list_skills(self) -> list[str]:
        return self._registry.registered_names

    def list_active_skills(self) -> list[str]:
        return self._registry.active_names

    # ── Auto-registration of built-in packs ──────────────────────────

    async def _register_builtin_packs(self) -> None:
        """Register all built-in Skill Packs."""
        from backend.modules.coding_agent.skills.packs._base import BaseSkillPack
        from backend.modules.coding_agent.skills.packs.ai_ml_expert import AIMLExpertPack
        from backend.modules.coding_agent.skills.packs.c_expert import CExpertPack
        from backend.modules.coding_agent.skills.packs.competitive_programming_expert import (
            CompetitiveProgrammingExpertPack,
        )
        from backend.modules.coding_agent.skills.packs.cpp_expert import CppExpertPack
        from backend.modules.coding_agent.skills.packs.devops_expert import DevOpsExpertPack
        from backend.modules.coding_agent.skills.packs.django_expert import DjangoExpertPack
        from backend.modules.coding_agent.skills.packs.docker_expert import DockerExpertPack
        from backend.modules.coding_agent.skills.packs.dsa_expert import DSAExpertPack
        from backend.modules.coding_agent.skills.packs.express_expert import ExpressExpertPack
        from backend.modules.coding_agent.skills.packs.fastapi_expert import FastAPIExpertPack
        from backend.modules.coding_agent.skills.packs.git_expert import GitExpertPack
        from backend.modules.coding_agent.skills.packs.java_expert import JavaExpertPack
        from backend.modules.coding_agent.skills.packs.javascript_expert import JavaScriptExpertPack
        from backend.modules.coding_agent.skills.packs.kubernetes_expert import KubernetesExpertPack
        from backend.modules.coding_agent.skills.packs.linux_expert import LinuxExpertPack
        from backend.modules.coding_agent.skills.packs.mongodb_expert import MongoDBExpertPack
        from backend.modules.coding_agent.skills.packs.nextjs_expert import NextJsExpertPack
        from backend.modules.coding_agent.skills.packs.nodejs_expert import NodeJsExpertPack
        from backend.modules.coding_agent.skills.packs.postgresql_expert import PostgreSQLExpertPack
        from backend.modules.coding_agent.skills.packs.python_expert import PythonExpertPack
        from backend.modules.coding_agent.skills.packs.react_expert import ReactExpertPack
        from backend.modules.coding_agent.skills.packs.sql_expert import SQlExpertPack
        from backend.modules.coding_agent.skills.packs.typescript_expert import TypeScriptExpertPack
        from backend.modules.coding_agent.skills.packs.web_security_expert import (
            WebSecurityExpertPack,
        )

        builtin_packs: list[tuple[str, BaseSkillPack]] = [
            ("c", CExpertPack()),
            ("cpp", CppExpertPack()),
            ("python", PythonExpertPack()),
            ("java", JavaExpertPack()),
            ("javascript", JavaScriptExpertPack()),
            ("typescript", TypeScriptExpertPack()),
            ("react", ReactExpertPack()),
            ("nextjs", NextJsExpertPack()),
            ("nodejs", NodeJsExpertPack()),
            ("express", ExpressExpertPack()),
            ("django", DjangoExpertPack()),
            ("fastapi", FastAPIExpertPack()),
            ("sql", SQlExpertPack()),
            ("mongodb", MongoDBExpertPack()),
            ("postgresql", PostgreSQLExpertPack()),
            ("git", GitExpertPack()),
            ("docker", DockerExpertPack()),
            ("kubernetes", KubernetesExpertPack()),
            ("linux", LinuxExpertPack()),
            ("dsa", DSAExpertPack()),
            ("competitive_programming", CompetitiveProgrammingExpertPack()),
            ("web_security", WebSecurityExpertPack()),
            ("devops", DevOpsExpertPack()),
            ("ai_ml", AIMLExpertPack()),
        ]

        for name, pack in builtin_packs:
            try:
                await self._registry.register(name, pack)
            except Exception as exc:
                self._logger.error(
                    "Failed to register builtin pack '%s': %s", name, exc
                )

        self._builtin_registered = True
        self._logger.info(
            "Registered %d built-in Skill Packs",
            len(builtin_packs),
        )

    # ── Project & Capability Detection ────────────────────────────────

    async def detect_project(self, root_path: str) -> ProjectContext:
        """Detect project type and characteristics."""
        return await self._project_detector.detect(root_path)

    async def detect_capabilities(
        self, root_path: str, project_files: list[str] | None = None
    ) -> dict[str, Any]:
        """Detect project capabilities (build system, frameworks, etc.)."""
        return await self._capability_detector.detect(root_path, project_files)

    # ── Routing ───────────────────────────────────────────────────────

    async def route(self, context: Any, query: str = "") -> list[SkillPort]:
        """Route request to appropriate Skill Packs."""
        self._statistics.record_routing()
        return await self._router.route(context, query=query)

    async def route_by_file(
        self, file_path: str, project: ProjectContext
    ) -> list[SkillPort]:
        """Route by file path."""
        self._statistics.record_routing()
        return await self._router.route_by_file(file_path, project)

    # ── Skill Composition ─────────────────────────────────────────────

    async def compose_plan(
        self,
        skills: list[SkillPort],
        context: SkillContext,
        query: str = "",
    ) -> SkillResult:
        """Execute and compose plans from multiple skills."""
        self._statistics.record_composition()
        return await self._composer.compose_plan(skills, context, query)

    async def compose_review(
        self,
        skills: list[SkillPort],
        context: SkillContext,
    ) -> SkillResult:
        """Execute and compose reviews from multiple skills."""
        self._statistics.record_composition()
        return await self._composer.compose_review(skills, context)

    # ── Direct Skill Operations ───────────────────────────────────────

    async def _execute_skill_op(
        self,
        skill_name: str,
        op: str,
        context: SkillContext,
    ) -> SkillResult:
        """Execute a single skill operation with metrics tracking."""
        skill = self._registry.get(skill_name)
        if skill is None:
            return SkillResult.fail(f"Skill '{skill_name}' not found")

        start = time.time()
        try:
            ops = {
                "analyse": skill.analyse,
                "plan": skill.plan,
                "review": skill.review,
                "generate": skill.generate,
                "refactor": skill.refactor,
                "debug": skill.debug,
                "explain": skill.explain,
            }
            method = ops.get(op)
            if method is None:
                return SkillResult.fail(f"Unknown operation: {op}")

            await self._emit_event("skills.skill_execution_start", {
                "skill": skill_name,
                "operation": op,
            })

            result = await method(context)
            duration_ms = (time.time() - start) * 1000
            result.duration_ms = duration_ms
            self._statistics.record_skill(skill_name, duration_ms, result.success)

            await self._emit_event("skills.skill_execution_complete", {
                "skill": skill_name,
                "operation": op,
                "success": result.success,
                "duration_ms": duration_ms,
            })
            return result
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            self._statistics.record_skill(skill_name, duration_ms, False)

            await self._emit_event("skills.skill_execution_error", {
                "skill": skill_name,
                "operation": op,
                "error": str(exc),
                "duration_ms": duration_ms,
            })
            return SkillResult.fail(f"{skill_name}.{op}: {exc}")

    async def analyse(
        self, skill_name: str, context: SkillContext
    ) -> SkillResult:
        return await self._execute_skill_op(skill_name, "analyse", context)

    async def plan(
        self, skill_name: str, context: SkillContext
    ) -> SkillResult:
        return await self._execute_skill_op(skill_name, "plan", context)

    async def review(
        self, skill_name: str, context: SkillContext
    ) -> SkillResult:
        return await self._execute_skill_op(skill_name, "review", context)

    async def generate(
        self, skill_name: str, context: SkillContext
    ) -> SkillResult:
        return await self._execute_skill_op(skill_name, "generate", context)

    async def refactor(
        self, skill_name: str, context: SkillContext
    ) -> SkillResult:
        return await self._execute_skill_op(skill_name, "refactor", context)

    async def debug(
        self, skill_name: str, context: SkillContext
    ) -> SkillResult:
        return await self._execute_skill_op(skill_name, "debug", context)

    async def explain(
        self, skill_name: str, context: SkillContext
    ) -> SkillResult:
        return await self._execute_skill_op(skill_name, "explain", context)

    # ── Session Persistence ──────────────────────────────────────────

    def save_state(self) -> dict[str, Any]:
        """Serialize current skill manager state for session persistence."""
        return {
            "enabled": self._config.enable_skills,
            "degraded": self._degraded,
            "initialized": self._initialized,
            "skill_count": self._registry.count(),
            "registered_skills": self._registry.registered_names,
            "active_skills": self._registry.active_names,
            "statistics": self._statistics.to_dict(),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore skill manager state from persisted data."""
        if not state:
            return
        self._logger.info(
            "Restoring skill manager state — %d skill(s)",
            state.get("skill_count", 0),
        )

    # ── Hot Reload ────────────────────────────────────────────────────

    async def hot_reload_skill(self, skill_name: str) -> bool:
        """Hot-reload a single skill pack by name.

        Re-imports the module, recreates the pack, and re-registers it.
        Returns True if the reload succeeded.
        """
        import importlib
        import sys

        from backend.modules.coding_agent.skills.packs._base import BaseSkillPack

        skill = self._registry.get(skill_name)
        if skill is None:
            self._logger.warning("Cannot hot-reload unknown skill '%s'", skill_name)
            return False

        module_name = type(skill).__module__
        if module_name not in sys.modules:
            self._logger.warning("Module '%s' not found in sys.modules", module_name)
            return False

        try:
            importlib.reload(sys.modules[module_name])
            module = sys.modules[module_name]
            new_skill = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, type(skill)) and attr is not type(skill):
                    new_skill = attr()
                    break
            if new_skill is None:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseSkillPack):
                        new_skill = attr()
                        break
            if new_skill is not None:
                old_meta = skill.metadata()
                await self._registry.unregister(skill_name)
                await self._registry.register(skill_name, new_skill)
                await self._emit_event("skills.skill_hot_reloaded", {
                    "name": skill_name,
                    "old_version": old_meta.description,
                })
                self._logger.info("Hot-reloaded skill '%s'", skill_name)
                return True
            else:
                self._logger.warning("Could not find replacement class for '%s'", skill_name)
                return False
        except Exception as exc:
            self._logger.error("Failed to hot-reload skill '%s': %s", skill_name, exc)
            return False

    # ── Internal helpers ──────────────────────────────────────────────

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            try:
                await emit(event_type, data, source="skill_manager")
            except Exception:
                self._logger.debug("Failed to emit event '%s'", event_type)

    # ── Health & Metrics ──────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Return health report for the entire skills subsystem.

        Sync to match ModuleInterface protocol.  Cache is refreshed
        during async_init, on degrade, and via _refresh_health_cache.
        """
        return dict(self._cached_health)

    def _refresh_health_cache(self) -> None:
        """Rebuild the sync health cache from current registry state."""
        reports: dict[str, Any] = {}
        for name in self._registry.registered_names:
            try:
                reports[name] = {"name": name, "status": "registered"}
            except Exception as exc:
                reports[name] = {"error": str(exc)}

        subsystem = SkillHealthReportBuilder.subsystem_report(
            registered_skills=self._registry.registered_names,
            active_skills=self._registry.active_names,
            degraded=self._degraded,
            stats=self._statistics,
        )
        self._cached_health = {
            "subsystem": subsystem,
            "per_skill": reports,
        }

    def metrics(self) -> dict[str, Any]:
        """Return aggregated metrics."""
        return self._statistics.to_dict()

    def get_statistics(self) -> AggregatedStatistics:
        return self._statistics
