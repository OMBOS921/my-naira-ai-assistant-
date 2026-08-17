"""Unit tests verifying Tool Call Visibility events (tool_execution_start & tool_execution_result)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.eventbus import EventBus
from backend.modules.tools import ToolDefinition, ToolManager
from backend.runtime.tool_router import ToolRouter
from backend.types import ToolCall
@pytest.mark.asyncio
async def test_tool_visibility_events_in_tool_manager() -> None:
    event_bus = EventBus()
    emitted_events: list[dict] = []

    async def _on_event(event: object) -> None:
        emitted_events.append({
            "type": getattr(event, "type", ""),
            "data": getattr(event, "data", {}),
        })

    event_bus.subscribe("tool_execution_start", _on_event)
    event_bus.subscribe("tool_execution_result", _on_event)

    tool_mgr = ToolManager(event_bus=event_bus)

    async def mock_python_handler(script_code: str) -> str:
        return f"Output of: {script_code}"

    tool_mgr.register_tool(
        ToolDefinition(
            name="execute_local_python",
            description="Execute Python code",
            parameters={"type": "object", "properties": {"script_code": {"type": "string"}}},
        ),
        mock_python_handler,
    )

    tc = ToolCall(id="call_1", name="execute_local_python", arguments={"script_code": "print('hello')"})\
    
    result = await tool_mgr.execute_tool_call(tc, context={"session_id": "test_sess"})

    assert result.status == "success"
    assert "hello" in result.output

    # Wait briefly for EventBus async dispatch
    await asyncio.sleep(0.1)

    event_types = [e["type"] for e in emitted_events]
    assert "tool_execution_start" in event_types
    assert "tool_execution_result" in event_types

    start_event = next(e for e in emitted_events if e["type"] == "tool_execution_start")
    assert start_event["data"]["tool"] == "execute_local_python"
    assert start_event["data"]["script_code"] == "print('hello')"
    assert "```python" in start_event["data"]["text"]

    result_event = next(e for e in emitted_events if e["type"] == "tool_execution_result")
    assert result_event["data"]["tool"] == "execute_local_python"
    assert "Output of: print('hello')" in result_event["data"]["output"]
    assert "```text" in result_event["data"]["text"]


@pytest.mark.asyncio
async def test_tool_visibility_events_in_tool_router() -> None:
    event_bus = EventBus()
    emitted_events: list[dict] = []

    async def _on_event(event: object) -> None:
        emitted_events.append({
            "type": getattr(event, "type", ""),
            "data": getattr(event, "data", {}),
        })

    event_bus.subscribe("tool_execution_start", _on_event)
    event_bus.subscribe("tool_execution_result", _on_event)

    tool_mgr = ToolManager(event_bus=event_bus)

    async def mock_python_handler(script_code: str) -> str:
        return "42"

    tool_mgr.register_tool(
        ToolDefinition(
            name="execute_local_python",
            description="Execute Python code",
            parameters={"type": "object", "properties": {"script_code": {"type": "string"}}},
        ),
        mock_python_handler,
    )

    router = ToolRouter(tool_manager=tool_mgr, event_bus=event_bus)

    tc = ToolCall(id="call_2", name="execute_local_python", arguments={"script_code": "print(42)"})
    messages = await router.execute_tool_calls([tc], session_id="test_sess_2")

    assert len(messages) == 1
    assert messages[0].content == "42"

    await asyncio.sleep(0.1)

    event_types = [e["type"] for e in emitted_events]
    assert "tool_execution_start" in event_types
    assert "tool_execution_result" in event_types

    start_event = next(e for e in emitted_events if e["type"] == "tool_execution_start")
    assert start_event["data"]["script_code"] == "print(42)"

    result_event = next(e for e in emitted_events if e["type"] == "tool_execution_result")
    assert result_event["data"]["output"] == "42"
