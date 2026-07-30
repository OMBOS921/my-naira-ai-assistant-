"""Logician module for language-agnostic logic decomposition."""

from backend.modules.syntax_master.logician.prompt_templates import (
    LOGICIAN_SYSTEM_PROMPT,
    generate_logician_prompt,
)
from backend.modules.syntax_master.logician.schema import (
    StepDefinition,
    StepType,
    TaskLogic,
    VariableDefinition,
)
from backend.modules.syntax_master.logician.validator import (
    LogicianValidator,
    ValidationResult,
)

__all__ = [
    "StepType",
    "VariableDefinition",
    "StepDefinition",
    "TaskLogic",
    "LOGICIAN_SYSTEM_PROMPT",
    "generate_logician_prompt",
    "ValidationResult",
    "LogicianValidator",
]
