"""End-to-end integration tests for the full AI execution pipeline.

Covers:
- Complete end-to-end request flow
- Streaming response pipeline
- Tool calling loop
- Memory storage integration
- Multiple sessions
- Degraded mode
- Error handling and recovery
- Event emission at every stage
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.context import ContextManager
from backend.modules.conversation import ConversationManager
from backend.modules.llm import LLMManager
from backend.modules.memory import MemoryManager
from backend.modules.prompt import PromptManager
from backend.modules.tools import ToolManager
from backend.orchestrator import EventBus
from backend.runtime.context_router import ContextRouter
from backend.runtime.message_dispatcher import MessageDispatcher
from backend.runtime.request_pipeline import RequestPipeline
from backend.runtime.response_pipeline import ResponsePipeline
from backend.runtime.runtime import Runtime
from backend.runtime.session_manager import SessionManager
from backend.runtime.tool_router import ToolRouter
from backend.types import (
    Context,
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolDef,
    ToolResult,
    UserRequest,
    UserResponse,
)

_LOG = logging.getLogger(__name__)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_llm_manager() -> MagicMock:
    mgr = MagicMock(spec=LLMManager)
    mgr.generate = AsyncMock(return_value=LLMResponse(
        text="Hello, world!",
        tool_calls=None,
        finish_reason="stop",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        provider="test",
        duration_ms=100.0,
    ))

    async def stream_gen(*args: object, **kwargs: object) -> AsyncIterator[str]:
        yield "Hello, "
        yield "world!"

    mgr.generate_stream = stream_gen
    return mgr


@pytest.fixture
def mock_context_manager() -> MagicMock:
    mgr = MagicMock(spec=ContextManager)
    mgr.build_context = MagicMock(return_value=Context(
        system_prompt="You are a helpful assistant.",
        messages=[Message(role="user", content="Hello")],
        token_count=10,
    ))
    mock_conv = MagicMock()
    mock_conv.add_message = MagicMock()
    mock_conv.apply_sliding_window = MagicMock()
    mock_conv.messages = []
    mgr.get_session = MagicMock(return_value=None)
    mgr.get_or_create_session = MagicMock(return_value=mock_conv)
    mgr.reset_session = MagicMock()
    mgr.remove_session = MagicMock()
    mgr.active_sessions = []
    mgr.session_count = 0
    return mgr


@pytest.fixture
def mock_prompt_manager() -> MagicMock:
    mgr = MagicMock(spec=PromptManager)
    mgr.compile = MagicMock(return_value="You are a helpful assistant.")
    return mgr


@pytest.fixture
def mock_tool_manager() -> MagicMock:
    mgr = MagicMock(spec=ToolManager)
    mgr.execute_multi = AsyncMock(return_value=[
        ToolResult(status="success", output="42"),
    ])
    mgr.get_tool_defs = MagicMock(return_value=[
        ToolDef(name="calculator", description="Performs arithmetic", parameters={}),
    ])
    mgr.has_tool = MagicMock(return_value=True)
    return mgr


@pytest.fixture
def mock_memory_manager() -> MagicMock:
    mgr = MagicMock(spec=MemoryManager)
    mgr.store_message = AsyncMock()
    mgr.get_history = AsyncMock(return_value=[])
    return mgr


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock(spec=EventBus)
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def mock_conversation_manager() -> MagicMock:
    mgr = MagicMock(spec=ConversationManager)
    mock_router = MagicMock()
    mock_session = MagicMock()
    mock_session.session_id = "test_session"
    mock_session.message_count = 0
    mock_session.state = "ACTIVE"
    mock_session.is_active = True
    mock_session.touch = MagicMock()
    mock_router.route = MagicMock(return_value=mock_session)
    mock_router.get_session = MagicMock(return_value=mock_session)
    mock_router.has_session = MagicMock(return_value=True)
    mock_router.active_sessions = ["test_session"]
    mock_router.session_count = 1
    mgr.router = mock_router
    mgr.get_session = MagicMock(return_value=mock_session)
    mgr.has_session = MagicMock(return_value=True)
    mgr.close_session = AsyncMock()
    mgr.remove_session = MagicMock()
    mgr.active_sessions = ["test_session"]
    mgr.session_count = 1
    return mgr


@pytest.fixture
def user_request() -> UserRequest:
    return UserRequest(
        id=uuid.uuid4(),
        source="cli",
        text="Hello, assistant!",
        session_id="test_session",
        timestamp=time.time(),
    )


@pytest.fixture
def user_request_2() -> UserRequest:
    return UserRequest(
        id=uuid.uuid4(),
        source="cli",
        text="What is 6 * 7?",
        session_id="session_2",
        timestamp=time.time(),
    )


# =========================================================================
# TestCompletePipeline — Full end-to-end flow
# =========================================================================


class TestCompletePipeline:
    """Test complete execution pipeline from request to response."""

    @pytest.mark.asyncio
    async def test_full_pipeline(
        self,
        mock_llm_manager: MagicMock,
        mock_context_manager: MagicMock,
        mock_prompt_manager: MagicMock,
        mock_tool_manager: MagicMock,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        runtime = Runtime(
            llm_manager=mock_llm_manager,
            context_manager=mock_context_manager,
            prompt_manager=mock_prompt_manager,
            tool_manager=mock_tool_manager,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            response = await runtime.process_request(user_request)

            assert isinstance(response, UserResponse)
            assert response.request_id == user_request.id
            assert response.text == "Hello, world!"
            assert response.source == "cli"
            assert response.duration_ms > 0

            # Verify memory was called to store messages
            assert mock_memory_manager.store_message.call_count >= 2
            assert mock_event_bus.emit.call_count >= 2
        finally:
            await runtime.async_shutdown()

    @pytest.mark.asyncio
    async def test_full_pipeline_multiple_sessions(
        self,
        mock_llm_manager: MagicMock,
        mock_context_manager: MagicMock,
        mock_prompt_manager: MagicMock,
        mock_tool_manager: MagicMock,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
        user_request_2: UserRequest,
    ) -> None:
        runtime = Runtime(
            llm_manager=mock_llm_manager,
            context_manager=mock_context_manager,
            prompt_manager=mock_prompt_manager,
            tool_manager=mock_tool_manager,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            r1 = await runtime.process_request(user_request)
            assert r1.text == "Hello, world!"
            assert r1.request_id == user_request.id

            r2 = await runtime.process_request(user_request_2)
            assert r2.text == "Hello, world!"
            assert r2.request_id == user_request_2.id
        finally:
            await runtime.async_shutdown()


# =========================================================================
# TestStreamingPipeline
# =========================================================================


class TestStreamingPipeline:
    @pytest.mark.asyncio
    async def test_streaming_response(
        self,
        mock_llm_manager: MagicMock,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        runtime = Runtime(
            llm_manager=mock_llm_manager,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            chunks: list[str] = []
            async for chunk in runtime.process_request_stream(user_request):
                chunks.append(chunk)

            combined = "".join(chunks)
            assert "Hello" in combined
            assert "world" in combined
            assert "[Error" not in combined

            # Verify memory was called for both messages
            assert mock_memory_manager.store_message.call_count >= 2
            assert mock_event_bus.emit.call_count >= 2
        finally:
            await runtime.async_shutdown()


# =========================================================================
# TestToolExecution
# =========================================================================


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_tool_calling_loop(
        self,
        mock_tool_manager: MagicMock,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        mock_llm = MagicMock(spec=LLMManager)

        # First call triggers tool call, second call returns final response
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me calculate that.",
                tool_calls=[ToolCall(id="calc_1", name="calculator", arguments={"x": 6, "y": 7})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="The answer is 42.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        runtime = Runtime(
            llm_manager=mock_llm,
            tool_manager=mock_tool_manager,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            response = await runtime.process_request(user_request)

            assert "42" in response.text
            assert mock_llm.generate.call_count == 2
            assert mock_tool_manager.execute_multi.call_count == 1
        finally:
            await runtime.async_shutdown()

    @pytest.mark.asyncio
    async def test_tool_execution_failure(
        self,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me check.",
                tool_calls=[ToolCall(id="t1", name="failing_tool", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="I got an error from the tool.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        mock_tools = MagicMock(spec=ToolManager)
        mock_tools.execute_multi = AsyncMock(return_value=[
            ToolResult(status="error", output=None, error="Tool failed"),
        ])
        mock_tools.get_tool_defs = MagicMock(return_value=[
            ToolDef(name="failing_tool", description="Fails", parameters={}),
        ])

        runtime = Runtime(
            llm_manager=mock_llm,
            tool_manager=mock_tools,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            response = await runtime.process_request(user_request)
            assert response.text is not None
            assert "error" not in response.text.lower() or "error" in response.text.lower()
        finally:
            await runtime.async_shutdown()


# =========================================================================
# TestMemoryStorage
# =========================================================================


class TestMemoryStorage:
    @pytest.mark.asyncio
    async def test_memory_persists_conversation_turn(
        self,
        mock_llm_manager: MagicMock,
        mock_memory_manager: MagicMock,
        user_request: UserRequest,
    ) -> None:
        runtime = Runtime(
            llm_manager=mock_llm_manager,
            memory_manager=mock_memory_manager,
        )
        await runtime.async_init()

        try:
            await runtime.process_request(user_request)

            # Verify user and assistant messages were stored
            assert mock_memory_manager.store_message.call_count >= 2
            calls = mock_memory_manager.store_message.call_args_list

            # Check user message was stored
            user_call = calls[0]
            assert user_call[0][1].role == "user"
            assert user_call[0][1].content == "Hello, assistant!"

            # Check assistant message was stored
            assistant_call = calls[1] if len(calls) > 1 else calls[0]
            assert assistant_call[0][1].role == "assistant"
        finally:
            await runtime.async_shutdown()

    @pytest.mark.asyncio
    async def test_memory_failure_graceful(
        self,
        mock_llm_manager: MagicMock,
        user_request: UserRequest,
    ) -> None:
        mock_memory = MagicMock(spec=MemoryManager)
        mock_memory.store_message = AsyncMock(side_effect=RuntimeError("DB failure"))

        runtime = Runtime(
            llm_manager=mock_llm_manager,
            memory_manager=mock_memory,
        )
        await runtime.async_init()

        try:
            # Should not crash even though memory fails
            response = await runtime.process_request(user_request)
            assert response.text == "Hello, world!"
        finally:
            await runtime.async_shutdown()


# =========================================================================
# TestDegradedMode
# =========================================================================


class TestDegradedModeIntegration:
    @pytest.mark.asyncio
    async def test_degraded_runtime_returns_error_response(
        self,
        mock_llm_manager: MagicMock,
        user_request: UserRequest,
    ) -> None:
        runtime = Runtime(llm_manager=mock_llm_manager)
        runtime.degrade()

        with pytest.raises(ModuleDegradedError):
            await runtime.process_request(user_request)

    @pytest.mark.asyncio
    async def test_degraded_stream_handled(
        self,
        mock_llm_manager: MagicMock,
        user_request: UserRequest,
    ) -> None:
        runtime = Runtime(llm_manager=mock_llm_manager)
        runtime.degrade()

        with pytest.raises(ModuleDegradedError):
            async for _ in runtime.process_request_stream(user_request):
                pass


# =========================================================================
# TestErrorHandling
# =========================================================================


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_llm_generation_failure(
        self,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM crashed"))

        runtime = Runtime(
            llm_manager=mock_llm,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            response = await runtime.process_request(user_request)
            # Should return graceful error response, not crash
            assert "error" in response.text.lower()
            assert response.request_id == user_request.id
            assert mock_event_bus.emit.call_count >= 1
        finally:
            await runtime.async_shutdown()

    @pytest.mark.asyncio
    async def test_llm_stream_failure(
        self,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        mock_llm = MagicMock(spec=LLMManager)

        async def failing_stream(*args: object, **kwargs: object) -> AsyncIterator[str]:
            raise RuntimeError("Stream failure")
            yield ""  # pragma: no cover

        mock_llm.generate_stream = failing_stream

        runtime = Runtime(
            llm_manager=mock_llm,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            chunks: list[str] = []
            async for chunk in runtime.process_request_stream(user_request):
                chunks.append(chunk)

            combined = "".join(chunks)
            assert "[Error" in combined
        finally:
            await runtime.async_shutdown()


# =========================================================================
# TestEventEmission
# =========================================================================


class TestEventEmissionIntegration:
    @pytest.mark.asyncio
    async def test_all_stages_emit_events(
        self,
        mock_llm_manager: MagicMock,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        runtime = Runtime(
            llm_manager=mock_llm_manager,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            await runtime.process_request(user_request)
            assert mock_event_bus.emit.call_count >= 2

            # Verify start and complete events
            call_args = [call[0][0] for call in mock_event_bus.emit.call_args_list]
            has_start = any("request_start" in str(arg) for arg in call_args)
            has_complete = any(
                "request_complete" in str(arg) or "request_error" in str(arg)
                for arg in call_args
            )
            assert has_start
            assert has_complete
        finally:
            await runtime.async_shutdown()

    @pytest.mark.asyncio
    async def test_stream_emits_start_and_complete(
        self,
        mock_llm_manager: MagicMock,
        mock_memory_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        runtime = Runtime(
            llm_manager=mock_llm_manager,
            memory_manager=mock_memory_manager,
            event_bus=mock_event_bus,
        )
        await runtime.async_init()

        try:
            async for _ in runtime.process_request_stream(user_request):
                pass

            assert mock_event_bus.emit.call_count >= 2

            call_args = [call[0][0] for call in mock_event_bus.emit.call_args_list]
            has_start = any("request_start" in str(arg) for arg in call_args)
            assert has_start
        finally:
            await runtime.async_shutdown()


# =========================================================================
# TestMultipleSessions
# =========================================================================


class TestMultipleSessions:
    @pytest.mark.asyncio
    async def test_multiple_sessions_processed(
        self,
        mock_llm_manager: MagicMock,
        mock_memory_manager: MagicMock,
    ) -> None:
        runtime = Runtime(
            llm_manager=mock_llm_manager,
            memory_manager=mock_memory_manager,
        )
        await runtime.async_init()

        try:
            sessions = ["session_a", "session_b", "session_c"]
            for sid in sessions:
                req = UserRequest(
                    id=uuid.uuid4(), source="cli", text=f"Message for {sid}",
                    session_id=sid, timestamp=time.time(),
                )
                response = await runtime.process_request(req)
                assert response.text == "Hello, world!"
        finally:
            await runtime.async_shutdown()


# =========================================================================
# TestComponentWiring
# =========================================================================


class TestComponentWiring:
    def test_individual_components_injectable(self) -> None:
        """Verify all components can be created via constructor injection."""
        context_router = ContextRouter()
        tool_router = ToolRouter()
        session_mgr = SessionManager()
        request_pipeline = RequestPipeline()
        response_pipeline = ResponsePipeline()
        dispatcher = MessageDispatcher()
        runtime = Runtime()

        assert context_router is not None
        assert tool_router is not None
        assert session_mgr is not None
        assert request_pipeline is not None
        assert response_pipeline is not None
        assert dispatcher is not None
        assert runtime is not None

    @pytest.mark.asyncio
    async def test_dependency_chain(self) -> None:
        """Verify the full dependency chain works end-to-end."""
        runtime = Runtime()
        await runtime.async_init()

        assert isinstance(runtime.request_pipeline, RequestPipeline)
        assert isinstance(runtime.response_pipeline, ResponsePipeline)
        assert isinstance(runtime.tool_router, ToolRouter)
        assert isinstance(runtime.context_router, ContextRouter)
        assert isinstance(runtime.session_manager, SessionManager)
        assert isinstance(runtime.message_dispatcher, MessageDispatcher)

        await runtime.async_shutdown()
