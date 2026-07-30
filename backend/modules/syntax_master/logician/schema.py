"""Pydantic v2 schema definitions for the Logician module."""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class StepType(str, Enum):
    """Supported step types representing fundamental logic constructs."""
    CONDITION = "condition"
    LOOP = "loop"
    ASSIGNMENT = "assignment"
    IO = "io"
    FUNCTION_CALL = "function_call"
    RETURN = "return"
    ERROR_HANDLING = "error_handling"
    EXPRESSION = "expression"


class VariableDefinition(BaseModel):
    """Definition of a variable used within the logical flow."""
    name: str = Field(..., description="Unique identifier name of the variable")
    type: str = Field(..., description="Abstract data type (e.g., int, str, float, bool, list, dict, object)")
    initial_value: Optional[Any] = Field(default=None, description="Optional initial value or representation")

    @field_validator("name", "type", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("String field cannot be empty.")
        return v


class StepDefinition(BaseModel):
    """Represents a single discrete logical step in the task execution breakdown."""
    step_id: str = Field(..., description="Unique step identifier (e.g., '1', '1.1', 'step_1')")
    type: StepType = Field(..., description="Logical step category")
    description: str = Field(..., description="Language-agnostic natural language step explanation (no syntax)")
    condition: Optional[str] = Field(default=None, description="Branching/loop evaluation condition (if applicable)")
    body: Optional[List[StepDefinition]] = Field(default=None, description="Nested child steps for loops or conditional blocks")
    target_variable: Optional[str] = Field(default=None, description="Variable assigned or modified by this step (if applicable)")
    arguments: Optional[List[str]] = Field(default=None, description="Logical argument descriptions for function call or IO step")

    @field_validator("step_id", "description", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("String field cannot be empty.")
        return v

    @model_validator(mode="after")
    def validate_step_structure(self) -> StepDefinition:
        if self.type in (StepType.CONDITION, StepType.LOOP):
            if not self.condition and not self.body:
                # Require at least condition description or body for condition/loop steps
                pass
        return self


class TaskLogic(BaseModel):
    """Main model capturing the complete, language-agnostic logic for a requested task."""
    target_language: str = Field(..., description="Target programming language for subsequent code synthesis")
    task_summary: str = Field(..., description="High-level description of what this logical algorithm accomplishes")
    variables: List[VariableDefinition] = Field(default_factory=list, description="Variables declared or manipulated in the task")
    steps: List[StepDefinition] = Field(..., min_length=1, description="Ordered list of logical execution steps")

    @field_validator("target_language", "task_summary", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Field cannot be empty.")
        return v
