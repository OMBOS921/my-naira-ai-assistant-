"""
Reasoning Gateway module implementation.

Conforms to ``ModuleInterface`` (``backend/types.py``).
Sits between Fast Command Router (FCR) and LLM pipeline to optimize LLM token usage.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.modules.reasoning_gateway.evaluators import evaluate_request
from backend.modules.reasoning_gateway.gateway_types import (
    IntentCategory,
    ReasoningGatewayDecision,
)

_LOG = logging.getLogger("naira.reasoning_gateway")


class ReasoningGateway:
    """Reasoning Gateway — evaluates user requests to decide if LLM reasoning is required.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration.
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        Event bus instance.
    memory_manager : object | None
        MemoryManager instance (optional).
    tool_manager : object | None
        ToolManager instance (optional).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        memory_manager: object | None = None,
        tool_manager: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._memory_manager = memory_manager
        self._tool_manager = tool_manager
        self._degraded: bool = False
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise ReasoningGateway resources."""
        self._initialized = True
        self._logger.info("ReasoningGateway initialised")

    async def async_shutdown(self) -> None:
        """Shut down ReasoningGateway resources."""
        self._degraded = False
        self._initialized = False
        self._logger.info("ReasoningGateway shut down")

    def degrade(self) -> None:
        """Mark ReasoningGateway as degraded."""
        self._degraded = True
        self._logger.warning("ReasoningGateway marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self, request: str, context: dict[str, Any] | None = None
    ) -> ReasoningGatewayDecision:
        """Evaluate an inbound request to determine if LLM reasoning is required.

        If degraded, safely defaults to requiring LLM.
        """
        start_t = time.perf_counter()

        if self._degraded:
            return ReasoningGatewayDecision(
                category=IntentCategory.REASONING,
                complexity_score=50,
                llm_required=True,
                memory_lookup=False,
                web_search_only=False,
                planning_required=False,
                clarification_required=False,
                confidence=1.0,
                reasoning="ReasoningGateway is degraded; falling back to LLM execution.",
            )

        decision = evaluate_request(
            request_text=request,
            context=context,
            memory_manager=self._memory_manager,
            tool_manager=self._tool_manager,
        )

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        self._logger.debug(
            "[REASONING GATEWAY] Evaluated '%s' -> category=%s llm_required=%s elapsed=%.3fms",
            request, decision.category, decision.llm_required, elapsed_ms
        )

        return decision
