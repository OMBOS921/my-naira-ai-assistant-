from typing import Any
"""Comprehensive tests for the conversation module.

Covers:
- ConversationState enum
- ConversationSession dataclass
- ConversationMemoryBridge
- ConversationHistory (merge, deduplicate, sliding window)
- ConversationRouter (routing, session lifecycle, cleanup)
- ConversationPipeline (full request processing flow)
- ConversationManager (ModuleInterface, lifecycle, process_request, idle cleanup)
- Session timeout management
- Event integration
- Any merging
"""

from __future__ import annotations

import logging
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.conversation._bridge import ConversationMemoryBridge
from backend.modules.conversation._history import ConversationHistory
from backend.modules.conversation._pipeline import ConversationPipeline
from backend.modules.conversation._router import ConversationRouter
from backend.modules.conversation._session import ConversationSession
from backend.modules.conversation._state import ConversationState
from backend.modules.conversation.conversation_module import ConversationManager
from backend.types import (
    Any, Message, ModuleInterface, UserRequest, UserResponse
)

# =========================================================================
# ConversationState
# =========================================================================


class TestConversationState:
    def test_state_values(self) -> None:
        assert ConversationState.ACTIVE == "ACTIVE"
        assert ConversationState.IDLE == "IDLE"
        assert ConversationState.PROCESSING == "PROCESSING"
        assert ConversationState.TIMEOUT == "TIMEOUT"
        assert ConversationState.CLOSED == "CLOSED"

    def test_state_is_string_enum(self) -> None:
        assert isinstance(ConversationState.ACTIVE, str)
        assert ConversationState.ACTIVE.value == "ACTIVE"

    def test_all_states_defined(self) -> None:
        expected = {"ACTIVE", "IDLE", "PROCESSING", "TIMEOUT", "CLOSED"}
        actual = {s.value for s in ConversationState}
        assert actual == expected


# =========================================================================
# ConversationSession
# =========================================================================


class TestConversationSessionCreation:
    def test_default_creation(self) -> None:
        session = ConversationSession(session_id="sess_1")
        assert session.session_id == "sess_1"
        assert session.state == ConversationState.ACTIVE
        assert session.message_count == 0
        assert session.metadata == {}
        assert session.timeout_seconds == 300.0
        assert session.is_active

    def test_custom_timeout(self) -> None:
        session = ConversationSession(session_id="s1", timeout_seconds=600.0)
        assert session.timeout_seconds == 600.0

    def test_initial_last_activity(self) -> None:
        now = time.time()
        session = ConversationSession(session_id="s1")
        assert session.last_activity >= now
        assert session.created_at >= now

    def test_custom_state(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.IDLE
        )
        assert session.state == ConversationState.IDLE

    def test_custom_metadata(self) -> None:
        session = ConversationSession(
            session_id="s1", metadata={"source": "cli"}
        )
        assert session.metadata == {"source": "cli"}


class TestConversationSessionTouch:
    def test_touch_updates_activity(self) -> None:
        session = ConversationSession(session_id="s1")
        old = session.last_activity
        time.sleep(0.01)
        session.touch()
        assert session.last_activity > old

    def test_touch_sets_active(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.IDLE
        )
        session.touch()
        assert session.state == ConversationState.ACTIVE

    def test_touch_does_not_change_processing(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.PROCESSING
        )
        session.touch()
        assert session.state == ConversationState.PROCESSING


class TestConversationSessionExpiry:
    def test_fresh_session_not_expired(self) -> None:
        session = ConversationSession(session_id="s1")
        assert not session.is_expired

    def test_closed_is_expired(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.CLOSED
        )
        assert session.is_expired

    def test_timeout_is_expired(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.TIMEOUT
        )
        assert session.is_expired

    def test_expired_by_timeout(self) -> None:
        session = ConversationSession(
            session_id="s1", timeout_seconds=10.0
        )
        session.last_activity = 1000.0
        with patch("backend.modules.conversation._session.time") as mock_time:
            mock_time.time.return_value = 1011.0
            assert session.is_expired

    def test_idle_duration(self) -> None:
        session = ConversationSession(session_id="s1")
        session.last_activity = 1000.0
        with patch("backend.modules.conversation._session.time") as mock_time:
            mock_time.time.return_value = 1005.0
            assert 4.9 <= session.idle_duration <= 5.1

    def test_is_active_false_when_closed(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.CLOSED
        )
        assert not session.is_active

    def test_is_active_false_when_timed_out(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.TIMEOUT
        )
        assert not session.is_active

    def test_is_active_true_when_processing(self) -> None:
        session = ConversationSession(
            session_id="s1", state=ConversationState.PROCESSING
        )
        assert session.is_active


# =========================================================================
# ConversationMemoryBridge
# =========================================================================


class TestConversationMemoryBridge:
    @pytest.mark.asyncio
    async def test_bridge_without_memory(self) -> None:
        bridge = ConversationMemoryBridge()
        assert not bridge.available
        history = await bridge.get_history("s1")
        assert history == []
        healthy = await bridge.health_check()
        assert not healthy

    @pytest.mark.asyncio
    async def test_bridge_with_memory(self) -> None:
        mock_memory = MagicMock()
        mock_memory.store_message = AsyncMock()
        mock_memory.get_history = AsyncMock(return_value=[
            Message(role="user", content="Hello"),
        ])

        bridge = ConversationMemoryBridge(memory_manager=mock_memory)
        assert bridge.available

        msg = Message(role="user", content="Hi")
        await bridge.store_message("s1", msg)
        mock_memory.store_message.assert_called_once_with("s1", msg)

        history = await bridge.get_history("s1")
        assert len(history) == 1
        assert history[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_store_messages(self) -> None:
        mock_memory = MagicMock()
        mock_memory.store_message = AsyncMock()

        bridge = ConversationMemoryBridge(memory_manager=mock_memory)
        msgs = [
            Message(role="user", content="A"),
            Message(role="assistant", content="B"),
        ]
        await bridge.store_messages("s1", msgs)
        assert mock_memory.store_message.call_count == 2

    @pytest.mark.asyncio
    async def test_store_message_without_memory_raises(self) -> None:
        bridge = ConversationMemoryBridge()
        with pytest.raises(RuntimeError, match="no MemoryManager configured"):
            await bridge.store_message("s1", Message(role="user", content="Hi"))

    @pytest.mark.asyncio
    async def test_health_check_with_adapter(self) -> None:
        mock_adapter = MagicMock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_memory = MagicMock()
        mock_memory.memory_adapter = mock_adapter

        bridge = ConversationMemoryBridge(memory_manager=mock_memory)
        healthy = await bridge.health_check()
        assert healthy
        mock_adapter.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_without_adapter(self) -> None:
        mock_memory = MagicMock(spec=[])
        bridge = ConversationMemoryBridge(memory_manager=mock_memory)
        healthy = await bridge.health_check()
        assert healthy


# =========================================================================
# ConversationHistory
# =========================================================================


class TestConversationHistory:
    @pytest.fixture
    def bridge(self) -> ConversationMemoryBridge:
        mock_memory = MagicMock()
        mock_memory.get_history = AsyncMock(return_value=[])
        return ConversationMemoryBridge(memory_manager=mock_memory)

    @pytest.mark.asyncio
    async def test_load_persistent_history(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        messages = await history.load_persistent_history("s1")
        assert messages == []

    @pytest.mark.asyncio
    async def test_load_persistent_history_with_data(self) -> None:
        mock_memory = MagicMock()
        mock_memory.get_history = AsyncMock(return_value=[
            Message(role="user", content="Old message"),
        ])
        bridge = ConversationMemoryBridge(memory_manager=mock_memory)
        history = ConversationHistory(bridge)
        messages = await history.load_persistent_history("s1", limit=10)
        assert len(messages) == 1
        assert messages[0].content == "Old message"

    def test_merge_empty(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        result = history.merge_context([], [])
        assert result == []

    def test_merge_only_persistent(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        persistent = [Message(role="user", content="A")]
        result = history.merge_context(persistent, [])
        assert len(result) == 1
        assert result[0].content == "A"

    def test_merge_only_current(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        current = [Message(role="user", content="B")]
        result = history.merge_context([], current)
        assert len(result) == 1
        assert result[0].content == "B"

    def test_merge_concatenates(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        persistent = [Message(role="user", content="A")]
        current = [Message(role="assistant", content="B")]
        result = history.merge_context(persistent, current)
        assert len(result) == 2
        assert result[0].content == "A"
        assert result[1].content == "B"

    def test_merge_with_persistent_alias(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        result = history.merge_with_persistent(
            [Message(role="user", content="B")],
            [Message(role="user", content="A")],
        )
        assert len(result) == 2

    def test_deduplicate_consecutive_same(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        msgs = [
            Message(role="user", content="Hello"),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="World"),
        ]
        result = history.merge_context([], msgs)
        assert len(result) == 2

    def test_deduplicate_preserves_different(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge)
        msgs = [
            Message(role="user", content="A"),
            Message(role="assistant", content="B"),
            Message(role="user", content="A"),
        ]
        result = history.merge_context([], msgs)
        assert len(result) == 3

    def test_sliding_window_truncates(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge, max_tokens=10)
        msgs = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="World"),
            Message(role="user", content="Extra"),
        ]
        result = history.merge_context([], msgs)
        assert len(result) <= 2

    def test_sliding_window_preserves_one(self, bridge: ConversationMemoryBridge) -> None:
        history = ConversationHistory(bridge, max_tokens=1)
        msgs = [Message(role="user", content="A" * 100)]
        result = history.merge_context([], msgs)
        assert len(result) == 1

    def test_estimate_tokens(self, bridge: ConversationMemoryBridge) -> None:
        assert ConversationHistory._estimate_tokens("") == 1
        assert ConversationHistory._estimate_tokens("a") == 1
        assert ConversationHistory._estimate_tokens("aaaa") == 1
        assert ConversationHistory._estimate_tokens("aaaaaaaa") == 2


# =========================================================================
# ConversationRouter
# =========================================================================


class TestConversationRouterCreation:
    def test_default_creation(self) -> None:
        router = ConversationRouter()
        assert router.session_count == 0
        assert router.active_sessions == []
        assert router.all_sessions == []

    def test_custom_timeout(self) -> None:
        router = ConversationRouter(session_timeout=600.0)
        session = router.route("s1")
        assert session.timeout_seconds == 600.0


class TestConversationRouterRoute:
    def test_route_creates_new_session(self) -> None:
        router = ConversationRouter()
        session = router.route("s1")
        assert session.session_id == "s1"
        assert session.state == ConversationState.ACTIVE
        assert router.session_count == 1

    def test_route_returns_existing_session(self) -> None:
        router = ConversationRouter()
        s1 = router.route("s1")
        s2 = router.route("s1")
        assert s1 is s2
        assert router.session_count == 1

    def test_route_multiple_sessions(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        router.route("s2")
        router.route("s3")
        assert router.session_count == 3
        assert len(router.active_sessions) == 3

    def test_route_touches_session(self) -> None:
        router = ConversationRouter()
        s1 = router.route("s1")
        old = s1.last_activity
        time.sleep(0.01)
        s2 = router.route("s1")
        assert s2.last_activity > old

    def test_route_revives_timed_out(self) -> None:
        router = ConversationRouter()
        session = router.route("s1")
        session.state = ConversationState.TIMEOUT
        revived = router.route("s1")
        assert revived.state == ConversationState.ACTIVE
        assert revived is session


class TestConversationRouterSessionManagement:
    def test_get_session(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        session = router.get_session("s1")
        assert session is not None
        assert session.session_id == "s1"

    def test_get_session_nonexistent(self) -> None:
        router = ConversationRouter()
        assert router.get_session("nonexistent") is None

    def test_has_session(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        assert router.has_session("s1")
        assert not router.has_session("nonexistent")

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        await router.close_session("s1")
        session = router.get_session("s1")
        assert session is not None
        assert session.state == ConversationState.CLOSED

    @pytest.mark.asyncio
    async def test_close_nonexistent_session(self) -> None:
        router = ConversationRouter()
        await router.close_session("nonexistent")
        assert router.session_count == 0

    def test_remove_session(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        router.remove_session("s1")
        assert router.get_session("s1") is None
        assert router.session_count == 0

    def test_remove_nonexistent(self) -> None:
        router = ConversationRouter()
        router.remove_session("nonexistent")
        assert router.session_count == 0

    def test_active_sessions(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        router.route("s2")
        router.route("s3")
        s2 = router.get_session("s2")
        assert s2 is not None
        s2.state = ConversationState.CLOSED
        active = router.active_sessions
        assert "s1" in active
        assert "s2" not in active
        assert "s3" in active

    def test_all_sessions(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        router.route("s2")
        assert set(router.all_sessions) == {"s1", "s2"}

    def test_cleanup_expired(self) -> None:
        router = ConversationRouter(session_timeout=10.0)
        s1 = router.route("s1")
        s2 = router.route("s2")
        s1.last_activity = 1000.0
        s2.last_activity = 1000.0
        with patch("backend.modules.conversation._session.time") as mock_time:
            mock_time.time.return_value = 1015.0
            timed_out = router.cleanup_expired()
            assert len(timed_out) == 2
            assert s1.state == ConversationState.TIMEOUT
            assert s2.state == ConversationState.TIMEOUT

    def test_cleanup_expired_skips_active(self) -> None:
        router = ConversationRouter(session_timeout=10.0)
        s1 = router.route("s1")
        s1.last_activity = 1000.0
        with patch("backend.modules.conversation._session.time") as mock_time:
            mock_time.time.return_value = 1005.0
            timed_out = router.cleanup_expired()
            assert timed_out == []

    def test_purge_closed(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        router.route("s2")
        router.get_session("s1").state = ConversationState.CLOSED  # type: ignore[union-attr]
        purged = router.purge_closed()
        assert "s1" in purged or router.session_count == 1

    def test_get_session_data(self) -> None:
        router = ConversationRouter()
        router.route("s1")
        data = router.get_session_data("s1")
        assert data is not None

    def test_get_session_data_nonexistent(self) -> None:
        router = ConversationRouter()
        assert router.get_session_data("nonexistent") is None


# =========================================================================
# ConversationPipeline
# =========================================================================


class TestConversationPipeline:
    @pytest.fixture
    def mock_context_manager(self) -> MagicMock:
        mgr = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.messages = [Message(role="user", content="Hello")]
        mock_ctx.system_prompt = "Test prompt"
        mgr.build_context = MagicMock(return_value=mock_ctx)

        mock_conv = MagicMock()
        mock_conv.add_assistant_message = MagicMock()
        mgr.get_session = MagicMock(return_value=mock_conv)
        return mgr

    @pytest.fixture
    def mock_prompt_manager(self) -> MagicMock:
        mgr = MagicMock()
        mgr.compile = MagicMock(return_value="Compiled system prompt")
        return mgr

    @pytest.fixture
    def mock_llm_manager(self) -> MagicMock:
        mgr = MagicMock()
        mgr.generate = AsyncMock(return_value=Any(
            text="Hello, world!",
            tool_calls=None,
            finish_reason="stop",
            token_usage=Any(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            provider="test",
            duration_ms=100.0,
        ))
        return mgr

    @pytest.fixture
    def mock_memory(self) -> MagicMock:
        mgr = MagicMock()
        mgr.store_message = AsyncMock()
        return mgr

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        bus = MagicMock()
        bus.emit = AsyncMock()
        return bus

    @pytest.fixture
    def user_request(self) -> UserRequest:
        return UserRequest(
            id=uuid.uuid4(),
            source="cli",
            text="Hello!",
            session_id="test_session",
            timestamp=time.time(),
        )

    @pytest.mark.asyncio
    async def test_process_success(
        self,
        mock_context_manager: MagicMock,
        mock_prompt_manager: MagicMock,
        mock_llm_manager: MagicMock,
        mock_memory: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        bridge = ConversationMemoryBridge(memory_manager=mock_memory)
        history = ConversationHistory(bridge)
        pipeline = ConversationPipeline(
            context_manager=mock_context_manager,
            prompt_manager=mock_prompt_manager,
            llm_manager=mock_llm_manager,
            bridge=bridge,
            history=history,
            event_bus=mock_event_bus,
        )

        session = ConversationSession(session_id="test_session")
        response = await pipeline.process(user_request, session)

        assert isinstance(response, UserResponse)
        assert response.text == "Hello, world!"
        assert response.request_id == user_request.id
        assert response.source == "cli"
        assert response.duration_ms > 0

        mock_prompt_manager.compile.assert_called_once()
        mock_context_manager.build_context.assert_called_once_with(
            "test_session", "Hello!", "Compiled system prompt"
        )
        mock_llm_manager.generate.assert_called_once()
        assert mock_memory.store_message.call_count == 2
        mock_event_bus.emit.assert_called()

    @pytest.mark.asyncio
    async def test_process_degraded(self, user_request: UserRequest) -> None:
        pipeline = ConversationPipeline()
        pipeline.degrade()
        session = ConversationSession(session_id="s1")
        response = await pipeline.process(user_request, session)
        assert "degraded" in response.text.lower()

    @pytest.mark.asyncio
    async def test_process_without_dependencies(
        self, user_request: UserRequest
    ) -> None:
        pipeline = ConversationPipeline()
        session = ConversationSession(session_id="s1")
        response = await pipeline.process(user_request, session)
        assert isinstance(response, UserResponse)
        assert response.request_id == user_request.id

    @pytest.mark.asyncio
    async def test_process_error_handling(
        self,
        mock_llm_manager: MagicMock,
        user_request: UserRequest,
    ) -> None:
        mock_llm_manager.generate = AsyncMock(
            side_effect=RuntimeError("LLM failed")
        )
        pipeline = ConversationPipeline(llm_manager=mock_llm_manager)
        session = ConversationSession(session_id="s1")
        response = await pipeline.process(user_request, session)
        assert "error" in response.text.lower()

    @pytest.mark.asyncio
    async def test_process_sets_session_state(
        self,
        mock_context_manager: MagicMock,
        mock_prompt_manager: MagicMock,
        mock_llm_manager: MagicMock,
        user_request: UserRequest,
    ) -> None:
        bridge = ConversationMemoryBridge()
        pipeline = ConversationPipeline(
            context_manager=mock_context_manager,
            prompt_manager=mock_prompt_manager,
            llm_manager=mock_llm_manager,
            bridge=bridge,
        )
        session = ConversationSession(session_id="s1")
        await pipeline.process(user_request, session)
        assert session.state == ConversationState.ACTIVE
        assert session.message_count == 2

    @pytest.mark.asyncio
    async def test_process_increments_message_count(
        self,
        mock_context_manager: MagicMock,
        mock_prompt_manager: MagicMock,
        mock_llm_manager: MagicMock,
        mock_memory: MagicMock,
        user_request: UserRequest,
    ) -> None:
        bridge = ConversationMemoryBridge(memory_manager=mock_memory)
        pipeline = ConversationPipeline(
            context_manager=mock_context_manager,
            prompt_manager=mock_prompt_manager,
            llm_manager=mock_llm_manager,
            bridge=bridge,
        )
        session = ConversationSession(session_id="s1")
        assert session.message_count == 0
        await pipeline.process(user_request, session)
        assert session.message_count == 2

    @pytest.mark.asyncio
    async def test_pipeline_event_emission(
        self,
        mock_context_manager: MagicMock,
        mock_prompt_manager: MagicMock,
        mock_llm_manager: MagicMock,
        mock_event_bus: MagicMock,
        user_request: UserRequest,
    ) -> None:
        bridge = ConversationMemoryBridge()
        pipeline = ConversationPipeline(
            context_manager=mock_context_manager,
            prompt_manager=mock_prompt_manager,
            llm_manager=mock_llm_manager,
            bridge=bridge,
            event_bus=mock_event_bus,
        )
        session = ConversationSession(session_id="s1")
        await pipeline.process(user_request, session)
        assert mock_event_bus.emit.call_count >= 2


# =========================================================================
# ConversationManager — ModuleInterface
# =========================================================================


class TestConversationManagerModuleInterface:
    def test_conversation_manager_conforms_to_protocol(self) -> None:
        assert isinstance(ConversationManager(), ModuleInterface)

    def test_conversation_manager_has_required_methods(self) -> None:
        mgr = ConversationManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")


# =========================================================================
# ConversationManager — Lifecycle
# =========================================================================


class TestConversationManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = ConversationManager()
        assert not mgr.degraded
        assert not mgr.initialized
        assert mgr.session_count == 0

    @pytest.mark.asyncio
    async def test_async_init(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        assert mgr.initialized
        assert not mgr.degraded
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_resets_state(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        assert not mgr.initialized
        assert not mgr.degraded
        assert mgr.session_count == 0

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = ConversationManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = logging.getLogger("test.conversation")
        mgr = ConversationManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_config_injection(self) -> None:
        config = {"key": "value"}
        mgr = ConversationManager(config=config)
        assert mgr._config is config


# =========================================================================
# ConversationManager — process_request
# =========================================================================


class TestConversationManagerProcessRequest:
    @pytest.fixture
    def mgr(self) -> ConversationManager:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=Any(
            text="Hi there!",
            tool_calls=None,
            finish_reason="stop",
            token_usage=Any(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            provider="test",
            duration_ms=50.0,
        ))
        mock_ctx = MagicMock()
        mock_ctx.build_context = MagicMock(
            return_value=MagicMock(
                messages=[Message(role="user", content="Hello")],
                system_prompt="SP",
            )
        )
        mock_ctx.get_session = MagicMock(
            return_value=MagicMock(add_assistant_message=MagicMock())
        )
        return ConversationManager(
            llm_manager=mock_llm,
            context_manager=mock_ctx,
            prompt_manager=MagicMock(compile=MagicMock(return_value="SP")),
        )

    @pytest.mark.asyncio
    async def test_process_request_returns_response(self, mgr: ConversationManager) -> None:
        await mgr.async_init()
        request = UserRequest(
            id=uuid.uuid4(),
            source="cli",
            text="Hello",
            session_id="s1",
            timestamp=time.time(),
        )
        response = await mgr.process_request(request)
        assert isinstance(response, UserResponse)
        assert response.text == "Hi there!"
        assert response.request_id == request.id
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_process_request_creates_session(self, mgr: ConversationManager) -> None:
        await mgr.async_init()
        request = UserRequest(
            id=uuid.uuid4(),
            source="cli",
            text="Hello",
            session_id="session_test",
            timestamp=time.time(),
        )
        await mgr.process_request(request)
        assert mgr.has_session("session_test")
        assert mgr.session_count == 1
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_process_request_degraded_raises(self) -> None:
        mgr = ConversationManager()
        mgr.degrade()
        request = UserRequest(
            id=uuid.uuid4(),
            source="cli",
            text="Hello",
            session_id="s1",
            timestamp=time.time(),
        )
        with pytest.raises(ModuleDegradedError):
            await mgr.process_request(request)

    @pytest.mark.asyncio
    async def test_process_request_multiple_sessions(self, mgr: ConversationManager) -> None:
        await mgr.async_init()
        req1 = UserRequest(
            id=uuid.uuid4(), source="cli", text="A", session_id="s1", timestamp=time.time()
        )
        req2 = UserRequest(
            id=uuid.uuid4(), source="cli", text="B", session_id="s2", timestamp=time.time()
        )
        req3 = UserRequest(
            id=uuid.uuid4(), source="cli", text="C", session_id="s1", timestamp=time.time()
        )
        await mgr.process_request(req1)
        await mgr.process_request(req2)
        await mgr.process_request(req3)
        assert mgr.session_count == 2
        assert sorted(mgr.active_sessions) == ["s1", "s2"]
        await mgr.async_shutdown()


# =========================================================================
# ConversationManager — Session management
# =========================================================================


class TestConversationManagerSessions:
    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        assert mgr.get_session("nonexistent") is None
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_get_session_after_request(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=Any(
            text="OK", tool_calls=None, finish_reason="stop",
            token_usage=Any(1, 1, 2), provider="test", duration_ms=10.0,
        ))
        mgr = ConversationManager(
            llm_manager=mock_llm,
            context_manager=MagicMock(
                build_context=MagicMock(
                    return_value=MagicMock(messages=[], system_prompt="")
                ),
                get_session=MagicMock(return_value=None),
            ),
            prompt_manager=MagicMock(compile=MagicMock(return_value="")),
        )
        await mgr.async_init()
        request = UserRequest(
            id=uuid.uuid4(), source="cli", text="Hi", session_id="s1", timestamp=time.time(),
        )
        await mgr.process_request(request)
        session = mgr.get_session("s1")
        assert session is not None
        assert session.session_id == "s1"
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_close_session(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        mgr._router.route("s1")
        await mgr.close_session("s1")
        session = mgr.get_session("s1")
        assert session is not None
        assert session.state == ConversationState.CLOSED
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_remove_session(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        mgr._router.route("s1")
        mgr.remove_session("s1")
        assert mgr.get_session("s1") is None
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_active_sessions(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        mgr._router.route("s1")
        mgr._router.route("s2")
        assert set(mgr.active_sessions) == {"s1", "s2"}
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_session_count(self) -> None:
        mgr = ConversationManager()
        await mgr.async_init()
        assert mgr.session_count == 0
        mgr._router.route("s1")
        assert mgr.session_count == 1
        await mgr.async_shutdown()


# =========================================================================
# ConversationManager — Idle cleanup
# =========================================================================


class TestConversationManagerIdleCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_task_starts_on_init(self) -> None:
        mgr = ConversationManager(idle_cleanup_interval=0.1)
        await mgr.async_init()
        assert mgr._cleanup_task is not None
        assert not mgr._cleanup_task.done()
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_cleanup_task_stops_on_shutdown(self) -> None:
        mgr = ConversationManager(idle_cleanup_interval=0.1)
        await mgr.async_init()
        await mgr.async_shutdown()
        assert mgr._cleanup_task is None or mgr._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_cleanup_task_stops_on_degrade(self) -> None:
        mgr = ConversationManager(idle_cleanup_interval=0.1)
        await mgr.async_init()
        mgr.degrade()
        assert mgr._cleanup_task is None or mgr._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self) -> None:
        with patch("backend.modules.conversation.conversation_module.asyncio.sleep"):
            mgr = ConversationManager(
                session_timeout=0.01,
                idle_cleanup_interval=0.01,
            )
            mgr._event_bus = MagicMock()
            mgr._event_bus.emit = AsyncMock()
            await mgr.async_init()

            session = mgr._router.route("s1")
            session.last_activity = 0.0  # force expired

            timed_out = mgr._router.cleanup_expired()
            assert len(timed_out) >= 1
            assert session.state == ConversationState.TIMEOUT
            await mgr.async_shutdown()


# =========================================================================
# ConversationManager — Session timeout management
# =========================================================================


class TestSessionTimeout:
    def test_custom_timeout_per_session(self) -> None:
        session = ConversationSession(session_id="s1", timeout_seconds=30.0)
        assert session.timeout_seconds == 30.0

    def test_timeout_detection(self) -> None:
        session = ConversationSession(session_id="s1", timeout_seconds=5.0)
        session.last_activity = 1000.0
        with patch("backend.modules.conversation._session.time") as mock_time:
            mock_time.time.return_value = 1003.0
            assert not session.is_expired
            mock_time.time.return_value = 1006.0
            assert session.is_expired

    def test_router_timeout_applied_to_new_sessions(self) -> None:
        router = ConversationRouter(session_timeout=60.0)
        session = router.route("s1")
        assert session.timeout_seconds == 60.0


# =========================================================================
# ConversationManager — Property accessors
# =========================================================================


class TestConversationManagerProperties:
    @pytest.mark.asyncio
    async def test_router_property(self) -> None:
        mgr = ConversationManager()
        assert isinstance(mgr.router, ConversationRouter)

    @pytest.mark.asyncio
    async def test_pipeline_property(self) -> None:
        mgr = ConversationManager()
        assert isinstance(mgr.pipeline, ConversationPipeline)

    @pytest.mark.asyncio
    async def test_bridge_property(self) -> None:
        mgr = ConversationManager()
        assert isinstance(mgr.bridge, ConversationMemoryBridge)
