from __future__ import annotations
from typing import Any
"""Automatic Any Expansion — expands context with related files automatically.

Analyses the current context and automatically discovers and includes
related files, symbols, and dependencies to enrich the LLM's context.
"""



import logging

from backend.modules.context_intelligence._types import (
    CodeChunk,
    MCPContext,
    RelatedFileSet,
)

_LOG = logging.getLogger("naira.context_intelligence.auto_context_expansion")


class AutomaticContextExpansion:
    """Automatically expands context with related code.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    max_expansion_files : int
        Maximum files to add during expansion (default 5).
    expansion_token_budget : int
        Token budget for expansion content (default 4096).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        max_expansion_files: int = 5,
        expansion_token_budget: int = 4096,
    ) -> None:
        self._logger = logger or _LOG
        self._max_expansion_files = max_expansion_files
        self._expansion_token_budget = expansion_token_budget
        self._total_expansions = 0

    def expand_context(
        self,
        context: MCPContext,
        related_sets: list[RelatedFileSet],
        available_chunks: dict[str, list[CodeChunk]],
        current_token_count: int,
        max_total_tokens: int = 128_000,
    ) -> MCPContext:
        """Expand an MCP context with related file chunks.

        Parameters
        ----------
        context : MCPContext
            Current context to expand.
        related_sets : list[RelatedFileSet]
            Related file sets discovered for context files.
        available_chunks : dict[str, list[CodeChunk]]
            Pre-computed chunks keyed by file path.
        current_token_count : int
            Current token count of the context.
        max_total_tokens : int
            Maximum total tokens allowed.

        Returns
        -------
        MCPContext
            Expanded context with additional chunks.
        """
        self._total_expansions += 1
        budget = min(
            self._expansion_token_budget,
            max(0, max_total_tokens - current_token_count),
        )

        if budget <= 0:
            return context

        ranked_candidates: list[tuple[float, CodeChunk]] = []
        seen_files: set[str] = set(c.file_path for c in context.chunks)

        for related_set in related_sets:
            for ranking in related_set.related_files:
                if ranking.file_path in seen_files:
                    continue
                seen_files.add(ranking.file_path)
                chunks = available_chunks.get(ranking.file_path, [])
                for chunk in chunks[:3]:
                    ranked_candidates.append((ranking.score, chunk))

        ranked_candidates.sort(key=lambda x: x[0], reverse=True)

        new_chunks: list[CodeChunk] = []
        used_tokens = 0
        files_added = 0

        for _score, chunk in ranked_candidates:
            if files_added >= self._max_expansion_files:
                break
            chunk_tokens = chunk.token_count or max(1, len(chunk.content) // 4)
            if used_tokens + chunk_tokens <= budget:
                new_chunks.append(chunk)
                used_tokens += chunk_tokens
                files_added += 1

        if not new_chunks:
            return context

        existing_chunks = list(context.chunks)
        all_chunks = existing_chunks + new_chunks

        self._logger.debug(
            "Expanded context with %d new chunks (%d tokens) from %d files",
            len(new_chunks), used_tokens, files_added,
        )

        return MCPContext(
            context_id=context.context_id,
            session_id=context.session_id,
            system_prompt=context.system_prompt,
            chunks=tuple(all_chunks),
            symbols=context.symbols,
            token_count=current_token_count + used_tokens,
            metadata={
                **context.metadata,
                "expanded": True,
                "expansion_files_added": files_added,
                "expansion_tokens_added": used_tokens,
            },
        )

    def suggest_expansion(
        self,
        current_files: list[str],
        related_sets: list[RelatedFileSet],
    ) -> list[str]:
        """Suggest files to add to the current context.

        Parameters
        ----------
        current_files : list[str]
            Files already in context.
        related_sets : list[RelatedFileSet]
            Related file sets.

        Returns
        -------
        list[str]
            Suggested file paths for expansion.
        """
        current_set = set(current_files)
        suggestions: list[tuple[float, str]] = []

        for related_set in related_sets:
            for ranking in related_set.related_files:
                if ranking.file_path not in current_set:
                    suggestions.append((ranking.score, ranking.file_path))

        suggestions.sort(key=lambda x: x[0], reverse=True)
        return [fp for _, fp in suggestions[:self._max_expansion_files]]

    @property
    def total_expansions(self) -> int:
        return self._total_expansions

    async def health_check(self) -> bool:
        return True
