"""
Unit and Integration tests for Project Jarvis Architecture Upgrades.

Tests:
1. UserRequest & UserResponse dataclass timestamp/duration defaults.
2. Response Caching (LLMResponseCache) with TTL and <50ms hit performance.
3. ProactiveWatchdog monitoring & WebSocket broadcasting.
4. PC Control tool registrations & execution.
5. ReasoningGateway & RuntimeManager CodingAgent TDD loop routing.
"""

import asyncio
import time
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.types import UserRequest, UserResponse, LLMResponse, TokenUsage, Message
from backend.modules.llm._response_cache import LLMResponseCache
from backend.modules.llm.llm_module import LLMManager
from backend.runtime.proactive_watchdog import ProactiveWatchdog
from backend.modules.pc_control.pc_control_module import PCControlManager
from backend.modules.reasoning_gateway.gateway import ReasoningGateway
from backend.modules.reasoning_gateway.gateway_types import IntentCategory
from backend.runtime._runtime_manager import RuntimeManager


@pytest.mark.asyncio
async def test_user_request_timestamp_default():
    """Verify UserRequest can be instantiated without explicit timestamp argument."""
    req = UserRequest(
        id=uuid.uuid4(),
        source="websocket",
        text="test query",
        session_id="s1",
    )
    assert req.timestamp > 0.0

    res = UserResponse(
        request_id=req.id,
        text="test response",
        source="websocket",
    )
    assert res.duration_ms == 0.0


@pytest.mark.asyncio
async def test_response_cache_hit_and_miss():
    """Verify LLMResponseCache stores and retrieves identical queries within TTL."""
    cache = LLMResponseCache(max_size=10, ttl_seconds=5.0)

    prompt = "what is the system status?"
    context = [Message(role="user", content=prompt)]

    # Initial get (miss)
    assert cache.get(prompt, context) is None

    # Put response
    original_resp = LLMResponse(
        text="System status is optimal.",
        tool_calls=None,
        finish_reason="stop",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        provider="gemini",
        duration_ms=450.0,
    )
    cache.put(prompt, context, None, original_resp)

    # Subsequent get (hit)
    cached_resp = cache.get(prompt, context)
    assert cached_resp is not None
    assert cached_resp.text == "System status is optimal."
    assert cached_resp.provider == "cache"
    assert cached_resp.duration_ms < 50.0


@pytest.mark.asyncio
async def test_proactive_watchdog_broadcast():
    """Verify ProactiveWatchdog detects threshold breach and broadcasts to WS."""
    mock_ws = AsyncMock()
    websockets = {mock_ws}

    watchdog = ProactiveWatchdog(
        active_websockets=websockets,
        check_interval=0.1,
        cpu_threshold=0.0,  # Force alert
        memory_threshold=0.0,
    )

    await watchdog.check_and_notify()
    assert mock_ws.send_json.called
    sent_payload = mock_ws.send_json.call_args[0][0]
    assert sent_payload["sender"] == "naira"
    assert sent_payload["proactive"] is True


@pytest.mark.asyncio
async def test_pc_control_alias_tools_registration():
    """Verify GUI automation tools are registered in PCControlManager."""
    mock_tool_mgr = MagicMock()
    pc_mgr = PCControlManager(tool_manager=mock_tool_mgr)

    await pc_mgr.async_init()
    assert mock_tool_mgr.register_tool.called
    registered_names = [call.args[0].name for call in mock_tool_mgr.register_tool.call_args_list]

    assert "pc_mouse" in registered_names
    assert "mouse_click" in registered_names
    assert "keyboard_type" in registered_names
    assert "window_focus" in registered_names


@pytest.mark.asyncio
async def test_coding_agent_routing_in_runtime():
    """Verify RuntimeManager routes CODING intent to CodingAgentManager."""
    mock_reasoning_gw = MagicMock()
    mock_decision = MagicMock()
    mock_decision.category = IntentCategory.CODING
    mock_decision.llm_required = True
    mock_decision.complexity_score = 80
    mock_decision.reasoning = "Coding intent detected"
    mock_reasoning_gw.evaluate.return_value = mock_decision

    mock_coding_agent = AsyncMock()
    mock_coding_agent.execute_task.return_value = MagicMock(
        status="success",
        output="Successfully wrote and tested script using TDD loop.",
        error=None,
    )

    runtime_mgr = RuntimeManager(
        reasoning_gateway=mock_reasoning_gw,
        coding_agent_manager=mock_coding_agent,
    )
    await runtime_mgr.async_init()

    req = UserRequest(
        id=uuid.uuid4(),
        source="websocket",
        text="Write a python script to calculate fibonacci numbers",
        session_id="test_session",
    )

    user_resp = await runtime_mgr.process_request(req)
    assert mock_coding_agent.execute_task.called
    assert "fibonacci" in mock_coding_agent.execute_task.call_args[0][0]
    assert "TDD loop" in user_resp.text
