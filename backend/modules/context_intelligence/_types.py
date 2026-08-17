"""Shared types for the Any Intelligence module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

ChunkStrategy = Literal["function", "class", "block", "line", "paragraph"]
"""Strategies for code chunking."""


IndexEntryType = Literal["symbol", "file", "workspace", "dependency", "import"]
"""Types of index entries."""


@dataclass(frozen=True)
class CodeChunk:
    """A chunk of code with metadata."""

    chunk_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    strategy: ChunkStrategy
    language: str = ""
    symbol_name: str = ""
    token_count: int = 0


@dataclass(frozen=True)
class IndexEntry:
    """An entry in a context intelligence index."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entry_type: IndexEntryType = "file"
    key: str = ""
    value: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SymbolInfo:
    """Information about a code symbol."""

    name: str
    symbol_type: Literal["class", "function", "method", "variable", "import", "module"]
    file_path: str
    line: int
    column: int = 0
    parent_name: str = ""
    docstring: str = ""
    signature: str = ""


@dataclass(frozen=True)
class DependencyInfo:
    """A dependency relationship between files."""

    source_path: str
    target_path: str
    dep_type: Literal["import", "reference", "inherit", "call"]
    line: int = 0


@dataclass(frozen=True)
class RepositoryNode:
    """A node in the repository map tree."""

    path: str
    name: str
    node_type: Literal["directory", "file"]
    children: tuple[RepositoryNode, ...] = ()
    size: int = 0
    language: str = ""


@dataclass(frozen=True)
class ContextStatistics:
    """Statistical data about context usage."""

    total_contexts_built: int = 0
    total_tokens_processed: int = 0
    total_compressions: int = 0
    total_chunks_created: int = 0
    total_searches: int = 0
    total_cache_hits: int = 0
    total_cache_misses: int = 0
    total_navigations: int = 0
    avg_build_time_ms: float = 0.0
    avg_search_time_ms: float = 0.0
    compression_ratio: float = 1.0


@dataclass(frozen=True)
class MCPContext:
    """A structured context payload following MCP."""

    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    system_prompt: str = ""
    chunks: list[CodeChunk] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    dependencies: list[DependencyInfo] = field(default_factory=list)
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FileRanking:
    """Ranking result for a file."""

    file_path: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RelatedFileSet:
    """A set of related files with relevance scores."""

    source_path: str
    related_files: list[FileRanking] = field(default_factory=list)
    relationship_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HealthReport:
    """Health report for the Any Intelligence module."""

    healthy: bool = True
    degraded: bool = False
    services_online: int = 0
    services_total: int = 0
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricsSnapshot:
    """Snapshot of collected metrics."""

    timestamp: float = 0.0
    values: dict[str, float] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
