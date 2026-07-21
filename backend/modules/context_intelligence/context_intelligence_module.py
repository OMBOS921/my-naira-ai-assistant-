"""ContextIntelligenceManager — the single public class for the context
intelligence module.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §4.2 — ModuleInterface protocol.

Orchestrates the full Context Intelligence layer:
- Model Context Protocol (MCP)
- Repository Map
- Multi-file Context Tree
- Workspace Index
- Symbol Index
- Cross-file Navigation
- Dependency Graph
- Import Graph
- File Ranking Engine
- Context Window Optimizer
- Project Knowledge Cache
- Session Persistence
- Context Compression
- Semantic Search
- Code Chunking
- Related File Discovery
- Automatic Context Expansion
- Context Statistics
- Health Reporting
- Metrics Collection
"""

from __future__ import annotations

import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.context_intelligence._automatic_context_expansion import (
    AutomaticContextExpansion,
)
from backend.modules.context_intelligence._code_chunking import CodeChunking
from backend.modules.context_intelligence._context_compression import (
    ContextCompression,
)
from backend.modules.context_intelligence._context_statistics import (
    ContextStatisticsTracker,
)
from backend.modules.context_intelligence._context_window_optimizer import (
    ContextWindowOptimizer,
)
from backend.modules.context_intelligence._cross_file_navigation import (
    CrossFileNavigation,
)
from backend.modules.context_intelligence._dependency_graph import DependencyGraph
from backend.modules.context_intelligence._file_ranking_engine import (
    FileRankingEngine,
)
from backend.modules.context_intelligence._health_reporting import HealthReporting
from backend.modules.context_intelligence._import_graph import ImportGraph
from backend.modules.context_intelligence._mcp_protocol import MCPProtocol
from backend.modules.context_intelligence._metrics_collection import MetricsCollector
from backend.modules.context_intelligence._multi_file_context_tree import (
    MultiFileContextTree,
)
from backend.modules.context_intelligence._project_knowledge_cache import (
    ProjectKnowledgeCache,
)
from backend.modules.context_intelligence._related_file_discovery import (
    RelatedFileDiscovery,
)
from backend.modules.context_intelligence._repository_map import RepositoryMap
from backend.modules.context_intelligence._semantic_search import SemanticSearch
from backend.modules.context_intelligence._session_persistence import (
    SessionPersistence,
)
from backend.modules.context_intelligence._symbol_index import SymbolIndex
from backend.modules.context_intelligence._types import (
    CodeChunk,
    ContextStatistics,
    HealthReport,
    MCPContext,
    MetricsSnapshot,
    RelatedFileSet,
    SymbolInfo,
)
from backend.modules.context_intelligence._workspace_index import WorkspaceIndex

_LOG = logging.getLogger("naira.context_intelligence")


class ContextIntelligenceManager:
    """Central context intelligence manager.

    Owns all 20 context intelligence services and exposes a unified
    API for context assembly, indexing, search, and optimisation.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        ``EventBus`` instance for event emission.
    memory_manager : object | None
        ``MemoryManager`` instance for persistence.
    context_manager : object | None
        ``ContextManager`` instance for context operations.
    tool_manager : object | None
        ``ToolManager`` instance for tool registration.
    workspace_root : str | None
        Root path for workspace indexing.
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        memory_manager: object | None = None,
        context_manager: object | None = None,
        tool_manager: object | None = None,
        workspace_root: str | None = None,
        max_chunk_size: int = 500,
        max_tree_nodes: int = 100,
        cache_ttl: int = 300,
        expansion_token_budget: int = 4096,
        default_max_tokens: int = 128_000,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._memory_manager = memory_manager
        self._context_manager = context_manager
        self._tool_manager = tool_manager
        self._workspace_root = workspace_root or ""
        self._degraded: bool = False
        self._initialized: bool = False

        self._max_chunk_size = max_chunk_size
        self._max_tree_nodes = max_tree_nodes

        self._mcp = MCPProtocol(logger=logger)
        self._repository_map = RepositoryMap(
            logger=logger, max_depth=20,
        )
        self._multi_file_context = MultiFileContextTree(
            logger=logger, max_nodes=max_tree_nodes,
        )
        self._workspace_index = WorkspaceIndex(
            logger=logger, max_file_size=1_048_576,
        )
        self._symbol_index = SymbolIndex(logger=logger)
        self._cross_file_nav = CrossFileNavigation(logger=logger)
        self._dependency_graph = DependencyGraph(logger=logger)
        self._import_graph = ImportGraph(logger=logger)
        self._file_ranking = FileRankingEngine(logger=logger)
        self._window_optimizer = ContextWindowOptimizer(
            logger=logger, default_max_tokens=default_max_tokens,
        )
        self._knowledge_cache = ProjectKnowledgeCache(
            logger=logger, ttl_seconds=cache_ttl,
        )
        self._session_persistence = SessionPersistence(
            logger=logger,
        )
        self._context_compression = ContextCompression(logger=logger)
        self._semantic_search = SemanticSearch(logger=logger)
        self._code_chunking = CodeChunking(
            logger=logger, max_chunk_size=max_chunk_size,
        )
        self._related_file_discovery = RelatedFileDiscovery(logger=logger)
        self._auto_expansion = AutomaticContextExpansion(
            logger=logger,
            expansion_token_budget=expansion_token_budget,
        )
        self._stats = ContextStatisticsTracker(logger=logger)
        self._health_reporting = HealthReporting(logger=logger)
        self._metrics = MetricsCollector(logger=logger)

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        self._register_health_checks()
        if self._workspace_root:
            try:
                self._workspace_index.index_workspace(self._workspace_root)
                self._repository_map.build_map(self._workspace_root)
                self._logger.info(
                    "Workspace indexed: %s (%d files)",
                    self._workspace_root,
                    self._workspace_index.entry_count,
                )
            except Exception as exc:
                self._logger.warning("Workspace indexing failed: %s", exc)

        self._initialized = True
        self._logger.info(
            "ContextIntelligenceManager initialised — %d services",
            self._service_count,
        )
        await self._emit_event("context_intelligence.initialized", {
            "workspace_root": self._workspace_root,
            "service_count": self._service_count,
        })

    async def async_shutdown(self) -> None:
        await self._session_persistence.persist_all()
        self._knowledge_cache.clear()
        self._session_persistence.clear()
        self._degraded = False
        self._initialized = False
        self._logger.info("ContextIntelligenceManager shut down.")
        await self._emit_event("context_intelligence.shutdown", {})

    def degrade(self) -> None:
        self._degraded = True
        self._health_reporting.mark_degraded()
        self._logger.warning("ContextIntelligenceManager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Service accessors
    # ------------------------------------------------------------------

    @property
    def mcp(self) -> MCPProtocol:
        return self._mcp

    @property
    def repository_map(self) -> RepositoryMap:
        return self._repository_map

    @property
    def multi_file_context(self) -> MultiFileContextTree:
        return self._multi_file_context

    @property
    def workspace_index(self) -> WorkspaceIndex:
        return self._workspace_index

    @property
    def symbol_index(self) -> SymbolIndex:
        return self._symbol_index

    @property
    def cross_file_navigation(self) -> CrossFileNavigation:
        return self._cross_file_nav

    @property
    def dependency_graph(self) -> DependencyGraph:
        return self._dependency_graph

    @property
    def import_graph(self) -> ImportGraph:
        return self._import_graph

    @property
    def file_ranking(self) -> FileRankingEngine:
        return self._file_ranking

    @property
    def window_optimizer(self) -> ContextWindowOptimizer:
        return self._window_optimizer

    @property
    def knowledge_cache(self) -> ProjectKnowledgeCache:
        return self._knowledge_cache

    @property
    def session_persistence(self) -> SessionPersistence:
        return self._session_persistence

    @property
    def context_compression(self) -> ContextCompression:
        return self._context_compression

    @property
    def semantic_search(self) -> SemanticSearch:
        return self._semantic_search

    @property
    def code_chunking(self) -> CodeChunking:
        return self._code_chunking

    @property
    def related_file_discovery(self) -> RelatedFileDiscovery:
        return self._related_file_discovery

    @property
    def auto_expansion(self) -> AutomaticContextExpansion:
        return self._auto_expansion

    @property
    def stats(self) -> ContextStatisticsTracker:
        return self._stats

    @property
    def health_reporting(self) -> HealthReporting:
        return self._health_reporting

    @property
    def metrics_collector(self) -> MetricsCollector:
        return self._metrics

    @property
    def _service_count(self) -> int:
        return 20

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    async def build_rich_context(
        self,
        session_id: str,
        query: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
        include_symbols: bool = True,
        include_dependencies: bool = True,
        expand_automatically: bool = True,
    ) -> MCPContext:
        """Build a rich, multi-file context for the given session.

        Parameters
        ----------
        session_id : str
            Session identifier.
        query : str
            Current user query / task description.
        system_prompt : str
            System prompt.
        max_tokens : int | None
            Token budget for the context.
        include_symbols : bool
            Whether to include symbol definitions.
        include_dependencies : bool
            Whether to include dependency information.
        expand_automatically : bool
            Whether to auto-expand with related files.

        Returns
        -------
        MCPContext
            Rich structured context.
        """
        self._ensure_not_degraded()
        import time
        start = time.monotonic()

        files = self._workspace_index.search(query, top_k=20)
        file_paths = [f.value.get("relative_path", f.key) for f in files]

        chunks: list[CodeChunk] = []
        for rel_path in file_paths[:10]:
            full_path = self._resolve_path(rel_path)
            file_chunks = self._code_chunking.chunk_file(
                full_path, strategy="function",
            )
            chunks.extend(file_chunks[:5])

        self._stats.record_chunks_created(len(chunks))

        if self._file_ranking.total_rankings > 0:
            rankings = self._file_ranking.rank_files(
                query, file_paths, top_k=10,
            )
        else:
            rankings = []

        if max_tokens and chunks:
            chunks = self._window_optimizer.optimize_chunks(
                chunks, rankings, max_tokens=max_tokens,
            )

        symbols: list[SymbolInfo] = []
        if include_symbols:
            for rel_path in file_paths[:10]:
                full_path = self._resolve_path(rel_path)
                self._symbol_index.index_file(full_path)
                symbols.extend(self._symbol_index.get_symbols_in_file(full_path))

        context = self._mcp.create_context(
            session_id=session_id,
            system_prompt=system_prompt,
            chunks=chunks,
            symbols=symbols[:30],
            metadata={"query": query, "file_count": len(file_paths)},
        )

        if expand_automatically and file_paths:
            related_sets: list[RelatedFileSet] = []
            for fp in file_paths[:3]:
                full_fp = self._resolve_path(fp)
                rs = self._related_file_discovery.find_related(
                    full_fp, file_paths, top_k=3,
                )
                related_sets.append(rs)

            available: dict[str, list[CodeChunk]] = {}
            for fp in file_paths:
                full_fp = self._resolve_path(fp)
                available[full_fp] = self._code_chunking.chunk_file(
                    full_fp, strategy="function",
                )

            expanded = self._auto_expansion.expand_context(
                context,
                related_sets,
                available,
                context.token_count,
                max_total_tokens=max_tokens or 128_000,
            )
            context = expanded

        duration_ms = (time.monotonic() - start) * 1000
        self._stats.record_context_built(context.token_count, duration_ms)
        self._metrics.increment("contexts_built")
        self._metrics.record_value("build_time_ms", duration_ms)
        self._metrics.set_gauge("context_token_count", float(context.token_count))

        await self._emit_event("context_intelligence.context_built", {
            "session_id": session_id,
            "chunks": len(context.chunks),
            "symbols": len(context.symbols),
            "tokens": context.token_count,
            "duration_ms": duration_ms,
        })

        return context

    async def search_codebase(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[Any]:
        """Search the codebase using semantic search.

        Parameters
        ----------
        query : str
            Search query.
        top_k : int
            Maximum results.

        Returns
        -------
        list[SearchResult]
            Search results.
        """
        self._ensure_not_degraded()
        import time
        start = time.monotonic()

        results = self._semantic_search.search(query, top_k=top_k)
        duration_ms = (time.monotonic() - start) * 1000
        self._stats.record_search(duration_ms)
        self._metrics.increment("searches")
        return results

    async def index_workspace(self, root_path: str) -> dict[str, int]:
        """Index a workspace for context intelligence.

        Parameters
        ----------
        root_path : str
            Root path of the workspace.

        Returns
        -------
        dict[str, int]
            Indexing results with counts.
        """
        self._ensure_not_degraded()
        file_count = self._workspace_index.index_workspace(root_path)
        self._repository_map.build_map(root_path)

        symbol_count = 0
        for rel_path in self._workspace_index.get_all_paths()[:200]:
            full_path = self._resolve_path(rel_path)
            self._symbol_index.index_file(full_path)
            self._cross_file_nav.index_file(full_path, root_path)
            self._dependency_graph.index_file(full_path, root_path)
            self._import_graph.index_file(full_path, root_path)
            try:
                fpath = self._resolve_path(rel_path)
                with open(fpath, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                self._semantic_search.index_document(rel_path, content)
            except OSError:
                pass
            syms = self._symbol_index.get_symbols_in_file(full_path)
            symbol_count += len(syms)

        self._workspace_root = root_path
        self._metrics.set_gauge("files_indexed", float(file_count))
        self._metrics.set_gauge("symbols_indexed", float(symbol_count))
        self._metrics.increment("workspaces_indexed")

        await self._emit_event("context_intelligence.workspace_indexed", {
            "root_path": root_path,
            "files": file_count,
            "symbols": symbol_count,
        })

        return {
            "files": file_count,
            "symbols": symbol_count,
        }

    async def navigate_to_symbol(self, symbol_name: str) -> list[dict[str, Any]]:
        """Find definitions and references for a symbol.

        Parameters
        ----------
        symbol_name : str
            Symbol name to navigate to.

        Returns
        -------
        list[dict[str, Any]]
            Definition and reference locations.
        """
        self._ensure_not_degraded()
        defs = self._cross_file_nav.find_definition(symbol_name)
        refs = self._cross_file_nav.find_references(symbol_name)
        self._stats.record_navigation()
        self._metrics.increment("navigations")
        return {"definitions": defs, "references": refs}

    async def get_context_statistics(self) -> ContextStatistics:
        """Get current context usage statistics.

        Returns
        -------
        ContextStatistics
            Current statistics.
        """
        return self._stats.snapshot()

    async def get_health_report(self) -> HealthReport:
        """Get the current health report.

        Returns
        -------
        HealthReport
            Current health status.
        """
        return await self._health_reporting.generate_report()

    async def get_metrics_snapshot(self) -> MetricsSnapshot:
        """Get a snapshot of current metrics.

        Returns
        -------
        MetricsSnapshot
            Current metrics.
        """
        return self._metrics.snapshot()

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    async def save_session_state(
        self,
        session_id: str,
        context_data: dict[str, Any] | None = None,
        state_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Save session state.

        Parameters
        ----------
        session_id : str
            Session identifier.
        context_data : dict[str, Any] | None
            Context data to persist.
        state_data : dict[str, Any] | None
            State data to persist.
        metadata : dict[str, Any] | None
            Metadata.

        Returns
        -------
        bool
            True if saved successfully.
        """
        existing = self._session_persistence.get_session(session_id)
        if existing is None:
            self._session_persistence.create_session(
                session_id, metadata=metadata,
            )
        self._session_persistence.update_session(
            session_id,
            context_data=context_data,
            state_data=state_data,
            metadata=metadata,
        )
        success = await self._session_persistence.persist_session(session_id)
        self._metrics.increment("sessions_saved" if success else "sessions_failed")
        return success

    async def restore_session_state(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:
        """Restore session state.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        dict[str, Any] | None
            Restored state data.
        """
        state = await self._session_persistence.restore_session(session_id)
        if state is None:
            self._stats.record_cache_miss()
            return None
        self._stats.record_cache_hit()
        return {
            "context_data": state.context_data,
            "state_data": state.state_data,
            "metadata": state.metadata,
        }

    # ------------------------------------------------------------------
    # Compression
    # ------------------------------------------------------------------

    async def compress_context(
        self,
        chunks: list[CodeChunk],
        target_ratio: float = 0.5,
    ) -> list[CodeChunk]:
        """Compress code chunks.

        Parameters
        ----------
        chunks : list[CodeChunk]
            Chunks to compress.
        target_ratio : float
            Target compression ratio.

        Returns
        -------
        list[CodeChunk]
            Compressed chunks.
        """
        self._ensure_not_degraded()
        original_tokens = sum(c.token_count for c in chunks)
        compressed = self._context_compression.compress_chunks(
            chunks, target_ratio,
        )
        compressed_tokens = sum(c.token_count for c in compressed)
        self._stats.record_compression(original_tokens, compressed_tokens)
        self._metrics.increment("compressions")
        return compressed

    # ------------------------------------------------------------------
    # Knowledge cache
    # ------------------------------------------------------------------

    async def cache_knowledge(self, key: str, value: Any) -> None:
        """Cache project knowledge.

        Parameters
        ----------
        key : str
            Cache key.
        value : Any
            Value to cache.
        """
        self._knowledge_cache.set(key, value)

    async def get_cached_knowledge(self, key: str) -> Any | None:
        """Get cached project knowledge.

        Parameters
        ----------
        key : str
            Cache key.

        Returns
        -------
        Any | None
            Cached value if found.
        """
        value = self._knowledge_cache.get(key)
        if value is not None:
            self._stats.record_cache_hit()
            self._metrics.increment("cache_hits")
        else:
            self._stats.record_cache_miss()
            self._metrics.increment("cache_misses")
        return value

    # ------------------------------------------------------------------
    # Metrics and health
    # ------------------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Return current metrics snapshot.

        Returns
        -------
        dict[str, Any]
            Metrics dictionary.
        """
        stats = self._stats.to_dict()
        metrics_dict = self._metrics.to_dict()
        cache_stats = self._knowledge_cache.stats()
        return {
            "statistics": stats,
            "metrics": metrics_dict,
            "cache": cache_stats,
            "file_index_count": self._workspace_index.entry_count,
            "symbol_count": self._symbol_index.symbol_count,
            "session_count": self._session_persistence.session_count,
        }

    def health(self) -> dict[str, Any]:
        """Return health status of the context intelligence module.

        Returns
        -------
        dict[str, Any]
            Health report dictionary.
        """
        report = self._health_reporting.generate_report_sync()
        return {
            "healthy": report.healthy and not self._degraded,
            "degraded": self._degraded,
            "initialized": self._initialized,
            "services_online": report.services_online,
            "services_total": report.services_total,
            "checks": report.checks,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_health_checks(self) -> None:
        self._health_reporting.register_service(
            "mcp", self._mcp.health_check,
        )
        self._health_reporting.register_service(
            "repository_map", self._repository_map.health_check,
        )
        self._health_reporting.register_service(
            "multi_file_context", self._multi_file_context.health_check,
        )
        self._health_reporting.register_service(
            "workspace_index", self._workspace_index.health_check,
        )
        self._health_reporting.register_service(
            "symbol_index", self._symbol_index.health_check,
        )
        self._health_reporting.register_service(
            "cross_file_navigation", self._cross_file_nav.health_check,
        )
        self._health_reporting.register_service(
            "dependency_graph", self._dependency_graph.health_check,
        )
        self._health_reporting.register_service(
            "import_graph", self._import_graph.health_check,
        )
        self._health_reporting.register_service(
            "file_ranking", self._file_ranking.health_check,
        )
        self._health_reporting.register_service(
            "window_optimizer", self._window_optimizer.health_check,
        )
        self._health_reporting.register_service(
            "knowledge_cache", self._knowledge_cache.health_check,
        )
        self._health_reporting.register_service(
            "session_persistence", self._session_persistence.health_check,
        )
        self._health_reporting.register_service(
            "context_compression", self._context_compression.health_check,
        )
        self._health_reporting.register_service(
            "semantic_search", self._semantic_search.health_check,
        )
        self._health_reporting.register_service(
            "code_chunking", self._code_chunking.health_check,
        )
        self._health_reporting.register_service(
            "related_file_discovery", self._related_file_discovery.health_check,
        )
        self._health_reporting.register_service(
            "auto_expansion", self._auto_expansion.health_check,
        )
        self._health_reporting.register_service(
            "statistics", self._stats.health_check,
        )
        self._health_reporting.register_service(
            "health_reporting", self._health_reporting.health_check,
        )
        self._health_reporting.register_service(
            "metrics_collection", self._metrics.health_check,
        )

    def _resolve_path(self, relative_path: str) -> str:
        if self._workspace_root:
            import os
            return os.path.join(self._workspace_root, relative_path)
        return relative_path

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "ContextIntelligenceManager is degraded",
                context={"module": "context_intelligence"},
            )

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)
