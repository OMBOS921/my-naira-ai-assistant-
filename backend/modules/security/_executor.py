from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from backend.modules.security._types import (
    AuditEntry,
    RiskLevel,
    SecurityCheck,
    SecurityContext,
    SecurityStatus,
)
from backend.modules.security.ports.security_port import SecurityPort
from backend.types import ToolResult

_LOG = logging.getLogger("naira.security.executor")


class SecurityExecutor:
    def __init__(
        self,
        adapter: SecurityPort,
        default_timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._adapter = adapter
        self._default_timeout = default_timeout
        self._logger = logger or _LOG

    async def check_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        effective_timeout = self._default_timeout
        try:
            return await asyncio.wait_for(
                self._adapter.check_tool_execution(tool_name, arguments, context),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            return SecurityCheck(
                status=SecurityStatus.ERROR,
                risk_level=RiskLevel.CRITICAL,
                reason="Security check timed out",
            )
        except Exception as exc:
            self._logger.warning("Security check failed: %s", exc)
            return SecurityCheck(
                status=SecurityStatus.ERROR,
                risk_level=RiskLevel.HIGH,
                reason=f"Security check error: {exc}",
            )

    async def check_path(
        self,
        path: str,
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        try:
            return await asyncio.wait_for(
                self._adapter.validate_path(path, context),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            return SecurityCheck(
                status=SecurityStatus.ERROR,
                risk_level=RiskLevel.HIGH,
                reason="Path validation timed out",
            )
        except Exception as exc:
            return SecurityCheck(
                status=SecurityStatus.ERROR,
                risk_level=RiskLevel.HIGH,
                reason=f"Path validation error: {exc}",
            )

    async def check_command(
        self,
        command: str,
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        try:
            return await asyncio.wait_for(
                self._adapter.validate_command(command, context),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            return SecurityCheck(
                status=SecurityStatus.ERROR,
                risk_level=RiskLevel.HIGH,
                reason="Command validation timed out",
            )
        except Exception as exc:
            return SecurityCheck(
                status=SecurityStatus.ERROR,
                risk_level=RiskLevel.HIGH,
                reason=f"Command validation error: {exc}",
            )

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
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            tool=tool,
            arguments=arguments,
            caller=caller,
            approval=approval,
            result=result,
            execution_time_ms=execution_time_ms,
            risk_score=risk_score,
        )
        await self._adapter.log_audit(entry)

    async def get_audit_log(self, limit: int = 100) -> list[AuditEntry]:
        return await self._adapter.get_audit_log(limit=limit)

    async def get_status(self) -> ToolResult:
        return await self._adapter.get_status()

    @property
    def is_available(self) -> bool:
        return self._adapter.is_available
