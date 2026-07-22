"""
DecisionManager — central public manager for the decision engine.

21_System_Contracts.md §4.2 — ModuleInterface protocol.
18_Boot_Sequence.md §2 — Boot sequence.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modules.decision._routes import RouteDecision, RouteTarget
from backend.modules.decision._scoring import score_route

_LOG = logging.getLogger("naira.decision")


class DecisionManager:
    """Central decision manager — decides which subsystem handles incoming user requests.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration.
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        Event bus instance.
    analytics : object | None
        AnalyticsManager instance (optional).
    fast_command_router : object | None
        FastCommandRouter instance (optional).
    planning_manager : object | None
        PlanningManager instance (optional).
    coding_agent_manager : object | None
        CodingAgentManager instance (optional).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        analytics: object | None = None,
        fast_command_router: object | None = None,
        planning_manager: object | None = None,
        coding_agent_manager: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._analytics = analytics
        self._fast_command_router = fast_command_router
        self._planning_manager = planning_manager
        self._coding_agent_manager = coding_agent_manager
        self._degraded: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise DecisionManager resources."""
        self._logger.info("DecisionManager initialised")

    async def async_shutdown(self) -> None:
        """Shut down DecisionManager resources."""
        self._degraded = False
        self._logger.info("DecisionManager shut down")

    def degrade(self) -> None:
        """Mark DecisionManager as degraded."""
        self._degraded = True
        self._logger.warning("DecisionManager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decide(
        self, request: str, context: dict[str, Any] | None = None
    ) -> RouteDecision:
        """Decide target subsystem route for an inbound request.

        Gracefully falls back to static routing logic if analytics is None or degraded.
        """
        if self._degraded:
            return RouteDecision(
                target=RouteTarget.LLM_CONVERSATION,
                confidence=1.0,
                reason="DecisionManager is degraded; using safe default fallback",
            )

        # Check analytics availability
        effective_analytics = self._analytics
        if self._analytics is not None and getattr(self._analytics, "degraded", False):
            self._logger.debug("AnalyticsManager is degraded; skipping dynamic demotion")
            effective_analytics = None

        return score_route(
            request=request,
            context=context,
            analytics=effective_analytics,
            fast_command_router=self._fast_command_router,
            planning_manager=self._planning_manager,
            coding_agent_manager=self._coding_agent_manager,
        )
