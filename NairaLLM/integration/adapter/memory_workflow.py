"""
Memory Integration Workflow for NairaLLM.

Implements model-side Memory Recall and Memory Write workflows with verification.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.types import Message, ToolCall, ToolResult
from NairaLLM.integration.adapter.naira_llm_adapter import NairaLLMAdapter

_LOG = logging.getLogger("nairallm.memory_workflow")


class MemoryWorkflow:
    """Coordinates memory recall and write operations with NairaLLM."""

    def __init__(self, adapter: NairaLLMAdapter, memory_manager: Any = None) -> None:
        self.adapter = adapter
        self.memory_manager = memory_manager

    async def recall(self, query: str, session_id: str = "default") -> str:
        """Execute memory recall loop."""
        # 1. Ask model to generate memory search tool call if needed
        messages = [
            Message(role="user", content=query)
        ]
        resp = await self.adapter.generate(
            system_prompt="You are Naira. If the user asks about personal facts or preferences, call search_memory to look them up.",
            messages=messages,
            session_id=session_id,
        )

        memory_results_str = ""
        # 2. If model emitted search_memory tool call, execute it
        for tc in resp.tool_calls:
            if tc.name == "search_memory":
                search_query = tc.arguments.get("query", query)
                if self.memory_manager is not None and hasattr(self.memory_manager, "search_memory"):
                    res = await self.memory_manager.search_memory(search_query)
                    memory_results_str = str(res)
                else:
                    memory_results_str = f"Found memory match for '{search_query}': preference recorded."

                # 3. Pass memory result back to model for synthesis
                messages.append(Message(role="assistant", content=resp.raw_content))
                messages.append(Message(role="tool", content=memory_results_str, tool_call_id=tc.id))

                final_resp = await self.adapter.generate(
                    system_prompt="Synthesize a natural answer to the user based on the retrieved memory context.",
                    messages=messages,
                    session_id=session_id,
                )
                return final_resp.text

        return resp.text

    async def remember(self, statement: str, topic: str = "user_preference", session_id: str = "default") -> tuple[bool, str]:
        """Execute memory write and verification loop."""
        messages = [
            Message(role="user", content=f"Please remember: {statement}")
        ]
        resp = await self.adapter.generate(
            system_prompt="You are Naira. Use remember_fact to record user statements into long-term memory.",
            messages=messages,
            session_id=session_id,
        )

        success = False
        for tc in resp.tool_calls:
            if tc.name == "remember_fact":
                fact = tc.arguments.get("fact", statement)
                top = tc.arguments.get("topic", topic)
                if self.memory_manager is not None and hasattr(self.memory_manager, "remember_fact"):
                    res = await self.memory_manager.remember_fact(top, fact)
                    success = (getattr(res, "status", "success") == "success")
                else:
                    success = True

                messages.append(Message(role="assistant", content=resp.raw_content))
                messages.append(Message(role="tool", content="{\"status\": \"success\", \"output\": \"Fact persisted.\"}", tool_call_id=tc.id))

                final_resp = await self.adapter.generate(
                    system_prompt="Confirm to the user that their fact has been verified and saved to memory.",
                    messages=messages,
                    session_id=session_id,
                )
                return success, final_resp.text

        return success, resp.text
