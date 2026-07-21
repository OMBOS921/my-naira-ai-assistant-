"""Comprehensive tests for the ToolCallingEngine.

Covers:
- Single tool call
- Multiple tool calls in one response
- Iterative/nested tool calls
- Timeout protection
- Tool failure handling
- Invalid tool
- Disabled tool
- Permission denied
- Context rebuild after tool results
- Conversation update after tool results
- Runtime loop iteration limits
- Infinite loop / recursion protection
- EventBus events at every stage
- Cancellation (graceful)
- Degraded mode
- Module lifecycle
- Stream mode with tool calls
- LLM generation timeout
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.modules.conversation import ConversationManager
from backend.modules.tools import ToolManager
from backend.orchestrator import EventBus
from backend.runtime._tool_calling_engine import ToolCallingEngine, ToolCallingResult
from backend.runtime.tool_router import ToolRouter
from backend.types import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolDef,
    ToolResult,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_llm() -> MagicMock:
    mgr = MagicMock()
    mgr.degraded = False
    return mgr


@pytest.fixture
def mock_tool_manager() -> MagicMock:
    mgr = MagicMock(spec=ToolManager)
    mgr.execute_multi = AsyncMock(return_value=[
        ToolResult(status="success", output="42"),
    ])
    mgr.get_tool_defs = MagicMock(return_value=[])
    mgr.has_tool = MagicMock(return_value=True)
    mgr.degraded = False
    return mgr


@pytest.fixture
def mock_tool_router(mock_tool_manager: MagicMock) -> ToolRouter:
    router = ToolRouter(tool_manager=mock_tool_manager)
    return router


@pytest.fixture
def mock_event_bus() -> MagicMock:
    bus = MagicMock(spec=EventBus)
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def mock_conversation_manager() -> MagicMock:
    mgr = MagicMock(spec=ConversationManager)
    mock_bridge = MagicMock()
    mock_bridge.store_message = AsyncMock()
    mgr.bridge = mock_bridge
    return mgr


@pytest.fixture
def mock_context_manager() -> MagicMock:
    mock_session = MagicMock()
    mock_session.apply_sliding_window = MagicMock()
    mgr = MagicMock()
    mgr.get_session = MagicMock(return_value=mock_session)
    mgr.build_context = MagicMock(
        return_value=MagicMock(
            messages=[Message(role="user", content="Hello")],
            system_prompt="test",
            token_count=5,
        )
    )
    return mgr


@pytest.fixture
def tool_defs() -> list[ToolDef]:
    return [
        ToolDef(name="calculator", description="Performs arithmetic", parameters={}),
        ToolDef(name="search", description="Searches the web", parameters={}),
    ]


@pytest.fixture
def messages() -> list[Message]:
    return [Message(role="user", content="What is 6 * 7?")]


@pytest.fixture
def session_id() -> str:
    return "test_session"


@pytest.fixture
def tool_calling_engine(
    mock_llm: MagicMock,
    mock_tool_router: ToolRouter,
    mock_event_bus: MagicMock,
    mock_conversation_manager: MagicMock,
    mock_context_manager: MagicMock,
) -> ToolCallingEngine:
    return ToolCallingEngine(
        llm_manager=mock_llm,
        tool_router=mock_tool_router,
        conversation_manager=mock_conversation_manager,
        context_manager=mock_context_manager,
        event_bus=mock_event_bus,
        max_iterations=10,
        timeout_seconds=30.0,
    )


# =========================================================================
# Module lifecycle
# =========================================================================


class TestLifecycle:
    def test_implements_module_interface(self) -> None:
        engine = ToolCallingEngine()
        from backend.types import ModuleInterface
        assert isinstance(engine, ModuleInterface)

    @pytest.mark.asyncio
    async def test_lifecycle(self) -> None:
        engine = ToolCallingEngine()
        await engine.async_init()
        assert engine.initialized
        assert not engine.degraded
        await engine.async_shutdown()
        assert not engine.initialized

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        engine = ToolCallingEngine()
        engine.degrade()
        assert engine.degraded

    @pytest.mark.asyncio
    async def test_init_with_tool_router(self, mock_tool_router: ToolRouter) -> None:
        engine = ToolCallingEngine(tool_router=mock_tool_router)
        await engine.async_init()
        assert engine.initialized
        await engine.async_shutdown()

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        engine = ToolCallingEngine()
        await engine.async_init()
        await engine.async_shutdown()
        await engine.async_shutdown()
        assert not engine.initialized

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        engine = ToolCallingEngine()
        engine.degrade()
        engine.degrade()
        assert engine.degraded


# =========================================================================
# Single tool call
# =========================================================================


class TestSingleToolCall:
    @pytest.mark.asyncio
    async def test_single_tool_call_returns_result(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me calculate.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 6, "y": 7})],
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

        result = await tool_calling_engine.execute(
            system_prompt="You are a calculator.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert isinstance(result, ToolCallingResult)
        assert result.response.text == "The answer is 42."
        assert result.response.finish_reason == "stop"
        assert result.iterations == 2
        assert result.tool_calls_executed == 1
        assert mock_llm.generate.call_count == 2
        assert mock_tool_manager.execute_multi.call_count == 1

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_immediately(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Hello!",
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(5, 5, 10),
            provider="test",
            duration_ms=50.0,
        ))

        result = await tool_calling_engine.execute(
            system_prompt="Be helpful.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "Hello!"
        assert result.iterations == 1
        assert result.tool_calls_executed == 0
        assert mock_llm.generate.call_count == 1


# =========================================================================
# Multiple tool calls in one response
# =========================================================================


class TestMultipleToolCalls:
    @pytest.mark.asyncio
    async def test_two_tool_calls_in_one_response(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me look up both.",
                tool_calls=[
                    ToolCall(id="c1", name="search", arguments={"q": "population of Paris"}),
                    ToolCall(id="c2", name="calculator", arguments={"x": 100, "y": 200}),
                ],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="Here are the results.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "Here are the results."
        assert result.iterations == 2
        assert result.tool_calls_executed == 2
        assert mock_tool_manager.execute_multi.call_count == 1

    @pytest.mark.asyncio
    async def test_three_consecutive_tool_calls(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        calls = 0

        async def llm_generate(*args: object, **kwargs: object) -> LLMResponse:
            nonlocal calls
            calls += 1
            if calls < 3:
                return LLMResponse(
                    text=f"Calling tool {calls}.",
                    tool_calls=[ToolCall(
                        id=f"c{calls}", name="calculator", arguments={"x": calls},
                    )],
                    finish_reason="tool_calls",
                    token_usage=TokenUsage(10, 5, 15),
                    provider="test",
                    duration_ms=100.0,
                )
            return LLMResponse(
                text="All done.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            )

        mock_llm.generate = llm_generate

        result = await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "All done."
        assert result.iterations == 3
        assert result.tool_calls_executed == 2


# =========================================================================
# Iterative / nested tool calls
# =========================================================================


class TestIterativeToolCalls:
    @pytest.mark.asyncio
    async def test_chained_tool_calls(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        step = 0

        async def llm_generate(*args: object, **kwargs: object) -> LLMResponse:
            nonlocal step
            step += 1
            if step == 1:
                return LLMResponse(
                    text="First, search.",
                    tool_calls=[ToolCall(id="s1", name="search", arguments={"q": "weather"})],
                    finish_reason="tool_calls",
                    token_usage=TokenUsage(10, 5, 15),
                    provider="test",
                    duration_ms=100.0,
                )
            if step == 2:
                return LLMResponse(
                    text="Now calculate.",
                    tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 1, "y": 2})],
                    finish_reason="tool_calls",
                    token_usage=TokenUsage(15, 8, 23),
                    provider="test",
                    duration_ms=150.0,
                )
            return LLMResponse(
                text="Final answer.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            )

        mock_llm.generate = llm_generate

        result = await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "Final answer."
        assert result.iterations == 3
        assert result.tool_calls_executed == 2


# =========================================================================
# Tool failure handling
# =========================================================================


class TestToolFailure:
    @pytest.mark.asyncio
    async def test_tool_execution_error(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_tool_manager.execute_multi = AsyncMock(return_value=[
            ToolResult(status="error", output=None, error="Tool crashed"),
        ])

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me try.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 1})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="I got an error.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "I got an error."
        assert result.iterations == 2
        assert result.tool_calls_executed == 1

    @pytest.mark.asyncio
    async def test_tool_router_raises_exception(
        self,
        mock_llm: MagicMock,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_tools = MagicMock(spec=ToolManager)
        mock_tools.execute_multi = AsyncMock(side_effect=RuntimeError("Tool router failed"))
        mock_tools.get_tool_defs = MagicMock(return_value=[])
        mock_tools.has_tool = MagicMock(return_value=True)
        router = ToolRouter(tool_manager=mock_tools)

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=router,
            event_bus=mock_event_bus,
            max_iterations=3,
        )

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Trying.",
                tool_calls=[ToolCall(id="c1", name="calc", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="Recovered.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "Recovered."
        assert result.iterations == 2


# =========================================================================
# Invalid / unknown tool
# =========================================================================


class TestInvalidTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_tool_manager.execute_multi = AsyncMock(return_value=[
            ToolResult(status="error", output=None, error="Tool not found: 'unknown_tool'"),
        ])

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Calling unknown tool.",
                tool_calls=[ToolCall(id="c1", name="unknown_tool", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="The tool was not found.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "The tool was not found."
        assert result.iterations == 2


# =========================================================================
# Disabled tool
# =========================================================================


class TestDisabledTool:
    @pytest.mark.asyncio
    async def test_disabled_tool_returned_as_error(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_tool_manager.execute_multi = AsyncMock(return_value=[
            ToolResult(status="error", output=None, error="Tool is disabled: 'calculator'"),
        ])

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Calling disabled tool.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="The tool is disabled.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert "disabled" in result.response.text.lower()


# =========================================================================
# Permission denied
# =========================================================================


class TestPermissionDenied:
    @pytest.mark.asyncio
    async def test_permission_denied_returned_as_error(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_tool_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_tool_manager.execute_multi = AsyncMock(return_value=[
            ToolResult(
                status="error", output=None,
                error="Permission denied for tool: 'admin_tool'",
            ),
        ])

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Calling admin tool.",
                tool_calls=[ToolCall(id="c1", name="admin_tool", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="Permission denied.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert "denied" in result.response.text.lower()


# =========================================================================
# Maximum iteration protection
# =========================================================================


class TestMaxIterationProtection:
    @pytest.mark.asyncio
    async def test_max_iterations_enforced(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Calling tool.",
            tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 1})],
            finish_reason="tool_calls",
            token_usage=TokenUsage(10, 5, 15),
            provider="test",
            duration_ms=100.0,
        ))

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
            max_iterations=3,
        )

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.iterations == 3
        assert mock_llm.generate.call_count == 3


# =========================================================================
# Infinite loop / recursion protection
# =========================================================================


class TestRecursionProtection:
    @pytest.mark.asyncio
    async def test_identical_tool_calls_trigger_recursion_protection(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Calling tool again.",
            tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 1, "y": 2})],
            finish_reason="tool_calls",
            token_usage=TokenUsage(10, 5, 15),
            provider="test",
            duration_ms=100.0,
        ))

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
            max_iterations=10,
        )

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.iterations == 3  # Recursion protection triggers at 3rd iteration
        assert mock_llm.generate.call_count == 3

    @pytest.mark.asyncio
    async def test_different_tool_calls_not_blocked(
        self,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        call_count = 0

        async def varying_llm(*args: object, **kwargs: object) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            return LLMResponse(
                text=f"Step {call_count}.",
                tool_calls=[ToolCall(
                    id=f"c{call_count}", name="calculator", arguments={"x": call_count},
                )],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            )

        mock_llm = MagicMock()
        mock_llm.generate = varying_llm

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
            max_iterations=10,
        )

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.iterations == 10  # Max iterations, not recursion protection
        assert call_count == 10


# =========================================================================
# Timeout protection
# =========================================================================


class TestTimeoutProtection:
    @pytest.mark.asyncio
    async def test_llm_timeout_returns_empty_response(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        async def slow_llm(*args: object, **kwargs: object) -> LLMResponse:
            await asyncio.sleep(10)
            return LLMResponse(
                text="Done.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(1, 1, 2),
                provider="test",
                duration_ms=0.0,
            )

        mock_llm.generate = slow_llm

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
            timeout_seconds=0.1,
            max_iterations=3,
        )

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.finish_reason == "error"
        assert result.iterations == 1

    @pytest.mark.asyncio
    async def test_tool_timeout_returns_timeout_result(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_tool_manager = MagicMock(spec=ToolManager)
        mock_tool_manager.execute_multi = AsyncMock(return_value=[
            ToolResult(status="timeout", output=None, error="Tool timed out"),
        ])
        mock_tool_manager.get_tool_defs = MagicMock(return_value=[])
        mock_tool_manager.has_tool = MagicMock(return_value=True)
        router = ToolRouter(tool_manager=mock_tool_manager)

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=router,
            event_bus=mock_event_bus,
            max_iterations=3,
        )

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Calling tool.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="Timed out.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "Timed out."
        assert result.tool_calls_executed == 1


# =========================================================================
# Context rebuild
# =========================================================================


class TestContextUpdate:
    @pytest.mark.asyncio
    async def test_context_rebuilt_after_tool_execution(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_context_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me calculate.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 6})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="42.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert mock_context_manager.get_session.call_count >= 1

    @pytest.mark.asyncio
    async def test_context_not_required_for_operation(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Hello!",
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(5, 5, 10),
            provider="test",
            duration_ms=50.0,
        ))

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "Hello!"


# =========================================================================
# Conversation history update
# =========================================================================


class TestConversationUpdate:
    @pytest.mark.asyncio
    async def test_conversation_history_updated(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_conversation_manager: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Let me calculate.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 6})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="42.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        store_msg = mock_conversation_manager.bridge.store_message
        assert store_msg.call_count >= 1

    @pytest.mark.asyncio
    async def test_conversation_manager_not_required(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Calculating.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="42.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "42."


# =========================================================================
# EventBus events
# =========================================================================


class TestEventBusEvents:
    @pytest.mark.asyncio
    async def test_events_emitted_for_each_stage(
        self,
        tool_calling_engine: ToolCallingEngine,
        mock_llm: MagicMock,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Calculating.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 6})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="42.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        await tool_calling_engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert mock_event_bus.emit.call_count >= 5
        event_types = [call[0][0] for call in mock_event_bus.emit.call_args_list]
        assert "tool_calling.start" in event_types
        assert "tool_calling.llm_generation_start" in event_types
        assert "tool_calling.llm_generation_complete" in event_types
        assert "tool_calling.tool_calls_detected" in event_types
        assert "tool_calling.batch_execution_start" in event_types
        assert "tool_calling.batch_execution_complete" in event_types
        assert "tool_calling.complete" in event_types


# =========================================================================
# Cancellation
# =========================================================================


class TestCancellation:
    @pytest.mark.asyncio
    async def test_graceful_cancellation(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Step 1.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 1})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="Step 2.",
                tool_calls=[ToolCall(id="c2", name="calculator", arguments={"x": 2})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
        ])

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
            max_iterations=10,
        )

        # Cancel before execution
        engine.cancel()

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.finish_reason == "error"
        assert result.iterations == 0

    @pytest.mark.asyncio
    async def test_cancel_during_execution(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        call_count = 0

        async def llm_with_cancel(*args: object, **kwargs: object) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    text="Step 1.",
                    tool_calls=[ToolCall(id="c1", name="calculator", arguments={"x": 1})],
                    finish_reason="tool_calls",
                    token_usage=TokenUsage(10, 5, 15),
                    provider="test",
                    duration_ms=100.0,
                )
            return LLMResponse(
                text="Step 2.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            )

        mock_llm.generate = llm_with_cancel

        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
            max_iterations=10,
        )

        # Cancel after first tool result is processed (during the next LLM call)
        # Since our mock is synchronous, cancel before second generation
        original_generate = mock_llm.generate

        async def cancel_after_first(*args: object, **kwargs: object) -> LLMResponse:
            result_value = await original_generate(*args, **kwargs)
            if call_count >= 1:
                engine.cancel()
            return result_value

        mock_llm.generate = cancel_after_first

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.iterations >= 1


# =========================================================================
# Degraded mode
# =========================================================================


class TestDegradedMode:
    @pytest.mark.asyncio
    async def test_degraded_engine_raises(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
        )
        engine.degrade()

        with pytest.raises(RuntimeError, match="degraded"):
            await engine.execute(
                system_prompt="Help.",
                messages=messages,
                tool_defs=tool_defs,
                session_id=session_id,
            )

    @pytest.mark.asyncio
    async def test_degraded_stream_returns_empty(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
        )
        engine.degrade()

        chunks = [chunk async for chunk in engine.execute_stream(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )]
        assert chunks == [""]

    @pytest.mark.asyncio
    async def test_cancel_reset_for_new_invocation(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
        )

        engine.cancel()
        assert engine._cancel_event.is_set()

        engine.reset_cancellation()
        assert not engine._cancel_event.is_set()

        mock_llm.generate = AsyncMock(return_value=LLMResponse(
            text="Hello!",
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(5, 5, 10),
            provider="test",
            duration_ms=50.0,
        ))

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == "Hello!"


# =========================================================================
# No LLM manager
# =========================================================================


class TestNoLLM:
    @pytest.mark.asyncio
    async def test_no_llm_returns_empty(
        self,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == ""
        assert result.response.finish_reason == "error"

    @pytest.mark.asyncio
    async def test_no_llm_generate_method(
        self,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        mock_llm = MagicMock()
        del mock_llm.generate
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text == ""


# =========================================================================
# No tool router
# =========================================================================


class TestNoToolRouter:
    @pytest.mark.asyncio
    async def test_no_tool_router_returns_unavailable(
        self,
        mock_llm: MagicMock,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            event_bus=mock_event_bus,
        )

        mock_llm.generate = AsyncMock(side_effect=[
            LLMResponse(
                text="Calling tool.",
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={})],
                finish_reason="tool_calls",
                token_usage=TokenUsage(10, 5, 15),
                provider="test",
                duration_ms=100.0,
            ),
            LLMResponse(
                text="Unavailable.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(20, 10, 30),
                provider="test",
                duration_ms=200.0,
            ),
        ])

        result = await engine.execute(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        assert result.response.text is not None


# =========================================================================
# Streaming
# =========================================================================


class TestStreaming:
    @pytest.mark.asyncio
    async def test_stream_basic(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        async def stream_gen(*args: object, **kwargs: object) -> AsyncIterator[str]:
            yield "Hello "
            yield "world"

        mock_llm.generate_stream = stream_gen

        chunks = [chunk async for chunk in engine.execute_stream(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )]
        assert chunks == ["Hello ", "world"]

    @pytest.mark.asyncio
    async def test_stream_no_llm(
        self,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        chunks = [chunk async for chunk in engine.execute_stream(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )]
        assert chunks == [""]

    @pytest.mark.asyncio
    async def test_stream_no_generate_stream_method(
        self,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        class _NoStreamLLM:
            generate = AsyncMock()

        engine = ToolCallingEngine(
            llm_manager=_NoStreamLLM(),
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        chunks = [chunk async for chunk in engine.execute_stream(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )]
        assert chunks == [""]

    @pytest.mark.asyncio
    async def test_stream_cancellation(
        self,
        mock_llm: MagicMock,
        mock_tool_router: ToolRouter,
        mock_event_bus: MagicMock,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> None:
        engine = ToolCallingEngine(
            llm_manager=mock_llm,
            tool_router=mock_tool_router,
            event_bus=mock_event_bus,
        )

        async def stream_gen(*args: object, **kwargs: object) -> AsyncIterator[str]:
            yield "Hello"
            yield " world"

        mock_llm.generate_stream = stream_gen
        engine.cancel()

        chunks = [chunk async for chunk in engine.execute_stream(
            system_prompt="Help.",
            messages=messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )]
        assert len(chunks) == 0


# =========================================================================
# Signalence detection
# =========================================================================


class TestSignatureDetection:
    def test_tool_call_signature(self) -> None:
        sig = ToolCallingEngine._tool_call_signature([
            ToolCall(id="c1", name="calc", arguments={"x": 1}),
            ToolCall(id="c2", name="search", arguments={"q": "hello"}),
        ])
        assert "calc" in sig
        assert "search" in sig
        assert "hello" in sig

    def test_tool_call_signature_deterministic(self) -> None:
        sig1 = ToolCallingEngine._tool_call_signature([
            ToolCall(id="a", name="b", arguments={"z": 1, "a": 2}),
        ])
        sig2 = ToolCallingEngine._tool_call_signature([
            ToolCall(id="c", name="b", arguments={"a": 2, "z": 1}),
        ])
        assert sig1 == sig2

    def test_empty_tool_calls(self) -> None:
        sig = ToolCallingEngine._tool_call_signature([])
        assert sig == ""


# =========================================================================
# Empty response
# =========================================================================


class TestEmptyResponse:
    def test_empty_response(self) -> None:
        response = ToolCallingEngine._empty_response()
        assert response.text == ""
        assert response.tool_calls is None
        assert response.finish_reason == "error"
        assert response.provider == "tool_calling_engine"
