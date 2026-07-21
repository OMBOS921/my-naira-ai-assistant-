from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.compose")


class SuggestionStatus(Enum):
    ACTIVE = "active"
    APPLIED = "applied"
    DISMISSED = "dismissed"
    MODIFIED = "modified"


@dataclass
class ComposeSuggestion:
    id: str
    file_path: str
    ghost_text: str
    original_text: str | None
    line_start: int
    line_end: int
    description: str = ""
    status: SuggestionStatus = SuggestionStatus.ACTIVE
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    applied_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ComposeMode:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._active_suggestions: dict[str, ComposeSuggestion] = {}
        self._history: list[ComposeSuggestion] = []
        self._total_suggestions = 0
        self._applied_count = 0
        self._dismissed_count = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("ComposeMode marked degraded")

    def generate_ghost_text(
        self,
        file_path: str,
        original_text: str | None,
        suggested_text: str,
        line_start: int = 1,
        line_end: int | None = None,
        description: str = "",
        confidence: float = 1.0,
    ) -> ComposeSuggestion:
        if not self._enabled:
            suggestion = ComposeSuggestion(
                id=str(uuid.uuid4()),
                file_path=file_path,
                ghost_text=suggested_text,
                original_text=original_text,
                line_start=line_start,
                line_end=line_end or line_start + suggested_text.count("\n"),
                description=description,
                status=SuggestionStatus.APPLIED,
                confidence=confidence,
                applied_at=time.time(),
            )
            self._total_suggestions += 1
            self._applied_count += 1
            self._history.append(suggestion)
            return suggestion

        suggestion = ComposeSuggestion(
            id=str(uuid.uuid4()),
            file_path=file_path,
            ghost_text=suggested_text,
            original_text=original_text,
            line_start=line_start,
            line_end=line_end or line_start + suggested_text.count("\n"),
            description=description,
            status=SuggestionStatus.ACTIVE,
            confidence=confidence,
        )
        self._active_suggestions[suggestion.id] = suggestion
        self._total_suggestions += 1
        self._logger.debug(
            "Ghost text suggestion %s for %s:%d-%d",
            suggestion.id, file_path, line_start, suggestion.line_end,
        )
        return suggestion

    def apply_suggestion(
        self, suggestion_id: str, modified_text: str | None = None,
    ) -> ComposeSuggestion | None:
        suggestion = self._active_suggestions.get(suggestion_id)
        if suggestion is None:
            return None
        if modified_text is not None:
            suggestion.ghost_text = modified_text
            suggestion.status = SuggestionStatus.MODIFIED
        else:
            suggestion.status = SuggestionStatus.APPLIED
        suggestion.applied_at = time.time()
        self._active_suggestions.pop(suggestion_id, None)
        self._applied_count += 1
        self._history.append(suggestion)
        return suggestion

    def dismiss_suggestion(
        self, suggestion_id: str,
    ) -> ComposeSuggestion | None:
        suggestion = self._active_suggestions.get(suggestion_id)
        if suggestion is None:
            return None
        suggestion.status = SuggestionStatus.DISMISSED
        suggestion.applied_at = time.time()
        self._active_suggestions.pop(suggestion_id, None)
        self._dismissed_count += 1
        self._history.append(suggestion)
        self._logger.debug("Suggestion %s dismissed", suggestion_id)
        return suggestion

    def get_active_suggestions(
        self, file_path: str | None = None,
    ) -> list[ComposeSuggestion]:
        if file_path is None:
            return list(self._active_suggestions.values())
        return [
            s for s in self._active_suggestions.values()
            if s.file_path == file_path
        ]

    def get_suggestion(self, suggestion_id: str) -> ComposeSuggestion | None:
        s = self._active_suggestions.get(suggestion_id)
        if s is not None:
            return s
        for h in reversed(self._history):
            if h.id == suggestion_id:
                return h
        return None

    def clear_suggestions(self) -> None:
        self._active_suggestions.clear()

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "total_suggestions": self._total_suggestions,
            "applied_count": self._applied_count,
            "dismissed_count": self._dismissed_count,
            "active_count": len(self._active_suggestions),
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
