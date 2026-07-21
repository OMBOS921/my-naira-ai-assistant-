"""Comprehensive unit tests for runtime module components.

Covers:
- ContextRouter
- ToolRouter
- SessionManager
- MessageDispatcher
- RequestPipeline
- ResponsePipeline
- Runtime (full orchestrator)
- ModuleInterface compliance
- Event emission
- Degraded mode
- Error handling
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

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
from backend.runtime.request_pipeline import RequestContextResult, RequestPipeline
from backend.runtime.response_pipeline import ResponsePipeline
from backend.runtime.runtime import Runtime
from backend.runtime.session_manager import SessionManager, _SimpleSession
from backend.runtime.tool_router import ToolRouter
from backend.types import (
    Context,
    LLMResponse,
    Message,
    ModuleInterface,
    TokenUsage,
    ToolCall,
    ToolDef,
    ToolResult,
    UserRequest,
    UserResponse,
)

# =========================================================================
# ContextRouter
# =========================================================================


class TestContextRouter:
    def test_implements_module_interface(self) -> None:
        assert isinstance(ContextRouter(), ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        router = ContextRouter()
        await router.async_init()
        assert router.initialized
        assert not router.degraded
        await router.async_shutdown()
        assert not router.initialized

    @pytest.mark.asyncio
    async def test_degarde_sets_flag(self) -> None:
        router = ContextRouter()
        router.degrade()
        assert router.degraded

    def test_build_context_without_manager(self) -> None:
        router = ContextRouter()
        ctx = router.build_context("s1", "hello", "test prompt")
        assert isinstance(ctx, Context)
        assert ctx.messages == []

    def test_build_context_with_manager(self) -> None:
        mock_mgr = MagicMock(spec=ContextManager)
        mock_mgr.build_context = MagicMock(return_value=Context(
            system_prompt="test", messages=[Message(role="user", content="hi")], token_count=5,
        ))
        router = ContextRouter(context_manager=mock_mgr)
        ctx = router.build_context("s1", "hi", "test")
        assert ctx.messages[0].content == "hi"

    def test_get_session_context_missing(self) -> None:
        router = ContextRouter()
        assert router.get_session_context("nonexistent") is None

    def test_active_sessions_empty(self) -> None:
        router = ContextRouter()
        assert router.active_sessions == []

    def test_session_count_zero(self) -> None:
        router = ContextRouter()
        assert router.session_count == 0

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        router = ContextRouter()
        router.degrade()
        with pytest.raises(ModuleDegradedError):
            router.build_context("s1", "hi", "test")


# =========================================================================
# ToolRouter
# =========================================================================


class TestToolRouter:
    def test_implements_module_interface(self) -> None:
        assert isinstance(ToolRouter(), ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        router = ToolRouter()
        await router.async_init()
        assert router.initialized
        await router.async_shutdown()
        assert not router.initialized

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        router = ToolRouter()
        router.degrade()
        assert router.degraded

    @pytest.mark.asyncio
    async def test_execute_tool_calls_no_manager(self) -> None:
        router = ToolRouter()
        messages = await router.execute_tool_calls(
            [ToolCall(id="1", name="test", arguments={})],
            session_id="s1",
        )
        assert len(messages) == 1
        assert "unavailable" in messages[0].content

    @pytest.mark.asyncio
    async def test_execute_tool_calls_empty(self) -> None:
        router = ToolRouter()
        messages = await router.execute_tool_calls([], session_id="s1")
        assert messages == []

    @pytest.mark.asyncio
    async def test_execute_tool_calls_success(self) -> None:
        mock_mgr = MagicMock(spec=ToolManager)
        mock_mgr.execute_multi = AsyncMock(return_value=[
            ToolResult(status="success", output="result_1"),
        ])
        router = ToolRouter(tool_manager=mock_mgr)
        messages = await router.execute_tool_calls(
            [ToolCall(id="1", name="test", arguments={})],
            session_id="s1",
        )
        assert len(messages) == 1
        assert messages[0].role == "tool"
        assert messages[0].content == "result_1"
        assert messages[0].tool_call_id == "1"

    @pytest.mark.asyncio
    async def test_execute_single_tool(self) -> None:
        mock_mgr = MagicMock(spec=ToolManager)
        mock_mgr.execute_multi = AsyncMock(return_value=[
            ToolResult(status="success", output="single_result"),
        ])
        router = ToolRouter(tool_manager=mock_mgr)
        msg = await router.execute_single_tool(
            ToolCall(id="1", name="test", arguments={}),
            session_id="s1",
        )
        assert msg.role == "tool"
        assert msg.content == "single_result"

    @pytest.mark.asyncio
    async def test_execute_tool_calls_error(self) -> None:
        mock_mgr = MagicMock(spec=ToolManager)
        mock_mgr.execute_multi = AsyncMock(side_effect=RuntimeError("Tool failed"))
        router = ToolRouter(tool_manager=mock_mgr)
        messages = await router.execute_tool_calls(
            [ToolCall(id="1", name="test", arguments={})],
            session_id="s1",
        )
        assert len(messages) == 1
        assert "Error" in messages[0].content

    def test_get_tool_defs_no_manager(self) -> None:
        router = ToolRouter()
        assert router.get_tool_defs() == []

    def test_get_tool_defs_with_manager(self) -> None:
        mock_mgr = MagicMock(spec=ToolManager)
        mock_mgr.get_tool_defs = MagicMock(return_value=[
            ToolDef(name="tool1", description="desc", parameters={}),
        ])
        router = ToolRouter(tool_manager=mock_mgr)
        defs = router.get_tool_defs()
        assert len(defs) == 1
        assert defs[0].name == "tool1"

    def test_has_tool_no_manager(self) -> None:
        router = ToolRouter()
        assert not router.has_tool("test")

    def test_has_tool_with_manager(self) -> None:
        mock_mgr = MagicMock(spec=ToolManager)
        mock_mgr.has_tool = MagicMock(return_value=True)
        router = ToolRouter(tool_manager=mock_mgr)
        assert router.has_tool("test")

    @pytest.mark.asyncio
    async def test_tool_manager_property(self) -> None:
        mock_mgr = MagicMock(spec=ToolManager)
        router = ToolRouter(tool_manager=mock_mgr)
        assert router.tool_manager is mock_mgr

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        router = ToolRouter()
        router.degrade()
        with pytest.raises(ModuleDegradedError):
            await router.execute_tool_calls(
                [ToolCall(id="1", name="test", arguments={})],
                session_id="s1",
            )


# =========================================================================
# SessionManager
# =========================================================================


class TestSessionManager:
    def test_implements_module_interface(self) -> None:
        assert isinstance(SessionManager(), ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        mgr = SessionManager()
        await mgr.async_init()
        assert mgr.initialized
        await mgr.async_shutdown()
        assert not mgr.initialized

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = SessionManager()
        mgr.degrade()
        assert mgr.degraded

    @pytest.mark.asyncio
    async def test_get_or_create_session_no_manager(self) -> None:
        mgr = SessionManager()
        session = await mgr.get_or_create_session("s1")
        assert session.session_id == "s1"

    @pytest.mark.asyncio
    async def test_get_or_create_session_with_manager(self) -> None:
        mock_conv = MagicMock(spec=ConversationManager)
        mock_router = MagicMock()
        mock_session = MagicMock()
        mock_session.session_id = "s1"
        mock_session.message_count = 0
        mock_router.route = MagicMock(return_value=mock_session)
        mock_conv.router = mock_router
        mgr = SessionManager(conversation_manager=mock_conv)
        session = await mgr.get_or_create_session("s1")
        assert session.session_id == "s1"

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        mock_conv = MagicMock(spec=ConversationManager)
        mock_conv.close_session = AsyncMock()
        mock_ctx = MagicMock(spec=ContextManager)
        mock_ctx.remove_session = MagicMock()
        mgr = SessionManager(
            conversation_manager=mock_conv,
            context_manager=mock_ctx,
        )
        await mgr.close_session("s1")
        mock_conv.close_session.assert_called_once_with("s1")
        mock_ctx.remove_session.assert_called_once_with("s1")

    def test_remove_session(self) -> None:
        mock_conv = MagicMock(spec=ConversationManager)
        mock_ctx = MagicMock(spec=ContextManager)
        mgr = SessionManager(
            conversation_manager=mock_conv,
            context_manager=mock_ctx,
        )
        mgr.remove_session("s1")
        mock_conv.remove_session.assert_called_once_with("s1")
        mock_ctx.remove_session.assert_called_once_with("s1")

    @pytest.mark.asyncio
    async def test_update_session_with_context_manager(self) -> None:
        mock_ctx = MagicMock(spec=ContextManager)
        mock_conv_obj = MagicMock()
        mock_conv = MagicMock(spec=ConversationManager)
        mock_conv.get_session = MagicMock(return_value=mock_conv_obj)
        mock_ctx.get_or_create_session = MagicMock(return_value=mock_conv_obj)

        mgr = SessionManager(
            conversation_manager=mock_conv,
            context_manager=mock_ctx,
        )
        await mgr.update_session("s1", "user text", "assistant text")
        assert mock_conv_obj.add_message.call_count == 2
        mock_conv_obj.touch.assert_called_once()

    def test_get_session_none(self) -> None:
        mgr = SessionManager()
        assert mgr.get_session("nonexistent") is None

    def test_has_session_no_manager(self) -> None:
        mgr = SessionManager()
        assert not mgr.has_session("s1")

    def test_active_sessions_no_manager(self) -> None:
        mgr = SessionManager()
        assert mgr.active_sessions == []

    def test_session_count_no_manager(self) -> None:
        mgr = SessionManager()
        assert mgr.session_count == 0

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        mgr = SessionManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.get_or_create_session("s1")


# =========================================================================
# _SimpleSession
# =========================================================================


class TestSimpleSession:
    def test_default_creation(self) -> None:
        session = _SimpleSession(session_id="s1")
        assert session.session_id == "s1"
        assert session.state == "ACTIVE"
        assert session.message_count == 0
        assert session.is_active
        assert not session.is_expired

    def test_touch_updates_activity(self) -> None:
        session = _SimpleSession(session_id="s1")
        old = session.last_activity
        time.sleep(0.01)
        session.touch()
        assert session.last_activity > old

    def test_expired_by_timeout(self) -> None:
        session = _SimpleSession(session_id="s1")
        session.timeout_seconds = 10.0
        session.last_activity = 1000.0
        with patch("backend.runtime.session_manager.time") as mock_time:
            mock_time.time.return_value = 1015.0
            assert session.is_expired

    def test_closed_is_expired(self) -> None:
        session = _SimpleSession(session_id="s1")
        session.state = "CLOSED"
        assert session.is_expired

    def test_not_active_when_closed(self) -> None:
        session = _SimpleSession(session_id="s1")
        session.state = "CLOSED"
        assert not session.is_active


# =========================================================================
# RequestPipeline
# =========================================================================


class TestRequestPipeline:
    def test_implements_module_interface(self) -> None:
        assert isinstance(RequestPipeline(), ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        pipeline = RequestPipeline()
        await pipeline.async_init()
        assert pipeline.initialized
        await pipeline.async_shutdown()
        assert not pipeline.initialized

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        pipeline = RequestPipeline()
        pipeline.degrade()
        assert pipeline.degraded

    @pytest.mark.asyncio
    async def test_process_without_dependencies(self) -> None:
        pipeline = RequestPipeline()
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        result = await pipeline.process(request)
        assert isinstance(result, RequestContextResult)
        assert result.session_id == "s1"
        assert result.system_prompt == ""
        assert result.messages == []
        assert result.tool_defs == []

    @pytest.mark.asyncio
    async def test_process_with_context_manager(self) -> None:
        mock_ctx = MagicMock(spec=ContextManager)
        mock_ctx.build_context = MagicMock(return_value=Context(
            system_prompt="test prompt",
            messages=[Message(role="user", content="Hello")],
            token_count=5,
        ))
        pipeline = RequestPipeline(context_manager=mock_ctx)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        result = await pipeline.process(request)
        assert result.system_prompt == ""
        assert len(result.messages) == 1

    @pytest.mark.asyncio
    async def test_process_with_prompt_manager(self) -> None:
        mock_prompt = MagicMock(spec=PromptManager)
        mock_prompt.compile = MagicMock(return_value="Compiled system prompt")
        pipeline = RequestPipeline(prompt_manager=mock_prompt)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        result = await pipeline.process(request)
        assert result.system_prompt == "Compiled system prompt"

    @pytest.mark.asyncio
    async def test_prompt_compile_failure(self) -> None:
        mock_prompt = MagicMock(spec=PromptManager)
        mock_prompt.compile = MagicMock(side_effect=RuntimeError("Compile failed"))
        pipeline = RequestPipeline(prompt_manager=mock_prompt)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        result = await pipeline.process(request)
        assert result.system_prompt == ""

    @pytest.mark.asyncio
    async def test_context_router_property(self) -> None:
        pipeline = RequestPipeline()
        assert isinstance(pipeline.context_router, ContextRouter)

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        pipeline = RequestPipeline()
        pipeline.degrade()
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        with pytest.raises(ModuleDegradedError):
            await pipeline.process(request)

    @pytest.mark.asyncio
    async def test_event_emission(self) -> None:
        mock_bus = MagicMock(spec=EventBus)
        mock_bus.emit = AsyncMock()
        pipeline = RequestPipeline(
            context_manager=MagicMock(
                build_context=MagicMock(return_value=Context(
                    system_prompt="sp", messages=[], token_count=0,
                ))
            ),
            prompt_manager=MagicMock(compile=MagicMock(return_value="sp")),
            event_bus=mock_bus,
        )
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hi", session_id="s1",
            timestamp=time.time(),
        )
        await pipeline.process(request)
        assert mock_bus.emit.call_count >= 3

    @pytest.mark.asyncio
    async def test_process_with_tool_defs(self) -> None:
        mock_router = MagicMock()
        mock_router.get_tool_defs = MagicMock(return_value=[
            ToolDef(name="calc", description="Calculator", parameters={}),
        ])
        pipeline = RequestPipeline(tool_router=mock_router)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Calculate", session_id="s1",
            timestamp=time.time(),
        )
        result = await pipeline.process(request)
        assert result.tool_defs is not None


# =========================================================================
# ResponsePipeline
# =========================================================================


class TestResponsePipeline:
    def test_implements_module_interface(self) -> None:
        assert isinstance(ResponsePipeline(), ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        pipeline = ResponsePipeline()
        await pipeline.async_init()
        assert pipeline.initialized
        await pipeline.async_shutdown()
        assert not pipeline.initialized

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        pipeline = ResponsePipeline()
        pipeline.degrade()
        assert pipeline.degraded

    @pytest.mark.asyncio
    async def test_generate_no_llm(self) -> None:
        pipeline = ResponsePipeline()
        response = await pipeline.generate(
            system_prompt="test", messages=[], tool_defs=[], session_id="s1",
        )
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Hello world",
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="test",
            duration_ms=100.0,
        ))
        pipeline = ResponsePipeline(llm_manager=mock_llm)
        response = await pipeline.generate(
            system_prompt="test", messages=[], tool_defs=[], session_id="s1",
        )
        assert response.text == "Hello world"
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_with_tool_call(self) -> None:
        mock_llm = MagicMock(spec=LLMManager)
        mock_tools = MagicMock(spec=ToolManager)
        mock_tools.execute_multi = AsyncMock(return_value=[
            ToolResult(status="success", output="42"),
        ])

        # First call returns tool calls, second returns final text
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me calculate",
                tool_calls=[ToolCall(id="1", name="calc", arguments={"x": 6, "y": 7})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="The answer is 42",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])
        pipeline = ResponsePipeline(
            llm_manager=mock_llm,
            tool_router=ToolRouter(tool_manager=mock_tools),
        )
        response = await pipeline.generate(
            system_prompt="test", messages=[], tool_defs=[
                ToolDef(name="calc", description="Calc", parameters={}),
            ],
            session_id="s1",
        )
        assert response.text == "The answer is 42"
        assert mock_llm.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_max_iterations(self) -> None:
        mock_llm = MagicMock(spec=LLMManager)
        mock_tools = MagicMock(spec=ToolManager)
        mock_tools.execute_multi = AsyncMock(return_value=[
            ToolResult(status="success", output="result"),
        ])
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Calling tool",
            tool_calls=[ToolCall(id="1", name="calc", arguments={"x": 1})],
            finish_reason="tool_calls",
            token_usage=TokenUsage(10, 5, 15),
            provider="test",
            duration_ms=100.0,
        ))
        pipeline = ResponsePipeline(
            llm_manager=mock_llm,
            tool_router=ToolRouter(tool_manager=mock_tools),
            max_tool_iterations=3,
        )
        response = await pipeline.generate(
            system_prompt="test", messages=[], tool_defs=[
                ToolDef(name="calc", description="Calc", parameters={}),
            ],
            session_id="s1",
        )
        assert mock_llm.generate.call_count == 3
        assert response.text == "Calling tool"

    @pytest.mark.asyncio
    async def test_generate_stream_no_llm(self) -> None:
        pipeline = ResponsePipeline()
        chunks = [chunk async for chunk in pipeline.generate_stream(
            system_prompt="test", messages=[], tool_defs=[], session_id="s1",
        )]
        assert chunks == [""]

    @pytest.mark.asyncio
    async def test_generate_stream_success(self) -> None:
        mock_llm = MagicMock(spec=LLMManager)

        async def stream_generator(*args: object, **kwargs: object) -> AsyncIterator[str]:
            yield "Hello "
            yield "world"

        mock_llm.generate_stream = stream_generator
        pipeline = ResponsePipeline(llm_manager=mock_llm)
        chunks = [chunk async for chunk in pipeline.generate_stream(
            system_prompt="test", messages=[], tool_defs=[], session_id="s1",
        )]
        assert chunks == ["Hello ", "world"]

    @pytest.mark.asyncio
    async def test_tool_router_property(self) -> None:
        mock_tools = MagicMock(spec=ToolManager)
        router = ToolRouter(tool_manager=mock_tools)
        pipeline = ResponsePipeline(tool_router=router)
        assert pipeline.tool_router is router

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        pipeline = ResponsePipeline()
        pipeline.degrade()
        with pytest.raises(ModuleDegradedError):
            await pipeline.generate(
                system_prompt="test", messages=[], tool_defs=[], session_id="s1",
            )


# =========================================================================
# MessageDispatcher
# =========================================================================


class TestMessageDispatcher:
    def test_implements_module_interface(self) -> None:
        assert isinstance(MessageDispatcher(), ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        dispatcher = MessageDispatcher()
        await dispatcher.async_init()
        assert dispatcher.initialized
        await dispatcher.async_shutdown()
        assert not dispatcher.initialized

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        dispatcher = MessageDispatcher()
        dispatcher.degrade()
        assert dispatcher.degraded

    @pytest.mark.asyncio
    async def test_dispatch_basic(self) -> None:
        mock_session_mgr = MagicMock(spec=SessionManager)
        mock_session = MagicMock()
        mock_session.session_id = "s1"
        mock_session.message_count = 0
        mock_session_mgr.get_or_create_session = AsyncMock(return_value=mock_session)
        mock_session_mgr.update_session = AsyncMock()

        mock_request_pipeline = MagicMock(spec=RequestPipeline)
        mock_request_pipeline.process = AsyncMock(return_value=RequestContextResult(
            system_prompt="test prompt",
            messages=[Message(role="user", content="Hello")],
            tool_defs=[],
            session_id="s1",
            request_id=str(uuid.uuid4()),
        ))

        mock_response_pipeline = MagicMock(spec=ResponsePipeline)
        mock_response_pipeline.generate = AsyncMock(return_value=LLMResponse(
            text="Hi there!",
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(5, 5, 10),
            provider="test",
            duration_ms=50.0,
        ))

        dispatcher = MessageDispatcher(
            request_pipeline=mock_request_pipeline,
            response_pipeline=mock_response_pipeline,
            session_manager=mock_session_mgr,
        )

        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        response = await dispatcher.dispatch(request)
        assert response.text == "Hi there!"
        assert response.request_id == request.id
        mock_session_mgr.update_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_without_pipelines(self) -> None:
        mock_session_mgr = MagicMock(spec=SessionManager)
        mock_session = MagicMock()
        mock_session.session_id = "s1"
        mock_session.message_count = 0
        mock_session_mgr.get_or_create_session = AsyncMock(return_value=mock_session)
        mock_session_mgr.update_session = AsyncMock()

        dispatcher = MessageDispatcher(session_manager=mock_session_mgr)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        response = await dispatcher.dispatch(request)
        assert response.text == "" or "error" in response.text.lower()

    @pytest.mark.asyncio
    async def test_dispatch_error_handling(self) -> None:
        mock_session_mgr = MagicMock(spec=SessionManager)
        mock_session_mgr.get_or_create_session = AsyncMock(
            side_effect=RuntimeError("Session error")
        )
        mock_session_mgr.update_session = AsyncMock()

        dispatcher = MessageDispatcher(session_manager=mock_session_mgr)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        response = await dispatcher.dispatch(request)
        assert "error" in response.text.lower()

    @pytest.mark.asyncio
    async def test_dispatch_stream(self) -> None:
        mock_session_mgr = MagicMock(spec=SessionManager)
        mock_session = MagicMock()
        mock_session.session_id = "s1"
        mock_session.message_count = 0
        mock_session_mgr.get_or_create_session = AsyncMock(return_value=mock_session)
        mock_session_mgr.update_session = AsyncMock()

        mock_request_pipeline = MagicMock(spec=RequestPipeline)
        mock_request_pipeline.process = AsyncMock(return_value=RequestContextResult(
            system_prompt="test", messages=[], tool_defs=[], session_id="s1",
            request_id=str(uuid.uuid4()),
        ))

        mock_response_pipeline = MagicMock(spec=ResponsePipeline)
        mock_response_pipeline.generate_stream = MagicMock()

        async def stream_gen(*args: object, **kwargs: object) -> AsyncIterator[str]:
            yield "Hello "
            yield "world"

        mock_response_pipeline.generate_stream = stream_gen

        dispatcher = MessageDispatcher(
            request_pipeline=mock_request_pipeline,
            response_pipeline=mock_response_pipeline,
            session_manager=mock_session_mgr,
        )

        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        chunks = [chunk async for chunk in dispatcher.dispatch_stream(request)]
        assert chunks == ["Hello ", "world"]

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        dispatcher = MessageDispatcher()
        dispatcher.degrade()
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        with pytest.raises(ModuleDegradedError):
            await dispatcher.dispatch(request)

    @pytest.mark.asyncio
    async def test_properties(self) -> None:
        mock_rp = MagicMock(spec=RequestPipeline)
        mock_rsp = MagicMock(spec=ResponsePipeline)
        mock_sm = MagicMock(spec=SessionManager)
        mock_cr = MagicMock(spec=ContextRouter)
        dispatcher = MessageDispatcher(
            request_pipeline=mock_rp,
            response_pipeline=mock_rsp,
            session_manager=mock_sm,
            context_router=mock_cr,
        )
        assert dispatcher.request_pipeline is mock_rp
        assert dispatcher.response_pipeline is mock_rsp
        assert dispatcher.session_manager is mock_sm
        assert dispatcher.context_router is mock_cr


# =========================================================================
# Runtime
# =========================================================================


class TestRuntime:
    def test_implements_module_interface(self) -> None:
        assert isinstance(Runtime(), ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        runtime = Runtime()
        await runtime.async_init()
        assert runtime.initialized
        assert not runtime.degraded
        await runtime.async_shutdown()
        assert not runtime.initialized

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        runtime = Runtime()
        runtime.degrade()
        assert runtime.degraded

    @pytest.mark.asyncio
    async def test_process_request_without_deps(self) -> None:
        runtime = Runtime()
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        response = await runtime.process_request(request)
        assert isinstance(response, UserResponse)
        assert response.request_id == request.id
        assert response.text == ""

    @pytest.mark.asyncio
    async def test_process_request_success(self) -> None:
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Success response",
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(10, 5, 15),
            provider="test",
            duration_ms=100.0,
        ))
        mock_ctx = MagicMock(spec=ContextManager)
        mock_ctx.build_context = MagicMock(return_value=Context(
            system_prompt="System prompt",
            messages=[Message(role="user", content="Hello")],
            token_count=5,
        ))
        mock_ctx.get_or_create_session = MagicMock(return_value=MagicMock(
            add_message=MagicMock(),
            apply_sliding_window=MagicMock(),
        ))
        mock_ctx.get_session = MagicMock(return_value=None)
        mock_prompt = MagicMock(spec=PromptManager)
        mock_prompt.compile = MagicMock(return_value="System prompt")
        mock_tools = MagicMock(spec=ToolManager)
        mock_tools.get_tool_defs = MagicMock(return_value=[])
        mock_memory = MagicMock(spec=MemoryManager)
        mock_memory.store_message = AsyncMock()

        runtime = Runtime(
            llm_manager=mock_llm,
            context_manager=mock_ctx,
            prompt_manager=mock_prompt,
            tool_manager=mock_tools,
            memory_manager=mock_memory,
        )

        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        response = await runtime.process_request(request)
        assert response.text == "Success response"
        assert mock_memory.store_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_process_request_error_handling(self) -> None:
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM failure"))
        runtime = Runtime(llm_manager=mock_llm)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        response = await runtime.process_request(request)
        assert "error" in response.text.lower()

    @pytest.mark.asyncio
    async def test_process_request_stream(self) -> None:
        mock_llm = MagicMock(spec=LLMManager)

        async def stream_gen(*args: object, **kwargs: object) -> AsyncIterator[str]:
            yield "Chunk1"
            yield "Chunk2"

        mock_llm.generate_stream = stream_gen
        mock_memory = MagicMock(spec=MemoryManager)
        mock_memory.store_message = AsyncMock()
        runtime = Runtime(llm_manager=mock_llm, memory_manager=mock_memory)

        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        chunks = [chunk async for chunk in runtime.process_request_stream(request)]
        assert len(chunks) >= 2
        # Check that chunks don't contain error message
        assert not any("[Error" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        runtime = Runtime()
        runtime.degrade()
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        with pytest.raises(ModuleDegradedError):
            await runtime.process_request(request)

    @pytest.mark.asyncio
    async def test_properties(self) -> None:
        runtime = Runtime()
        await runtime.async_init()
        assert isinstance(runtime.request_pipeline, RequestPipeline)
        assert isinstance(runtime.response_pipeline, ResponsePipeline)
        assert isinstance(runtime.tool_router, ToolRouter)
        assert isinstance(runtime.context_router, ContextRouter)
        assert isinstance(runtime.session_manager, SessionManager)
        assert isinstance(runtime.message_dispatcher, MessageDispatcher)
        await runtime.async_shutdown()


# =========================================================================
# Runtime — event emission
# =========================================================================


class TestRuntimeEventEmission:
    @pytest.mark.asyncio
    async def test_events_emitted_during_request(self) -> None:
        mock_bus = MagicMock(spec=EventBus)
        mock_bus.emit = AsyncMock()
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="OK", tool_calls=None, finish_reason="stop",
            token_usage=TokenUsage(1, 1, 2), provider="test", duration_ms=10.0,
        ))
        mock_memory = MagicMock(spec=MemoryManager)
        mock_memory.store_message = AsyncMock()

        runtime = Runtime(
            llm_manager=mock_llm,
            event_bus=mock_bus,
            memory_manager=mock_memory,
        )
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        await runtime.process_request(request)
        # Should emit request_start and request_error or request_complete
        assert mock_bus.emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_stream_events(self) -> None:
        mock_bus = MagicMock(spec=EventBus)
        mock_bus.emit = AsyncMock()
        mock_llm = MagicMock(spec=LLMManager)

        async def stream_gen(*args: object, **kwargs: object) -> AsyncIterator[str]:
            yield "A"

        mock_llm.generate_stream = stream_gen
        mock_memory = MagicMock(spec=MemoryManager)
        mock_memory.store_message = AsyncMock()
        runtime = Runtime(
            llm_manager=mock_llm,
            event_bus=mock_bus,
            memory_manager=mock_memory,
        )
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        _chunks = [chunk async for chunk in runtime.process_request_stream(request)]
        assert mock_bus.emit.call_count >= 2


# =========================================================================
# Runtime — Memory integration
# =========================================================================


class TestRuntimeMemoryIntegration:
    @pytest.mark.asyncio
    async def test_messages_stored_after_response(self) -> None:
        mock_memory = MagicMock(spec=MemoryManager)
        mock_memory.store_message = AsyncMock()
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Response text", tool_calls=None, finish_reason="stop",
            token_usage=TokenUsage(1, 1, 2), provider="test", duration_ms=10.0,
        ))
        runtime = Runtime(llm_manager=mock_llm, memory_manager=mock_memory)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="User message", session_id="s1",
            timestamp=time.time(),
        )
        await runtime.process_request(request)
        assert mock_memory.store_message.call_count >= 2

    @pytest.mark.asyncio
    async def test_memory_failure_does_not_crash(self) -> None:
        mock_memory = MagicMock(spec=MemoryManager)
        mock_memory.store_message = AsyncMock(
            side_effect=RuntimeError("Memory store failed")
        )
        mock_llm = MagicMock(spec=LLMManager)
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Response", tool_calls=None, finish_reason="stop",
            token_usage=TokenUsage(1, 1, 2), provider="test", duration_ms=10.0,
        ))
        runtime = Runtime(llm_manager=mock_llm, memory_manager=mock_memory)
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hi", session_id="s1",
            timestamp=time.time(),
        )
        response = await runtime.process_request(request)
        assert response.text == "Response"


# =========================================================================
# Runtime — Degraded mode
# =========================================================================


class TestRuntimeDegradedMode:
    @pytest.mark.asyncio
    async def test_degraded_request_raises(self) -> None:
        runtime = Runtime()
        runtime.degrade()
        assert runtime.degraded
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        with pytest.raises(ModuleDegradedError):
            await runtime.process_request(request)

    @pytest.mark.asyncio
    async def test_degraded_stream_raises(self) -> None:
        runtime = Runtime()
        runtime.degrade()
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hello", session_id="s1",
            timestamp=time.time(),
        )
        with pytest.raises(ModuleDegradedError):
            async for _ in runtime.process_request_stream(request):
                pass

    @pytest.mark.asyncio
    async def test_degraded_propagates_to_subcomponents(self) -> None:
        runtime = Runtime()
        runtime.degrade()
        assert runtime.request_pipeline.degraded
        assert runtime.response_pipeline.degraded
        assert runtime.session_manager.degraded
        assert runtime.message_dispatcher.degraded
