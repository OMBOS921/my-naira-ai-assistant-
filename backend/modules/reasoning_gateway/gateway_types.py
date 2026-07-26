"""
Reasoning Gateway types and decision containers.

Defines the IntentCategory enum and ReasoningGatewayDecision dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IntentCategory(StrEnum):
    """Intent category evaluated by the Reasoning Gateway."""

    GREETING = "GREETING"
    MEMORY_RECALL = "MEMORY_RECALL"
    WEB_SEARCH = "WEB_SEARCH"
    CLARIFICATION = "CLARIFICATION"
    REASONING = "REASONING"
    PLANNING = "PLANNING"
    CODING = "CODING"
    CREATIVE_WRITING = "CREATIVE_WRITING"
    COMPLEX_ANALYSIS = "COMPLEX_ANALYSIS"
    LOCAL_CAPABILITY = "LOCAL_CAPABILITY"


@dataclass
class ReasoningGatewayDecision:
    """Structured decision object produced by the Reasoning Gateway.

    Controls whether the request proceeds to an expensive LLM invocation
    or is answered via deterministic memory, web search summary, local capability,
    or clarification prompt.
    """

    category: IntentCategory | str
    complexity_score: int  # 0 to 100
    llm_required: bool
    memory_lookup: bool
    web_search_only: bool
    planning_required: bool
    clarification_required: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    ambiguity_level: float = 0.0  # 0.0 to 1.0
    memory_available: bool = False
    local_capability_available: bool = False
    web_search_sufficient: bool = False
    creativity_required: bool = False
    tool_required: bool = False
