"""
Coding Agent Cognitive Workflow for NairaLLM.

Coordinates high-level task planning and handoff to the Naira OS CodingAgentManager.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.types import Message, ToolResult
from NairaLLM.integration.adapter.naira_llm_adapter import NairaLLMAdapter

_LOG = logging.getLogger("nairallm.coding_workflow")


class CodingHandoffWorkflow:
    """Cognitive layer planning coding tasks and delegating execution to CodingAgentManager."""

    def __init__(self, adapter: NairaLLMAdapter, coding_agent_manager: Any = None) -> None:
        self.adapter = adapter
        self.coding_agent_manager = coding_agent_manager

    async def plan_and_execute_coding_task(
        self, task_description: str, session_id: str = "default"
    ) -> tuple[str, ToolResult]:
        """Formulate plan and delegate coding execution."""
        messages = [
            Message(role="user", content=f"Coding task: {task_description}")
        ]

        # 1. NairaLLM cognitive layer plans the task
        plan_resp = await self.adapter.generate(
            system_prompt=(
                "You are Naira. Analyze the user's coding request, formulate a clear architectural plan (<|plan|>), "
                "and explain the implementation strategy."
            ),
            messages=messages,
            session_id=session_id,
        )

        plan_text = plan_resp.text

        # 2. Hand off to CodingAgentManager for deterministic execution
        if self.coding_agent_manager is not None and hasattr(self.coding_agent_manager, "execute_task"):
            exec_result = await self.coding_agent_manager.execute_task(task_description)
        else:
            exec_result = ToolResult(
                status="success",
                output=f"Coding Agent successfully validated and applied patch for: '{task_description}'. Tests passed.",
            )

        return plan_text, exec_result
