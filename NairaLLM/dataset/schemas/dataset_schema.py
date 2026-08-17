"""
Canonical Dataset Schemas for NairaLLM.

Defines Pydantic models for all 18 dataset families, canonical JSONL structures,
provenance metadata, and validation rules.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class DatasetFamily(StrEnum):
    CONVERSATION = "conversation"
    INTENT = "intent"
    CONTEXT_RESOLUTION = "context_resolution"
    TOOL_SELECTION = "tool_selection"
    TOOL_ARGUMENTS = "tool_arguments"
    TOOL_RESULTS = "tool_results"
    VERIFICATION = "verification"
    PLANNING = "planning"
    MEMORY = "memory"
    BROWSER_RESEARCH = "browser_research"
    CODING = "coding"
    PERSONALITY = "personality"
    EMOTION_USER_STATE = "emotion_user_state"
    PROACTIVE_BEHAVIOR = "proactive_behavior"
    BOUNDED_AUTONOMY = "bounded_autonomy"
    ERROR_RECOVERY = "error_recovery"
    SAFETY_PERMISSIONS = "safety_permissions"
    MULTI_STEP_TASKS = "multi_step_tasks"


class Language(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"


class ProvenanceMetadata(BaseModel):
    """Provenance and origin tracking for dataset samples."""

    author: str = Field(default="nairallm_core_team", description="Creator or generator identifier")
    created_at: str = Field(default="2026-08-14", description="Creation date ISO string")
    source_type: Literal["human_curated", "rule_synthesized", "verified_scenario"] = Field(
        default="human_curated",
        description="Origin type of the sample (no undocumented proprietary teacher models)",
    )
    verified_by_naira_runtime: bool = Field(
        default=True,
        description="Whether tool calls and behavior were verified against actual Naira OS interfaces",
    )
    notes: str = Field(default="", description="Additional context or rationale")


class ToolCallItem(BaseModel):
    """Structured tool call representation matching Naira OS ToolCall."""

    name: str = Field(..., description="Exact tool name matching Naira OS registry")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Validated JSON arguments")


class MessageItem(BaseModel):
    """Single conversation turn."""

    role: Literal["system", "user", "assistant", "tool"] = Field(..., description="Message role")
    content: str = Field(..., description="Text content")
    tool_calls: list[ToolCallItem] | None = Field(default=None, description="Optional tool calls")
    tool_name: str | None = Field(default=None, description="Tool name for role='tool'")


class NairaDatasetSample(BaseModel):
    """Canonical dataset record for NairaLLM training, validation, and evaluation."""

    id: str = Field(..., description="Unique sample identifier (e.g., 'conv_001', 'tool_pc_005')")
    family: DatasetFamily = Field(..., description="Dataset family category")
    language: Language = Field(default=Language.ENGLISH, description="Language code")
    system_prompt: str = Field(
        default="You are Naira, a thoughtful, helpful, proactive AI operating system assistant.",
        description="System instruction prompt for this turn",
    )
    conversations: list[MessageItem] = Field(..., description="Multi-turn conversation sequence")
    target_tool_calls: list[ToolCallItem] = Field(
        default_factory=list,
        description="Expected ground truth tool calls (if any)",
    )
    expected_reasoning: str | None = Field(
        default=None,
        description="Internal planning or reasoning chain before response",
    )
    verification_target: str | None = Field(
        default=None,
        description="Verification check assertion for the outcome",
    )
    provenance: ProvenanceMetadata = Field(
        default_factory=ProvenanceMetadata,
        description="Traceability metadata",
    )
    quality_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Curated quality score (0.0 to 1.0)",
    )
    difficulty: Literal["basic", "intermediate", "complex", "challenge"] = Field(
        default="basic",
        description="Complexity level",
    )

    @field_validator("conversations")
    @classmethod
    def validate_conversations_non_empty(cls, v: list[MessageItem]) -> list[MessageItem]:
        if not v:
            raise ValueError("conversations list cannot be empty")
        return v
