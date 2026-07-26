"""
Unit tests for main.py entrypoint request flow via Orchestrator and RuntimeManager.
"""

from __future__ import annotations

import pytest
import main
from backend.eventbus import EventBus
from backend.orchestrator import FSMState, Orchestrator
from backend.modules.settings import AppConfig, EnvironmentSnapshot
from backend.types import UserRequest, UserResponse


import time
import uuid

@pytest.mark.asyncio
async def test_orchestrator_process_user_request_delegation():
    """Verify Orchestrator transitions FSM states and delegates to registered runtime module."""
    event_bus = EventBus()
    config = AppConfig.load()
    env = EnvironmentSnapshot(naira_api_key="test_key")

    orchestrator = Orchestrator(event_bus=event_bus, config=config, env=env)
    orchestrator.state = FSMState.IDLE

    class MockRuntime:
        async def process_request(self, request: UserRequest) -> UserResponse:
            return UserResponse(
                request_id=request.id,
                text=f"Processed: {request.text}",
                source=request.source,
                duration_ms=10.0,
            )

    orchestrator.register_module("runtime", MockRuntime())

    req = UserRequest(
        id=uuid.uuid4(),
        source="websocket",
        text="Hello Naira",
        session_id="test_session",
        timestamp=time.time(),
    )
    res = await orchestrator.process_user_request(req)

    assert res.text == "Processed: Hello Naira"
    assert orchestrator.state == FSMState.IDLE


@pytest.mark.asyncio
async def test_main_process_user_input_uninitialized():
    """Verify process_user_input handles uninitialized orchestrator gracefully."""
    main._orchestrator = None
    res = await main.process_user_input("hello")
    assert "[System Error]" in res


@pytest.mark.asyncio
async def test_main_process_user_input_initialized():
    """Verify process_user_input delegates request to main._orchestrator."""
    event_bus = EventBus()
    config = AppConfig.load()
    env = EnvironmentSnapshot(naira_api_key="test_key")

    orchestrator = Orchestrator(event_bus=event_bus, config=config, env=env)
    orchestrator.state = FSMState.IDLE

    class MockRuntime:
        async def process_request(self, request: UserRequest) -> UserResponse:
            return UserResponse(
                request_id=request.id,
                text=f"Echo: {request.text}",
                source=request.source,
                duration_ms=10.0,
            )

    orchestrator.register_module("runtime", MockRuntime())
    main._orchestrator = orchestrator

    res = await main.process_user_input("wake up")
    assert res == "Echo: wake up"

    # Cleanup
    main._orchestrator = None
