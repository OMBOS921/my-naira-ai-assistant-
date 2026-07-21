from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionMode(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"
    ADMIN = "admin"


class SecurityStatus(str, Enum):
    PASS = "pass"
    DENY = "deny"
    CONFIRM = "confirm"
    ERROR = "error"


@dataclass(frozen=True)
class SecurityCheck:
    status: SecurityStatus
    risk_level: RiskLevel = RiskLevel.LOW
    reason: str | None = None
    denied: bool = False
    requires_confirmation: bool = False
    sanitized_input: dict[str, Any] | None = None


@dataclass(frozen=True)
class AuditEntry:
    timestamp: datetime
    tool: str
    arguments: dict[str, Any]
    caller: str
    approval: str
    result: str
    execution_time_ms: float
    risk_score: RiskLevel
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class SecurityPolicyRule:
    tool_pattern: str
    mode: PermissionMode
    risk_level: RiskLevel = RiskLevel.LOW
    require_approval: bool = False


@dataclass(frozen=True)
class SecurityContext:
    user_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    caller: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)
