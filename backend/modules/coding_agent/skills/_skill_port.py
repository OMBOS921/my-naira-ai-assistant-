"""
SkillPort — abstract interface every Skill Pack must implement.

Follows the same Port pattern as LLMPort, VisionPort, VoicePort.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.coding_agent.skills._health import SkillHealthReport
from backend.modules.coding_agent.skills._types import (
    SkillCapability,
    SkillMetadata,
    SkillResult,
    SkillStatistics,
)
from backend.modules.coding_agent.skills.context._models import SkillContext


class SkillPort(ABC):
    """Port that every Skill Pack adapter must implement."""

    # ── Identity ──────────────────────────────────────────────────────

    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Return immutable metadata about this Skill Pack."""

    @abstractmethod
    def capabilities(self) -> list[SkillCapability]:
        """Return the list of capabilities this Skill Pack exposes."""

    # ── Core Operations ───────────────────────────────────────────────

    @abstractmethod
    async def analyse(self, context: SkillContext) -> SkillResult:
        """Analyse code or project structure and return insights."""

    @abstractmethod
    async def plan(self, context: SkillContext) -> SkillResult:
        """Create an execution plan for a given task."""

    @abstractmethod
    async def review(self, context: SkillContext) -> SkillResult:
        """Review code for quality, bugs, and improvements."""

    @abstractmethod
    async def generate(self, context: SkillContext) -> SkillResult:
        """Generate code based on the provided context."""

    @abstractmethod
    async def refactor(self, context: SkillContext) -> SkillResult:
        """Refactor existing code for better quality."""

    @abstractmethod
    async def debug(self, context: SkillContext) -> SkillResult:
        """Analyse and suggest fixes for bugs."""

    @abstractmethod
    async def explain(self, context: SkillContext) -> SkillResult:
        """Explain code in natural language."""

    # ── Health & Metrics ──────────────────────────────────────────────

    @abstractmethod
    async def health(self) -> SkillHealthReport:
        """Return current health status."""

    @abstractmethod
    async def metrics(self) -> SkillStatistics:
        """Return usage statistics."""
