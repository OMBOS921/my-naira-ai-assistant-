"""
Unit tests for NairaLLM Integration Adapter and Subsystem Workflows.
"""

from __future__ import annotations

import pytest
from backend.types import Message, ToolCall, ToolResult
from NairaLLM.integration.adapter.browser_workflow import BrowserResearchWorkflow
from NairaLLM.integration.adapter.coding_workflow import CodingHandoffWorkflow
from NairaLLM.integration.adapter.memory_workflow import MemoryWorkflow
from NairaLLM.integration.adapter.naira_llm_adapter import NairaLLMAdapter, NairaLLMResponse
from NairaLLM.integration.adapter.proactive_workflow import AutonomyLevel, BoundedProactiveWorkflow
from NairaLLM.model.runtime.naira_runtime import NairaRuntime


class MockRuntime:
    def __init__(self, canned_response: str) -> None:
        self.canned_response = canned_response

    def generate(self, prompt: str, **kwargs) -> str:
        return self.canned_response

    def extract_tool_calls(self, text: str) -> list[dict]:
        runtime = NairaRuntime(model=None)
        return runtime.extract_tool_calls(text)


@pytest.mark.asyncio
async def test_adapter_generation_and_tool_call() -> None:
    canned = '<|thought|>\nAdjust volume.\n<|tool_call|>\n{"name": "pc_system_settings", "arguments": {"setting": "volume", "value": 70}}'
    mock_rt = MockRuntime(canned)
    adapter = NairaLLMAdapter(runtime=mock_rt)

    resp = await adapter.generate(
        system_prompt="You are Naira.",
        messages=[Message(role="user", content="Set volume to 70%")],
    )

    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "pc_system_settings"
    assert resp.tool_calls[0].arguments["value"] == 70


@pytest.mark.asyncio
async def test_memory_workflow() -> None:
    canned_search = '<|tool_call|>\n{"name": "search_memory", "arguments": {"query": "favorite color"}}'
    mock_rt = MockRuntime(canned_search)
    adapter = NairaLLMAdapter(runtime=mock_rt)

    class MockMemoryManager:
        async def search_memory(self, query: str):
            return "Favorite color is teal."

    wf = MemoryWorkflow(adapter=adapter, memory_manager=MockMemoryManager())
    result = await wf.recall("What is my favorite color?")
    assert result is not None


@pytest.mark.asyncio
async def test_browser_workflow() -> None:
    canned_search = '<|tool_call|>\n{"name": "browser_search", "arguments": {"query": "Python 3.14 features"}}'
    mock_rt = MockRuntime(canned_search)
    adapter = NairaLLMAdapter(runtime=mock_rt)

    class MockBrowserManager:
        async def browser_search(self, query: str, max_results: int = 3):
            return ToolResult(status="success", output="Python 3.14 includes template strings and faster comprehensions.")

    wf = BrowserResearchWorkflow(adapter=adapter, browser_manager=MockBrowserManager())
    result = await wf.research("Python 3.14 features")
    assert result is not None


@pytest.mark.asyncio
async def test_coding_workflow() -> None:
    canned_plan = '<|plan|>\n1. Implement health check in backend/api/health.py\n2. Run tests'
    mock_rt = MockRuntime(canned_plan)
    adapter = NairaLLMAdapter(runtime=mock_rt)

    class MockCodingAgent:
        async def execute_task(self, task: str):
            return ToolResult(status="success", output="Created backend/api/health.py")

    wf = CodingHandoffWorkflow(adapter=adapter, coding_agent_manager=MockCodingAgent())
    plan, exec_res = await wf.plan_and_execute_coding_task("Add health endpoint")
    assert "backend/api/health.py" in plan
    assert exec_res.status == "success"


@pytest.mark.asyncio
async def test_proactive_workflow_level_2() -> None:
    canned_notif = "System memory is high (88%). Would you like me to close background tabs?"
    mock_rt = MockRuntime(canned_notif)
    adapter = NairaLLMAdapter(runtime=mock_rt)

    wf = BoundedProactiveWorkflow(adapter=adapter)
    res = await wf.handle_system_event(
        event_type="MEMORY_USAGE_HIGH",
        event_data={"ram_percent": 88},
        required_level=AutonomyLevel.LEVEL_2_CONFIRM,
    )
    assert res["requires_confirmation"] is True
    assert "88%" in res["message_text"]
