"""
Shared core types — enums, dataclasses, type aliases, and protocols.

21_System_Contracts.md §7, §10, §15.

FSMState is defined in ``backend/orchestrator.py`` and imported here
for convenience; all other shared types originate in this module.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Type aliases  (Python 3.12+ ``type`` syntax)
# ---------------------------------------------------------------------------

type JSON = dict[str, Any]
"""Serialisable JSON-compatible dictionary."""

type EventPriority = Literal["high", "normal", "low"]
"""Priority level for Event Bus messages."""

type RequestSource = Literal["cli", "websocket", "voice"]
"""Origin of a user request."""

type FinishReason = Literal["stop", "tool_calls", "length", "error"]
"""Reason an LLM response finished."""

# ---------------------------------------------------------------------------
# Immutable data objects  (@dataclass(frozen=True))
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption for an LLM invocation."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ToolCall:
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolDef:
    """Definition of an available tool for the LLM."""

    name: str
    description: str
    parameters: JSON


@dataclass(frozen=True)
class Message:
    """A single message in a conversation turn."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from an LLM provider."""

    text: str
    tool_calls: list[ToolCall] | None
    finish_reason: FinishReason
    token_usage: TokenUsage
    provider: str
    duration_ms: float


@dataclass(frozen=True)
class UserRequest:
    """An immutable inbound request from any presentation layer."""

    id: uuid.UUID
    source: RequestSource
    text: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserResponse:
    """Outbound response delivered to the presentation layer."""

    request_id: uuid.UUID
    text: str
    source: RequestSource
    duration_ms: float = 0.0


@dataclass(frozen=True)
class Context:
    """Assembled context for an LLM invocation."""

    system_prompt: str
    messages: list[Message]
    token_count: int


@dataclass(frozen=True)
class ValidationResult:
    """Result of security validation on a user input."""

    status: Literal["pass", "reject", "sanitized"]
    sanitized_text: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ToolResult:
    """Result returned by a tool or module execution."""

    status: Literal["success", "error", "timeout"]
    output: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class SearchResult:
    """A single result from a vector index query."""

    source_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    """An event published on the Event Bus."""

    type: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = "normal"
    timestamp: float = 0.0
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocols  (structural subtyping)
# ---------------------------------------------------------------------------


@runtime_checkable
class ModuleInterface(Protocol):
    """Contract every loadable module must satisfy.

    21_System_Contracts.md §4.2.

    Implementations must also accept keyword-only constructor arguments
    (e.g. ``config``, ``logger``) via ``__init__(*, ...)``.
    """

    async def async_init(self) -> None:
        """Perform asynchronous initialisation after construction."""
        ...

    async def async_shutdown(self) -> None:
        """Release all resources held by the module."""
        ...

    def degrade(self) -> None:
        """Mark the module as degraded after a non-fatal failure."""
        ...
