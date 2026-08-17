"""
ToolDefinition — static descriptor for a registered tool.

21_System_Contracts.md §15 — Tool contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.types import JSON, ToolDef
@dataclass(frozen=True)
class RetryPolicy:
    """Retry behaviour for tool execution.

    Parameters
    ----------
    max_retries : int
        Maximum number of retry attempts (default 3).
    base_delay : float
        Initial delay in seconds before the first retry (default 1.0).
    max_delay : float
        Maximum delay in seconds between retries (default 30.0).
    backoff_multiplier : float
        Exponential backoff factor (default 2.0).
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_multiplier: float = 2.0


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable descriptor for a single tool.

    Combines the LLM-facing ``ToolDef`` fields with runtime metadata
    such as category, permissions, timeout, and retry policy.

    Parameters
    ----------
    name : str
        Unique tool name.
    description : str
        Human-readable description of what the tool does.
    parameters : JSON
        JSON Schema describing the expected input arguments.
    category : str
        Logical grouping category (e.g. ``"system"``, ``"file"``,
        ``"web"``).  Default ``"general"``.
    enabled : bool
        Whether the tool is available for execution (default True).
    timeout_seconds : float
        Maximum wall-clock time for a single execution (default 30.0).
    retry_policy : RetryPolicy
        Retry configuration (default ``RetryPolicy()``).
    required_permissions : tuple[str, ...]
        Permission keys required to execute this tool.
    metadata : dict[str, Any]
        Extensible bag for custom tool metadata.
    """

    name: str
    description: str
    parameters: JSON = field(default_factory=dict)
    category: str = "general"
    enabled: bool = True
    timeout_seconds: float = 30.0
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    required_permissions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_tool_def(self) -> ToolDef:
        """Convert to the lightweight ``ToolDef`` used by the LLM layer."""
        return ToolDef(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )
