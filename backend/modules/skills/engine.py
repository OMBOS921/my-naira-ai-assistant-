"""
Skill Engine — Orchestration and Intent Matching Engine for Naira OS.

CRITICAL INVARIANT: The Skill Engine NEVER executes skills directly!
It selects the appropriate skill, validates capability prerequisites against
CapabilityRegistry, converts the skill intent into a task specification, and
hands execution over to AutonomousTaskEngine.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from backend.modules.skills.models import Skill, SkillMatch, SkillMatchConfig
from backend.modules.skills.registry import SkillRegistry

_LOG = logging.getLogger("naira.skills.engine")


class SkillEngine:
    """Orchestrates skill matching and delegates execution to TaskEngine.

    Parameters
    ----------
    registry : SkillRegistry
        Central skill registry instance.
    capability_registry : Any | None
        CapabilityRegistry instance for real-time capability checks.
    task_engine : Any | None
        AutonomousTaskEngine instance for executing tasks.
    event_bus : Any | None
        EventBus instance for publishing/subscribing events.
    """

    def __init__(
        self,
        registry: SkillRegistry,
        capability_registry: Any | None = None,
        task_engine: Any | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._registry = registry
        self._capability_registry = capability_registry
        self._task_engine = task_engine
        self._event_bus = event_bus
        self._lock = threading.RLock()

        if self._event_bus:
            self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        try:
            self._event_bus.subscribe("CAPABILITY_CHANGED", self._on_capability_changed)
        except Exception as err:
            _LOG.warning("Could not subscribe to CAPABILITY_CHANGED event: %s", err)

    def _on_capability_changed(self, event_data: Dict[str, Any]) -> None:
        _LOG.debug("Capability state changed event received: %s", event_data)
        # Clear registry match cache on capability status changes
        if hasattr(self._registry, "_cache"):
            self._registry._cache.clear()

    # ------------------------------------------------------------------
    # Capability Query Helper
    # ------------------------------------------------------------------

    def get_available_capability_names(self) -> List[str]:
        """Fetch active/satisfied capability names from CapabilityRegistry."""
        if not self._capability_registry:
            return []

        try:
            # Check if CapabilityRegistry has list/query methods
            if hasattr(self._capability_registry, "list_active_capabilities"):
                active = self._capability_registry.list_active_capabilities()
                return [c.name if hasattr(c, "name") else str(c) for c in active]
            elif hasattr(self._capability_registry, "list_all"):
                all_caps = self._capability_registry.list_all()
                return [c.name if hasattr(c, "name") else str(c) for c in all_caps]
            elif hasattr(self._capability_registry, "get_all"):
                all_caps = self._capability_registry.get_all()
                return [c.name if hasattr(c, "name") else str(c) for c in all_caps]
        except Exception as err:
            _LOG.warning("Failed querying CapabilityRegistry: %s", err)

        return []

    # ------------------------------------------------------------------
    # Intent Resolution & Skill Selection
    # ------------------------------------------------------------------

    def match_intent(
        self,
        intent: str,
        min_confidence: float = 0.4,
        override_capabilities: Optional[List[str]] = None,
    ) -> List[SkillMatch]:
        """Find matching skills for an intent string, validating capability availability.

        Parameters
        ----------
        intent : str
            User intent or action request.
        min_confidence : float
            Minimum match confidence score (0.0 to 1.0).
        override_capabilities : Optional[List[str]]
            Optional explicit capabilities list overriding CapabilityRegistry.

        Returns
        -------
        List[SkillMatch]
            Sorted candidate skill matches.
        """
        caps = override_capabilities
        if caps is None and self._capability_registry is not None:
            caps = self.get_available_capability_names()

        return self._registry.find_skill_by_intent(
            intent=intent,
            min_confidence=min_confidence,
            available_capabilities=caps,
        )

    def select_best_skill(
        self,
        intent: str,
        override_capabilities: Optional[List[str]] = None,
    ) -> Tuple[Optional[SkillMatch], List[SkillMatch]]:
        """Select single best executable skill match and candidate list."""
        candidates = self.match_intent(
            intent=intent,
            min_confidence=0.4,
            override_capabilities=override_capabilities,
        )
        if not candidates:
            return None, []

        # Top executable candidate
        for cand in candidates:
            if cand.is_executable:
                return cand, candidates

        return candidates[0], candidates

    # ------------------------------------------------------------------
    # Execution Handoff (Delegation to TaskEngine)
    # ------------------------------------------------------------------

    def dispatch_skill_execution(
        self,
        skill_or_id: Union[Skill, str],
        context_data: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepare skill execution package and hand over to TaskEngine.

        NOTE: Skill Engine NEVER executes the skill directly!

        Parameters
        ----------
        skill_or_id : Union[Skill, str]
            Skill object or skill ID string.
        context_data : Optional[Dict[str, Any]]
            Runtime variables / context parameters for execution.
        task_id : Optional[str]
            Optional custom task ID.

        Returns
        -------
        Dict[str, Any]
            Execution dispatch metadata including task_id, status, and task node info.
        """
        skill: Optional[Skill] = None
        if isinstance(skill_or_id, Skill):
            skill = skill_or_id
        else:
            skill = self._registry.get_skill(skill_or_id)

        if not skill:
            raise KeyError(f"Skill not found in registry: {skill_or_id}")

        # Capability readiness check
        if self._capability_registry is not None:
            active_caps = set(self.get_available_capability_names())
            missing = [c for c in skill.required_capabilities if c not in active_caps]
            if missing:
                _LOG.warning(
                    "Skill '%s' dispatched with unsatisfied capabilities: %s",
                    skill.id,
                    missing,
                )

        tid = task_id or f"task_skill_{skill.id.replace('.', '_')}_{uuid.uuid4().hex[:8]}"
        payload = {
            "task_id": tid,
            "skill_id": skill.id,
            "skill_name": skill.name,
            "category": skill.category,
            "executor": skill.executor,
            "verifier": skill.verifier,
            "rollback_support": skill.rollback_support,
            "estimated_duration": skill.estimated_duration,
            "context": context_data or {},
            "status": "QUEUED",
        }

        _LOG.info("Handing off skill '%s' to TaskEngine (task_id=%s)", skill.name, tid)

        # Handoff to Task Engine if attached
        if self._task_engine is not None:
            try:
                # Check Task Engine methods
                if hasattr(self._task_engine, "submit_task"):
                    self._task_engine.submit_task(
                        task_id=tid,
                        action_type=skill.id,
                        params=payload,
                    )
                elif hasattr(self._task_engine, "execute_task"):
                    self._task_engine.execute_task(payload)
                payload["status"] = "HANDED_OFF"
            except Exception as err:
                _LOG.error("Failed submitting task to TaskEngine: %s", err)
                payload["status"] = "HANDOFF_FAILED"
                payload["error"] = str(err)
        else:
            _LOG.info("No active TaskEngine attached; task packaged for deferred execution.")
            payload["status"] = "PACKAGED_DEFERRED"

        if self._event_bus:
            try:
                if hasattr(self._event_bus, "publish"):
                    self._event_bus.publish(
                        "SKILL_DISPATCHED",
                        {"task_id": tid, "skill_id": skill.id, "status": payload["status"]},
                    )
                elif hasattr(self._event_bus, "emit"):
                    res = self._event_bus.emit(
                        "SKILL_DISPATCHED",
                        {"task_id": tid, "skill_id": skill.id, "status": payload["status"]},
                    )
                    if hasattr(res, "__await__"):
                        try:
                            import asyncio
                            loop = asyncio.get_running_loop()
                            loop.create_task(res)
                        except RuntimeError:
                            pass
            except Exception as err:
                _LOG.warning("Failed publishing SKILL_DISPATCHED event: %s", err)

        return payload
