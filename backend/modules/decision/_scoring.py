"""
Pure scoring functions for candidate route evaluation.

21_System_Contracts.md §4.2 — Scoring and routing rules.
"""

from __future__ import annotations

import re
from typing import Any

from backend.modules.decision._routes import RouteDecision, RouteTarget

_CODING_PATTERNS = re.compile(
    r"\b(?:refactor|fix bug|create function|write script|debug|code|"
    r"git commit|pip install|pytest)\b",
    re.IGNORECASE,
)


def score_route(
    request: str,
    context: dict[str, Any] | None = None,
    analytics: object | None = None,
    fast_command_router: object | None = None,
    planning_manager: object | None = None,
    coding_agent_manager: object | None = None,
) -> RouteDecision:
    """Pure scoring function to decide the target subsystem route for a request.

    Evaluates FCR matches, analytics feedback, multi-step heuristics,
    and coding agent capabilities without making LLM calls.
    """
    req_text = request.strip()
    if not req_text:
        return RouteDecision(
            target=RouteTarget.LLM_CONVERSATION,
            confidence=1.0,
            reason="Empty request default fallback",
        )

    # 1. Check FastCommandRouter match
    if fast_command_router is not None:
        is_fast_fn = getattr(fast_command_router, "is_fast_command", None)
        if callable(is_fast_fn) and is_fast_fn(req_text):
            # Check analytics demotion rule if analytics is available and non-degraded
            if analytics is not None and not getattr(analytics, "degraded", False):
                rate_fn = getattr(analytics, "get_intent_success_rate", None)
                if callable(rate_fn):
                    intent_rate = rate_fn(req_text)
                    if intent_rate < 0.5:
                        return RouteDecision(
                            target=RouteTarget.LLM_CONVERSATION,
                            confidence=0.7,
                            reason=(
                                f"FCR matched but demoted due to low analytics success rate "
                                f"({intent_rate:.2f})"
                            ),
                        )

            return RouteDecision(
                target=RouteTarget.FAST_COMMAND_ROUTER,
                confidence=0.95,
                reason="FastCommandRouter matched deterministic desktop command",
            )

    # 2. Check Planning Engine multi-step heuristic
    if planning_manager is not None:
        is_multi_fn = getattr(planning_manager, "is_multi_step", None)
        if callable(is_multi_fn) and is_multi_fn(req_text):
            return RouteDecision(
                target=RouteTarget.PLANNING_ENGINE,
                confidence=0.9,
                reason="PlanningEngine detected multi-step intent structure",
            )
    elif re.search(r"\b(?:and then|then|phir|uske baad|aur)\b", req_text, re.IGNORECASE):
        return RouteDecision(
            target=RouteTarget.PLANNING_ENGINE,
            confidence=0.85,
            reason="Static rule detected multi-step intent structure",
        )

    # 3. Check Coding Agent skill/project patterns
    if _CODING_PATTERNS.search(req_text):
        return RouteDecision(
            target=RouteTarget.CODING_AGENT,
            confidence=0.85,
            reason="Coding agent domain pattern matched",
        )

    # 4. Default fallback to LLM conversation
    return RouteDecision(
        target=RouteTarget.LLM_CONVERSATION,
        confidence=1.0,
        reason="Default LLM conversation path",
    )
