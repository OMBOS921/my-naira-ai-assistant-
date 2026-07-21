from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.modules.security._audit_logger import AuditLogger
from backend.modules.security._command_validator import CommandValidator
from backend.modules.security._exceptions import (
    SecurityConfigError,
    SecurityExecutionError,
    SecurityNotImplementedError,
    SecurityPermissionError,
    SecurityTimeoutError,
)
from backend.modules.security._local_adapter import LocalSecurityAdapter
from backend.modules.security._path_validator import PathValidator
from backend.modules.security._permission_manager import PermissionManager
from backend.modules.security._policy_engine import SecurityPolicyEngine
from backend.modules.security._risk_analyzer import RiskAnalyzer
from backend.modules.security._sandbox_manager import SandboxManager
from backend.modules.security._security_context import build_security_context
from backend.modules.security._types import (
    AuditEntry,
    PermissionMode,
    RiskLevel,
    SecurityCheck,
    SecurityContext,
    SecurityPolicyRule,
    SecurityStatus,
)
from backend.modules.security.ports.security_port import SecurityPort
from backend.modules.security.security_module import SecurityManager
from backend.modules.settings._config import AppConfig, SecurityConfig
from backend.types import ToolResult

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_logger() -> MagicMock:
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig()


@pytest.fixture
def security_adapter() -> LocalSecurityAdapter:
    return LocalSecurityAdapter(
        enabled=True,
        sandbox_enabled=True,
        audit_enabled=True,
    )


@pytest.fixture
def security_adapter_disabled() -> LocalSecurityAdapter:
    return LocalSecurityAdapter(
        enabled=False,
        sandbox_enabled=False,
        audit_enabled=False,
    )


@pytest.fixture
def security_manager(security_adapter, mock_logger) -> SecurityManager:
    mgr = SecurityManager(
        config=AppConfig(),
        logger=mock_logger,
        adapter=security_adapter,
    )
    return mgr


# =========================================================================
# Test Types
# =========================================================================


class TestRiskLevel:
    def test_values(self) -> None:
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_order(self) -> None:
        levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert levels.index(RiskLevel.LOW) < levels.index(RiskLevel.CRITICAL)


class TestPermissionMode:
    def test_values(self) -> None:
        assert PermissionMode.ALLOW.value == "allow"
        assert PermissionMode.DENY.value == "deny"
        assert PermissionMode.CONFIRM.value == "confirm"
        assert PermissionMode.ADMIN.value == "admin"


class TestSecurityStatus:
    def test_values(self) -> None:
        assert SecurityStatus.PASS.value == "pass"
        assert SecurityStatus.DENY.value == "deny"
        assert SecurityStatus.CONFIRM.value == "confirm"
        assert SecurityStatus.ERROR.value == "error"


class TestSecurityCheck:
    def test_minimal(self) -> None:
        check = SecurityCheck(status=SecurityStatus.PASS)
        assert check.status == SecurityStatus.PASS
        assert check.risk_level == RiskLevel.LOW
        assert check.denied is False
        assert check.requires_confirmation is False

    def test_denied(self) -> None:
        check = SecurityCheck(
            status=SecurityStatus.DENY,
            risk_level=RiskLevel.CRITICAL,
            reason="Blocked",
            denied=True,
        )
        assert check.denied
        assert check.reason == "Blocked"

    def test_frozen(self) -> None:
        check = SecurityCheck(status=SecurityStatus.PASS)
        with pytest.raises(AttributeError):
            check.status = SecurityStatus.DENY  # type: ignore[misc]


class TestAuditEntry:
    def test_minimal(self) -> None:
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            tool="test_tool",
            arguments={"key": "value"},
            caller="test",
            approval="auto",
            result="success",
            execution_time_ms=10.0,
            risk_score=RiskLevel.LOW,
        )
        assert entry.tool == "test_tool"
        assert entry.id is not None

    def test_frozen(self) -> None:
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            tool="test",
            arguments={},
            caller="test",
            approval="auto",
            result="ok",
            execution_time_ms=0.0,
            risk_score=RiskLevel.LOW,
        )
        with pytest.raises(AttributeError):
            entry.tool = "other"  # type: ignore[misc]


class TestSecurityContext:
    def test_minimal(self) -> None:
        ctx = SecurityContext()
        assert ctx.caller == "system"
        assert ctx.metadata == {}

    def test_build(self) -> None:
        ctx = build_security_context(
            user_id="user1",
            session_id="sess1",
            caller="test",
            metadata={"key": "val"},
        )
        assert ctx.user_id == "user1"
        assert ctx.session_id == "sess1"
        assert ctx.caller == "test"
        assert ctx.metadata["key"] == "val"


class TestSecurityPolicyRule:
    def test_minimal(self) -> None:
        rule = SecurityPolicyRule(
            tool_pattern="browser_*",
            mode=PermissionMode.ALLOW,
        )
        assert rule.tool_pattern == "browser_*"
        assert rule.mode == PermissionMode.ALLOW


# =========================================================================
# Test Exceptions
# =========================================================================


class TestSecurityExceptions:
    def test_security_execution_error(self) -> None:
        exc = SecurityExecutionError("exec failed", context={"module": "security"})
        assert "exec failed" in str(exc)
        assert exc.context["module"] == "security"

    def test_security_permission_error(self) -> None:
        exc = SecurityPermissionError("denied")
        assert "denied" in str(exc)

    def test_security_timeout_error(self) -> None:
        exc = SecurityTimeoutError("timeout")
        assert "timeout" in str(exc)

    def test_security_not_implemented_error(self) -> None:
        exc = SecurityNotImplementedError("not impl")
        assert "not impl" in str(exc)

    def test_security_config_error(self) -> None:
        exc = SecurityConfigError("bad config")
        assert "bad config" in str(exc)


# =========================================================================
# Test PermissionManager
# =========================================================================


class TestPermissionManager:
    def test_default_allow(self) -> None:
        pm = PermissionManager()
        assert pm.check_permission("any_tool")

    def test_set_deny(self) -> None:
        pm = PermissionManager()
        pm.set_permission("dangerous_tool", PermissionMode.DENY)
        assert not pm.check_permission("dangerous_tool")

    def test_set_allow(self) -> None:
        pm = PermissionManager()
        pm.set_permission("safe_tool", PermissionMode.ALLOW)
        assert pm.check_permission("safe_tool")

    def test_confirm(self) -> None:
        pm = PermissionManager()
        pm.set_permission("confirm_tool", PermissionMode.CONFIRM)
        assert pm.check_permission("confirm_tool")
        assert pm.requires_confirmation("confirm_tool")

    def test_admin(self) -> None:
        pm = PermissionManager()
        pm.set_permission("admin_tool", PermissionMode.ADMIN)
        assert pm.check_permission("admin_tool")
        assert pm.requires_admin("admin_tool")

    def test_remove_permission(self) -> None:
        pm = PermissionManager()
        pm.set_permission("tool", PermissionMode.DENY)
        pm.remove_permission("tool")
        assert pm.check_permission("tool")

    def test_list_permissions(self) -> None:
        pm = PermissionManager()
        pm.set_permission("a", PermissionMode.DENY)
        pm.set_permission("b", PermissionMode.CONFIRM)
        perms = pm.list_permissions()
        assert perms["a"] == PermissionMode.DENY
        assert perms["b"] == PermissionMode.CONFIRM

    def test_clear(self) -> None:
        pm = PermissionManager()
        pm.set_permission("tool", PermissionMode.DENY)
        pm.clear()
        assert pm.list_permissions() == {}


# =========================================================================
# Test AuditLogger
# =========================================================================


class TestAuditLogger:
    @pytest.mark.asyncio
    async def test_disabled(self) -> None:
        logger = AuditLogger(enabled=False)
        await logger.log("test", {}, "caller", "auto", "ok", 1.0, RiskLevel.LOW)
        entries = await logger.get_log()
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_log_and_retrieve(self) -> None:
        logger = AuditLogger(enabled=True, max_entries=100)
        await logger.log("tool1", {"arg": 1}, "user1", "auto", "success", 5.0, RiskLevel.LOW)
        await logger.log("tool2", {}, "user2", "confirmed", "success", 10.0, RiskLevel.HIGH)
        entries = await logger.get_log()
        assert len(entries) == 2
        assert entries[0].tool == "tool1"
        assert entries[1].risk_score == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_log_limit(self) -> None:
        logger = AuditLogger(enabled=True, max_entries=100)
        for i in range(20):
            await logger.log(f"tool{i}", {}, "test", "auto", "ok", 1.0, RiskLevel.LOW)
        entries = await logger.get_log(limit=5)
        assert len(entries) == 5

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        logger = AuditLogger(enabled=True)
        await logger.log("tool", {}, "test", "auto", "ok", 1.0, RiskLevel.LOW)
        await logger.clear()
        entries = await logger.get_log()
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_count(self) -> None:
        logger = AuditLogger(enabled=True)
        assert logger.count == 0
        await logger.log("tool", {}, "test", "auto", "ok", 1.0, RiskLevel.LOW)
        assert logger.count == 1


# =========================================================================
# Test CommandValidator
# =========================================================================


class TestCommandValidator:
    @pytest.mark.asyncio
    async def test_safe_command(self) -> None:
        validator = CommandValidator()
        check = await validator.validate("dir /b")
        assert check.status == SecurityStatus.PASS
        assert not check.denied

    @pytest.mark.asyncio
    async def test_denylist_command(self) -> None:
        validator = CommandValidator()
        check = await validator.validate("rm -rf /")
        assert check.status == SecurityStatus.DENY
        assert check.denied

    @pytest.mark.asyncio
    async def test_dangerous_keyword(self) -> None:
        validator = CommandValidator()
        check = await validator.validate("cmd1 && cmd2")
        assert check.status == SecurityStatus.CONFIRM
        assert check.requires_confirmation

    @pytest.mark.asyncio
    async def test_tokenize(self) -> None:
        tokens = CommandValidator.tokenize('echo "hello world"')
        assert tokens == ["echo", "hello world"]

    @pytest.mark.asyncio
    async def test_empty_command(self) -> None:
        validator = CommandValidator()
        check = await validator.validate("")
        assert check.status == SecurityStatus.PASS


# =========================================================================
# Test PathValidator
# =========================================================================


class TestPathValidator:
    @pytest.mark.asyncio
    async def test_safe_path(self) -> None:
        validator = PathValidator()
        check = await validator.validate("C:\\Users\\test\\file.txt")
        assert check.status == SecurityStatus.PASS

    @pytest.mark.asyncio
    async def test_directory_traversal(self) -> None:
        validator = PathValidator()
        check = await validator.validate("C:\\Users\\test\\..\\..\\Windows\\system32\\cmd.exe")
        assert check.denied

    @pytest.mark.asyncio
    async def test_system_path(self) -> None:
        validator = PathValidator()
        check = await validator.validate("C:\\Windows\\System32\\config")
        assert check.requires_confirmation or check.denied

    @pytest.mark.asyncio
    async def test_blocked_path(self) -> None:
        validator = PathValidator(blocked_paths=("C:\\Secret",))
        check = await validator.validate("C:\\Secret\\data.txt")
        assert check.denied

    @pytest.mark.asyncio
    async def test_allowed_path_override(self) -> None:
        validator = PathValidator(
            allowed_paths=("C:\\Windows\\Temp",),
            blocked_paths=(),
        )
        check = await validator.validate("C:\\Users\\public\\file.txt")
        assert not check.denied


# =========================================================================
# Test SandboxManager
# =========================================================================


class TestSandboxManager:
    @pytest.mark.asyncio
    async def test_allowed_action(self) -> None:
        sandbox = SandboxManager(enabled=True)
        check = await sandbox.check_action("mouse_get_position")
        assert not check.denied
        assert check.status == SecurityStatus.PASS

    @pytest.mark.asyncio
    async def test_denied_action(self) -> None:
        sandbox = SandboxManager(enabled=True)
        check = await sandbox.check_action("filesystem_delete_file")
        assert check.denied

    @pytest.mark.asyncio
    async def test_sandbox_disabled(self) -> None:
        sandbox = SandboxManager(enabled=False)
        check = await sandbox.check_action("filesystem_delete_file")
        assert not check.denied
        assert check.status == SecurityStatus.PASS

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        sandbox = SandboxManager(enabled=True)
        check = await sandbox.check_action("unknown_action")
        assert check.requires_confirmation

    @pytest.mark.asyncio
    async def test_is_path_allowed(self) -> None:
        sandbox = SandboxManager(enabled=True)
        assert not await sandbox.is_path_allowed("C:\\Windows\\System32\\evil.exe")
        assert await sandbox.is_path_allowed("C:\\Users\\test\\file.txt")

    @pytest.mark.asyncio
    async def test_is_path_allowed_disabled(self) -> None:
        sandbox = SandboxManager(enabled=False)
        assert await sandbox.is_path_allowed("C:\\Windows\\System32\\evil.exe")


# =========================================================================
# Test RiskAnalyzer
# =========================================================================


class TestRiskAnalyzer:
    def test_low_risk_tool(self) -> None:
        analyzer = RiskAnalyzer()
        risk = analyzer.analyze("mouse_get_position")
        assert risk == RiskLevel.LOW

    def test_high_risk_tool(self) -> None:
        analyzer = RiskAnalyzer()
        risk = analyzer.analyze("pc_power")
        assert risk == RiskLevel.HIGH

    def test_medium_risk_tool(self) -> None:
        analyzer = RiskAnalyzer()
        risk = analyzer.analyze("pc_clipboard")
        assert risk == RiskLevel.MEDIUM

    def test_dangerous_action(self) -> None:
        analyzer = RiskAnalyzer()
        risk = analyzer.analyze("pc_filesystem", {"action": "delete_file"})
        assert risk == RiskLevel.HIGH

    def test_safe_action(self) -> None:
        analyzer = RiskAnalyzer()
        risk = analyzer.analyze("pc_filesystem", {"action": "list_directory"})
        assert risk == RiskLevel.LOW

    def test_above_threshold(self) -> None:
        analyzer = RiskAnalyzer(max_risk="low")
        assert analyzer.is_above_threshold(RiskLevel.MEDIUM)
        assert not analyzer.is_above_threshold(RiskLevel.LOW)

    def test_default_threshold(self) -> None:
        analyzer = RiskAnalyzer()
        assert not analyzer.is_above_threshold(RiskLevel.CRITICAL)


# =========================================================================
# Test PolicyEngine
# =========================================================================


class TestSecurityPolicyEngine:
    def test_default_allow(self) -> None:
        engine = SecurityPolicyEngine(default_policy="allow")
        mode = engine.evaluate("any_tool")
        assert mode == PermissionMode.ALLOW

    def test_default_deny(self) -> None:
        engine = SecurityPolicyEngine(default_policy="deny")
        mode = engine.evaluate("any_tool")
        assert mode == PermissionMode.DENY

    def test_rule_match(self) -> None:
        engine = SecurityPolicyEngine()
        engine.add_rule(SecurityPolicyRule(
            tool_pattern="power_*",
            mode=PermissionMode.DENY,
        ))
        mode = engine.evaluate("power_shutdown")
        assert mode == PermissionMode.DENY

    def test_rule_no_match(self) -> None:
        engine = SecurityPolicyEngine(default_policy="allow")
        engine.add_rule(SecurityPolicyRule(
            tool_pattern="power_*",
            mode=PermissionMode.DENY,
        ))
        mode = engine.evaluate("browser_navigate")
        assert mode == PermissionMode.ALLOW

    def test_wildcard_pattern(self) -> None:
        engine = SecurityPolicyEngine()
        engine.add_rule(SecurityPolicyRule(
            tool_pattern="pc_*",
            mode=PermissionMode.CONFIRM,
        ))
        assert engine.evaluate("pc_power") == PermissionMode.CONFIRM
        assert engine.evaluate("pc_clipboard") == PermissionMode.CONFIRM

    def test_requires_approval(self) -> None:
        engine = SecurityPolicyEngine()
        engine.add_rule(SecurityPolicyRule(
            tool_pattern="delete_*",
            mode=PermissionMode.DENY,
            require_approval=True,
        ))
        assert engine.requires_approval("delete_file")
        assert not engine.requires_approval("read_file")

    def test_remove_rule(self) -> None:
        engine = SecurityPolicyEngine()
        engine.add_rule(SecurityPolicyRule("test", PermissionMode.DENY))
        assert engine.remove_rule("test") == 1
        assert engine.remove_rule("nonexistent") == 0

    def test_clear(self) -> None:
        engine = SecurityPolicyEngine()
        engine.add_rule(SecurityPolicyRule("test", PermissionMode.DENY))
        engine.clear()
        assert len(engine.list_rules()) == 0


# =========================================================================
# Test LocalSecurityAdapter
# =========================================================================


class TestLocalSecurityAdapter:
    @pytest.mark.asyncio
    async def test_is_available_enabled(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True)
        assert adapter.is_available

    @pytest.mark.asyncio
    async def test_is_available_disabled(self) -> None:
        adapter = LocalSecurityAdapter(enabled=False)
        assert not adapter.is_available

    @pytest.mark.asyncio
    async def test_closed_not_available(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True)
        await adapter.close()
        assert not adapter.is_available

    @pytest.mark.asyncio
    async def test_check_tool_pass(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True, sandbox_enabled=False)
        check = await adapter.check_tool_execution("mouse_get_position", {})
        assert check.status == SecurityStatus.PASS
        assert not check.denied

    @pytest.mark.asyncio
    async def test_check_tool_sandbox_deny(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True, sandbox_enabled=True)
        check = await adapter.check_tool_execution("filesystem_delete_file", {})
        assert check.denied

    @pytest.mark.asyncio
    async def test_check_tool_disabled(self) -> None:
        adapter = LocalSecurityAdapter(enabled=False)
        check = await adapter.check_tool_execution("power_shutdown", {})
        assert not check.denied
        assert check.status == SecurityStatus.PASS

    @pytest.mark.asyncio
    async def test_validate_path(self) -> None:
        adapter = LocalSecurityAdapter()
        check = await adapter.validate_path("/safe/path")
        assert not check.denied

    @pytest.mark.asyncio
    async def test_validate_command(self) -> None:
        adapter = LocalSecurityAdapter()
        check = await adapter.validate_command("echo hello")
        assert not check.denied

    @pytest.mark.asyncio
    async def test_get_risk_level(self) -> None:
        adapter = LocalSecurityAdapter()
        risk = await adapter.get_risk_level("pc_power")
        assert risk == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_log_and_get_audit(self) -> None:
        adapter = LocalSecurityAdapter(audit_enabled=True)
        await adapter.log_audit(AuditEntry(
            timestamp=datetime.now(timezone.utc),
            tool="test",
            arguments={},
            caller="test",
            approval="auto",
            result="ok",
            execution_time_ms=0.0,
            risk_score=RiskLevel.LOW,
        ))
        entries = await adapter.get_audit_log()
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_get_status(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True)
        status = await adapter.get_status()
        assert status.status == "success"
        assert "enabled=True" in (status.output or "")

    @pytest.mark.asyncio
    async def test_check_tool_risk_above_threshold(self) -> None:
        adapter = LocalSecurityAdapter(
            enabled=True,
            sandbox_enabled=False,
            max_risk="low",
        )
        check = await adapter.check_tool_execution("pc_filesystem", {"action": "delete_file"})
        assert check.denied
        assert "Risk level" in (check.reason or "")


# =========================================================================
# Test SecurityManager
# =========================================================================


class TestSecurityManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self, security_manager: SecurityManager) -> None:
        assert not security_manager.degraded

    @pytest.mark.asyncio
    async def test_async_init(self, security_manager: SecurityManager) -> None:
        await security_manager.async_init()
        assert security_manager.is_available

    @pytest.mark.asyncio
    async def test_shutdown(self, security_manager: SecurityManager) -> None:
        await security_manager.async_shutdown()
        assert not security_manager.degraded

    @pytest.mark.asyncio
    async def test_degrade(self, security_manager: SecurityManager) -> None:
        await security_manager.async_init()
        security_manager.degrade()
        assert security_manager.degraded

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self, security_manager: SecurityManager) -> None:
        await security_manager.async_shutdown()
        await security_manager.async_shutdown()

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self, security_manager: SecurityManager) -> None:
        security_manager.degrade()
        security_manager.degrade()
        assert security_manager.degraded


class TestSecurityManagerChecks:
    @pytest.mark.asyncio
    async def test_check_tool_pass(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        check = await mgr.check_tool_execution("mouse_get_position", {})
        assert not check.denied
        assert check.status == SecurityStatus.PASS

    @pytest.mark.asyncio
    async def test_check_tool_denied(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        check = await mgr.check_tool_execution("filesystem_delete_file", {})
        assert check.denied

    @pytest.mark.asyncio
    async def test_check_path(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        check = await mgr.check_path("/safe/path")
        assert not check.denied

    @pytest.mark.asyncio
    async def test_check_command(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        check = await mgr.check_command("echo hello")
        assert not check.denied

    @pytest.mark.asyncio
    async def test_get_risk_level(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        risk = await mgr.get_risk_level("pc_power")
        assert risk == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_get_status(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        status = await mgr.get_status()
        assert status.status == "success"

    @pytest.mark.asyncio
    async def test_tool_execution_denied_raises_on_degraded(
        self, security_manager: SecurityManager
    ) -> None:
        security_manager.degrade()
        with pytest.raises(Exception):
            await security_manager.check_tool_execution("test", {})


class TestSecurityManagerPermissions:
    @pytest.mark.asyncio
    async def test_set_and_get_permission(
        self, security_adapter: LocalSecurityAdapter
    ) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        mgr.set_tool_permission("test_tool", PermissionMode.DENY)
        assert mgr.get_tool_permission("test_tool") == PermissionMode.DENY

    @pytest.mark.asyncio
    async def test_list_permissions(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        mgr.set_tool_permission("a", PermissionMode.CONFIRM)
        perms = mgr.list_tool_permissions()
        assert "a" in perms

    @pytest.mark.asyncio
    async def test_check_permission_integration(
        self, security_adapter: LocalSecurityAdapter
    ) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        assert mgr.check_permission("any_tool", "execute")
        mgr.set_tool_permission("blocked_tool", PermissionMode.DENY)
        assert not mgr.check_permission("blocked_tool", "execute")


class TestSecurityManagerPolicy:
    @pytest.mark.asyncio
    async def test_add_and_list_rules(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        mgr.add_policy_rule(SecurityPolicyRule(
            tool_pattern="power_*",
            mode=PermissionMode.DENY,
        ))
        rules = mgr.list_policy_rules()
        assert len(rules) == 1
        assert rules[0].tool_pattern == "power_*"

    @pytest.mark.asyncio
    async def test_remove_rule(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        mgr.add_policy_rule(SecurityPolicyRule("test", PermissionMode.DENY))
        assert mgr.remove_policy_rule("test") == 1
        assert len(mgr.list_policy_rules()) == 0


class TestSecurityManagerAudit:
    @pytest.mark.asyncio
    async def test_log_and_retrieve(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        await mgr.log_audit(
            tool="test",
            arguments={"key": "val"},
            caller="tester",
            approval="auto",
            result="success",
            execution_time_ms=5.0,
            risk_score=RiskLevel.MEDIUM,
        )
        entries = await mgr.get_audit_log()
        assert len(entries) == 1
        assert entries[0].tool == "test"


class TestSecurityManagerApproval:
    @pytest.mark.asyncio
    async def test_request_approval_timeout(
        self, security_adapter: LocalSecurityAdapter
    ) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        result = await mgr.request_approval("power_shutdown", {}, timeout=0.01)
        assert not result


class TestSecurityManagerToolHandlers:
    @pytest.mark.asyncio
    async def test_status_tool(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        result = await mgr._handle_status_tool()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_audit_tool_empty(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        result = await mgr._handle_audit_tool()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_policy_tool_list(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        result = await mgr._handle_policy_tool(action="list")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_policy_tool_unknown(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        result = await mgr._handle_policy_tool(action="invalid")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_permissions_tool(self, security_adapter: LocalSecurityAdapter) -> None:
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=security_adapter,
        )
        result = await mgr._handle_permissions_tool()
        assert result.status == "success"


# =========================================================================
# Test Port/Adapter pattern
# =========================================================================


class TestSecurityPortAbc:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            SecurityPort()  # type: ignore[abstract]

    def test_concrete_adapter(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True)
        assert isinstance(adapter, SecurityPort)


# =========================================================================
# Test SecurityConfig
# =========================================================================


class TestSecurityConfig:
    def test_defaults(self) -> None:
        config = SecurityConfig()
        assert config.enabled is False
        assert config.sandbox_enabled is True
        assert config.audit_enabled is True
        assert config.default_policy == "allow"
        assert config.approval_timeout == 60.0
        assert config.max_risk == "critical"
        assert config.allow_browser is True

    def test_custom_values(self) -> None:
        config = SecurityConfig(
            enabled=True,
            sandbox_enabled=False,
            default_policy="deny",
            max_risk="medium",
        )
        assert config.enabled
        assert not config.sandbox_enabled
        assert config.default_policy == "deny"
        assert config.max_risk == "medium"

    def test_app_config_integration(self) -> None:
        config = AppConfig()
        assert isinstance(config.security, SecurityConfig)
        assert config.security.enabled is False


# =========================================================================
# Test ToolManager integration
# =========================================================================


class TestToolManagerSecurityIntegration:
    @pytest.mark.asyncio
    async def test_security_manager_in_constructor(self) -> None:
        from backend.modules.tools import ToolManager

        tm = ToolManager()
        assert tm is not None

    @pytest.mark.asyncio
    async def test_set_security_manager(self) -> None:
        from backend.modules.tools import ToolManager

        tm = ToolManager()
        mgr = SecurityManager()
        tm.set_security_manager(mgr)
        assert tm._security_manager is mgr

    @pytest.mark.asyncio
    async def test_security_denies_tool(self) -> None:
        from backend.modules.tools import ToolManager
        from backend.modules.tools._definition import ToolDefinition

        adapter = LocalSecurityAdapter(enabled=True, sandbox_enabled=True)
        sec_mgr = SecurityManager(config=AppConfig(), adapter=adapter)

        tm = ToolManager(security_manager=sec_mgr)
        tm.register_tool(
            ToolDefinition(
                name="filesystem_delete_file",
                description="Delete a file",
                parameters={"type": "object", "properties": {}},
                category="filesystem",
            ),
            lambda **kw: ToolResult(status="success", output="done"),
        )
        result = await tm.execute_tool("filesystem_delete_file", {"path": "/test"})
        assert result.status == "error"
        assert "Security denied" in (result.error or "")


# =========================================================================
# Test EventBus integration
# =========================================================================


class TestSecurityEventBus:
    @pytest.mark.asyncio
    async def test_check_start_event(self) -> None:
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()

        adapter = LocalSecurityAdapter(enabled=True, sandbox_enabled=False)
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=adapter,
            event_bus=event_bus_mock,
        )
        await mgr.check_tool_execution("mouse_get_position", {})
        event_bus_mock.emit.assert_any_await("security.check.start", {
            "tool": "mouse_get_position",
            "caller": "system",
        })

    @pytest.mark.asyncio
    async def test_denied_event(self) -> None:
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()

        adapter = LocalSecurityAdapter(enabled=True, sandbox_enabled=True)
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=adapter,
            event_bus=event_bus_mock,
        )
        await mgr.check_tool_execution("filesystem_delete_file", {})
        event_bus_mock.emit.assert_any_await("security.denied", {
            "tool": "filesystem_delete_file",
            "reason": "Action 'filesystem_delete_file' is denied by sandbox policy",
            "risk": "critical",
        })

    @pytest.mark.asyncio
    async def test_audit_event(self) -> None:
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()

        adapter = LocalSecurityAdapter(enabled=True)
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=adapter,
            event_bus=event_bus_mock,
        )
        await mgr.log_audit("test", {}, "caller", "auto", "ok", 1.0, RiskLevel.LOW)
        event_bus_mock.emit.assert_any_await("security.audit", {
            "tool": "test",
            "caller": "caller",
            "result": "ok",
        })

    @pytest.mark.asyncio
    async def test_approval_requested_event(self) -> None:
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()

        adapter = LocalSecurityAdapter(enabled=True)
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=adapter,
            event_bus=event_bus_mock,
        )
        await mgr.request_approval("power_shutdown", {}, timeout=0.01)
        event_bus_mock.emit.assert_any_await("security.approval_requested", {
            "tool": "power_shutdown",
            "caller": "system",
        })

    @pytest.mark.asyncio
    async def test_no_event_bus_does_not_fail(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True)
        mgr = SecurityManager(
            config=AppConfig(),
            adapter=adapter,
            event_bus=None,
        )
        check = await mgr.check_tool_execution("mouse_get_position", {})
        assert not check.denied


# =========================================================================
# Test Error Handling / Edge Cases
# =========================================================================


class TestSecurityErrorHandling:
    @pytest.mark.asyncio
    async def test_adapter_closed_returns_pass(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True)
        await adapter.close()
        check = await adapter.check_tool_execution("test", {})
        assert check.status == SecurityStatus.PASS
        assert not check.denied

    @pytest.mark.asyncio
    async def test_disabled_adapter_returns_pass(self) -> None:
        adapter = LocalSecurityAdapter(enabled=False)
        check = await adapter.check_tool_execution("dangerous_tool", {})
        assert check.status == SecurityStatus.PASS

    @pytest.mark.asyncio
    async def test_empty_arguments(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True, sandbox_enabled=True)
        check = await adapter.check_tool_execution("", {})
        assert check.status == SecurityStatus.CONFIRM

    @pytest.mark.asyncio
    async def test_none_arguments(self) -> None:
        adapter = LocalSecurityAdapter(enabled=True, sandbox_enabled=True)
        check = await adapter.check_tool_execution("test", None)  # type: ignore[arg-type]
        assert check.status == SecurityStatus.CONFIRM


# =========================================================================
# Test ModuleInterface conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_security_manager_conforms_to_protocol(self) -> None:
        from backend.types import ModuleInterface

        mgr = SecurityManager()
        assert isinstance(mgr, ModuleInterface)

    def test_security_manager_has_required_methods(self) -> None:
        mgr = SecurityManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
