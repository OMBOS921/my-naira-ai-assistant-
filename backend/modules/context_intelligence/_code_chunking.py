"""Code Chunking — splits code into manageable chunks for context inclusion.

Implements multiple chunking strategies: by function, class, block,
or line count, enabling flexible context assembly.
"""

from __future__ import annotations

import ast
import logging
import uuid
from pathlib import Path

from backend.modules.context_intelligence._types import ChunkStrategy, CodeChunk

_LOG = logging.getLogger("naira.context_intelligence.code_chunking")

_DEFAULT_MAX_CHUNK_SIZE = 500
_DEFAULT_MIN_CHUNK_SIZE = 10


class CodeChunking:
    """Splits source code into chunks for context management.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    max_chunk_size : int
        Maximum lines per chunk (default 500).
    min_chunk_size : int
        Minimum lines per chunk (default 10).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        max_chunk_size: int = _DEFAULT_MAX_CHUNK_SIZE,
        min_chunk_size: int = _DEFAULT_MIN_CHUNK_SIZE,
    ) -> None:
        self._logger = logger or _LOG
        self._max_chunk_size = max_chunk_size
        self._min_chunk_size = min_chunk_size
        self._total_chunks = 0

    def chunk_file(
        self,
        file_path: str,
        strategy: ChunkStrategy = "function",
        language: str = "",
    ) -> list[CodeChunk]:
        """Chunk a source file using the specified strategy.

        Parameters
        ----------
        file_path : str
            Path to the source file.
        strategy : ChunkStrategy
            Chunking strategy to use.
        language : str
            Programming language of the file.

        Returns
        -------
        list[CodeChunk]
            Code chunks.
        """
        path = Path(file_path)
        if not path.is_file():
            return []

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        lines = source.splitlines()
        detected_lang = language or self._detect_language(file_path)

        if strategy == "function":
            chunks = self._chunk_by_function(file_path, source, lines, detected_lang)
        elif strategy == "class":
            chunks = self._chunk_by_class(file_path, source, lines, detected_lang)
        elif strategy == "block":
            chunks = self._chunk_by_block(file_path, lines, detected_lang)
        elif strategy == "line":
            chunks = self._chunk_by_line(file_path, lines, detected_lang)
        elif strategy == "paragraph":
            chunks = self._chunk_by_paragraph(file_path, lines, detected_lang)
        else:
            chunks = self._chunk_by_block(file_path, lines, detected_lang)

        self._total_chunks += len(chunks)
        return chunks

    def _chunk_by_function(
        self,
        file_path: str,
        source: str,
        lines: list[str],
        language: str,
    ) -> list[CodeChunk]:
        """Chunk by function/class definitions using AST parsing."""
        chunks: list[CodeChunk] = []
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return self._chunk_by_block(file_path, lines, language)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 1) or (start + 1)
                content = "\n".join(lines[start:end])
                chunk = CodeChunk(
                    chunk_id=str(uuid.uuid4()),
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=end,
                    content=content,
                    strategy="function",
                    language=language,
                    symbol_name=node.name,
                    token_count=max(1, len(content) // 4),
                )
                chunks.append(chunk)

        if not chunks:
            return self._chunk_by_block(file_path, lines, language)

        return chunks

    def _chunk_by_class(
        self,
        file_path: str,
        source: str,
        lines: list[str],
        language: str,
    ) -> list[CodeChunk]:
        """Chunk by class definitions only."""
        chunks: list[CodeChunk] = []
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return self._chunk_by_block(file_path, lines, language)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 1) or (start + 1)
                content = "\n".join(lines[start:end])
                chunk = CodeChunk(
                    chunk_id=str(uuid.uuid4()),
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=end,
                    content=content,
                    strategy="class",
                    language=language,
                    symbol_name=node.name,
                    token_count=max(1, len(content) // 4),
                )
                chunks.append(chunk)

        if not chunks:
            return self._chunk_by_block(file_path, lines, language)

        return chunks

    def _chunk_by_block(
        self,
        file_path: str,
        lines: list[str],
        language: str,
    ) -> list[CodeChunk]:
        """Chunk by fixed-size block."""
        chunks: list[CodeChunk] = []
        chunk_size = min(self._max_chunk_size, max(self._min_chunk_size, len(lines) // 5 + 1))

        for i in range(0, len(lines), chunk_size):
            block_lines = lines[i:i + chunk_size]
            if len(block_lines) < self._min_chunk_size and chunks:
                prev = chunks.pop()
                merged_lines = prev.content.splitlines() + block_lines
                merged = CodeChunk(
                    chunk_id=str(uuid.uuid4()),
                    file_path=file_path,
                    start_line=prev.start_line,
                    end_line=i + len(block_lines),
                    content="\n".join(merged_lines),
                    strategy="block",
                    language=language,
                    token_count=sum(len(line) // 4 + 1 for line in merged_lines),
                )
                chunks.append(merged)
            else:
                content = "\n".join(block_lines)
                chunk = CodeChunk(
                    chunk_id=str(uuid.uuid4()),
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=i + len(block_lines),
                    content=content,
                    strategy="block",
                    language=language,
                    token_count=max(1, len(content) // 4),
                )
                chunks.append(chunk)

        return chunks

    def _chunk_by_line(
        self,
        file_path: str,
        lines: list[str],
        language: str,
    ) -> list[CodeChunk]:
        """Chunk each line individually."""
        chunks: list[CodeChunk] = []
        for idx, line in enumerate(lines):
            chunk = CodeChunk(
                chunk_id=str(uuid.uuid4()),
                file_path=file_path,
                start_line=idx + 1,
                end_line=idx + 1,
                content=line,
                strategy="line",
                language=language,
                token_count=max(1, len(line) // 4),
            )
            chunks.append(chunk)
        return chunks

    def _chunk_by_paragraph(
        self,
        file_path: str,
        lines: list[str],
        language: str,
    ) -> list[CodeChunk]:
        """Chunk by blank-line-separated paragraphs."""
        chunks: list[CodeChunk] = []
        start = 0

        for idx, line in enumerate(lines):
            if line.strip() == "" and idx > start:
                content = "\n".join(lines[start:idx])
                chunk = CodeChunk(
                    chunk_id=str(uuid.uuid4()),
                    file_path=file_path,
                    start_line=start + 1,
                    end_line=idx,
                    content=content,
                    strategy="paragraph",
                    language=language,
                    token_count=max(1, len(content) // 4),
                )
                chunks.append(chunk)
                start = idx + 1

        if start < len(lines):
            content = "\n".join(lines[start:])
            chunk = CodeChunk(
                chunk_id=str(uuid.uuid4()),
                file_path=file_path,
                start_line=start + 1,
                end_line=len(lines),
                content=content,
                strategy="paragraph",
                language=language,
                token_count=max(1, len(content) // 4),
            )
            chunks.append(chunk)

        return chunks

    def _detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript React",
            ".jsx": "JavaScript React",
            ".java": "Java",
            ".rs": "Rust",
            ".go": "Go",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C Header",
            ".cs": "C#",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
        }
        return mapping.get(ext, "Unknown")

    @property
    def total_chunks(self) -> int:
        return self._total_chunks

    async def health_check(self) -> bool:
        return True
