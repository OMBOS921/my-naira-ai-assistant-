"""
Bounded Proactive Behavior Workflow for NairaLLM.

Implements safe, bounded autonomy levels (0 to 5) for event-triggered notifications and safe actions.
"""

from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any

from backend.types import Message, ToolResult
from NairaLLM.integration.adapter.naira_llm_adapter import NairaLLMAdapter

_LOG = logging.getLogger("nairallm.proactive_workflow")


class AutonomyLevel(IntEnum):
    LEVEL_0_INFORM = 0
    LEVEL_1_SUGGEST = 1
    LEVEL_2_CONFIRM = 2
    LEVEL_3_LOW_RISK_EXECUTE = 3
    LEVEL_4_APPROVED_MULTI_STEP = 4
    LEVEL_5_BOUNDED_AUTOMATION = 5


class BoundedProactiveWorkflow:
    """Manages proactive event evaluation and bounded execution policy."""

    def __init__(self, adapter: NairaLLMAdapter, max_allowed_autonomy: AutonomyLevel = AutonomyLevel.LEVEL_2_CONFIRM) -> None:
        self.adapter = adapter
        self.max_allowed_autonomy = max_allowed_autonomy

    async def handle_system_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        required_level: AutonomyLevel = AutonomyLevel.LEVEL_2_CONFIRM,
    ) -> dict[str, Any]:
        """Evaluate an inbound system event and generate appropriate bounded response."""
        system_prompt = (
            "You are Naira. A background event occurred on the user's system. "
            "Evaluate its urgency and provide a helpful, polite notification. "
            "If action is recommended at Level 2+, ask the user for confirmation first."
        )

        event_desc = f"[EVENT: {event_type}] Details: {event_data}"
        messages = [
            Message(role="system", content=event_desc)
        ]

        resp = await self.adapter.generate(
            system_prompt=system_prompt,
            messages=messages,
        )

        requires_user_confirmation = required_level >= AutonomyLevel.LEVEL_2_CONFIRM

        return {
            "event_type": event_type,
            "autonomy_level": int(required_level),
            "requires_confirmation": requires_user_confirmation,
            "message_text": resp.text,
            "proposed_tool_calls": resp.tool_calls,
        }
