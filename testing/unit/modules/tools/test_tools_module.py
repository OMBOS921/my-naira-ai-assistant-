"""Comprehensive tests for the tools module.

Covers:
- RetryPolicy
- ToolDefinition and ToolDef conversion
- ToolRegistry
- ToolValidation
- ToolPermission
- ToolExecutor
- ToolManager (ModuleInterface lifecycle + registration + execution + enable/disable)
- ToolProvider port
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.tools import RetryPolicy, ToolDefinition, ToolManager
from backend.modules.tools._executor import ToolExecutor
from backend.modules.tools._permissions import ToolPermission
from backend.modules.tools._registry import ToolRegistry
from backend.modules.tools._validation import ToolValidation
from backend.modules.tools.ports.tool_provider import ToolProvider
from backend.types import ModuleInterface, ToolCall, ToolDef, ToolResult
# =========================================================================
# Helpers
# =========================================================================


def _async_return(result: ToolResult) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
    """Create an async callable that returns *result*."""
    async def _handler(**kwargs: object) -> ToolResult:
        return result
    return _handler


def _td(name: str, **kw: object) -> ToolDefinition:
    """Shortcut to build a ToolDefinition with empty description."""
    kw.setdefault("description", "")
    return ToolDefinition(name=name, **kw)


# =========================================================================
# RetryPolicy
# =========================================================================


class TestRetryPolicy:
    def test_defaults(self) -> None:
        p = RetryPolicy()
        assert p.max_retries == 3
        assert p.base_delay == 1.0
        assert p.max_delay == 30.0
        assert p.backoff_multiplier == 2.0

    def test_custom_values(self) -> None:
        p = RetryPolicy(
            max_retries=5, base_delay=0.5, max_delay=10.0, backoff_multiplier=3.0
        )
        assert p.max_retries == 5
        assert p.base_delay == 0.5
        assert p.max_delay == 10.0
        assert p.backoff_multiplier == 3.0

    def test_frozen(self) -> None:
        p = RetryPolicy()
        with pytest.raises(AttributeError):
            p.max_retries = 99  # type: ignore[misc]


# =========================================================================
# ToolDefinition
# =========================================================================


class TestToolDefinition:
    def test_minimal(self) -> None:
        td = _td("echo")
        assert td.name == "echo"
        assert td.description == ""
        assert td.parameters == {}
        assert td.category == "general"
        assert td.enabled is True
        assert td.timeout_seconds == 30.0
        assert td.retry_policy == RetryPolicy()
        assert td.required_permissions == ()
        assert td.metadata == {}

    def test_all_fields(self) -> None:
        td = ToolDefinition(
            name="add",
            description="Adds two numbers",
            parameters={"type": "object", "properties": {"x": {"type": "number"}}},
            category="math",
            enabled=False,
            timeout_seconds=10.0,
            retry_policy=RetryPolicy(max_retries=5),
            required_permissions=("admin",),
            metadata={"key": "value"},
        )
        assert td.name == "add"
        assert td.description == "Adds two numbers"
        assert td.category == "math"
        assert td.enabled is False
        assert td.timeout_seconds == 10.0
        assert td.retry_policy.max_retries == 5
        assert td.required_permissions == ("admin",)
        assert td.metadata == {"key": "value"}

    def test_to_tool_def(self) -> None:
        td = ToolDefinition(
            name="echo",
            description="Echoes input",
            parameters={"type": "object"},
        )
        tdef = td.to_tool_def()
        assert isinstance(tdef, ToolDef)
        assert tdef.name == "echo"
        assert tdef.description == "Echoes input"
        assert tdef.parameters == {"type": "object"}

    def test_frozen(self) -> None:
        td = _td("test")
        with pytest.raises(AttributeError):
            td.name = "other"  # type: ignore[misc]

    def test_default_category(self) -> None:
        td = _td("test")
        assert td.category == "general"


# =========================================================================
# ToolRegistry
# =========================================================================


class TestToolRegistry:
    def test_register(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="success"))
        reg.register(_td("echo"), handler)
        assert reg.tool_count == 1
        assert reg.has("echo")

    def test_register_duplicate_raises(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="success"))
        reg.register(_td("echo"), handler)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_td("echo"), handler)

    def test_unregister(self) -> None:
        reg = ToolRegistry()
        reg.register(_td("echo"), _async_return(ToolResult(status="success")))
        reg.unregister("echo")
        assert reg.tool_count == 0

    def test_unregister_nonexistent_does_not_raise(self) -> None:
        reg = ToolRegistry()
        reg.unregister("nonexistent")
        assert reg.tool_count == 0

    def test_get(self) -> None:
        reg = ToolRegistry()
        td = _td("echo")
        reg.register(td, _async_return(ToolResult(status="success")))
        got = reg.get("echo")
        assert got is td

    def test_get_nonexistent(self) -> None:
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_get_handler(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="success"))
        reg.register(_td("echo"), handler)
        assert reg.get_handler("echo") is handler

    def test_has(self) -> None:
        reg = ToolRegistry()
        assert reg.has("echo") is False
        reg.register(_td("echo"), _async_return(ToolResult(status="success")))
        assert reg.has("echo") is True

    def test_list(self) -> None:
        reg = ToolRegistry()
        reg.register(_td("a"), _async_return(ToolResult(status="success")))
        reg.register(_td("b"), _async_return(ToolResult(status="success")))
        items = reg.list()
        assert len(items) == 2
        assert items[0].name == "a"
        assert items[1].name == "b"

    def test_list_enabled_only(self) -> None:
        reg = ToolRegistry()
        reg.register(_td("a"), _async_return(ToolResult(status="success")))
        reg.register(
            _td("b", enabled=False),
            _async_return(ToolResult(status="success")),
        )
        items = reg.list(enabled_only=True)
        assert len(items) == 1
        assert items[0].name == "a"

    def test_list_by_category(self) -> None:
        reg = ToolRegistry()
        reg.register(
            _td("a", category="math"),
            _async_return(ToolResult(status="success")),
        )
        reg.register(
            _td("b", category="io"),
            _async_return(ToolResult(status="success")),
        )
        items = reg.list(category="math")
        assert len(items) == 1
        assert items[0].name == "a"

    def test_list_returns_copy(self) -> None:
        reg = ToolRegistry()
        reg.register(_td("a"), _async_return(ToolResult(status="success")))
        items = reg.list()
        items.clear()
        assert reg.tool_count == 1

    def test_enable(self) -> None:
        reg = ToolRegistry()
        reg.register(
            _td("a", enabled=False),
            _async_return(ToolResult(status="success")),
        )
        assert reg.is_enabled("a") is False
        reg.enable("a")
        assert reg.is_enabled("a") is True

    def test_enable_nonexistent_returns_false(self) -> None:
        reg = ToolRegistry()
        assert reg.enable("nonexistent") is False

    def test_disable(self) -> None:
        reg = ToolRegistry()
        reg.register(_td("a"), _async_return(ToolResult(status="success")))
        assert reg.is_enabled("a") is True
        reg.disable("a")
        assert reg.is_enabled("a") is False

    def test_disable_nonexistent_returns_false(self) -> None:
        reg = ToolRegistry()
        assert reg.disable("nonexistent") is False

    def test_categories(self) -> None:
        reg = ToolRegistry()
        reg.register(
            _td("a", category="math"),
            _async_return(ToolResult(status="success")),
        )
        reg.register(
            _td("b", category="io"),
            _async_return(ToolResult(status="success")),
        )
        assert set(reg.categories) == {"math", "io"}

    def test_categories_dedup(self) -> None:
        reg = ToolRegistry()
        reg.register(
            _td("a", category="math"),
            _async_return(ToolResult(status="success")),
        )
        reg.register(
            _td("b", category="math"),
            _async_return(ToolResult(status="success")),
        )
        assert len(reg.categories) == 1

    def test_clear(self) -> None:
        reg = ToolRegistry()
        reg.register(_td("a"), _async_return(ToolResult(status="success")))
        reg.register(_td("b"), _async_return(ToolResult(status="success")))
        assert reg.tool_count == 2
        reg.clear()
        assert reg.tool_count == 0

    def test_list_enabled_convenience(self) -> None:
        reg = ToolRegistry()
        reg.register(
            _td("a", enabled=False),
            _async_return(ToolResult(status="success")),
        )
        reg.register(_td("b"), _async_return(ToolResult(status="success")))
        items = reg.list_enabled()
        assert len(items) == 1
        assert items[0].name == "b"

    def test_list_by_category_convenience(self) -> None:
        reg = ToolRegistry()
        reg.register(
            _td("a", category="math"),
            _async_return(ToolResult(status="success")),
        )
        reg.register(
            _td("b", category="io"),
            _async_return(ToolResult(status="success")),
        )
        items = reg.list_by_category("math")
        assert len(items) == 1
        assert items[0].name == "a"

    def test_is_enabled_nonexistent(self) -> None:
        reg = ToolRegistry()
        assert reg.is_enabled("nonexistent") is False


# =========================================================================
# ToolValidation
# =========================================================================


class TestToolValidation:
    def test_validate_input_no_schema(self) -> None:
        td = _td("test")
        result = ToolValidation.validate_input(td, {"x": 1})
        assert result.status == "pass"

    def test_validate_input_passes(self) -> None:
        td = _td("test", parameters={
            "type": "object",
            "properties": {"x": {"type": "number"}},
        })
        result = ToolValidation.validate_input(td, {"x": 42})
        # int 42 is coerced to float via sanitize
        assert result.status == "sanitized"

    def test_validate_input_fails(self) -> None:
        td = _td("test", parameters={
            "type": "object",
            "properties": {"x": {"type": "number"}},
        })
        result = ToolValidation.validate_input(td, {"x": "not_a_number"})
        assert result.status == "reject"

    def test_validate_input_missing_required(self) -> None:
        td = _td("test", parameters={
            "type": "object",
            "required": ["x"],
            "properties": {"x": {"type": "number"}},
        })
        result = ToolValidation.validate_input(td, {})
        assert result.status == "reject"

    def test_validate_input_sanitizes(self) -> None:
        td = _td("test", parameters={
            "type": "object",
            "properties": {"x": {"type": "string"}},
        })
        result = ToolValidation.validate_input(td, {"x": 42})
        assert result.status == "sanitized"

    def test_validate_output_no_schema(self) -> None:
        td = _td("test")
        result = ToolValidation.validate_output(
            td, ToolResult(status="success", output="ok"),
        )
        assert result.status == "pass"

    def test_validate_output_rejects_empty_for_success(self) -> None:
        td = _td("test")
        result = ToolValidation.validate_output(
            td, ToolResult(status="success", output=None),
        )
        assert result.status == "reject"

    def test_validate_output_passes_for_error(self) -> None:
        td = _td("test")
        result = ToolValidation.validate_output(
            td, ToolResult(status="error", error="fail"),
        )
        assert result.status == "pass"

    def test_sanitize(self) -> None:
        td = _td("test", parameters={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "additionalProperties": False,
        })
        result = ToolValidation.sanitize(td, {"x": "42", "extra": True})
        assert result["x"] == 42
        assert "extra" not in result

    def test_sanitize_no_schema(self) -> None:
        td = _td("test")
        result = ToolValidation.sanitize(td, {"x": 1})
        assert result == {"x": 1}


# =========================================================================
# ToolPermission
# =========================================================================


class TestToolPermission:
    def test_lenient_construction(self) -> None:
        tp = ToolPermission()
        assert tp.is_lenient is True

    def test_lenient_check_always_true(self) -> None:
        tp = ToolPermission()
        td = _td("echo")
        result = tp.check(td)
        assert result is True

    def test_lenient_required_permissions_empty(self) -> None:
        tp = ToolPermission()
        td = _td("echo")
        result = tp.required_permissions(td)
        assert result == []

    def test_with_checker_delegates(self) -> None:
        checker = MagicMock()
        checker.check_permission = MagicMock(return_value=True)
        tp = ToolPermission(permission_checker=checker)
        td = _td("admin_tool", required_permissions=("admin",))
        result = tp.check(td)
        checker.check_permission.assert_called_once_with("admin_tool", "admin")
        assert result is True

    def test_with_checker_denies(self) -> None:
        checker = MagicMock()
        checker.check_permission = MagicMock(return_value=False)
        tp = ToolPermission(permission_checker=checker)
        td = _td("admin_tool", required_permissions=("admin",))
        result = tp.check(td)
        assert result is False

    def test_checker_calls_required(self) -> None:
        checker = MagicMock()
        checker.required_permissions = MagicMock(return_value=["admin", "audit"])
        tp = ToolPermission(permission_checker=checker)
        td = _td("admin_tool", required_permissions=("admin",))
        result = tp.required_permissions(td)
        assert result == ["admin", "audit"]

    def test_no_permissions_needed(self) -> None:
        tp = ToolPermission()
        td = _td("safe", required_permissions=())
        assert tp.check(td) is True


# =========================================================================
# ToolExecutor
# =========================================================================


class _ReturnValueProvider(ToolProvider):
    """ToolProvider that returns a canned value."""

    def __init__(self, definition: object) -> None:
        super().__init__(definition)
        self._result = ToolResult(status="success", output="done")

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return self._result


class _FailingProvider(ToolProvider):
    """ToolProvider that always fails."""

    def __init__(self, definition: object) -> None:
        super().__init__(definition)

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(status="error", error="always fails")


class _SlowProvider(ToolProvider):
    """ToolProvider that sleeps longer than timeout."""

    def __init__(self, definition: object) -> None:
        super().__init__(definition)

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        await asyncio.sleep(5)
        return ToolResult(status="success", output="done")


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="success", output="done"))
        reg.register(_td("echo"), handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        result = await exe.execute("echo", {})
        assert result.status == "success"
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_execute_returns_error(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="error", error="fail"))
        reg.register(_td("failing"), handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        result = await exe.execute("failing", {})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_execute_nonexistent(self) -> None:
        reg = ToolRegistry()
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        result = await exe.execute("nonexistent", {})
        assert result.status == "error"
        assert "not found" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_execute_tool_call(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="success", output="done"))
        reg.register(_td("echo"), handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        call = ToolCall(name="echo", arguments={}, id="call_1")
        result = await exe.execute_tool_call(call)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_multi(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="success", output="done"))
        reg.register(_td("echo"), handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        calls = [
            ToolCall(name="echo", arguments={}, id="c1"),
            ToolCall(name="echo", arguments={}, id="c2"),
        ]
        results = await exe.execute_multi(calls)
        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        async def _slow(**_kwargs: object) -> ToolResult:
            await asyncio.sleep(5)
            return ToolResult(status="success", output="done")

        reg = ToolRegistry()
        td = _td("slow", timeout_seconds=0.1)
        reg.register(td, _slow)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        result = await exe.execute("slow", {})
        assert result.status == "timeout"

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        reg = ToolRegistry()
        handler = _async_return(ToolResult(status="success", output="done"))
        reg.register(_td("echo"), handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
            max_concurrent=2,
        )
        calls = [
            ToolCall(name="echo", arguments={}, id=f"c{i}") for i in range(10)
        ]
        results = await exe.execute_multi(calls)
        assert all(r.status == "success" for r in results)

    @pytest.mark.asyncio
    async def test_disabled_tool_rejected(self) -> None:
        reg = ToolRegistry()
        td = _td("echo", enabled=False)
        handler = _async_return(ToolResult(status="success", output="done"))
        reg.register(td, handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        result = await exe.execute("echo", {})
        assert result.status == "error"
        assert "disabled" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        checker = MagicMock()
        checker.check_permission = MagicMock(return_value=False)
        reg = ToolRegistry()
        td = _td("admin", required_permissions=("admin",))
        handler = _async_return(ToolResult(status="success", output="done"))
        reg.register(td, handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(permission_checker=checker),
        )
        result = await exe.execute("admin", {})
        assert result.status == "error"
        assert "denied" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_input_validation_rejected(self) -> None:
        reg = ToolRegistry()
        td = _td("strict", parameters={
            "type": "object",
            "required": ["x"],
            "properties": {"x": {"type": "number"}},
        })
        handler = _async_return(ToolResult(status="success"))
        reg.register(td, handler)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        result = await exe.execute("strict", {})
        assert result.status == "error"
        assert "validation" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_retry_on_exception(self) -> None:
        attempt_count: int = 0

        async def _fail_twice(**kwargs: object) -> ToolResult:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                msg = f"attempt {attempt_count}"
                raise RuntimeError(msg)
            return ToolResult(status="success", output="done")

        reg = ToolRegistry()
        td = _td("retry", retry_policy=RetryPolicy(max_retries=3, base_delay=0.01))
        reg.register(td, _fail_twice)
        exe = ToolExecutor(
            registry=reg,
            validation=ToolValidation(),
            permission=ToolPermission(),
        )
        result = await exe.execute("retry", {})
        assert result.status == "success"
        assert attempt_count == 3


# =========================================================================
# ToolManager — ModuleInterface lifecycle
# =========================================================================


class TestToolManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = ToolManager()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_async_init(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("echo"), _async_return(ToolResult(status="success")),
        )
        assert mgr.tool_count == 1
        await mgr.async_shutdown()
        assert mgr.tool_count == 0

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()
        assert mgr.tool_count == 0

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_degrade_clears_registrations(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("echo"), _async_return(ToolResult(status="success")),
        )
        mgr.degrade()
        assert mgr.tool_count == 0

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = MagicMock()
        mgr = ToolManager(logger=logger)
        assert mgr._logger is logger


# =========================================================================
# ToolManager — registration
# =========================================================================


class TestToolManagerRegistration:
    @pytest.mark.asyncio
    async def test_register_tool(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("echo"), _async_return(ToolResult(status="success")),
        )
        assert mgr.has_tool("echo")

    @pytest.mark.asyncio
    async def test_register_tool_duplicate_raises(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        handler = _async_return(ToolResult(status="success"))
        mgr.register_tool(_td("echo"), handler)
        with pytest.raises(ValueError, match="already registered"):
            mgr.register_tool(_td("echo"), handler)

    @pytest.mark.asyncio
    async def test_unregister_tool(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("echo"), _async_return(ToolResult(status="success")),
        )
        mgr.unregister_tool("echo")
        assert mgr.has_tool("echo") is False

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_does_not_raise(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.unregister_tool("nonexistent")

    @pytest.mark.asyncio
    async def test_get_tool(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        td = _td("echo")
        mgr.register_tool(td, _async_return(ToolResult(status="success")))
        assert mgr.get_tool("echo") is td

    @pytest.mark.asyncio
    async def test_get_tool_nonexistent(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        assert mgr.get_tool("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_tools(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(_td("a"), _async_return(ToolResult(status="success")))
        mgr.register_tool(_td("b"), _async_return(ToolResult(status="success")))
        tools = mgr.list_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"a", "b"}

    @pytest.mark.asyncio
    async def test_register_degraded_raises(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.register_tool(
                _td("test"), _async_return(ToolResult(status="success")),
            )

    @pytest.mark.asyncio
    async def test_unregister_degraded_raises(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.unregister_tool("test")


# =========================================================================
# ToolManager — enable / disable
# =========================================================================


class TestToolManagerEnableDisable:
    @pytest.mark.asyncio
    async def test_disable_tool(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("echo"), _async_return(ToolResult(status="success")),
        )
        assert mgr.disable_tool("echo") is True

    @pytest.mark.asyncio
    async def test_enable_tool(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("echo"), _async_return(ToolResult(status="success")),
        )
        mgr.disable_tool("echo")
        assert mgr.enable_tool("echo") is True

    @pytest.mark.asyncio
    async def test_disable_nonexistent_returns_false(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        assert mgr.disable_tool("nonexistent") is False

    @pytest.mark.asyncio
    async def test_enable_nonexistent_returns_false(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        assert mgr.enable_tool("nonexistent") is False

    @pytest.mark.asyncio
    async def test_is_enabled(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(_td("a"), _async_return(ToolResult(status="success")))
        mgr.register_tool(
            _td("b", enabled=False),
            _async_return(ToolResult(status="success")),
        )
        assert mgr.is_enabled("a") is True
        assert mgr.is_enabled("b") is False

    @pytest.mark.asyncio
    async def test_enable_disable_degraded_raises(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.disable_tool("test")
        with pytest.raises(ModuleDegradedError):
            mgr.enable_tool("test")


# =========================================================================
# ToolManager — execution
# =========================================================================


class TestToolManagerExecution:
    @pytest.mark.asyncio
    async def test_execute_tool(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        handler = _async_return(ToolResult(status="success", output="done"))
        mgr.register_tool(_td("echo"), handler)
        result = await mgr.execute_tool("echo", {})
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_tool_nonexistent(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        result = await mgr.execute_tool("nonexistent", {})
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_execute_tool_call(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        handler = _async_return(ToolResult(status="success", output="done"))
        mgr.register_tool(_td("echo"), handler)
        call = ToolCall(name="echo", arguments={}, id="call_1")
        result = await mgr.execute_tool_call(call)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_multi(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        handler = _async_return(ToolResult(status="success", output="done"))
        mgr.register_tool(_td("echo"), handler)
        calls = [
            ToolCall(name="echo", arguments={}, id="c1"),
            ToolCall(name="echo", arguments={}, id="c2"),
        ]
        results = await mgr.execute_multi(calls)
        assert len(results) == 2
        assert all(r.status == "success" for r in results)

    @pytest.mark.asyncio
    async def test_execute_degraded_raises(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.execute_tool("echo", {})

    @pytest.mark.asyncio
    async def test_execute_tool_call_degraded_raises(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        call = ToolCall(name="echo", arguments={}, id="c1")
        with pytest.raises(ModuleDegradedError):
            await mgr.execute_tool_call(call)

    @pytest.mark.asyncio
    async def test_execute_multi_degraded_raises(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.execute_multi([])


# =========================================================================
# ToolManager — tool definitions for LLM
# =========================================================================


class TestToolManagerGetToolDefs:
    @pytest.mark.asyncio
    async def test_get_tool_defs(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        a_def = _td("a")
        b_def = _td("b")
        # We register *after* changing description since _td sets default
        mgr.register_tool(a_def, _async_return(ToolResult(status="success")))
        mgr.register_tool(b_def, _async_return(ToolResult(status="success")))
        defs = mgr.get_tool_defs()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"a", "b"}

    @pytest.mark.asyncio
    async def test_get_tool_defs_excludes_disabled(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(_td("a"), _async_return(ToolResult(status="success")))
        mgr.register_tool(
            _td("b", enabled=False),
            _async_return(ToolResult(status="success")),
        )
        defs = mgr.get_tool_defs()
        assert len(defs) == 1
        assert defs[0].name == "a"

    @pytest.mark.asyncio
    async def test_get_tool_defs_by_category(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("a", category="math"),
            _async_return(ToolResult(status="success")),
        )
        mgr.register_tool(
            _td("b", category="io"),
            _async_return(ToolResult(status="success")),
        )
        defs = mgr.get_tool_defs(category="math")
        assert len(defs) == 1
        assert defs[0].name == "a"

    @pytest.mark.asyncio
    async def test_get_tool_defs_degraded_raises(self) -> None:
        mgr = ToolManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.get_tool_defs()


# =========================================================================
# ToolManager — category access
# =========================================================================


class TestToolManagerCategories:
    @pytest.mark.asyncio
    async def test_get_categories(self) -> None:
        mgr = ToolManager()
        await mgr.async_init()
        mgr.register_tool(
            _td("a", category="math"),
            _async_return(ToolResult(status="success")),
        )
        mgr.register_tool(
            _td("b", category="io"),
            _async_return(ToolResult(status="success")),
        )
        cats = mgr.get_categories()
        assert set(cats) == {"math", "io"}


# =========================================================================
# ToolProvider — port
# =========================================================================


class TestToolProviderPort:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            ToolProvider(None)  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_implementation(self) -> None:
        td = _td("echo")
        provider = _ReturnValueProvider(td)
        assert isinstance(provider, ToolProvider)
        assert provider.definition is td
        result = await provider.execute({"x": 1})
        assert result.status == "success"
        assert result.output == "done"


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_tool_manager_conforms_to_protocol(self) -> None:
        assert isinstance(ToolManager(), ModuleInterface)

    def test_tool_manager_has_required_methods(self) -> None:
        mgr = ToolManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
