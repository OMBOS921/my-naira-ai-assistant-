from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from backend.modules.security._types import AuditEntry, RiskLevel

_LOG = logging.getLogger("naira.security.audit")


class AuditLogger:
    def __init__(
        self,
        enabled: bool = True,
        max_entries: int = 10000,
        logger: logging.Logger | None = None,
    ) -> None:
        self._enabled = enabled
        self._entries: deque[AuditEntry] = deque(maxlen=max_entries)
        self._logger = logger or _LOG

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def log(
        self,
        tool: str,
        arguments: dict[str, Any],
        caller: str,
        approval: str,
        result: str,
        execution_time_ms: float,
        risk_score: RiskLevel,
    ) -> None:
        if not self._enabled:
            return
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
        self._entries.append(entry)
        self._logger.debug("Audit: %s/%s -> %s (%s)", caller, tool, result, risk_score.value)

    async def get_log(self, limit: int = 100) -> list[AuditEntry]:
        return list(self._entries)[-limit:]

    async def clear(self) -> None:
        self._entries.clear()
        self._logger.info("Audit log cleared")

    @property
    def count(self) -> int:
        return len(self._entries)
