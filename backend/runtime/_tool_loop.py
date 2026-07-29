from __future__ import annotations

import logging

from backend.exceptions import ModuleDegradedError
from backend.types import LLMResponse, Message, ToolCall, ToolDef, ToolResult

_LOG = logging.getLogger("naira.runtime.tool_loop")

MAX_TOOL_ITERATIONS: int = 10


class ToolExecutionError(Exception):
    """Raised when tool execution fails in a non-recoverable way."""


import json
import re
import uuid

_MANDATE_INSTRUCTION = (
    "\n\n[MANDATORY TOOL EXECUTION INSTRUCTIONS]:\n"
    "You are an autonomous AI agent with tool execution capabilities.\n"
    "DO NOT output Python code in standard Markdown blocks if you intend to run it. You MUST use the `execute_local_python` tool.\n"
    "You are an autonomous agent; do NOT ask for user permission before executing tools; invoke all required tool calls immediately and autonomously.\n"
    "Never say 'I am executing this now' without physically emitting the tool call."
)


def _extract_fallback_tool_calls(
    text: str,
    tool_defs: list[ToolDef],
) -> list[ToolCall] | None:
    """Extract tool calls from response text if LLM did not emit native tool_calls."""
    if not text or not tool_defs:
        return None

    available_tool_names = {t.name for t in tool_defs}
    tool_calls: list[ToolCall] = []

    # 1. Try to extract JSON tool call objects
    json_blocks = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                tool_name = data.get("tool") or data.get("name") or data.get("action") or ""
                args = data.get("arguments") or data.get("args") or data.get("action_input") or {}
                if tool_name in available_tool_names:
                    tool_calls.append(
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            name=str(tool_name),
                            arguments=args if isinstance(args, dict) else {"input": str(args)},
                        )
                    )
        except Exception:
            pass

    if tool_calls:
        return tool_calls

    # 2. Extract python code blocks if execute_local_python is available
    if "execute_local_python" in available_tool_names or any(t.name in ("execute_local_python", "execute_script") for t in tool_defs):
        py_match = re.search(r"```(?:python|py)\s*\n([\s\S]+?)\s*```", text, re.IGNORECASE)
        if py_match:
            code_str = py_match.group(1).strip()
            if code_str:
                tool_name = "execute_local_python" if "execute_local_python" in available_tool_names else "execute_script"
                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name=tool_name,
                        arguments={"script_code": code_str},
                    )
                )
                return tool_calls

    return None


async def run_tool_loop(
    llm_manager: object,
    tool_manager: object,
    system_prompt: str,
    context_messages: list[Message],
    tool_defs: list[ToolDef],
) -> LLMResponse:
    """Execute tool calls iteratively up to MAX_TOOL_ITERATIONS and return final response.

    Passes tool results back into context_messages so the LLM receives full output context.
    """
    total_token_usage = None
    last_provider = "llm"
    last_duration_ms = 0.0

    eff_system_prompt = system_prompt
    if tool_defs and _MANDATE_INSTRUCTION not in eff_system_prompt:
        eff_system_prompt += _MANDATE_INSTRUCTION

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
        response = await llm_manager.generate(
            prompt=eff_system_prompt,
            context=context_messages,
            tools=tool_defs if tool_defs else None,
        )

        last_provider = response.provider
        last_duration_ms += response.duration_ms

        active_tool_calls = response.tool_calls or _extract_fallback_tool_calls(response.text or "", tool_defs)

        if not active_tool_calls:
            return response

        _LOG.info(
            "Tool call iteration %d/%d detected (%d call(s))",
            iteration,
            MAX_TOOL_ITERATIONS,
            len(active_tool_calls),
        )

        assistant_msg = Message(
            role="assistant",
            content=response.text or "",
            tool_calls=active_tool_calls,
        )
        context_messages.append(assistant_msg)

        tool_messages = await _execute_tool_calls(tool_manager, active_tool_calls)
        context_messages.extend(tool_messages)

        # Perform final conversational synthesis pass after tool execution
        synthesis_prompt = eff_system_prompt + (
            "\n\n[SYSTEM INSTRUCTION]: Now that the tools have executed, provide a natural, "
            "conversational, and concise reply to the user based on the results. "
            "Do NOT output technical logs or 'plan executed' messages."
        )
        final_response = await llm_manager.generate(
            prompt=synthesis_prompt,
            context=context_messages,
            tools=None,
        )
        return final_response

    return response


async def _execute_tool_calls(
    tool_manager: object,
    tool_calls: list[ToolCall],
) -> list[Message]:
    """Execute a batch of tool calls and return result messages.

    Each tool result is wrapped in a ``Message`` with role ``"tool"``.
    """
    messages: list[Message] = []
    for tc in tool_calls:
        try:
            result: ToolResult = await tool_manager.execute_tool_call(tc)
            content = result.output or result.error or ""
        except ModuleDegradedError:
            _LOG.error("Tool manager degraded while executing '%s'", tc.name)
            content = "Error: tool system is unavailable"
        except Exception as exc:
            _LOG.error("Unexpected error executing tool '%s': %s", tc.name, exc)
            content = f"Error: {exc}"

        messages.append(
            Message(
                role="tool",
                content=content,
                tool_call_id=tc.id,
            )
        )
    return messages
