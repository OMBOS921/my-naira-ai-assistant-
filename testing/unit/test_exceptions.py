"""Tests for the exception hierarchy (backend/exceptions.py).

21_System_Contracts.md §9 — All application exceptions inherit from
``NairaError`` and carry a ``context`` dict.
"""

from __future__ import annotations

from backend.exceptions import (
    AuditLogError,
    ConfigurationError,
    InputRejectedError,
    IntegrityError,
    NairaError,
    LLMError,
    MemoryError,
    ModuleDegradedError,
    ModuleError,
    ModuleLoadError,
    ModuleTimeoutError,
    NotFoundError,
    PermissionDeniedError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    SecurityError,
    ToolExecutionError,
    ToolRejectedError,
    ToolTimeoutError,
)


class TestNairaError:
    def test_base_exception(self) -> None:
        err = NairaError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"
        assert err.context == {}

    def test_with_context(self) -> None:
        err = NairaError("fail", context={"module": "test", "request_id": "abc"})
        assert err.context == {"module": "test", "request_id": "abc"}

    def test_context_shared_reference(self) -> None:
        orig = {"key": "value"}
        err = NairaError("msg", context=orig)
        orig["extra"] = "stuff"
        assert err.context == {"key": "value", "extra": "stuff"}


class TestConfigurationError:
    def test_inheritance(self) -> None:
        err = ConfigurationError("bad config")
        assert isinstance(err, NairaError)
        assert isinstance(err, Exception)

    def test_message(self) -> None:
        err = ConfigurationError("missing field: log.level")
        assert str(err) == "missing field: log.level"


class TestModuleErrors:
    def test_module_error_base(self) -> None:
        err = ModuleError("module error")
        assert isinstance(err, NairaError)

    def test_module_load_error(self) -> None:
        err = ModuleLoadError("cannot import vision")
        assert isinstance(err, ModuleError)

    def test_module_timeout_error(self) -> None:
        err = ModuleTimeoutError("vision init timed out")
        assert isinstance(err, ModuleError)

    def test_module_degraded_error(self) -> None:
        err = ModuleDegradedError("vision running in degraded mode")
        assert isinstance(err, ModuleError)

    def test_module_error_context(self) -> None:
        err = ModuleLoadError("fail", context={"module": "vision"})
        assert err.context == {"module": "vision"}


class TestSecurityErrors:
    def test_security_error_base(self) -> None:
        err = SecurityError("security violation")
        assert isinstance(err, NairaError)

    def test_input_rejected(self) -> None:
        err = InputRejectedError("suspicious payload")
        assert isinstance(err, SecurityError)

    def test_permission_denied(self) -> None:
        err = PermissionDeniedError("user denied access")
        assert isinstance(err, SecurityError)

    def test_audit_log_error(self) -> None:
        err = AuditLogError("cannot write audit log")
        assert isinstance(err, SecurityError)


class TestLLMErrors:
    def test_llm_error_base(self) -> None:
        err = LLMError("llm error")
        assert isinstance(err, NairaError)

    def test_provider_timeout(self) -> None:
        err = ProviderTimeoutError("gemini timed out")
        assert isinstance(err, LLMError)

    def test_provider_rate_limit(self) -> None:
        err = ProviderRateLimitError("rate limited")
        assert isinstance(err, LLMError)

    def test_provider_auth(self) -> None:
        err = ProviderAuthError("invalid API key")
        assert isinstance(err, LLMError)


class TestMemoryErrors:
    def test_memory_error_base(self) -> None:
        err = MemoryError("memory error")
        assert isinstance(err, NairaError)

    def test_integrity_error(self) -> None:
        err = IntegrityError("UNIQUE constraint failed")
        assert isinstance(err, MemoryError)

    def test_not_found(self) -> None:
        err = NotFoundError("key not found")
        assert isinstance(err, MemoryError)


class TestToolExecutionErrors:
    def test_tool_execution_error_base(self) -> None:
        err = ToolExecutionError("tool failed")
        assert isinstance(err, NairaError)

    def test_tool_timeout(self) -> None:
        err = ToolTimeoutError("tool timed out")
        assert isinstance(err, ToolExecutionError)

    def test_tool_rejected(self) -> None:
        err = ToolRejectedError("tool rejected by gatekeeper")
        assert isinstance(err, ToolExecutionError)
