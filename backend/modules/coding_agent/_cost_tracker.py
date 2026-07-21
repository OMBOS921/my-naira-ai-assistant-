from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.modules.coding_agent._exceptions import CostTrackingError
from backend.types import TokenUsage

_LOG = logging.getLogger("naira.coding_agent.cost")


@dataclass
class CostEntry:
    operation: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


_COST_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "gemini-2.0-flash": {"prompt": 0.0001, "completion": 0.0004},
    "gemini-2.5-flash": {"prompt": 0.00015, "completion": 0.0005},
    "deepseek-chat": {"prompt": 0.00014, "completion": 0.00028},
    "ollama": {"prompt": 0.0, "completion": 0.0},
    "default": {"prompt": 0.0001, "completion": 0.0004},
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = _COST_PER_1K_TOKENS.get(model) or _COST_PER_1K_TOKENS["default"]
    prompt_cost = (prompt_tokens / 1000) * rates["prompt"]
    completion_cost = (completion_tokens / 1000) * rates["completion"]
    return round(prompt_cost + completion_cost, 6)


class CostTracker:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
        budget_limit: float | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._budget_limit = budget_limit
        self._entries: list[CostEntry] = []
        self._total_cost: float = 0.0
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def total_cost(self) -> float:
        return self._total_cost

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("CostTracker marked degraded")

    def track(
        self,
        operation: str,
        model: str,
        token_usage: TokenUsage,
        metadata: dict[str, Any] | None = None,
    ) -> CostEntry:
        if not self._enabled or self._degraded:
            entry = CostEntry(
                operation=operation,
                model=model,
                prompt_tokens=token_usage.prompt_tokens,
                completion_tokens=token_usage.completion_tokens,
                total_tokens=token_usage.total_tokens,
                estimated_cost=0.0,
            )
            self._entries.append(entry)
            return entry

        estimated_cost = _estimate_cost(
            model, token_usage.prompt_tokens, token_usage.completion_tokens,
        )

        limit = self._budget_limit
        if limit is not None and (self._total_cost + estimated_cost) > limit:
            raise CostTrackingError(
                f"Cost limit ${self._budget_limit:.4f} exceeded",
                context={
                    "total_cost": self._total_cost,
                    "estimated_cost": estimated_cost,
                    "limit": self._budget_limit,
                },
            )

        entry = CostEntry(
            operation=operation,
            model=model,
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            total_tokens=token_usage.total_tokens,
            estimated_cost=estimated_cost,
            metadata=metadata or {},
        )

        self._entries.append(entry)
        self._total_cost += estimated_cost
        self._total_prompt_tokens += token_usage.prompt_tokens
        self._total_completion_tokens += token_usage.completion_tokens
        self._total_tokens += token_usage.total_tokens

        self._logger.debug(
            "Tracked %s: %d tokens, $%.6f (total: $%.4f)",
            operation, token_usage.total_tokens, estimated_cost, self._total_cost,
        )

        return entry

    def track_tokens(
        self,
        operation: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> CostEntry:
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return self.track(operation, model, usage)

    def get_costs(self) -> dict[str, Any]:
        return {
            "total_cost": round(self._total_cost, 6),
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_tokens,
            "entry_count": len(self._entries),
            "budget_limit": self._budget_limit,
        }

    def get_entries(
        self, operation: str | None = None, limit: int = 100,
    ) -> list[CostEntry]:
        if operation:
            filtered = [e for e in self._entries if e.operation == operation]
        else:
            filtered = self._entries
        return filtered[-limit:]

    def get_cost_by_operation(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for entry in self._entries:
            result[entry.operation] = result.get(entry.operation, 0.0) + entry.estimated_cost
        return result

    def reset(self) -> None:
        self._entries.clear()
        self._total_cost = 0.0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_tokens = 0

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "total_cost": round(self._total_cost, 6),
            "total_tokens": self._total_tokens,
            "entry_count": len(self._entries),
            "budget_limit": self._budget_limit,
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
