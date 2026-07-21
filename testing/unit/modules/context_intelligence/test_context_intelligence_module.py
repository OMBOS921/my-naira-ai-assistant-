"""Comprehensive tests for the Context Intelligence module.

Covers:
- All 20 service classes with unit tests
- ContextIntelligenceManager (ModuleInterface lifecycle + API)
- Types and data classes
- Port/Adapter pattern
- ModuleInterface protocol conformance
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.context_intelligence import ContextIntelligenceManager
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
    DependencyInfo,
    FileRanking,
    HealthReport,
    IndexEntry,
    MCPContext,
    MetricsSnapshot,
    RelatedFileSet,
    RepositoryNode,
    SymbolInfo,
)
from backend.modules.context_intelligence._workspace_index import WorkspaceIndex
from backend.modules.context_intelligence.ports.ports import (
    ContextPort,
)
from backend.modules.context_intelligence.providers.providers import (
    DictMemoryAdapter,
    MemoryAdapter,
)
from backend.types import ModuleInterface

# =========================================================================
# Helper
# =========================================================================


def _make_chunk(
    file_path: str = "test.py",
    content: str = "def foo(): pass",
    start: int = 1,
    end: int = 2,
) -> CodeChunk:
    return CodeChunk(
        chunk_id=f"chunk_{file_path}_{start}",
        file_path=file_path,
        start_line=start,
        end_line=end,
        content=content,
        strategy="function",
        language="Python",
        symbol_name="foo",
        token_count=max(1, len(content) // 4),
    )


# =========================================================================
# Types
# =========================================================================


class TestTypes:
    def test_code_chunk(self) -> None:
        c = _make_chunk()
        assert c.start_line == 1
        assert c.symbol_name == "foo"

    def test_symbol_info(self) -> None:
        s = SymbolInfo(name="Foo", symbol_type="class", file_path="a.py", line=10)
        assert s.name == "Foo"
        assert s.symbol_type == "class"

    def test_dependency_info(self) -> None:
        d = DependencyInfo(
            source_path="a.py", target_path="b.py", dep_type="import", line=5,
        )
        assert d.dep_type == "import"

    def test_repository_node(self) -> None:
        n = RepositoryNode(path="/root", name="root", node_type="directory")
        assert n.node_type == "directory"

    def test_context_statistics(self) -> None:
        s = ContextStatistics(total_contexts_built=10, total_tokens_processed=5000)
        assert s.total_contexts_built == 10

    def test_mcp_context(self) -> None:
        ctx = MCPContext(session_id="s1", system_prompt="You are a bot")
        assert ctx.session_id == "s1"

    def test_file_ranking(self) -> None:
        r = FileRanking(file_path="a.py", score=0.95, reasons=["test"])
        assert r.score == 0.95

    def test_related_file_set(self) -> None:
        rs = RelatedFileSet(source_path="a.py")
        assert rs.source_path == "a.py"

    def test_health_report(self) -> None:
        hr = HealthReport(healthy=True, services_online=5, services_total=5)
        assert hr.healthy

    def test_metrics_snapshot(self) -> None:
        ms = MetricsSnapshot(timestamp=100.0)
        assert ms.timestamp == 100.0

    def test_index_entry(self) -> None:
        ie = IndexEntry(entry_type="file", key="test.py")
        assert ie.entry_type == "file"


# =========================================================================
# MCP Protocol
# =========================================================================


class TestMCPProtocol:
    def test_create_context(self) -> None:
        mcp = MCPProtocol()
        ctx = mcp.create_context(
            session_id="s1",
            system_prompt="You are a coding assistant",
            chunks=[_make_chunk()],
            symbols=[SymbolInfo(name="foo", symbol_type="function", file_path="a.py", line=1)],
        )
        assert ctx.session_id == "s1"
        assert len(ctx.chunks) == 1
        assert len(ctx.symbols) == 1

    def test_merge_contexts(self) -> None:
        mcp = MCPProtocol()
        c1 = mcp.create_context(session_id="s1", system_prompt="p1")
        c2 = mcp.create_context(session_id="s1", system_prompt="p2",
                                chunks=[_make_chunk()])
        merged = mcp.merge_contexts([c1, c2])
        assert len(merged.chunks) == 1
        assert "p1" in merged.system_prompt

    def test_to_dict(self) -> None:
        mcp = MCPProtocol()
        ctx = mcp.create_context(session_id="s1")
        d = mcp.to_dict(ctx)
        assert d["session_id"] == "s1"
        assert "context_id" in d

    def test_estimate_tokens(self) -> None:
        mcp = MCPProtocol()
        ctx = mcp.create_context(
            session_id="s1",
            system_prompt="Hello world",
            chunks=[_make_chunk(content="x" * 100)],
        )
        tokens = mcp.estimate_tokens(ctx)
        assert tokens > 0

    def test_context_counter(self) -> None:
        mcp = MCPProtocol()
        mcp.create_context(session_id="s1")
        mcp.create_context(session_id="s2")
        assert mcp.total_contexts_created == 2

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        mcp = MCPProtocol()
        assert await mcp.health_check()


# =========================================================================
# Repository Map
# =========================================================================


class TestRepositoryMap:
    def test_build_map(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "test.py").write_text("x = 1")
        (tmp_path / "data.txt").write_text("hello")

        rm = RepositoryMap()
        root = rm.build_map(str(tmp_path))
        assert root.node_type == "directory"
        children_names = [c.name for c in root.children]
        assert "sub" in children_names or len(root.children) > 0

    def test_flatten_map(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.py").write_text("y = 2")

        rm = RepositoryMap()
        rm.build_map(str(tmp_path))
        files = rm.flatten_map()
        assert any("a.py" in f for f in files)

    def test_search_files(self, tmp_path: Path) -> None:
        (tmp_path / "model.py").write_text("x = 1")
        (tmp_path / "view.py").write_text("y = 2")

        rm = RepositoryMap()
        rm.build_map(str(tmp_path))
        results = rm.search_files("model")
        assert any("model" in r for r in results)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        rm = RepositoryMap()
        assert await rm.health_check()

    def test_empty_directory(self, tmp_path: Path) -> None:
        rm = RepositoryMap()
        root = rm.build_map(str(tmp_path))
        assert root.node_type == "directory"


# =========================================================================
# Multi-file Context Tree
# =========================================================================


class TestMultiFileContextTree:
    def test_build_tree(self) -> None:
        mfct = MultiFileContextTree()
        files = [
            {"path": "src/main.py", "chunks": [_make_chunk("main.py")], "language": "Python"},
            {"path": "src/utils.py", "chunks": [_make_chunk("utils.py")], "language": "Python"},
        ]
        root = mfct.build_tree(files)
        assert root.file_path == "<root>"
        assert len(root.children) > 0

    def test_flatten_tree(self) -> None:
        mfct = MultiFileContextTree()
        files = [{"path": "src/main.py", "language": "Python"}]
        root = mfct.build_tree(files)
        flat = mfct.flatten_tree(root)
        assert len(flat) > 0
        assert flat[0]["path"] in ("<root>", "src")

    def test_prune_by_token_budget(self) -> None:
        mfct = MultiFileContextTree()
        chunks = [_make_chunk("a.py", content="x" * 100, start=1, end=10)]
        files = [{"path": "a.py", "chunks": chunks, "language": "Python"}]
        root = mfct.build_tree(files)
        pruned = mfct.prune_by_token_budget(root, budget=0)
        assert pruned is not None

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        mfct = MultiFileContextTree()
        assert await mfct.health_check()


# =========================================================================
# Workspace Index
# =========================================================================


class TestWorkspaceIndex:
    def test_index_workspace(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")

        wi = WorkspaceIndex()
        count = wi.index_workspace(str(tmp_path))
        assert count >= 1
        assert wi.entry_count >= 1

    def test_search(self, tmp_path: Path) -> None:
        (tmp_path / "model.py").write_text("x = 1")

        wi = WorkspaceIndex()
        wi.index_workspace(str(tmp_path))
        results = wi.search("model")
        assert len(results) >= 1

    def test_language_stats(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")

        wi = WorkspaceIndex()
        wi.index_workspace(str(tmp_path))
        stats = wi.language_stats()
        assert "Python" in stats

    def test_clear(self) -> None:
        wi = WorkspaceIndex()
        wi.index_workspace(tempfile.gettempdir())
        wi.clear()
        assert wi.entry_count == 0

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        wi = WorkspaceIndex()
        assert await wi.health_check()


# =========================================================================
# Symbol Index
# =========================================================================


class TestSymbolIndex:
    def test_index_file(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test_module.py"
        py_file.write_text("class Foo:\n    def bar(self): pass\ndef baz(): pass\nx = 1")
        si = SymbolIndex()
        count = si.index_file(str(py_file))
        assert count >= 3

    def test_search(self, tmp_path: Path) -> None:
        py_file = tmp_path / "search_test.py"
        py_file.write_text("class MyClass: pass\ndef my_func(): pass")
        si = SymbolIndex()
        si.index_file(str(py_file))
        results = si.search("MyClass")
        assert len(results) >= 1
        assert results[0].name == "MyClass"

    def test_search_by_type(self, tmp_path: Path) -> None:
        py_file = tmp_path / "type_test.py"
        py_file.write_text("class A: pass\ndef b(): pass")
        si = SymbolIndex()
        si.index_file(str(py_file))
        classes = si.search("A", symbol_type="class")
        assert len(classes) >= 1
        funcs = si.search("b", symbol_type="function")
        assert len(funcs) >= 1

    def test_get_symbols_in_file(self, tmp_path: Path) -> None:
        py_file = tmp_path / "symbols.py"
        py_file.write_text("class X: pass")
        si = SymbolIndex()
        si.index_file(str(py_file))
        syms = si.get_symbols_in_file(str(py_file))
        assert len(syms) >= 1

    def test_get_symbol_by_name(self, tmp_path: Path) -> None:
        py_file = tmp_path / "by_name.py"
        py_file.write_text("class UniqueName: pass")
        si = SymbolIndex()
        si.index_file(str(py_file))
        matches = si.get_symbol_by_name("UniqueName")
        assert len(matches) == 1

    def test_clear(self, tmp_path: Path) -> None:
        py_file = tmp_path / "clear_test.py"
        py_file.write_text("class A: pass")
        si = SymbolIndex()
        si.index_file(str(py_file))
        si.clear()
        assert si.symbol_count == 0

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        si = SymbolIndex()
        assert await si.health_check()

    def test_index_empty_file(self, tmp_path: Path) -> None:
        py_file = tmp_path / "empty.py"
        py_file.write_text("")
        si = SymbolIndex()
        count = si.index_file(str(py_file))
        assert count == 0

    def test_index_nonexistent_file(self) -> None:
        si = SymbolIndex()
        count = si.index_file("/nonexistent/file.py")
        assert count == 0


# =========================================================================
# Cross-file Navigation
# =========================================================================


class TestCrossFileNavigation:
    def test_index_file(self, tmp_path: Path) -> None:
        py_file = tmp_path / "nav_a.py"
        py_file.write_text("import os\nclass A: pass\ndef f(): pass")
        cfn = CrossFileNavigation()
        cfn.index_file(str(py_file))
        refs = cfn.get_all_references()
        assert str(py_file) in refs

    def test_find_references(self, tmp_path: Path) -> None:
        a = tmp_path / "a.py"
        a.write_text("import os\nos.path.join('a', 'b')")
        cfn = CrossFileNavigation()
        cfn.index_file(str(a))
        refs = cfn.find_references("os")
        assert len(refs) >= 1

    def test_find_definition(self, tmp_path: Path) -> None:
        a = tmp_path / "def_a.py"
        a.write_text("class DefinedHere: pass")
        cfn = CrossFileNavigation()
        cfn.index_file(str(a))
        defs = cfn.find_definition("DefinedHere")
        assert len(defs) >= 1

    def test_clear(self, tmp_path: Path) -> None:
        a = tmp_path / "clear_nav.py"
        a.write_text("class A: pass")
        cfn = CrossFileNavigation()
        cfn.index_file(str(a))
        cfn.clear()
        assert cfn.get_all_definitions() == {}

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        cfn = CrossFileNavigation()
        assert await cfn.health_check()


# =========================================================================
# Dependency Graph
# =========================================================================


class TestDependencyGraph:
    def test_index_file(self, tmp_path: Path) -> None:
        a = tmp_path / "dep_a.py"
        a.write_text("import os\nfrom pathlib import Path")
        dg = DependencyGraph()
        deps = dg.index_file(str(a))
        assert len(deps) >= 1

    def test_get_dependents(self) -> None:
        dg = DependencyGraph()
        dg.index_file.__globals__["__debug__"] = True  # ensure no-op
        assert dg.get_dependents("test.py") == []

    def test_find_affected_files(self) -> None:
        dg = DependencyGraph()
        affected = dg.find_affected_files("test.py")
        assert isinstance(affected, list)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        dg = DependencyGraph()
        assert await dg.health_check()

    def test_clear(self, tmp_path: Path) -> None:
        a = tmp_path / "dep_clear.py"
        a.write_text("import sys")
        dg = DependencyGraph()
        dg.index_file(str(a))
        dg.clear()
        assert dg.dependency_count == 0


# =========================================================================
# Import Graph
# =========================================================================


class TestImportGraph:
    def test_index_file(self, tmp_path: Path) -> None:
        a = tmp_path / "import_a.py"
        a.write_text("import os\nimport sys\nfrom pathlib import Path")
        ig = ImportGraph()
        ig.index_file(str(a))
        assert ig.indexed_file_count >= 1

    def test_get_imports(self, tmp_path: Path) -> None:
        a = tmp_path / "import_b.py"
        a.write_text("import os\nimport sys")
        ig = ImportGraph()
        ig.index_file(str(a))
        imports = ig.get_imports(str(a))
        assert "os" in imports
        assert "sys" in imports

    def test_get_importers(self, tmp_path: Path) -> None:
        a = tmp_path / "import_c.py"
        a.write_text("import os")
        ig = ImportGraph()
        ig.index_file(str(a))
        importers = ig.get_importers("os")
        assert str(a) in importers

    def test_detect_cycles(self, tmp_path: Path) -> None:
        a = tmp_path / "cycle_a.py"
        a.write_text("import os")
        ig = ImportGraph()
        ig.index_file(str(a))
        cycles = ig.detect_cycles()
        assert isinstance(cycles, list)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        ig = ImportGraph()
        assert await ig.health_check()

    def test_clear(self, tmp_path: Path) -> None:
        a = tmp_path / "import_clear.py"
        a.write_text("import os")
        ig = ImportGraph()
        ig.index_file(str(a))
        ig.clear()
        assert ig.indexed_file_count == 0


# =========================================================================
# File Ranking Engine
# =========================================================================


class TestFileRankingEngine:
    def test_rank_files(self) -> None:
        fre = FileRankingEngine()
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        results = fre.rank_files("main", files)
        assert len(results) >= 1

    def test_rank_files_with_symbols(self) -> None:
        fre = FileRankingEngine()
        files = ["src/model.py", "src/view.py"]
        symbols = {"src/model.py": ["ModelClass", "model_func"]}
        results = fre.rank_files("ModelClass", files, symbol_matches=symbols)
        assert len(results) >= 1

    def test_rank_by_dependency_impact(self) -> None:
        fre = FileRankingEngine()
        files = ["a.py", "b.py", "c.py"]
        dep_map = {"b.py": ["a.py"], "c.py": ["a.py"]}
        results = fre.rank_by_dependency_impact("a.py", files, dep_map)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        fre = FileRankingEngine()
        assert await fre.health_check()


# =========================================================================
# Context Window Optimizer
# =========================================================================


class TestContextWindowOptimizer:
    def test_optimize_chunks(self) -> None:
        cwo = ContextWindowOptimizer(default_max_tokens=100)
        chunks = [
            _make_chunk("a.py", content="x" * 20),
            _make_chunk("b.py", content="y" * 20),
        ]
        optimized = cwo.optimize_chunks(chunks, max_tokens=50, preserve_system_prompt=False)
        assert len(optimized) >= 1

    def test_estimate_tokens(self) -> None:
        cwo = ContextWindowOptimizer()
        assert cwo.estimate_tokens("hello") == 1
        assert cwo.estimate_tokens("a" * 100) == 25

    def test_suggest_budget_allocation(self) -> None:
        cwo = ContextWindowOptimizer()
        allocation = cwo.suggest_budget_allocation(
            1000, {"code": 0.6, "docs": 0.4}
        )
        assert "code" in allocation
        assert "docs" in allocation

    def test_fit_to_window(self) -> None:
        cwo = ContextWindowOptimizer()
        short = "Hello world"
        assert cwo.fit_to_window(short, 1000) == short
        long_text = "A" * 1000
        fitted = cwo.fit_to_window(long_text, 10)
        assert len(fitted) < len(long_text)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        cwo = ContextWindowOptimizer()
        assert await cwo.health_check()


# =========================================================================
# Project Knowledge Cache
# =========================================================================


class TestProjectKnowledgeCache:
    def test_set_and_get(self) -> None:
        cache = ProjectKnowledgeCache(ttl_seconds=60)
        cache.set("key1", {"data": "value"})
        val = cache.get("key1")
        assert val == {"data": "value"}

    def test_miss(self) -> None:
        cache = ProjectKnowledgeCache()
        val = cache.get("nonexistent")
        assert val is None

    def test_invalidate(self) -> None:
        cache = ProjectKnowledgeCache()
        cache.set("key", "value")
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_stats(self) -> None:
        cache = ProjectKnowledgeCache()
        cache.set("a", 1)
        cache.get("a")
        cache.get("b")
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_clear(self) -> None:
        cache = ProjectKnowledgeCache()
        cache.set("a", 1)
        cache.clear()
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_persist_and_load(self, tmp_path: Path) -> None:
        p = tmp_path / "cache.json"
        cache = ProjectKnowledgeCache(persist_path=p, ttl_seconds=600)
        cache.set("test_key", [1, 2, 3])
        await cache.persist()
        assert p.exists()

        cache2 = ProjectKnowledgeCache(persist_path=p, ttl_seconds=600)
        await cache2.load_persisted()
        val = cache2.get("test_key")
        assert val == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        cache = ProjectKnowledgeCache()
        assert await cache.health_check()


# =========================================================================
# Session Persistence
# =========================================================================


class TestSessionPersistence:
    def test_create_and_get(self) -> None:
        sp = SessionPersistence()
        state = sp.create_session("s1", metadata={"user": "alice"})
        assert state.session_id == "s1"
        retrieved = sp.get_session("s1")
        assert retrieved is not None
        assert retrieved.metadata["user"] == "alice"

    def test_update_session(self) -> None:
        sp = SessionPersistence()
        sp.create_session("s1")
        sp.update_session("s1", state_data={"progress": 50})
        state = sp.get_session("s1")
        assert state is not None
        assert state.state_data["progress"] == 50

    def test_delete_session(self) -> None:
        sp = SessionPersistence()
        sp.create_session("s1")
        sp.delete_session("s1")
        assert sp.get_session("s1") is None

    def test_list_sessions(self) -> None:
        sp = SessionPersistence()
        sp.create_session("a")
        sp.create_session("b")
        sessions = sp.list_sessions()
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_persist_and_restore(self, tmp_path: Path) -> None:
        persist_dir = tmp_path / "sessions"
        sp = SessionPersistence(persist_dir=persist_dir)
        sp.create_session("test_sess", metadata={"test": True})
        sp.update_session("test_sess", state_data={"done": True})
        ok = await sp.persist_session("test_sess")
        assert ok

        sp2 = SessionPersistence(persist_dir=persist_dir)
        restored = await sp2.restore_session("test_sess")
        assert restored is not None
        assert restored.metadata["test"] is True

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        sp = SessionPersistence()
        assert await sp.health_check()


# =========================================================================
# Context Compression
# =========================================================================


class TestContextCompression:
    def test_compress_chunks(self) -> None:
        cc = ContextCompression()
        chunks = [
            _make_chunk("a.py", content="def foo(): pass"),
            _make_chunk("b.py", content="def bar(): pass"),
        ]
        compressed = cc.compress_chunks(chunks, target_ratio=1.0)
        assert len(compressed) >= 1

    def test_compress_text(self) -> None:
        cc = ContextCompression()
        short = "Hello world"
        assert cc.compress_text(short, 100) == short
        long_text = "A" * 1000
        compressed = cc.compress_text(long_text, 100)
        assert len(compressed) < len(long_text)

    def test_deduplicate_texts(self) -> None:
        cc = ContextCompression()
        texts = ["hello world", "hello world", "different"]
        deduped = cc.deduplicate_texts(texts)
        assert len(deduped) == 2

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        cc = ContextCompression()
        assert await cc.health_check()


# =========================================================================
# Semantic Search
# =========================================================================


class TestSemanticSearch:
    def test_index_and_search(self) -> None:
        ss = SemanticSearch()
        ss.index_document("doc1", "This module handles user authentication")
        ss.index_document("doc2", "This module handles payment processing")
        results = ss.search("authentication")
        assert len(results) >= 1
        assert results[0].source_id == "doc1"

    def test_search_empty(self) -> None:
        ss = SemanticSearch()
        results = ss.search("anything")
        assert results == []

    def test_remove_document(self) -> None:
        ss = SemanticSearch()
        ss.index_document("doc1", "user auth module")
        ss.remove_document("doc1")
        results = ss.search("auth")
        assert len(results) == 0

    def test_search_with_multiple_terms(self) -> None:
        ss = SemanticSearch()
        ss.index_document("doc1", "user login and registration module")
        ss.index_document("doc2", "payment gateway integration")
        results = ss.search("user login")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        ss = SemanticSearch()
        assert await ss.health_check()

    def test_clear(self) -> None:
        ss = SemanticSearch()
        ss.index_document("d1", "some content")
        ss.clear()
        assert ss.document_count == 0


# =========================================================================
# Code Chunking
# =========================================================================


class TestCodeChunking:
    def test_chunk_file_by_function(self, tmp_path: Path) -> None:
        py_file = tmp_path / "chunk_test.py"
        py_file.write_text("def foo():\n    pass\n\ndef bar():\n    return 1\n")
        cc = CodeChunking()
        chunks = cc.chunk_file(str(py_file), strategy="function")
        assert len(chunks) >= 2

    def test_chunk_file_by_class(self, tmp_path: Path) -> None:
        py_file = tmp_path / "class_chunk.py"
        py_file.write_text("class MyClass:\n    def method(self): pass\n")
        cc = CodeChunking()
        chunks = cc.chunk_file(str(py_file), strategy="class")
        assert len(chunks) >= 1
        assert chunks[0].symbol_name == "MyClass"

    def test_chunk_file_by_line(self, tmp_path: Path) -> None:
        py_file = tmp_path / "line_chunk.py"
        py_file.write_text("a=1\nb=2\nc=3\n")
        cc = CodeChunking()
        chunks = cc.chunk_file(str(py_file), strategy="line")
        assert len(chunks) == 3

    def test_chunk_file_by_block(self, tmp_path: Path) -> None:
        py_file = tmp_path / "block_chunk.py"
        py_file.write_text("\n".join(f"x = {i}" for i in range(100)))
        cc = CodeChunking(max_chunk_size=20, min_chunk_size=5)
        chunks = cc.chunk_file(str(py_file), strategy="block")
        assert len(chunks) >= 1

    def test_chunk_nonexistent_file(self) -> None:
        cc = CodeChunking()
        chunks = cc.chunk_file("/nonexistent/file.py")
        assert chunks == []

    def test_syntax_error_fallback(self, tmp_path: Path) -> None:
        py_file = tmp_path / "syntax_error.py"
        py_file.write_text("this is not valid python @@@")
        cc = CodeChunking()
        chunks = cc.chunk_file(str(py_file), strategy="function")
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        cc = CodeChunking()
        assert await cc.health_check()


# =========================================================================
# Related File Discovery
# =========================================================================


class TestRelatedFileDiscovery:
    def test_find_related(self) -> None:
        rfd = RelatedFileDiscovery()
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        result = rfd.find_related("src/main.py", files)
        assert result.source_path == "src/main.py"
        assert len(result.related_files) >= 1

    def test_find_related_with_imports(self) -> None:
        rfd = RelatedFileDiscovery()
        files = ["a.py", "b.py", "c.py"]
        imports = {"a.py": ["b"], "b.py": ["c"]}
        result = rfd.find_related("a.py", files, import_map=imports)
        assert len(result.related_files) >= 1

    def test_find_co_occurring(self) -> None:
        rfd = RelatedFileDiscovery()
        imports = {
            "a.py": ["os", "sys"],
            "b.py": ["os", "json"],
            "c.py": ["os", "sys"],
        }
        co = rfd.find_co_occurring(["a.py"], imports)
        assert isinstance(co, list)

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        rfd = RelatedFileDiscovery()
        assert await rfd.health_check()


# =========================================================================
# Automatic Context Expansion
# =========================================================================


class TestAutomaticContextExpansion:
    def test_expand_context(self) -> None:
        ace = AutomaticContextExpansion(max_expansion_files=2)
        ctx = MCPContext(session_id="s1", system_prompt="test")
        related = [
            RelatedFileSet(
                source_path="main.py",
                related_files=[FileRanking(file_path="utils.py", score=0.8)],
            )
        ]
        chunks = {
            "utils.py": [_make_chunk("utils.py", content="def util(): pass")],
        }
        expanded = ace.expand_context(ctx, related, chunks, current_token_count=10)
        assert expanded.session_id == "s1"

    def test_suggest_expansion(self) -> None:
        ace = AutomaticContextExpansion()
        related = [
            RelatedFileSet(
                source_path="a.py",
                related_files=[
                    FileRanking(file_path="b.py", score=0.9),
                    FileRanking(file_path="c.py", score=0.5),
                ],
            )
        ]
        suggestions = ace.suggest_expansion(["a.py"], related)
        assert "b.py" in suggestions

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        ace = AutomaticContextExpansion()
        assert await ace.health_check()


# =========================================================================
# Context Statistics
# =========================================================================


class TestContextStatisticsTracker:
    def test_record_context_built(self) -> None:
        tracker = ContextStatisticsTracker()
        tracker.record_context_built(1000, 50.0)
        tracker.record_context_built(2000, 75.0)
        stats = tracker.snapshot()
        assert stats.total_contexts_built == 2
        assert stats.total_tokens_processed == 3000

    def test_record_compression(self) -> None:
        tracker = ContextStatisticsTracker()
        tracker.record_compression(1000, 500)
        stats = tracker.snapshot()
        assert stats.total_compressions == 1
        assert stats.compression_ratio == 0.5

    def test_record_chunks_created(self) -> None:
        tracker = ContextStatisticsTracker()
        tracker.record_chunks_created(50)
        stats = tracker.snapshot()
        assert stats.total_chunks_created == 50

    def test_record_cache_hit_miss(self) -> None:
        tracker = ContextStatisticsTracker()
        tracker.record_cache_hit()
        tracker.record_cache_miss()
        stats = tracker.snapshot()
        assert stats.total_cache_hits == 1
        assert stats.total_cache_misses == 1

    def test_to_dict(self) -> None:
        tracker = ContextStatisticsTracker()
        tracker.record_context_built(500, 25.0)
        d = tracker.to_dict()
        assert d["total_contexts_built"] == 1
        assert d["total_tokens_processed"] == 500

    def test_reset(self) -> None:
        tracker = ContextStatisticsTracker()
        tracker.record_context_built(100, 10.0)
        tracker.reset()
        stats = tracker.snapshot()
        assert stats.total_contexts_built == 0

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        tracker = ContextStatisticsTracker()
        assert await tracker.health_check()


# =========================================================================
# Health Reporting
# =========================================================================


class TestHealthReporting:
    @pytest.mark.asyncio
    async def test_register_and_report(self) -> None:
        hr = HealthReporting()
        hr.register_service("svc1", lambda: True)
        hr.register_service("svc2", lambda: True)
        report = await hr.generate_report()
        assert report.services_online == 2
        assert report.services_total == 2
        assert report.healthy

    @pytest.mark.asyncio
    async def test_degraded(self) -> None:
        hr = HealthReporting()
        hr.register_service("svc1", lambda: True)
        hr.mark_degraded()
        report = await hr.generate_report()
        assert report.degraded

    @pytest.mark.asyncio
    async def test_failing_check(self) -> None:
        hr = HealthReporting()
        hr.register_service("fails", lambda: False)
        report = await hr.generate_report()
        assert not report.healthy

    @pytest.mark.asyncio
    async def test_check_exception(self) -> None:
        hr = HealthReporting()

        def _failing() -> bool:
            raise ValueError("fail")

        hr.register_service("bad", _failing)
        report = await hr.generate_report()
        checks = report.checks.get("bad", {})
        assert checks.get("healthy") is False

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        hr = HealthReporting()
        hr.register_service("t", lambda: True)
        assert await hr.health_check()


# =========================================================================
# Metrics Collection
# =========================================================================


class TestMetricsCollector:
    def test_increment(self) -> None:
        mc = MetricsCollector()
        mc.increment("requests")
        mc.increment("requests", 5)
        assert mc.get_counter("requests") == 6

    def test_gauge(self) -> None:
        mc = MetricsCollector()
        mc.set_gauge("temperature", 0.8)
        assert mc.get_gauge("temperature") == 0.8

    def test_record_value(self) -> None:
        mc = MetricsCollector()
        mc.record_value("latency_ms", 100.0)
        mc.record_value("latency_ms", 200.0)
        avg = mc.get_average("latency_ms")
        assert avg == 150.0

    def test_snapshot(self) -> None:
        mc = MetricsCollector()
        mc.increment("ops")
        mc.set_gauge("cpu", 0.5)
        snap = mc.snapshot()
        assert snap.counters["ops"] == 1
        assert snap.gauges["cpu"] == 0.5

    def test_to_dict(self) -> None:
        mc = MetricsCollector()
        mc.increment("count")
        d = mc.to_dict()
        assert d["counters"]["count"] == 1

    def test_reset(self) -> None:
        mc = MetricsCollector()
        mc.increment("x")
        mc.reset()
        assert mc.get_counter("x") == 0

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        mc = MetricsCollector()
        assert await mc.health_check()


# =========================================================================
# Ports and Adapters
# =========================================================================


class TestMemoryPort:
    def test_memory_adapter(self) -> None:
        adapter = MemoryAdapter()
        assert adapter is not None

    @pytest.mark.asyncio
    async def test_memory_adapter_store_load(self, tmp_path: Path) -> None:
        p = tmp_path / "test_memory.json"
        adapter = MemoryAdapter(storage_path=p)
        await adapter.store("key1", {"value": 42})
        val = await adapter.load("key1")
        assert val == {"value": 42}

    @pytest.mark.asyncio
    async def test_memory_adapter_delete(self, tmp_path: Path) -> None:
        p = tmp_path / "test_delete.json"
        adapter = MemoryAdapter(storage_path=p)
        await adapter.store("k", "v")
        await adapter.delete("k")
        val = await adapter.load("k")
        assert val is None

    @pytest.mark.asyncio
    async def test_memory_adapter_list_keys(self, tmp_path: Path) -> None:
        p = tmp_path / "test_list.json"
        adapter = MemoryAdapter(storage_path=p)
        await adapter.store("prefix_a", 1)
        await adapter.store("prefix_b", 2)
        keys = await adapter.list_keys("prefix_")
        assert len(keys) == 2

    @pytest.mark.asyncio
    async def test_memory_adapter_health(self, tmp_path: Path) -> None:
        adapter = MemoryAdapter(storage_path=tmp_path / "health.json")
        assert await adapter.health_check()

    @pytest.mark.asyncio
    async def test_dict_memory_adapter(self) -> None:
        adapter = DictMemoryAdapter()
        await adapter.store("k", "v")
        val = await adapter.load("k")
        assert val == "v"
        assert await adapter.health_check()


class TestContextPort:
    def test_context_port_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            ContextPort()  # type: ignore[abstract]


# =========================================================================
# ContextIntelligenceManager — Lifecycle
# =========================================================================


class TestContextIntelligenceManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = ContextIntelligenceManager()
        assert mgr.degraded is False
        assert mgr.initialized is False

    @pytest.mark.asyncio
    async def test_async_init(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        assert mgr.initialized is True
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        assert mgr.initialized is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()
        assert mgr.initialized is False

    @pytest.mark.asyncio
    async def test_degrade(self) -> None:
        mgr = ContextIntelligenceManager()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = ContextIntelligenceManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = MagicMock()
        mgr = ContextIntelligenceManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_all_services_accessible(self) -> None:
        mgr = ContextIntelligenceManager()
        assert mgr.mcp is not None
        assert mgr.repository_map is not None
        assert mgr.multi_file_context is not None
        assert mgr.workspace_index is not None
        assert mgr.symbol_index is not None
        assert mgr.cross_file_navigation is not None
        assert mgr.dependency_graph is not None
        assert mgr.import_graph is not None
        assert mgr.file_ranking is not None
        assert mgr.window_optimizer is not None
        assert mgr.knowledge_cache is not None
        assert mgr.session_persistence is not None
        assert mgr.context_compression is not None
        assert mgr.semantic_search is not None
        assert mgr.code_chunking is not None
        assert mgr.related_file_discovery is not None
        assert mgr.auto_expansion is not None
        assert mgr.stats is not None
        assert mgr.health_reporting is not None
        assert mgr.metrics_collector is not None


# =========================================================================
# ContextIntelligenceManager — Metrics and Health
# =========================================================================


class TestContextIntelligenceManagerMetrics:
    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        metrics = mgr.metrics()
        assert "statistics" in metrics
        assert "metrics" in metrics
        assert "cache" in metrics

    @pytest.mark.asyncio
    async def test_health(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        health = mgr.health()
        assert "healthy" in health
        assert "degraded" in health
        assert "services_online" in health


# =========================================================================
# ContextIntelligenceManager — High-level API
# =========================================================================


class TestContextIntelligenceManagerAPI:
    @pytest.mark.asyncio
    async def test_build_rich_context(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        ctx = await mgr.build_rich_context(
            session_id="test_sess",
            query="authentication module",
            system_prompt="You are a coding assistant",
            max_tokens=1000,
        )
        assert ctx.session_id == "test_sess"
        assert "coding assistant" in ctx.system_prompt

    @pytest.mark.asyncio
    async def test_search_codebase(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        mgr._semantic_search.index_document("test.py", "def authenticate(): pass")
        results = await mgr.search_codebase("authenticate")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_index_workspace(self, tmp_path: Path) -> None:
        (tmp_path / "sample.py").write_text("class Sample: pass")
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        result = await mgr.index_workspace(str(tmp_path))
        assert result["files"] >= 1

    @pytest.mark.asyncio
    async def test_navigate_to_symbol(self, tmp_path: Path) -> None:
        py_file = tmp_path / "nav_target.py"
        py_file.write_text("class NavTarget: pass")
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        mgr._cross_file_nav.index_file(str(py_file))
        nav = await mgr.navigate_to_symbol("NavTarget")
        assert "definitions" in nav
        assert len(nav["definitions"]) >= 1

    @pytest.mark.asyncio
    async def test_compress_context(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        chunks = [_make_chunk("a.py", content="def foo(): pass")]
        compressed = await mgr.compress_context(chunks, target_ratio=1.0)
        assert len(compressed) >= 1

    @pytest.mark.asyncio
    async def test_cache_knowledge(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        await mgr.cache_knowledge("project_summary", {"files": 10})
        val = await mgr.get_cached_knowledge("project_summary")
        assert val == {"files": 10}

    @pytest.mark.asyncio
    async def test_cache_miss(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        val = await mgr.get_cached_knowledge("nonexistent")
        assert val is None

    @pytest.mark.asyncio
    async def test_session_state_save_restore(self, tmp_path: Path) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        ok = await mgr.save_session_state(
            "sess_1",
            context_data={"files": ["a.py"]},
            metadata={"user": "test"},
        )
        assert ok

        state = await mgr.restore_session_state("sess_1")
        assert state is not None
        assert state["context_data"]["files"] == ["a.py"]

    @pytest.mark.asyncio
    async def test_restore_nonexistent_session(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        state = await mgr.restore_session_state("nosession")
        assert state is None

    @pytest.mark.asyncio
    async def test_get_context_statistics(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        stats = await mgr.get_context_statistics()
        assert isinstance(stats, ContextStatistics)

    @pytest.mark.asyncio
    async def test_get_health_report(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        report = await mgr.get_health_report()
        assert isinstance(report, HealthReport)

    @pytest.mark.asyncio
    async def test_get_metrics_snapshot(self) -> None:
        mgr = ContextIntelligenceManager()
        await mgr.async_init()
        snap = await mgr.get_metrics_snapshot()
        assert isinstance(snap, MetricsSnapshot)

    @pytest.mark.asyncio
    async def test_event_emission(self) -> None:
        event_bus = MagicMock()
        event_bus.emit = AsyncMock()
        mgr = ContextIntelligenceManager(event_bus=event_bus)
        await mgr.async_init()
        await mgr._emit_event("test.event", {"data": 1})
        event_bus.emit.assert_any_call("test.event", {"data": 1})

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        mgr = ContextIntelligenceManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.build_rich_context("s1", "query")


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_context_intelligence_manager_conforms(self) -> None:
        assert isinstance(ContextIntelligenceManager(), ModuleInterface)

    def test_has_required_methods(self) -> None:
        mgr = ContextIntelligenceManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")


# =========================================================================
# Helper
# =========================================================================


class AsyncMock(MagicMock):
    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return super().__call__(*args, **kwargs)
