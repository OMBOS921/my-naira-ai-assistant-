from __future__ import annotations

import logging

from backend.exceptions import ModuleDegradedError
from backend.types import LLMResponse, Message, ToolCall, ToolDef, ToolResult

_LOG = logging.getLogger("naira.runtime.tool_loop")

MAX_TOOL_ITERATIONS: int = 10


class ToolExecutionError(Exception):
    """Raised when tool execution fails in a non-recoverable way."""


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

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
        response = await llm_manager.generate(
            prompt=system_prompt,
            context=context_messages,
            tools=tool_defs if tool_defs else None,
        )

        last_provider = response.provider
        last_duration_ms += response.duration_ms

        if not response.tool_calls:
            return response

        _LOG.info(
            "Tool call iteration %d/%d detected (%d call(s))",
            iteration,
            MAX_TOOL_ITERATIONS,
            len(response.tool_calls),
        )

        assistant_msg = Message(
            role="assistant",
            content=response.text or "",
            tool_calls=response.tool_calls,
        )
        context_messages.append(assistant_msg)

        tool_messages = await _execute_tool_calls(tool_manager, response.tool_calls)
        context_messages.extend(tool_messages)

        # If last iteration reached, break and do final generation without tools to close loop
        if iteration == MAX_TOOL_ITERATIONS:
            final_response = await llm_manager.generate(
                prompt=system_prompt,
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
