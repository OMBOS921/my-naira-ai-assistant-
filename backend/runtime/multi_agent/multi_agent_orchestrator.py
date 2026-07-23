"""
MultiAgentOrchestrator — Sequential multi-agent task execution orchestrator.

Delegates sub-tasks sequentially to the SAME LLM with specialized system prompts.
Runs smoothly on resource-constrained hardware (i3 6th gen / 4GB RAM).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.runtime.multi_agent._agent_definitions import (
    BUILTIN_AGENTS,
    AgentPersona,
)
from backend.types import Message

_LOG = logging.getLogger("naira.runtime.multi_agent")


class MultiAgentOrchestrator:
    """Orchestrates multi-agent sub-task delegation sequentially using prompt personas."""

    def __init__(
        self,
        *,
        runtime_manager: Any,
        tool_manager: Any | None = None,
        logger: logging.Logger | None = None,
        max_agents_per_request: int = 4,
    ) -> None:
        self._runtime_manager = runtime_manager
        self._tool_manager = tool_manager
        self._logger = logger or _LOG
        self._max_agents_per_request = max_agents_per_request
        self._agents: dict[str, AgentPersona] = dict(BUILTIN_AGENTS)

    def register_custom_agent(self, agent: AgentPersona) -> None:
        """Register a custom agent persona."""
        self._agents[agent.role] = agent
        self._logger.info("Registered custom agent persona: '%s' (%s)", agent.name, agent.role)

    def should_use_multi_agent(self, user_request: str) -> bool:
        """Heuristic check if request requires multi-agent sequential breakdown."""
        req_lower = user_request.lower()

        keywords = [
            "build a",
            "create project",
            "research and code",
            "analyze and implement",
            "multi-step",
            "full stack",
            "design and develop",
        ]
        for kw in keywords:
            if kw in req_lower:
                return True

        if len(user_request) > 250:
            return True

        return False

    def _match_agent_for_subtask(self, subtask: str) -> str:
        """Match sub-task text to appropriate agent persona key."""
        st_lower = subtask.lower()

        if any(k in st_lower for k in ["code", "script", "python", "func", "debug", "class", "program"]):
            return "coder"

        if any(k in st_lower for k in ["search", "find", "research", "read", "fetch", "document", "summarize"]):
            return "researcher"

        if any(k in st_lower for k in ["run", "execute", "file", "command", "create file", "write file"]):
            return "executor"

        return "executor"

    async def execute_multi_agent(
        self,
        user_request: str,
        session_id: str = "default",
    ) -> dict[str, Any]:
        """Execute request using PLAN -> ASSIGN -> EXECUTE (Sequential) -> SYNTHESIS."""
        self._logger.info("Starting multi-agent execution for request: %r", user_request)

        llm_manager = getattr(self._runtime_manager, "_llm_manager", None)
        if llm_manager is None or not hasattr(llm_manager, "generate"):
            self._logger.warning("LLMManager not available; degrading multi-agent execution")
            return {
                "success": False,
                "error": "LLM manager unavailable",
                "result": "Multi-agent execution disabled or unavailable.",
            }

        try:
            # 1. PLAN PHASE
            planner = self._agents.get("planner", BUILTIN_AGENTS["planner"])
            plan_prompt = f"{planner.system_prompt}\nUser Request: {user_request}\nBreak this into up to {self._max_agents_per_request} sub-tasks as a JSON array of strings."

            plan_res = await llm_manager.generate(
                prompt=plan_prompt,
                context=[Message(role="user", content=user_request)],
            )

            subtasks = self._parse_subtasks(plan_res.text or "")
            if not subtasks:
                subtasks = [user_request]

            subtasks = subtasks[: self._max_agents_per_request]
            self._logger.info("Planned %d subtask(s): %s", len(subtasks), subtasks)

            # 2. EXECUTE PHASE (Sequentially)
            subtask_results: list[dict[str, Any]] = []
            accumulated_context: list[str] = []

            for idx, subtask in enumerate(subtasks, start=1):
                role = self._match_agent_for_subtask(subtask)
                persona = self._agents.get(role, self._agents.get("executor", BUILTIN_AGENTS["executor"]))

                self._logger.info("Executing subtask %d/%d with agent '%s': %s", idx, len(subtasks), persona.name, subtask)

                context_str = "\n".join(accumulated_context)
                step_prompt = (
                    f"{persona.system_prompt}\n"
                    f"Previous Subtask Outputs:\n{context_str if context_str else 'None'}\n\n"
                    f"Current Subtask: {subtask}"
                )

                exec_res = await llm_manager.generate(
                    prompt=step_prompt,
                    context=[Message(role="user", content=subtask)],
                )

                output_text = exec_res.text or "Subtask completed."
                accumulated_context.append(f"[Subtask {idx} - {persona.name}]: {output_text}")

                subtask_results.append({
                    "step": idx,
                    "agent": persona.name,
                    "role": persona.role,
                    "subtask": subtask,
                    "result": output_text,
                })

            # 3. SYNTHESIS PHASE
            synthesis_prompt = (
                "You are an executive synthesizer. Combine the following subtask execution results "
                "into a comprehensive, clear, final response for the user.\n\n"
                f"Original Request: {user_request}\n\n"
                f"Execution Results:\n" + "\n\n".join(accumulated_context)
            )

            synth_res = await llm_manager.generate(
                prompt=synthesis_prompt,
                context=[Message(role="user", content="Synthesize final answer")],
            )

            final_result = synth_res.text or "Execution completed."

            return {
                "success": True,
                "result": final_result,
                "subtasks": subtask_results,
                "agents_used": [r["agent"] for r in subtask_results],
            }

        except Exception as exc:
            self._logger.error("Multi-agent execution error: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "result": f"Multi-agent execution failed: {exc}",
            }

    def _parse_subtasks(self, text: str) -> list[str]:
        """Extract subtask strings from LLM output."""
        text = text.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                items = json.loads(text[start : end + 1])
                if isinstance(items, list):
                    return [str(item) for item in items if item]
            except Exception:
                pass

        lines = [line.strip("- *1234567890.") for line in text.splitlines() if line.strip()]
        return [line for line in lines if line]
