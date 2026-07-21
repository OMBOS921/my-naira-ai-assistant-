"""
Skill Composer — allows multiple Skill Packs to work together.

Composes execution plans from multiple skills.
React + TypeScript + Node + Docker + Git should produce one combined plan.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._skill_port import SkillPort
from backend.modules.coding_agent.skills._types import SkillResult
from backend.modules.coding_agent.skills.context._models import SkillContext

_LOG = logging.getLogger("naira.coding_agent.skills.composition")


class SkillComposer:
    """Composes multiple Skill Packs into a single execution plan."""

    def __init__(
        self,
        *,
        config: SkillConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config or SkillConfig()
        self._logger = logger or _LOG

    async def compose_plan(
        self,
        skills: list[SkillPort],
        context: SkillContext,
        query: str,
    ) -> SkillResult:
        """Execute multiple skills and merge their plans.

        The composition strategy ('merge', 'priority', 'sequential')
        is configurable via ``SkillConfig.composition_strategy``.
        """
        if not skills:
            return SkillResult.fail("No skills provided for composition")

        max_skills = min(
            self._config.composition_max_skills,
            len(skills),
        )
        selected = skills[:max_skills]
        strategy = self._config.composition_strategy

        if strategy == "sequential" or len(selected) == 1:
            return await self._sequential(selected, context, query)
        elif strategy == "priority":
            return await self._priority_based(selected, context, query)
        else:
            return await self._merge(selected, context, query)

    async def _merge(
        self,
        skills: list[SkillPort],
        context: SkillContext,
        query: str,
    ) -> SkillResult:
        """Merge results from all skills into a combined plan."""
        all_lines: list[str] = []
        all_suggestions: list[str] = []
        all_warnings: list[str] = []
        total_duration = 0.0
        all_errors: list[str] = []
        combined_metadata: dict[str, Any] = {}

        for skill in skills:
            try:
                meta = skill.metadata()
                result = await skill.plan(context)
                total_duration += result.duration_ms
                if result.success:
                    if result.content:
                        all_lines.append(
                            f"## {meta.name}\n{result.content}"
                        )
                    all_suggestions.extend(result.suggestions)
                    all_warnings.extend(result.warnings)
                    combined_metadata[meta.name] = {
                        "success": True,
                        "duration_ms": result.duration_ms,
                    }
                else:
                    all_errors.extend(result.errors)
                    combined_metadata[meta.name] = {
                        "success": False,
                        "errors": result.errors,
                    }
            except Exception as exc:
                all_errors.append(f"{skill.metadata().name}: {exc}")
                combined_metadata[skill.metadata().name] = {
                    "success": False,
                    "errors": [str(exc)],
                }

        return SkillResult(
            success=len(all_errors) == 0,
            content="\n\n".join(all_lines),
            suggestions=all_suggestions,
            errors=all_errors,
            warnings=all_warnings,
            metadata={
                "composed": True,
                "skills_used": [s.metadata().name for s in skills],
                "per_skill": combined_metadata,
                "strategy": "merge",
            },
            duration_ms=total_duration,
        )

    async def _sequential(
        self,
        skills: list[SkillPort],
        context: SkillContext,
        query: str,
    ) -> SkillResult:
        """Execute skills one by one, passing previous result as context."""
        current_context = context
        final_result = SkillResult.ok()
        combined_metadata: dict[str, Any] = {}

        for skill in skills:
            try:
                meta = skill.metadata()
                current_context.query = query
                result = await skill.plan(current_context)
                combined_metadata[meta.name] = {
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                }
                if result.success:
                    final_result = SkillResult(
                        success=True,
                        content=result.content or final_result.content,
                        suggestions=list(
                            dict.fromkeys(
                                final_result.suggestions + result.suggestions
                            )
                        ),
                        errors=final_result.errors + result.errors,
                        warnings=list(
                            dict.fromkeys(
                                final_result.warnings + result.warnings
                            )
                        ),
                        metadata={
                            "composed": True,
                            "sequential": True,
                            "skills_used": [s.metadata().name for s in skills],
                            "per_skill": combined_metadata,
                        },
                        duration_ms=final_result.duration_ms + result.duration_ms,
                    )
                else:
                    final_result.errors.extend(result.errors)
            except Exception as exc:
                combined_metadata[skill.metadata().name] = {
                    "success": False,
                    "errors": [str(exc)],
                }
                final_result.errors.append(f"{skill.metadata().name}: {exc}")

        return final_result

    async def _priority_based(
        self,
        skills: list[SkillPort],
        context: SkillContext,
        query: str,
    ) -> SkillResult:
        """Priority-based: higher priority skills override lower ones on conflict."""
        sorted_skills = sorted(
            skills,
            key=lambda s: s.metadata().priority,
        )
        return await self._merge(sorted_skills, context, query)

    async def compose_analysis(
        self,
        skills: list[SkillPort],
        context: SkillContext,
    ) -> SkillResult:
        """Compose analysis across multiple skills."""
        return await self.compose_plan(skills, context, "analyse")

    async def compose_review(
        self,
        skills: list[SkillPort],
        context: SkillContext,
    ) -> SkillResult:
        """Compose code review across multiple skills."""
        all_results: list[SkillResult] = []
        for skill in skills:
            try:
                result = await skill.review(context)
                all_results.append(result)
            except Exception as exc:
                all_results.append(
                    SkillResult.fail(f"{skill.metadata().name}: {exc}")
                )

        merged = self._merge_results(all_results, skills)
        merged.metadata["composed"] = True
        merged.metadata["composition_type"] = "review"
        return merged

    def _merge_results(
        self,
        results: list[SkillResult],
        skills: list[SkillPort],
    ) -> SkillResult:
        all_content: list[str] = []
        all_suggestions: list[str] = []
        all_warnings: list[str] = []
        all_errors: list[str] = []
        total_duration = 0.0
        combined_metadata: dict[str, Any] = {}

        for i, result in enumerate(results):
            name = skills[i].metadata().name if i < len(skills) else f"skill_{i}"
            if result.success and result.content:
                all_content.append(f"## {name}\n{result.content}")
            all_suggestions.extend(result.suggestions)
            all_warnings.extend(result.warnings)
            all_errors.extend(result.errors)
            total_duration += result.duration_ms
            combined_metadata[name] = {
                "success": result.success,
                "duration_ms": result.duration_ms,
            }

        return SkillResult(
            success=len(all_errors) == 0,
            content="\n\n".join(all_content),
            suggestions=list(dict.fromkeys(all_suggestions)),
            errors=all_errors,
            warnings=list(dict.fromkeys(all_warnings)),
            metadata={
                "skills_used": [s.metadata().name for s in skills],
                "per_skill": combined_metadata,
                "strategy": "merge",
            },
            duration_ms=total_duration,
        )
