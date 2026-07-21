"""Context Window Optimizer — optimises token usage within context windows.

Manages token budgets, prioritises high-value content, and applies
compression strategies to stay within model context limits.
"""

from __future__ import annotations

import logging

from backend.modules.context_intelligence._types import CodeChunk, FileRanking

_LOG = logging.getLogger("naira.context_intelligence.context_window_optimizer")


class ContextWindowOptimizer:
    """Optimises context content to fit within token budgets.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    default_max_tokens : int
        Default maximum token budget (default 128000).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        default_max_tokens: int = 128_000,
    ) -> None:
        self._logger = logger or _LOG
        self._default_max_tokens = default_max_tokens
        self._total_optimizations = 0

    def optimize_chunks(
        self,
        chunks: list[CodeChunk],
        rankings: list[FileRanking] | None = None,
        max_tokens: int | None = None,
        preserve_system_prompt: bool = True,
    ) -> list[CodeChunk]:
        """Select the best set of chunks to fit within the token budget.

        Parameters
        ----------
        chunks : list[CodeChunk]
            Candidate code chunks.
        rankings : list[FileRanking] | None
            Pre-computed file rankings for prioritisation.
        max_tokens : int | None
            Token budget. Defaults to default_max_tokens.
        preserve_system_prompt : bool
            Whether to reserve tokens for the system prompt.

        Returns
        -------
        list[CodeChunk]
            Optimised subset of chunks.
        """
        self._total_optimizations += 1
        budget = max_tokens if max_tokens is not None else self._default_max_tokens

        if preserve_system_prompt:
            budget = max(1, budget - 2048)

        if not chunks:
            return []

        ranking_map: dict[str, float] = {}
        if rankings:
            for r in rankings:
                ranking_map[r.file_path] = r.score

        scored_chunks: list[tuple[float, CodeChunk]] = []
        for chunk in chunks:
            score = ranking_map.get(chunk.file_path, 0.5)
            if chunk.symbol_name:
                score += 0.3
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        selected: list[CodeChunk] = []
        used_tokens = 0

        for _score, chunk in scored_chunks:
            chunk_tokens = chunk.token_count or max(1, len(chunk.content) // 4)
            if used_tokens + chunk_tokens <= budget:
                selected.append(chunk)
                used_tokens += chunk_tokens

        self._logger.debug(
            "Optimized %d chunks to %d (budget=%d, used=%d)",
            len(chunks), len(selected), budget, used_tokens,
        )
        return selected

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        int
            Estimated token count (4 chars per token heuristic).
        """
        return max(1, len(text) // 4)

    def suggest_budget_allocation(
        self,
        total_budget: int,
        categories: dict[str, float],
    ) -> dict[str, int]:
        """Suggest token budget allocation across categories.

        Parameters
        ----------
        total_budget : int
            Total token budget.
        categories : dict[str, float]
            Category name to importance weight mapping.

        Returns
        -------
        dict[str, int]
            Category name to allocated token count.
        """
        total_weight = sum(categories.values()) or 1.0
        allocation: dict[str, int] = {}
        reserved = int(total_budget * 0.1)

        for category, weight in categories.items():
            allocation[category] = int(
                (total_budget - reserved) * (weight / total_weight)
            )

        return allocation

    def fit_to_window(
        self, text: str, max_tokens: int
    ) -> str:
        """Truncate text to fit within a token window.

        Preserves the beginning and end of the text.

        Parameters
        ----------
        text : str
            Input text.
        max_tokens : int
            Maximum allowed tokens.

        Returns
        -------
        str
            Truncated text.
        """
        estimated = self.estimate_tokens(text)
        if estimated <= max_tokens:
            return text

        budget_chars = max_tokens * 4
        if budget_chars >= len(text):
            return text

        head_chars = budget_chars // 2
        tail_chars = budget_chars // 2

        head = text[:head_chars]
        tail = text[-tail_chars:] if tail_chars > 0 else ""

        return f"{head}\n... [truncated] ...\n{tail}"

    @property
    def total_optimizations(self) -> int:
        return self._total_optimizations

    async def health_check(self) -> bool:
        return True
