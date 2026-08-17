from __future__ import annotations

import logging
from typing import Any

from backend.modules.context_intelligence._types import CodeChunk, Any

_LOG = logging.getLogger("naira.coding_agent.mcp")


class MCPIntegration:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._contexts_created = 0
        self._total_contexts_created = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("MCPIntegration marked degraded")

    def create_context(
        self,
        session_id: str,
        system_prompt: str = "",
        chunks: list[CodeChunk] | None = None,
        symbols: list[SymbolInfo] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MCPContext:
        self._contexts_created += 1
        self._total_contexts_created += 1
        chunks = chunks or []
        symbols = symbols or []
        total_tokens = (
            len(system_prompt) // 4
            + sum(c.token_count for c in chunks)
            + sum(len(s.name) // 4 for s in symbols)
        )
        import uuid
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
        import uuid
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
        text_len = (
            len(context.system_prompt)
            + sum(len(c.content) for c in context.chunks)
            + sum(len(s.name) + len(s.signature) for s in context.symbols)
        )
        return max(1, text_len // 4)

    def metrics(self) -> dict[str, Any]:
        return {
            "contexts_created": self._contexts_created,
            "total_contexts_created": self._total_contexts_created,
            "enabled": self._enabled,
            "degraded": self._degraded,
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
