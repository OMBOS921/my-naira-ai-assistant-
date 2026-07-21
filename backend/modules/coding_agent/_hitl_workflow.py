from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.modules.coding_agent._exceptions import HITLRejectedError, HITLTimeoutError

_LOG = logging.getLogger("naira.coding_agent.hitl")


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    id: str
    action: str
    description: str
    details: dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: float = field(default_factory=time.time)
    decided_at: float | None = None
    decision_reason: str | None = None


class HITLWorkflow:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
        approval_timeout: float = 120.0,
        auto_approve_patterns: tuple[str, ...] | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._approval_timeout = approval_timeout
        self._auto_approve_patterns = auto_approve_patterns or (
            "read", "list", "get", "status", "diff", "log",
        )
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []
        self._total_requests = 0
        self._approved_count = 0
        self._rejected_count = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("HITLWorkflow marked degraded")

    def _should_auto_approve(self, action: str, details: dict[str, Any] | None = None) -> bool:
        action_lower = action.lower()
        for pattern in self._auto_approve_patterns:
            if action_lower.startswith(pattern.lower()):
                return True
        return False

    async def request_approval(
        self,
        action: str,
        description: str,
        details: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> ApprovalRequest:
        if not self._enabled or self._degraded:
            req = self._create_approved(action, description, details)
            return req

        if self._should_auto_approve(action, details):
            req = self._create_approved(action, description, details)
            self._logger.debug("Auto-approved: %s", action)
            return req

        req_id = str(uuid.uuid4())
        req = ApprovalRequest(
            id=req_id,
            action=action,
            description=description,
            details=details or {},
        )
        self._pending[req_id] = req
        self._total_requests += 1

        effective_timeout = timeout if timeout is not None else self._approval_timeout
        try:
            await asyncio.wait_for(
                self._wait_for_decision(req_id),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            req.status = ApprovalStatus.TIMED_OUT
            req.decided_at = time.time()
            req.decision_reason = "Approval timed out"
            self._pending.pop(req_id, None)
            self._history.append(req)
            raise HITLTimeoutError(
                f"Approval timed out for action: {action}",
                context={
                    "action": action,
                    "description": description,
                    "timeout": effective_timeout,
                },
            ) from None

        if req.status == ApprovalStatus.REJECTED:
            raise HITLRejectedError(
                f"Approval rejected for action: {action}",
                context={
                    "action": action,
                    "description": description,
                    "reason": req.decision_reason,
                },
            )

        return req

    async def _wait_for_decision(self, req_id: str) -> None:
        while req_id in self._pending:
            req = self._pending[req_id]
            if req.status in (
                ApprovalStatus.APPROVED, ApprovalStatus.REJECTED,
                ApprovalStatus.CANCELLED,
            ):
                return
            await asyncio.sleep(0.1)

    def approve(self, req_id: str, reason: str | None = None) -> ApprovalRequest | None:
        req = self._pending.get(req_id)
        if req is None:
            return None
        req.status = ApprovalStatus.APPROVED
        req.decided_at = time.time()
        req.decision_reason = reason
        self._approved_count += 1
        self._pending.pop(req_id, None)
        self._history.append(req)
        return req

    def reject(self, req_id: str, reason: str = "No reason provided") -> ApprovalRequest | None:
        req = self._pending.get(req_id)
        if req is None:
            return None
        req.status = ApprovalStatus.REJECTED
        req.decided_at = time.time()
        req.decision_reason = reason
        self._rejected_count += 1
        self._pending.pop(req_id, None)
        self._history.append(req)
        return req

    def cancel(self, req_id: str) -> ApprovalRequest | None:
        req = self._pending.get(req_id)
        if req is None:
            return None
        req.status = ApprovalStatus.CANCELLED
        req.decided_at = time.time()
        self._pending.pop(req_id, None)
        self._history.append(req)
        return req

    def get_pending(self) -> list[ApprovalRequest]:
        return list(self._pending.values())

    def get_history(self, max_items: int = 50) -> list[ApprovalRequest]:
        return self._history[-max_items:]

    def get_request(self, req_id: str) -> ApprovalRequest | None:
        req = self._pending.get(req_id)
        if req is not None:
            return req
        for h in reversed(self._history):
            if h.id == req_id:
                return h
        return None

    def _create_approved(
        self, action: str, description: str, details: dict[str, Any] | None
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            action=action,
            description=description,
            details=details or {},
            status=ApprovalStatus.APPROVED,
            decided_at=time.time(),
        )
        self._total_requests += 1
        self._approved_count += 1
        self._history.append(req)
        return req

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "total_requests": self._total_requests,
            "approved_count": self._approved_count,
            "rejected_count": self._rejected_count,
            "pending_count": len(self._pending),
            "approval_timeout": self._approval_timeout,
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
