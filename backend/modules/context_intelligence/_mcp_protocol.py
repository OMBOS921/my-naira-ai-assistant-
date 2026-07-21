"""Model Context Protocol (MCP) — structured context formatting and transmission.

Defines how context payloads are structured, serialised, and transmitted
between the Context Intelligence layer and consumers.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from backend.modules.context_intelligence._types import (
    CodeChunk,
    MCPContext,
    SymbolInfo,
)

_LOG = logging.getLogger("naira.context_intelligence.mcp")


class MCPProtocol:
    """Model Context Protocol — formats and manages context payloads.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._total_contexts_created = 0

    def create_context(
        self,
        session_id: str,
        system_prompt: str = "",
        chunks: list[CodeChunk] | None = None,
        symbols: list[SymbolInfo] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MCPContext:
        """Create a structured MCP context payload.

        Parameters
        ----------
        session_id : str
            Session identifier.
        system_prompt : str
            System prompt for this context.
        chunks : list[CodeChunk] | None
            Code chunks to include.
        symbols : list[SymbolInfo] | None
            Symbol definitions to include.
        metadata : dict[str, Any] | None
            Additional metadata.

        Returns
        -------
        MCPContext
            Structured context payload.
        """
        self._total_contexts_created += 1
        chunks = chunks or []
        symbols = symbols or []
        total_tokens = (
            len(system_prompt) // 4
            + sum(c.token_count for c in chunks)
            + sum(len(s.name) // 4 for s in symbols)
        )
        return MCPContext(
            context_id=str(uuid.uuid4()),
            session_id=session_id,
            system_prompt=system_prompt,
            chunks=tuple(chunks),
            symbols=tuple(symbols),
            token_count=total_tokens,
            metadata=metadata or {},
        )

    def merge_contexts(self, contexts: list[MCPContext]) -> MCPContext:
        """Merge multiple MCP contexts into one.

        Parameters
        ----------
        contexts : list[MCPContext]
            Contexts to merge.

        Returns
        -------
        MCPContext
            Merged context.
        """
        if not contexts:
            return self.create_context(session_id="")
        session_id = contexts[0].session_id
        all_chunks: list[CodeChunk] = []
        all_symbols: list[SymbolInfo] = []
        all_meta: dict[str, Any] = {}
        system_parts: list[str] = []
        token_count = 0
        for ctx in contexts:
            all_chunks.extend(ctx.chunks)
            all_symbols.extend(ctx.symbols)
            all_meta.update(ctx.metadata)
            if ctx.system_prompt:
                system_parts.append(ctx.system_prompt)
            token_count += ctx.token_count
        return MCPContext(
            context_id=str(uuid.uuid4()),
            session_id=session_id,
            system_prompt="\n".join(system_parts),
            chunks=tuple(all_chunks),
            symbols=tuple(all_symbols),
            token_count=token_count,
            metadata=all_meta,
        )

    def to_dict(self, context: MCPContext) -> dict[str, Any]:
        """Serialise an MCP context to a dictionary.

        Parameters
        ----------
        context : MCPContext
            Context to serialise.

        Returns
        -------
        dict[str, Any]
            Dictionary representation.
        """
        return {
            "context_id": context.context_id,
            "session_id": context.session_id,
            "system_prompt": context.system_prompt,
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "file_path": c.file_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "language": c.language,
                    "token_count": c.token_count,
                }
                for c in context.chunks
            ],
            "symbols": [
                {
                    "name": s.name,
                    "symbol_type": s.symbol_type,
                    "file_path": s.file_path,
                    "line": s.line,
                }
                for s in context.symbols
            ],
            "token_count": context.token_count,
            "metadata": context.metadata,
        }

    def estimate_tokens(self, context: MCPContext) -> int:
        """Estimate the token count for a context.

        Parameters
        ----------
        context : MCPContext
            Context to estimate.

        Returns
        -------
        int
            Estimated token count.
        """
        text_len = (
            len(context.system_prompt)
            + sum(len(c.content) for c in context.chunks)
            + sum(len(s.name) + len(s.signature) for s in context.symbols)
        )
        return max(1, text_len // 4)

    @property
    def total_contexts_created(self) -> int:
        return self._total_contexts_created

    async def health_check(self) -> bool:
        return True
