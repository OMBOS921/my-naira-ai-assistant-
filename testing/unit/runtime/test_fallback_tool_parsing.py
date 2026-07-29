"""
Unit tests for Fallback Tool Call Extraction and OpenCode Zen Tool Calling Mandate.
"""

from __future__ import annotations

import pytest
from backend.types import LLMResponse, Message, ToolCall, ToolDef
from backend.runtime._tool_loop import _extract_fallback_tool_calls, run_tool_loop
from backend.modules.llm.providers.deepseek_provider import extract_tool_calls_from_text, DeepSeekProvider


@pytest.mark.unit
def test_extract_fallback_python_block():
    tools = [
        ToolDef(
            name="execute_local_python",
            description="Run python script",
            parameters={"type": "object", "properties": {"script_code": {"type": "string"}}},
        )
    ]
    text = "I am running the script now:\n```python\nprint('Hello from Naira')\n```"
    calls = _extract_fallback_tool_calls(text, tools)

    assert calls is not None
    assert len(calls) == 1
    assert calls[0].name == "execute_local_python"
    assert calls[0].arguments == {"script_code": "print('Hello from Naira')"}


@pytest.mark.unit
def test_extract_fallback_json_tool_block():
    tools = [
        ToolDef(
            name="execute_local_python",
            description="Run python script",
            parameters={"type": "object", "properties": {"script_code": {"type": "string"}}},
        )
    ]
    text = (
        "Executing tool:\n```json\n"
        "{\n"
        '  "tool": "execute_local_python",\n'
        '  "arguments": {\n'
        '    "script_code": "x = 10\\nprint(x)"\n'
        "  }\n"
        "}\n```"
    )
    calls = _extract_fallback_tool_calls(text, tools)

    assert calls is not None
    assert len(calls) == 1
    assert calls[0].name == "execute_local_python"
    assert calls[0].arguments == {"script_code": "x = 10\nprint(x)"}


@pytest.mark.unit
def test_deepseek_provider_text_extraction():
    tools = [
        ToolDef(
            name="execute_local_python",
            description="Run python script",
            parameters={"type": "object", "properties": {"script_code": {"type": "string"}}},
        )
    ]
    text = "Writing script with NameError:\n```python\nprint(undefined_var)\n```"
    calls, finish_reason = extract_tool_calls_from_text(text, tools)

    assert calls is not None
    assert finish_reason == "tool_calls"
    assert len(calls) == 1
    assert calls[0].name == "execute_local_python"
    assert calls[0].arguments == {"script_code": "print(undefined_var)"}


class DummyLLMManager:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt: str, context: list[Message], tools: list[ToolDef] | None = None) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            # First turn: returns text with python code block, no native tool_calls
            return LLMResponse(
                text="Writing script:\n```python\nprint(undefined_variable)\n```",
                tool_calls=None,
                finish_reason="stop",
                token_usage=None,
                provider="deepseek",
                duration_ms=10.0,
            )
        else:
            # Second turn (after tool result): final summary
            return LLMResponse(
                text="Fixed and executed successfully.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=None,
                provider="deepseek",
                duration_ms=5.0,
            )


class DummyToolManager:
    async def execute_tool_call(self, tool_call: ToolCall):
        from backend.types import ToolResult
        return ToolResult(
            status="error",
            output="NameError: name 'undefined_variable' is not defined",
            error="NameError: name 'undefined_variable' is not defined",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_tool_loop_with_text_fallback():
    llm = DummyLLMManager()
    tool_mgr = DummyToolManager()
    tools = [
        ToolDef(
            name="execute_local_python",
            description="Run python script",
            parameters={"type": "object", "properties": {"script_code": {"type": "string"}}},
        )
    ]
    messages = [Message(role="user", content="Write a script with a NameError and run it")]

    resp = await run_tool_loop(
        llm_manager=llm,
        tool_manager=tool_mgr,
        system_prompt="System prompt",
        context_messages=messages,
        tool_defs=tools,
    )

    assert resp is not None
    assert llm.calls == 2
    # Verify that tool result was added to context
    tool_msgs = [m for m in messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "NameError" in tool_msgs[0].content
