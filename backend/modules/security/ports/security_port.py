from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.modules.security._types import (
    AuditEntry,
    RiskLevel,
    SecurityCheck,
    SecurityContext,
)
from backend.types import ToolResult


class SecurityPort(ABC):
    @abstractmethod
    async def check_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        ...

    @abstractmethod
    async def validate_path(
        self,
        path: str,
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        ...

    @abstractmethod
    async def validate_command(
        self,
        command: str,
        context: SecurityContext | None = None,
    ) -> SecurityCheck:
        ...

    @abstractmethod
    async def get_risk_level(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> RiskLevel:
        ...

    @abstractmethod
    async def log_audit(
        self,
        entry: AuditEntry,
    ) -> None:
        ...

    @abstractmethod
    async def get_audit_log(
        self,
        limit: int = 100,
    ) -> list[AuditEntry]:
        ...

    @abstractmethod
    async def get_status(self) -> ToolResult:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        ...
