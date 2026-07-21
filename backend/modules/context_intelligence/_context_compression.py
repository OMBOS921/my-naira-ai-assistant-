"""Context Compression — compresses context to fit within token windows.

Applies compression strategies including summarisation, deduplication,
and priority-based truncation to reduce context size.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from backend.modules.context_intelligence._types import CodeChunk

_LOG = logging.getLogger("naira.context_intelligence.context_compression")


class ContextCompression:
    """Compresses context data to fit within token budgets.

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
        self._total_compressions = 0
        self._total_bytes_saved = 0

    def compress_chunks(
        self,
        chunks: list[CodeChunk],
        target_ratio: float = 0.5,
    ) -> list[CodeChunk]:
        """Compress code chunks by removing redundancy.

        Parameters
        ----------
        chunks : list[CodeChunk]
            Code chunks to compress.
        target_ratio : float
            Target compression ratio (0.0 to 1.0). 0.5 means reduce to 50%.

        Returns
        -------
        list[CodeChunk]
            Compressed chunks.
        """
        self._total_compressions += 1
        if not chunks:
            return []

        original_size = sum(len(c.content) for c in chunks)
        target_size = int(original_size * target_ratio)

        # Deduplicate similar chunks
        deduplicated = self._deduplicate(chunks)

        # Calculate size after dedup
        dedup_size = sum(len(c.content) for c in deduplicated)

        # If still over target, remove low-priority chunks
        if dedup_size > target_size and len(deduplicated) > 1:
            compressed = self._truncate_lowest_priority(deduplicated, target_size)
        else:
            compressed = deduplicated

        compressed_size = sum(len(c.content) for c in compressed)
        bytes_saved = original_size - compressed_size
        self._total_bytes_saved += bytes_saved

        self._logger.debug(
            "Compressed %d chunks: %d -> %d bytes (%.1f%%)",
            len(chunks), original_size, compressed_size,
            (1 - compressed_size / max(original_size, 1)) * 100,
        )

        return compressed

    def _deduplicate(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Remove near-duplicate chunks using similarity comparison.

        Parameters
        ----------
        chunks : list[CodeChunk]
            Chunks to deduplicate.

        Returns
        -------
        list[CodeChunk]
            Deduplicated chunks.
        """
        result: list[CodeChunk] = []
        for chunk in chunks:
            is_duplicate = False
            for existing in result:
                similarity = SequenceMatcher(
                    None, chunk.content, existing.content
                ).ratio()
                if similarity > 0.85:
                    is_duplicate = True
                    break
            if not is_duplicate:
                result.append(chunk)
        return result

    def _truncate_lowest_priority(
        self,
        chunks: list[CodeChunk],
        target_size: int,
    ) -> list[CodeChunk]:
        """Remove lowest-priority chunks to reach target size.

        Parameters
        ----------
        chunks : list[CodeChunk]
            Chunks to truncate.
        target_size : int
            Target total byte size.

        Returns
        -------
        list[CodeChunk]
            Truncated list of chunks.
        """
        scored = [
            (chunk.symbol_name != "", len(chunk.content), chunk)
            for chunk in chunks
        ]
        scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)

        result: list[CodeChunk] = []
        current_size = 0

        for _has_symbol, size, chunk in scored:
            if current_size + size <= target_size:
                result.append(chunk)
                current_size += size
            elif not result:
                result.append(chunk)
                break

        return result

    def compress_text(self, text: str, max_chars: int) -> str:
        """Compress text to fit within a character limit.

        Preserves the most important parts (start and end).

        Parameters
        ----------
        text : str
            Text to compress.
        max_chars : int
            Maximum character count.

        Returns
        -------
        str
            Compressed text.
        """
        if len(text) <= max_chars:
            return text

        self._total_compressions += 1
        bytes_saved = len(text) - max_chars
        self._total_bytes_saved += bytes_saved

        head_ratio = 0.6
        head_len = int(max_chars * head_ratio)
        tail_len = max_chars - head_len

        head = text[:head_len]
        tail = text[-tail_len:] if tail_len > 0 else ""

        return f"{head}\n[...]\n{tail}"

    def deduplicate_texts(self, texts: list[str]) -> list[str]:
        """Remove duplicate or near-duplicate texts.

        Parameters
        ----------
        texts : list[str]
            Texts to deduplicate.

        Returns
        -------
        list[str]
            Deduplicated texts.
        """
        result: list[str] = []
        for text in texts:
            is_dup = False
            for existing in result:
                if SequenceMatcher(None, text, existing).ratio() > 0.9:
                    is_dup = True
                    break
            if not is_dup:
                result.append(text)
        return result

    @property
    def total_compressions(self) -> int:
        return self._total_compressions

    @property
    def total_bytes_saved(self) -> int:
        return self._total_bytes_saved

    async def health_check(self) -> bool:
        return True
