from __future__ import annotations
from typing import Any
"""Tests for shared core types (backend/types.py).

21_System_Contracts.md §7, §10, §15 — Covers frozen dataclasses,
type aliases, enums, and module interface protocols.
"""



import uuid

import pytest

from backend.types import (
    JSON, Event, Message, ModuleInterface, RequestSource, SearchResult, ToolCall, ToolDef, ToolResult, UserRequest, UserResponse, ValidationResult
)


class TestTypeAliases:
    def test_json_is_dict(self) -> None:
        data: JSON = {"key": "value", "num": 42}
        assert isinstance(data, dict)

    def test_finish_reason_literals(self) -> None:
        valid: Any = "stop"
        assert valid in ("stop", "tool_calls", "length", "error")

    def test_request_source_literals(self) -> None:
        source: RequestSource = "cli"
        assert source in ("cli", "websocket", "voice")


class TestTokenUsage:
    def test_creation(self) -> None:
        t = Any(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert t.prompt_tokens == 10
        assert t.completion_tokens == 20
        assert t.total_tokens == 30

    def test_immutable(self) -> None:
        t = Any(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        with pytest.raises(AttributeError):
            t.prompt_tokens = 99  # type: ignore[misc]

    def test_repr(self) -> None:
        t = Any(1, 2, 3)
        assert "prompt_tokens=1" in repr(t)
        assert "total_tokens=3" in repr(t)


class TestToolCall:
    def test_creation(self) -> None:
        tc = ToolCall(id="call_1", name="search", arguments={"q": "hello"})
        assert tc.id == "call_1"
        assert tc.name == "search"
        assert tc.arguments == {"q": "hello"}

    def test_frozen(self) -> None:
        tc = ToolCall(id="c1", name="n", arguments={"a": 1})
        with pytest.raises(AttributeError):
            tc.id = "c2"  # type: ignore[misc]


class TestToolDef:
    def test_creation(self) -> None:
        td = ToolDef(
            name="search",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
        )
        assert td.name == "search"
        assert td.description == "Search the web"
        assert td.parameters["type"] == "object"


class TestMessage:
    def test_user_message(self) -> None:
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None

    def test_assistant_with_tool_calls(self) -> None:
        tc = ToolCall(id="c1", name="search", arguments={"q": "test"})
        msg = Message(role="assistant", content="", tool_calls=[tc])
        assert msg.tool_calls == [tc]

    def test_tool_result_message(self) -> None:
        msg = Message(role="tool", content='{"result": "ok"}', tool_call_id="c1")
        assert msg.tool_call_id == "c1"


class TestLLMResponse:
    def test_creation(self) -> None:
        usage = Any(10, 20, 30)
        resp = Any(
            text="Hello world",
            tool_calls=None,
            finish_reason="stop",
            token_usage=usage,
            provider="gemini",
            duration_ms=150.5,
        )
        assert resp.text == "Hello world"
        assert resp.finish_reason == "stop"
        assert resp.provider == "gemini"
        assert resp.duration_ms == 150.5

    def test_with_tool_calls(self) -> None:
        tc = ToolCall(id="c1", name="search", arguments={"q": "test"})
        usage = Any(1, 1, 2)
        resp = Any(
            text="",
            tool_calls=[tc],
            finish_reason="tool_calls",
            token_usage=usage,
            provider="gemini",
            duration_ms=100.0,
        )
        assert resp.tool_calls == [tc]
        assert resp.finish_reason == "tool_calls"
        assert resp.token_usage.total_tokens == 2


class TestUserRequest:
    def test_creation(self) -> None:
        req_id = uuid.uuid4()
        req = UserRequest(
            id=req_id,
            source="cli",
            text="Hello",
            session_id="sess_1",
            timestamp=1000.0,
        )
        assert req.id == req_id
        assert req.source == "cli"
        assert req.text == "Hello"
        assert req.session_id == "sess_1"
        assert req.timestamp == 1000.0
        assert req.metadata == {}

    def test_with_metadata(self) -> None:
        req = UserRequest(
            id=uuid.uuid4(),
            source="voice",
            text="Hi",
            session_id="s1",
            timestamp=1.0,
            metadata={"language": "en"},
        )
        assert req.metadata == {"language": "en"}


class TestUserResponse:
    def test_creation(self) -> None:
        req_id = uuid.uuid4()
        resp = UserResponse(
            request_id=req_id,
            text="Hello back",
            source="cli",
            duration_ms=200.0,
        )
        assert resp.request_id == req_id
        assert resp.text == "Hello back"
        assert resp.source == "cli"
        assert resp.duration_ms == 200.0


class TestContext:
    def test_creation(self) -> None:
        msgs = [Message(role="user", content="Hi")]
        ctx = Any(system_prompt="You are a bot", messages=msgs, token_count=5)
        assert ctx.system_prompt == "You are a bot"
        assert ctx.messages == msgs
        assert ctx.token_count == 5


class TestValidationResult:
    def test_pass_defaults(self) -> None:
        vr = ValidationResult(status="pass")
        assert vr.status == "pass"
        assert vr.sanitized_text is None
        assert vr.reason is None

    def test_rejected_with_reason(self) -> None:
        vr = ValidationResult(status="reject", reason="suspicious input")
        assert vr.status == "reject"
        assert vr.reason == "suspicious input"
        assert vr.sanitized_text is None

    def test_sanitized(self) -> None:
        vr = ValidationResult(status="sanitized", sanitized_text="safe text")
        assert vr.status == "sanitized"
        assert vr.sanitized_text == "safe text"


class TestToolResult:
    def test_success_with_output(self) -> None:
        tr = ToolResult(status="success", output="result data")
        assert tr.status == "success"
        assert tr.output == "result data"
        assert tr.error is None

    def test_error_with_message(self) -> None:
        tr = ToolResult(status="error", error="something broke")
        assert tr.status == "error"
        assert tr.error == "something broke"
        assert tr.output is None

    def test_timeout(self) -> None:
        tr = ToolResult(status="timeout")
        assert tr.status == "timeout"
        assert tr.output is None
        assert tr.error is None


class TestSearchResult:
    def test_creation(self) -> None:
        sr = SearchResult(
            source_id="doc_1",
            content="some content",
            score=0.95,
            metadata={"author": "test"},
        )
        assert sr.source_id == "doc_1"
        assert sr.content == "some content"
        assert sr.score == 0.95
        assert sr.metadata == {"author": "test"}

    def test_default_metadata(self) -> None:
        sr = SearchResult(source_id="d1", content="c", score=0.5)
        assert sr.metadata == {}


class TestEvent:
    def test_creation_with_defaults(self) -> None:
        ev = Event(type="system.test", source="orchestrator", data={"key": "val"})
        assert ev.type == "system.test"
        assert ev.source == "orchestrator"
        assert ev.data == {"key": "val"}
        assert ev.priority == "normal"
        assert ev.timestamp == 0.0

    def test_high_priority(self) -> None:
        ev = Event(type="system.shutdown", source="orchestrator", priority="high")
        assert ev.priority == "high"

    def test_low_priority(self) -> None:
        ev = Event(type="system.debug", source="test", priority="low")
        assert ev.priority == "low"


class TestModuleInterface:
    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(ModuleInterface, "__instancecheck__")

    def test_module_that_conforms(self) -> None:
        class GoodModule:
            async def async_init(self) -> None:
                pass

            async def async_shutdown(self) -> None:
                pass

            def degrade(self) -> None:
                pass

        assert isinstance(GoodModule(), ModuleInterface)

    def test_module_missing_methods(self) -> None:
        class PartialModule:
            async def async_init(self) -> None:
                pass

        instance = PartialModule()
        assert not isinstance(instance, ModuleInterface)
