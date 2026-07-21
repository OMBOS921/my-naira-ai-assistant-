"""CodingAgent exceptions hierarchy.

21_System_Contracts.md §3 — all application exceptions inherit from
``NairaError`` and carry a ``context`` dict with debugging information.
"""

from __future__ import annotations

from backend.exceptions import NairaError


class CodingAgentError(NairaError):
    """Base exception for all CodingAgent errors."""


class AgentInitializationError(CodingAgentError):
    """Agent initialization failure."""


class AgentRuntimeError(CodingAgentError):
    """Agent runtime operation failure."""


class AgentTimeoutError(AgentRuntimeError):
    """Agent operation exceeded its deadline."""


class TaskPlanningError(CodingAgentError):
    """Task planning failure."""


class ToolSelectionError(CodingAgentError):
    """Tool selection failure."""


class WorkspaceError(CodingAgentError):
    """Workspace operation failure."""


class FileOperationError(CodingAgentError):
    """File operation failure."""


class GitOperationError(CodingAgentError):
    """Git operation failure."""


class CommandExecutionError(CodingAgentError):
    """Command execution failure."""


class LanguageDetectionError(CodingAgentError):
    """Language detection failure."""


class ReflectionError(CodingAgentError):
    """Reflection or analysis failure."""


class SafetyViolationError(CodingAgentError):
    """Safety layer violation."""


class ContextBuildError(CodingAgentError):
    """Context building failure."""


class MemoryError(CodingAgentError):
    """Agent memory operation failure."""


class HITLError(CodingAgentError):
    """Human-in-the-Loop operation failure."""


class HITLTimeoutError(HITLError):
    """HITL approval request timed out."""


class HITLRejectedError(HITLError):
    """HITL approval request was rejected."""


class ComposeModeError(CodingAgentError):
    """Compose mode operation failure."""


class TDDError(CodingAgentError):
    """Test-Driven Development loop failure."""


class TDDTestFailureError(TDDError):
    """A test in the TDD loop failed."""


class CICDError(CodingAgentError):
    """CI/CD monitoring operation failure."""


class CostTrackingError(CodingAgentError):
    """Cost tracking operation failure."""


class SecurityScanError(CodingAgentError):
    """Security scanning operation failure."""


class SecurityVulnerabilityFoundError(SecurityScanError):
    """A security vulnerability was detected."""


class PackageInstallError(CodingAgentError):
    """Package auto-install operation failure."""
