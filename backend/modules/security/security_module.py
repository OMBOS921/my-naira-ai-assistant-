from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.security._executor import SecurityExecutor
from backend.modules.security._local_adapter import LocalSecurityAdapter
from backend.modules.security._types import (
    AuditEntry,
    PermissionMode,
    RiskLevel,
    SecurityCheck,
    SecurityPolicyRule,
)
from backend.modules.security.ports.security_port import SecurityPort
from backend.types import ToolResult

_LOG = logging.getLogger("naira.security")


class SecurityManager:
    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        tool_manager: object | None = None,
        adapter: SecurityPort | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._degraded: bool = False
        self._default_timeout = default_timeout

        sec_config = getattr(config, "security", None) if config else None

        self._adapter = adapter or LocalSecurityAdapter(
            enabled=getattr(sec_config, "enabled", True) if sec_config else True,
            sandbox_enabled=getattr(sec_config, "sandbox_enabled", True) if sec_config else True,
            audit_enabled=getattr(sec_config, "audit_enabled", True) if sec_config else True,
            default_policy=(
                getattr(sec_config, "default_policy", "allow") if sec_config else "allow"
            ),
            max_risk=getattr(sec_config, "max_risk", "critical") if sec_config else "critical",
            allowed_paths=getattr(sec_config, "allowed_paths", ()) if sec_config else (),
            blocked_paths=getattr(sec_config, "blocked_paths", ()) if sec_config else (),
            logger=logger,
        )
        self._executor = SecurityExecutor(
            adapter=self._adapter,
            default_timeout=default_timeout,
            logger=logger,
        )

    async def async_init(self) -> None:
        self._register_capability()
        self._register_tools()
        self._logger.info(
            "Security manager initialised — adapter available: %s, sandbox: %s",
            self._executor.is_available,
            getattr(self._adapter.sandbox_manager, "enabled", False),
        )

    async def async_shutdown(self) -> None:
        try:
            await self._adapter.close()
        except Exception as exc:
            self._logger.warning("Error closing security adapter: %s", exc)
        self._degraded = False
        self._logger.info("Security manager shut down.")

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("Security manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def is_available(self) -> bool:
        return self._executor.is_available

    # ------------------------------------------------------------------
    # Permission API (used by ToolPermission integration)
    # ------------------------------------------------------------------

    def check_permission(self, tool_name: str, permission_key: str) -> bool:
        return self._adapter.permission_manager.check_permission(tool_name)

    # ------------------------------------------------------------------
    # Public API — security checks
    # ------------------------------------------------------------------

    async def check_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        caller: str = "system",
    ) -> SecurityCheck:
        self._ensure_not_degraded()
        await self._emit_event_async("security.check.start", {
            "tool": tool_name,
            "caller": caller,
        })
        check = await self._executor.check_tool(tool_name, arguments)
        await self._emit_event_async("security.check.complete", {
            "tool": tool_name,
            "status": check.status.value,
            "risk": check.risk_level.value,
            "denied": check.denied,
        })
        if check.denied:
            await self._emit_event_async("security.denied", {
                "tool": tool_name,
                "reason": check.reason,
                "risk": check.risk_level.value,
            })
        if check.requires_confirmation:
            await self._emit_event_async("security.confirm_required", {
                "tool": tool_name,
                "reason": check.reason,
                "risk": check.risk_level.value,
            })
        return check

    async def check_path(self, path: str) -> SecurityCheck:
        self._ensure_not_degraded()
        return await self._executor.check_path(path)

    async def check_command(self, command: str) -> SecurityCheck:
        self._ensure_not_degraded()
        return await self._executor.check_command(command)

    async def get_risk_level(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> RiskLevel:
        return await self._adapter.get_risk_level(tool_name, arguments)

    async def log_audit(
        self,
        tool: str,
        arguments: dict[str, Any],
        caller: str,
        approval: str,
        result: str,
        execution_time_ms: float,
        risk_score: RiskLevel,
    ) -> None:
        self._ensure_not_degraded()
        await self._executor.log_audit(
            tool=tool,
            arguments=arguments,
            caller=caller,
            approval=approval,
            result=result,
            execution_time_ms=execution_time_ms,
            risk_score=risk_score,
        )
        await self._emit_event_async("security.audit", {
            "tool": tool,
            "caller": caller,
            "result": result,
        })

    async def get_audit_log(self, limit: int = 100) -> list[AuditEntry]:
        return await self._executor.get_audit_log(limit=limit)

    async def get_status(self) -> ToolResult:
        self._ensure_not_degraded()
        return await self._executor.get_status()

    # ------------------------------------------------------------------
    # Policy API
    # ------------------------------------------------------------------

    def add_policy_rule(self, rule: SecurityPolicyRule) -> None:
        self._adapter.policy_engine.add_rule(rule)

    def remove_policy_rule(self, tool_pattern: str) -> int:
        return self._adapter.policy_engine.remove_rule(tool_pattern)

    def list_policy_rules(self) -> list[SecurityPolicyRule]:
        return self._adapter.policy_engine.list_rules()

    # ------------------------------------------------------------------
    # Permission API
    # ------------------------------------------------------------------

    def set_tool_permission(self, tool_name: str, mode: PermissionMode) -> None:
        self._adapter.permission_manager.set_permission(tool_name, mode)

    def get_tool_permission(self, tool_name: str) -> PermissionMode:
        return self._adapter.permission_manager.get_permission(tool_name)

    def list_tool_permissions(self) -> dict[str, PermissionMode]:
        return self._adapter.permission_manager.list_permissions()

    # ------------------------------------------------------------------
    # Human-in-the-loop approval
    # ------------------------------------------------------------------

    async def request_approval(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        caller: str = "system",
        timeout: float | None = None,
    ) -> bool:
        effective_timeout = timeout or getattr(
            getattr(self._config, "security", None), "approval_timeout", 60.0
        )
        self._logger.info(
            "Approval requested for '%s' by '%s' (timeout=%ss)",
            tool_name, caller, effective_timeout,
        )
        await self._emit_event_async("security.approval_requested", {
            "tool": tool_name,
            "caller": caller,
        })
        try:
            result = await asyncio.wait_for(
                self._wait_for_approval(tool_name),
                timeout=effective_timeout,
            )
            if result:
                await self._emit_event_async("security.approved", {
                    "tool": tool_name,
                    "caller": caller,
                })
            else:
                await self._emit_event_async("security.denied", {
                    "tool": tool_name,
                    "reason": "User denied approval",
                })
            return result
        except asyncio.TimeoutError:
            self._logger.warning("Approval timed out for '%s'", tool_name)
            await self._emit_event_async("security.denied", {
                "tool": tool_name,
                "reason": "Approval timed out",
            })
            return False

    async def _wait_for_approval(self, tool_name: str) -> bool:
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_capability(self) -> None:
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register", None)
            if register_cap is not None:
                from backend.modules.capability.capability import Capability
                register_cap(Capability(name="security", version="0.1.0"))

    def _register_tools(self) -> None:
        if self._tool_manager is not None:
            register = getattr(self._tool_manager, "register_tool", None)
            if register is not None:
                from backend.modules.tools import ToolDefinition

                register(
                    ToolDefinition(
                        name="security_status",
                        description="Get the current status and config of the security module",
                        parameters={
                            "type": "object",
                            "properties": {},
                        },
                        category="security",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_status_tool,
                )

                register(
                    ToolDefinition(
                        name="security_audit",
                        description="Retrieve recent audit log entries from the security module",
                        parameters={
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of audit entries to return",
                                },
                            },
                        },
                        category="security",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_audit_tool,
                )

                register(
                    ToolDefinition(
                        name="security_policy",
                        description="List or manage security policy rules",
                        parameters={
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["list"],
                                    "description": "Policy action to perform",
                                },
                            },
                            "required": ["action"],
                        },
                        category="security",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_policy_tool,
                )

                register(
                    ToolDefinition(
                        name="security_permissions",
                        description="List tool permission modes configured in the security module",
                        parameters={
                            "type": "object",
                            "properties": {},
                        },
                        category="security",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_permissions_tool,
                )

    async def _handle_status_tool(self) -> ToolResult:
        return await self.get_status()

    async def _handle_audit_tool(self, limit: int = 100) -> ToolResult:
        entries = await self.get_audit_log(limit=limit)
        if not entries:
            return ToolResult(status="success", output="No audit entries found")
        lines = [
            f"[{e.timestamp}] {e.tool} by {e.caller}: "
            f"{e.result} (risk={e.risk_score.value})"
            for e in entries
        ]
        return ToolResult(status="success", output="\n".join(lines))

    async def _handle_policy_tool(self, action: str = "list") -> ToolResult:
        if action == "list":
            rules = self.list_policy_rules()
            if not rules:
                return ToolResult(status="success", output="No policy rules configured")
            lines = [
                f"{r.tool_pattern} -> {r.mode.value} "
                f"(risk={r.risk_level.value}, approval={r.require_approval})"
                for r in rules
            ]
            return ToolResult(status="success", output="\n".join(lines))
        return ToolResult(status="error", error=f"Unknown policy action: {action}")

    async def _handle_permissions_tool(self) -> ToolResult:
        perms = self.list_tool_permissions()
        if not perms:
            return ToolResult(
                status="success",
                output="No custom permissions configured (all tools default to allow)",
            )
        lines = [f"{name}: {mode.value}" for name, mode in perms.items()]
        return ToolResult(status="success", output="\n".join(lines))

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "SecurityManager is degraded",
                context={"module": "security"},
            )

    def _emit_event_sync(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(event_type, data))
            except RuntimeError:
                self._logger.debug("No running loop — event not emitted: %s", event_type)

    async def _emit_event_async(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)
