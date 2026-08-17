from __future__ import annotations

import logging
from typing import Any

from backend.modules.security._audit_logger import AuditLogger
from backend.modules.security._command_validator import CommandValidator
from backend.modules.security._path_validator import PathValidator
from backend.modules.security._permission_manager import PermissionManager
from backend.modules.security._policy_engine import SecurityPolicyEngine
from backend.modules.security._risk_analyzer import RiskAnalyzer
from backend.modules.security._sandbox_manager import SandboxManager
from backend.modules.security._types import (
    AuditEntry,
    PermissionMode,
    RiskLevel,
    SecurityCheck,
    SecurityContext,
    SecurityStatus,
)
from backend.modules.security.ports.security_port import SecurityPort
from backend.types import ToolResult
_LOG = logging.getLogger("naira.security.adapter")


class LocalSecurityAdapter(SecurityPort):
    def __init__(
        self,
        *,
        enabled: bool = True,
        sandbox_enabled: bool = True,
        audit_enabled: bool = True,
        default_policy: str = "allow",
        max_risk: str = "critical",
        allowed_paths: tuple[str, ...] = (),
        blocked_paths: tuple[str, ...] = (),
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._closed = False
        self._enabled = enabled

        self.audit_logger = AuditLogger(enabled=audit_enabled, logger=logger)
        self.command_validator = CommandValidator()
        self.path_validator = PathValidator(
            allowed_paths=allowed_paths,
            blocked_paths=blocked_paths,
        )
        self.sandbox_manager = SandboxManager(enabled=sandbox_enabled, logger=logger)
        self.risk_analyzer = RiskAnalyzer(max_risk=max_risk, logger=logger)
        self.permission_manager = PermissionManager()
        self.policy_engine = SecurityPolicyEngine(
            default_policy=default_policy,
            logger=logger,
        )

    @property
    def is_available(self) -> bool:
        return self._enabled and not self._closed

    async def close(self) -> None:
        self._closed = True
        self._logger.info("Security adapter closed")

    async def check_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        if not self._enabled or self._closed:
            return SecurityCheck(
                status=SecurityStatus.PASS,
                risk_level=RiskLevel.LOW,
            )

        sandbox_check = await self.sandbox_manager.check_action(tool_name, arguments)
        if sandbox_check.denied:
            return sandbox_check
        if sandbox_check.requires_confirmation:
            return sandbox_check

        risk = self.risk_analyzer.analyze(tool_name, arguments)
        if self.risk_analyzer.is_above_threshold(risk):
            return SecurityCheck(
                status=SecurityStatus.DENY,
                risk_level=risk,
                reason="Risk level exceeds maximum allowed threshold",
                denied=True,
            )

        policy = self.policy_engine.evaluate(tool_name, risk)
        if policy == PermissionMode.DENY:
            return SecurityCheck(
                status=SecurityStatus.DENY,
                risk_level=risk,
                reason=f"Policy denies tool '{tool_name}'",
                denied=True,
            )

        needs_approval = self.policy_engine.requires_approval(tool_name, risk)
        if policy == PermissionMode.CONFIRM or needs_approval:
            return SecurityCheck(
                status=SecurityStatus.CONFIRM,
                risk_level=risk,
                reason=f"Tool '{tool_name}' requires human approval",
                requires_confirmation=True,
            )

        return SecurityCheck(
            status=SecurityStatus.PASS,
            risk_level=risk,
        )

    async def validate_path(
        self,
        path: str,
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        return await self.path_validator.validate(path)

    async def validate_command(
        self,
        command: str,
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        return await self.command_validator.validate(command)

    async def get_risk_level(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> RiskLevel:
        return self.risk_analyzer.analyze(tool_name, arguments)

    async def log_audit(self, entry: AuditEntry) -> None:
        await self.audit_logger.log(
            tool=entry.tool,
            arguments=entry.arguments,
            caller=entry.caller,
            approval=entry.approval,
            result=entry.result,
            execution_time_ms=entry.execution_time_ms,
            risk_score=entry.risk_score,
        )

    async def get_audit_log(self, limit: int = 100) -> list[AuditEntry]:
        return await self.audit_logger.get_log(limit=limit)

    async def get_status(self) -> ToolResult:
        return ToolResult(
            status="success",
            output=(
                f"enabled={self._enabled}, "
                f"available={self.is_available}, "
                f"audit_count={self.audit_logger.count}, "
                f"policy_rules={len(self.policy_engine.list_rules())}"
            ),
        )
