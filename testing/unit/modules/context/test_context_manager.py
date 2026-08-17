from typing import Any
"""Comprehensive tests for the context module.

Covers:
- RequestContext dataclass
- ConversationContext (messages, sliding window, token estimation)
- ContextBuilder (Any assembly)
- ContextManager (ModuleInterface lifecycle + build_context API)
- MemoryPort abstract interface
"""

from __future__ import annotations

import uuid

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.context._builder import ContextBuilder
from backend.modules.context._conversation import ConversationContext
from backend.modules.context._request import RequestContext
from backend.modules.context.context_module import ContextManager
from backend.modules.context.ports.memory_port import MemoryPort
from backend.types import Message, ModuleInterface
# =========================================================================
# RequestContext
# =========================================================================


class TestRequestContext:
    def test_creation_with_minimal_fields(self) -> None:
        rid = uuid.uuid4()
        rc = RequestContext(
            request_id=rid,
            session_id="sess_1",
            raw_text="Hello",
        )
        assert rc.request_id == rid
        assert rc.session_id == "sess_1"
        assert rc.raw_text == "Hello"
        assert rc.sanitized_text is None
        assert rc.source == "cli"
        assert rc.timestamp == 0.0
        assert rc.metadata == {}

    def test_creation_with_all_fields(self) -> None:
        rid = uuid.uuid4()
        rc = RequestContext(
            request_id=rid,
            session_id="sess_2",
            raw_text="Hi there",
            sanitized_text="hi there",
            source="voice",
            timestamp=1000.0,
            metadata={"language": "en"},
        )
        assert rc.sanitized_text == "hi there"
        assert rc.source == "voice"
        assert rc.timestamp == 1000.0
        assert rc.metadata == {"language": "en"}

    def test_mutable(self) -> None:
        rid = uuid.uuid4()
        rc = RequestContext(request_id=rid, session_id="s1", raw_text="x")
        rc.sanitized_text = "sanitized"
        assert rc.sanitized_text == "sanitized"

    def test_metadata_mutable(self) -> None:
        rid = uuid.uuid4()
        rc = RequestContext(request_id=rid, session_id="s1", raw_text="x")
        rc.metadata["key"] = "value"
        assert rc.metadata["key"] == "value"


# =========================================================================
# ConversationContext
# =========================================================================


class TestConversationContextCreation:
    def test_default_max_tokens(self) -> None:
        conv = ConversationContext(session_id="sess_1")
        assert conv.session_id == "sess_1"
        assert conv.max_tokens == 4096
        assert conv.messages == []
        assert conv.message_count == 0
        assert conv.token_count == 0

    def test_custom_max_tokens(self) -> None:
        conv = ConversationContext(session_id="sess_2", max_tokens=2048)
        assert conv.max_tokens == 2048

    def test_max_tokens_setter(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.max_tokens = 8192
        assert conv.max_tokens == 8192


class TestConversationContextMessages:
    def test_add_message(self) -> None:
        conv = ConversationContext(session_id="s1")
        msg = Message(role="user", content="Hello")
        conv.add_message(msg)
        assert conv.message_count == 1
        assert conv.messages[0] == msg

    def test_add_user_message(self) -> None:
        conv = ConversationContext(session_id="s1")
        msg = conv.add_user_message("Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert conv.message_count == 1

    def test_add_assistant_message(self) -> None:
        conv = ConversationContext(session_id="s1")
        msg = conv.add_assistant_message("Hi there")
        assert msg.role == "assistant"
        assert msg.content == "Hi there"

    def test_add_system_message(self) -> None:
        conv = ConversationContext(session_id="s1")
        msg = conv.add_system_message("You are a bot")
        assert msg.role == "system"
        assert msg.content == "You are a bot"

    def test_messages_returns_copy(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.add_user_message("Hello")
        msgs = conv.messages
        msgs.append(Message(role="user", content="extra"))
        assert conv.message_count == 1

    def test_get_recent_messages(self) -> None:
        conv = ConversationContext(session_id="s1")
        for i in range(5):
            conv.add_user_message(f"msg_{i}")
        recent = conv.get_recent_messages(limit=2)
        assert len(recent) == 2
        assert recent[0].content == "msg_3"
        assert recent[1].content == "msg_4"

    def test_get_recent_messages_default_limit(self) -> None:
        conv = ConversationContext(session_id="s1")
        for i in range(5):
            conv.add_user_message(f"msg_{i}")
        recent = conv.get_recent_messages()
        assert len(recent) == 5

    def test_clear(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.add_user_message("Hello")
        conv.add_assistant_message("World")
        conv.clear()
        assert conv.message_count == 0
        assert conv.messages == []


class TestConversationContextTokenEstimation:
    def test_empty_token_count(self) -> None:
        conv = ConversationContext(session_id="s1")
        assert conv.token_count == 0

    def test_token_count_with_one_message(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.add_user_message("Hello")
        # "Hello" = 5 chars -> 5//4 = 1 token + 4 overhead = 5
        assert conv.token_count == 5

    def test_token_count_with_multiple_messages(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.add_user_message("Hello")      # 1 + 4 = 5
        conv.add_assistant_message("World") # 1 + 4 = 5
        assert conv.token_count == 10

    def test_long_message_tokens(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.add_user_message("a" * 100)    # 100//4 = 25 + 4 = 29
        assert conv.token_count == 29

    def test_minimum_one_token_per_message_content(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.add_user_message("")           # max(1, 0//4) = 1 + 4 = 5
        assert conv.token_count == 5

    @staticmethod
    def test_estimate_tokens_static() -> None:
        assert ConversationContext._estimate_tokens("") == 1
        assert ConversationContext._estimate_tokens("a") == 1
        assert ConversationContext._estimate_tokens("aaaa") == 1
        assert ConversationContext._estimate_tokens("aaaaa") == 1
        assert ConversationContext._estimate_tokens("aaaaaaaa") == 2


class TestConversationContextSlidingWindow:
    def test_no_truncation_when_under_budget(self) -> None:
        conv = ConversationContext(session_id="s1", max_tokens=100)
        conv.add_user_message("Hello")
        conv.add_assistant_message("World")
        conv.apply_sliding_window()
        assert conv.message_count == 2

    def test_truncates_oldest_when_over_budget(self) -> None:
        conv = ConversationContext(session_id="s1", max_tokens=10)
        conv.add_user_message("Hello")  # 1 + 4 = 5
        conv.add_assistant_message("World")  # 1 + 4 = 5, total = 10
        conv.add_user_message("Extra")  # 1 + 4 = 5, total = 15 > 10
        conv.apply_sliding_window()
        assert conv.message_count == 2
        assert conv.messages[0].content == "World"
        assert conv.messages[1].content == "Extra"

    def test_preserves_at_least_one_message(self) -> None:
        conv = ConversationContext(session_id="s1", max_tokens=1)
        conv.add_user_message("Very long message content here")
        conv.apply_sliding_window()
        assert conv.message_count == 1

    def test_truncates_multiple_messages(self) -> None:
        conv = ConversationContext(session_id="s1", max_tokens=5)
        for i in range(5):
            conv.add_user_message(f"msg_{i}")
        conv.apply_sliding_window()
        assert conv.token_count <= 5 or conv.message_count == 1

    def test_sliding_window_with_empty_history(self) -> None:
        conv = ConversationContext(session_id="s1")
        conv.apply_sliding_window()
        assert conv.message_count == 0

    def test_sliding_window_preserves_order(self) -> None:
        conv = ConversationContext(session_id="s1", max_tokens=15)
        conv.add_user_message("one")     # 1 + 4 = 5
        conv.add_user_message("two")     # 1 + 4 = 5, total = 10
        conv.add_user_message("three")   # 1 + 4 = 5, total = 15
        conv.add_user_message("four")    # 1 + 4 = 5, total = 20 > 15
        conv.apply_sliding_window()
        assert conv.message_count == 3
        assert [m.content for m in conv.messages] == ["two", "three", "four"]


# =========================================================================
# ContextBuilder
# =========================================================================


class TestContextBuilder:
    def test_build_empty(self) -> None:
        ctx = ContextBuilder.build(system_prompt="You are a bot", messages=[])
        assert isinstance(ctx, Any)
        assert ctx.system_prompt == "You are a bot"
        assert ctx.messages == []
        assert ctx.token_count > 0

    def test_build_with_messages(self) -> None:
        msgs = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]
        ctx = ContextBuilder.build(
            system_prompt="System prompt",
            messages=msgs,
        )
        assert len(ctx.messages) == 2
        assert ctx.messages[0].content == "Hello"
        assert ctx.messages[1].content == "Hi"

    def test_build_returns_copy_of_messages(self) -> None:
        msgs = [Message(role="user", content="Hello")]
        ctx = ContextBuilder.build(system_prompt="SP", messages=msgs)
        msgs.append(Message(role="user", content="extra"))
        assert len(ctx.messages) == 1

    def test_build_context_is_frozen(self) -> None:
        ctx = ContextBuilder.build(system_prompt="SP", messages=[])
        with pytest.raises(AttributeError):
            ctx.system_prompt = "other"  # type: ignore[misc]

    def test_build_token_count(self) -> None:
        ctx = ContextBuilder.build(
            system_prompt="SP",  # 2//4 = 1 token
            messages=[
                Message(role="user", content="Hello"),  # 1 + 4 = 5
            ],
        )
        assert ctx.token_count == 1 + 5  # 6

    def test_max_tokens_parameter(self) -> None:
        ctx = ContextBuilder.build(
            system_prompt="SP",
            messages=[],
            max_tokens=2048,
        )
        assert ctx.token_count >= 0


# =========================================================================
# ContextManager — ModuleInterface lifecycle
# =========================================================================


class TestContextManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = ContextManager()
        assert mgr.degraded is False
        assert mgr.session_count == 0
        assert mgr.active_sessions == []

    @pytest.mark.asyncio
    async def test_async_init(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_sessions(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("sess_1", "Hello")
        assert mgr.session_count == 1
        await mgr.async_shutdown()
        assert mgr.session_count == 0
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()
        assert mgr.session_count == 0

    @pytest.mark.asyncio
    async def test_degrade_clears_sessions_and_sets_flag(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "Hello")
        mgr.degrade()
        assert mgr.degraded is True
        assert mgr.session_count == 0

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = ContextManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        import logging
        logger = logging.getLogger("test.context")
        mgr = ContextManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_custom_max_tokens(self) -> None:
        mgr = ContextManager(max_tokens=2048)
        assert mgr._max_tokens == 2048

    @pytest.mark.asyncio
    async def test_config_injection(self) -> None:
        config = {"key": "value"}
        mgr = ContextManager(config=config)
        assert mgr._config is config


# =========================================================================
# ContextManager — build_context
# =========================================================================


class TestContextManagerBuildContext:
    @pytest.mark.asyncio
    async def test_build_context_returns_context(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        ctx = mgr.build_context("sess_1", "Hello")
        assert isinstance(ctx, Any)
        assert ctx.system_prompt == ""
        assert len(ctx.messages) == 1
        assert ctx.messages[0].role == "user"
        assert ctx.messages[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_build_context_with_system_prompt(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        ctx = mgr.build_context("s1", "Hello", system_prompt="You are a bot")
        assert ctx.system_prompt == "You are a bot"

    @pytest.mark.asyncio
    async def test_build_context_accumulates_messages(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "Hello")
        mgr.build_context("s1", "How are you?")
        ctx = mgr.build_context("s1", "Fine")
        assert len(ctx.messages) == 3
        assert ctx.messages[0].content == "Hello"
        assert ctx.messages[1].content == "How are you?"
        assert ctx.messages[2].content == "Fine"

    @pytest.mark.asyncio
    async def test_build_context_different_sessions(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "Message for s1")
        mgr.build_context("s2", "Message for s2")
        ctx1 = mgr.build_context("s1", "Second for s1")
        ctx2 = mgr.build_context("s2", "Second for s2")
        assert len(ctx1.messages) == 2
        assert len(ctx2.messages) == 2
        assert ctx1.messages[0].content == "Message for s1"
        assert ctx2.messages[0].content == "Message for s2"

    @pytest.mark.asyncio
    async def test_build_context_token_count(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        ctx = mgr.build_context("s1", "Hello")
        assert ctx.token_count > 0

    @pytest.mark.asyncio
    async def test_build_context_triggers_sliding_window(self) -> None:
        mgr = ContextManager(max_tokens=10)
        await mgr.async_init()
        mgr.build_context("s1", "Hello")       # 1 + 4 = 5, total = 5
        mgr.build_context("s1", "World")       # 1 + 4 = 5, total = 10
        ctx = mgr.build_context("s1", "!!!!!")  # 1 + 4 = 5, total = 15 > 10
        assert len(ctx.messages) == 2
        assert ctx.messages[0].content == "World"
        assert ctx.messages[1].content == "!!!!!"

    @pytest.mark.asyncio
    async def test_build_context_degraded_raises(self) -> None:
        mgr = ContextManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.build_context("s1", "Hello")


# =========================================================================
# ContextManager — session management
# =========================================================================


class TestContextManagerSessions:
    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        assert mgr.get_session("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_session_after_build(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "Hello")
        conv = mgr.get_session("s1")
        assert conv is not None
        assert conv.session_id == "s1"
        assert conv.message_count == 1

    @pytest.mark.asyncio
    async def test_get_or_create_session_creates_new(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        conv = mgr.get_or_create_session("new_session")
        assert conv is not None
        assert conv.session_id == "new_session"
        assert conv.message_count == 0

    @pytest.mark.asyncio
    async def test_get_or_create_session_returns_existing(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "Hello")
        conv = mgr.get_or_create_session("s1")
        assert conv.message_count == 1

    @pytest.mark.asyncio
    async def test_reset_session(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "Hello")
        mgr.build_context("s1", "World")
        mgr.reset_session("s1")
        conv = mgr.get_session("s1")
        assert conv is not None
        assert conv.message_count == 0

    @pytest.mark.asyncio
    async def test_reset_nonexistent_session_is_safe(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.reset_session("nonexistent")
        assert mgr.session_count == 0

    @pytest.mark.asyncio
    async def test_remove_session(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "Hello")
        assert mgr.session_count == 1
        mgr.remove_session("s1")
        assert mgr.session_count == 0
        assert mgr.get_session("s1") is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent_session_is_safe(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.remove_session("nonexistent")
        assert mgr.session_count == 0

    @pytest.mark.asyncio
    async def test_active_sessions(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        mgr.build_context("s1", "A")
        mgr.build_context("s2", "B")
        mgr.build_context("s3", "C")
        sessions = mgr.active_sessions
        assert len(sessions) == 3
        assert "s1" in sessions
        assert "s2" in sessions
        assert "s3" in sessions

    @pytest.mark.asyncio
    async def test_session_count(self) -> None:
        mgr = ContextManager()
        await mgr.async_init()
        assert mgr.session_count == 0
        mgr.build_context("s1", "A")
        assert mgr.session_count == 1
        mgr.build_context("s2", "B")
        assert mgr.session_count == 2


# =========================================================================
# MemoryPort abstract interface
# =========================================================================


class TestMemoryPort:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            MemoryPort()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_implementation(self) -> None:
        class InMemoryMemoryPort(MemoryPort):
            async def store_message(self, session_id: str, message: Message) -> None:
                pass

            async def get_history(self, session_id: str, limit: int = 50) -> list[Message]:
                return []

            async def store_setting(self, key: str, value: object) -> None:
                pass

            async def get_setting(self, key: str) -> object | None:
                return None

            async def health_check(self) -> bool:
                return True

        port = InMemoryMemoryPort()
        assert isinstance(port, MemoryPort)
        result = await port.health_check()
        assert result is True


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_context_manager_conforms_to_protocol(self) -> None:
        assert isinstance(ContextManager(), ModuleInterface)

    def test_context_manager_has_required_methods(self) -> None:
        mgr = ContextManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
