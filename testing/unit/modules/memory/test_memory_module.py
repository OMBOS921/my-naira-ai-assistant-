"""Comprehensive tests for the memory module.

Covers:
- SQLiteStore (CRUD, migrations, settings, health)
- VectorIndex (load/save, index/search, tokenize)
- SearchAPI (conversation, semantic, combined)
- MemoryManager (ModuleInterface lifecycle, adapters, public API)
- SQLiteMemoryAdapter (MemoryPort conformance)
- JSONVectorIndexAdapter (VectorIndexPort conformance)
- ModuleInterface protocol conformance
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.context.ports.memory_port import MemoryPort
from backend.modules.memory.adapters.json_vector_index_adapter import (
    JSONVectorIndexAdapter,
)
from backend.modules.memory.adapters.sqlite_memory_adapter import (
    SQLiteMemoryAdapter,
)
from backend.modules.memory.memory_models import SCHEMA_VERSION
from backend.modules.memory.memory_module import MemoryManager
from backend.modules.memory.ports.vector_index_port import VectorIndexPort
from backend.modules.memory.search import SearchAPI
from backend.modules.memory.sqlite_store import SQLiteStore
from backend.modules.memory.vector_index import VectorIndex
from backend.types import Message, ModuleInterface, SearchResult

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_memory.db"


@pytest.fixture
def index_path(tmp_path: Path) -> Path:
    return tmp_path / "test_index.json"


@pytest.fixture
def sqlite_store(db_path: Path) -> SQLiteStore:
    store = SQLiteStore(db_path)
    store.open()
    return store


@pytest.fixture
def vector_index(index_path: Path) -> VectorIndex:
    index = VectorIndex(index_path)
    index.load()
    return index


@pytest.fixture
def search_api(sqlite_store: SQLiteStore, vector_index: VectorIndex) -> SearchAPI:
    return SearchAPI(sqlite_store, vector_index)


@pytest.fixture
def sample_messages() -> list[Message]:
    return [
        Message(role="user", content="Hello, what can you do?"),
        Message(role="assistant", content="I can help with many tasks."),
        Message(role="user", content="Search the web for Python"),
        Message(role="assistant", content="Here are Python search results."),
    ]


# =========================================================================
# SQLiteStore
# =========================================================================


class TestSQLiteStoreOpenClose:
    def test_open_creates_file(self, db_path: Path) -> None:
        assert not db_path.exists()
        store = SQLiteStore(db_path)
        store.open()
        assert db_path.exists()
        store.close()

    def test_open_creates_tables(self, db_path: Path) -> None:
        store = SQLiteStore(db_path)
        store.open()
        tables = store._require_conn().execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [row["name"] for row in tables]
        assert "_schema_version" in names
        assert "conversations" in names
        assert "settings" in names
        assert "session_metadata" in names
        store.close()

    def test_double_open_is_safe(self, db_path: Path) -> None:
        store = SQLiteStore(db_path)
        store.open()
        store.open()
        assert store.is_open
        store.close()

    def test_close_then_reopen(self, db_path: Path) -> None:
        store = SQLiteStore(db_path)
        store.open()
        store.close()
        assert not store.is_open
        store.open()
        assert store.is_open
        store.close()

    def test_operations_before_open_raises(self, db_path: Path) -> None:
        store = SQLiteStore(db_path)
        with pytest.raises(RuntimeError):
            store.health_check()


class TestSQLiteStoreSchemaMigration:
    def test_schema_version(self, db_path: Path) -> None:
        store = SQLiteStore(db_path)
        store.open()
        row = store._require_conn().execute(
            "SELECT version FROM _schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row["version"] == SCHEMA_VERSION
        store.close()

    def test_migration_applies_schema(self, db_path: Path) -> None:
        store = SQLiteStore(db_path)
        store.open()
        conn = store._require_conn()
        assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0
        store.close()


class TestSQLiteStoreMessages:
    def test_store_and_retrieve_message(self, sqlite_store: SQLiteStore) -> None:
        msg = Message(role="user", content="Hello!")
        sqlite_store.store_message("sess_1", msg)
        history = sqlite_store.get_history("sess_1")
        assert len(history) == 1
        assert history[0].role == "user"
        assert history[0].content == "Hello!"

    def test_store_multiple_messages(self, sqlite_store: SQLiteStore) -> None:
        messages = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
            Message(role="user", content="Q2"),
        ]
        for msg in messages:
            sqlite_store.store_message("sess_1", msg)
        history = sqlite_store.get_history("sess_1")
        assert len(history) == 3
        assert [m.content for m in history] == ["Q1", "A1", "Q2"]

    def test_get_history_limit(self, sqlite_store: SQLiteStore) -> None:
        for i in range(10):
            sqlite_store.store_message("sess_1", Message(role="user", content=f"Q{i}"))
        history = sqlite_store.get_history("sess_1", limit=5)
        assert len(history) == 5

    def test_get_history_empty_session(self, sqlite_store: SQLiteStore) -> None:
        history = sqlite_store.get_history("nonexistent")
        assert history == []

    def test_store_message_with_tool_calls(self, sqlite_store: SQLiteStore) -> None:
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[{"id": "c1", "name": "search", "arguments": {"q": "test"}}],  # type: ignore[arg-type]
        )
        sqlite_store.store_message("sess_1", msg)
        history = sqlite_store.get_history("sess_1")
        assert len(history) == 1

    def test_store_message_with_tool_call_id(self, sqlite_store: SQLiteStore) -> None:
        msg = Message(role="tool", content="result", tool_call_id="c1")
        sqlite_store.store_message("sess_1", msg)
        history = sqlite_store.get_history("sess_1")
        assert history[0].tool_call_id == "c1"

    def test_store_message_updates_metadata(self, sqlite_store: SQLiteStore) -> None:
        msg1 = Message(role="user", content="H1")
        msg2 = Message(role="assistant", content="H2")
        sqlite_store.store_message("sess_1", msg1)
        sqlite_store.store_message("sess_1", msg2)
        conn = sqlite_store._require_conn()
        row = conn.execute(
            "SELECT message_count FROM session_metadata WHERE session_id = ?",
            ("sess_1",),
        ).fetchone()
        assert row["message_count"] == 2


class TestSQLiteStoreSessions:
    def test_get_all_sessions(self, sqlite_store: SQLiteStore) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Hi"))
        sqlite_store.store_message("s2", Message(role="user", content="Hey"))
        sessions = sqlite_store.get_all_sessions()
        assert set(sessions) == {"s1", "s2"}

    def test_get_all_sessions_empty(self, sqlite_store: SQLiteStore) -> None:
        assert sqlite_store.get_all_sessions() == []

    def test_archive_session(self, sqlite_store: SQLiteStore) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Hi"))
        sqlite_store.archive_session("s1")
        assert sqlite_store.get_history("s1") == []
        assert "s1" not in sqlite_store.get_all_sessions()

    def test_delete_session(self, sqlite_store: SQLiteStore) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Hi"))
        sqlite_store.delete_session("s1")
        assert sqlite_store.get_history("s1") == []
        assert sqlite_store.get_all_sessions() == []


class TestSQLiteStoreSettings:
    def test_store_and_get_setting(self, sqlite_store: SQLiteStore) -> None:
        sqlite_store.store_setting("theme", "dark")
        assert sqlite_store.get_setting("theme") == "dark"

    def test_store_setting_overwrites(self, sqlite_store: SQLiteStore) -> None:
        sqlite_store.store_setting("key", "value1")
        sqlite_store.store_setting("key", "value2")
        assert sqlite_store.get_setting("key") == "value2"

    def test_get_setting_nonexistent(self, sqlite_store: SQLiteStore) -> None:
        assert sqlite_store.get_setting("nonexistent") is None

    def test_store_and_get_complex_value(self, sqlite_store: SQLiteStore) -> None:
        value = {"nested": [1, 2, 3], "flag": True}
        sqlite_store.store_setting("complex", value)
        assert sqlite_store.get_setting("complex") == value

    def test_get_all_settings(self, sqlite_store: SQLiteStore) -> None:
        sqlite_store.store_setting("k1", "v1")
        sqlite_store.store_setting("k2", "v2")
        all_settings = sqlite_store.get_all_settings()
        assert all_settings == {"k1": "v1", "k2": "v2"}


class TestSQLiteStoreHealth:
    def test_health_check_healthy(self, sqlite_store: SQLiteStore) -> None:
        assert sqlite_store.health_check() is True

    def test_health_check_after_close(self, db_path: Path) -> None:
        store = SQLiteStore(db_path)
        store.open()
        store.close()
        with pytest.raises(RuntimeError):
            store.health_check()

    def test_vacuum(self, sqlite_store: SQLiteStore) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Test"))
        sqlite_store.vacuum()
        assert sqlite_store.health_check() is True


# =========================================================================
# VectorIndex
# =========================================================================


class TestVectorIndexLifecycle:
    def test_load_empty_index(self, index_path: Path) -> None:
        index = VectorIndex(index_path)
        index.load()
        assert index.document_count == 0
        assert index.is_loaded

    def test_save_and_reload(self, index_path: Path) -> None:
        index = VectorIndex(index_path)
        index.load()
        index.index(["python", "programming"], "doc_1")
        index.save()

        index2 = VectorIndex(index_path)
        index2.load()
        assert index2.document_count == 1

    def test_save_creates_file(self, index_path: Path) -> None:
        assert not index_path.exists()
        index = VectorIndex(index_path)
        index.load()
        index.index(["test"], "doc_1")
        index.save()
        assert index_path.exists()

    def test_load_from_existing_file(self, index_path: Path) -> None:
        index_path.write_text(
            '{"version": 1, "documents": {"doc_1": {"keywords": ["kw1"], "updated_at": 100.0}}}',
            encoding="utf-8",
        )
        index = VectorIndex(index_path)
        index.load()
        assert index.document_count == 1


class TestVectorIndexOperations:
    def test_index_keywords(self, vector_index: VectorIndex) -> None:
        vector_index.index(["python", "code", "programming"], "doc_1")
        assert vector_index.document_count == 1

    def test_index_adds_to_existing(self, vector_index: VectorIndex) -> None:
        vector_index.index(["python"], "doc_1")
        vector_index.index(["programming"], "doc_1")
        assert vector_index.document_count == 1

    def test_index_empty_keywords(self, vector_index: VectorIndex) -> None:
        vector_index.index([], "doc_1")
        assert vector_index.document_count == 1

    def test_remove_existing(self, vector_index: VectorIndex) -> None:
        vector_index.index(["kw"], "doc_1")
        result = vector_index.remove("doc_1")
        assert result is True
        assert vector_index.document_count == 0

    def test_remove_nonexistent(self, vector_index: VectorIndex) -> None:
        result = vector_index.remove("nonexistent")
        assert result is False

    def test_clear(self, vector_index: VectorIndex) -> None:
        vector_index.index(["kw1"], "doc_1")
        vector_index.index(["kw2"], "doc_2")
        vector_index.clear()
        assert vector_index.document_count == 0

    def test_document_count_multiple(self, vector_index: VectorIndex) -> None:
        vector_index.index(["kw1"], "doc_1")
        vector_index.index(["kw2"], "doc_2")
        vector_index.index(["kw3"], "doc_3")
        assert vector_index.document_count == 3

    def test_is_modified_after_index(self, vector_index: VectorIndex) -> None:
        assert vector_index.is_modified is False
        vector_index.index(["kw"], "doc_1")
        assert vector_index.is_modified is True

    def test_is_modified_after_clear(self, vector_index: VectorIndex) -> None:
        vector_index.index(["kw"], "doc_1")
        vector_index.save()
        assert vector_index.is_modified is False
        vector_index.clear()
        assert vector_index.is_modified is True

    def test_is_modified_after_save(self, vector_index: VectorIndex) -> None:
        vector_index.index(["kw"], "doc_1")
        vector_index.save()
        assert vector_index.is_modified is False


class TestVectorIndexSearch:
    @pytest.fixture(autouse=True)
    def _setup_index(self, vector_index: VectorIndex) -> None:
        vector_index.index(["python", "programming", "code"], "doc_python")
        vector_index.index(["java", "programming", "jvm"], "doc_java")
        vector_index.index(["cooking", "recipe", "food"], "doc_cooking")
        self._index = vector_index

    def test_search_finds_relevant(self) -> None:
        results = self._index.search("python code")
        assert len(results) >= 1
        assert results[0]["source_id"] == "doc_python"

    def test_search_returns_top_k(self) -> None:
        results = self._index.search("programming", top_k=1)
        assert len(results) == 1

    def test_search_empty_query(self) -> None:
        results = self._index.search("")
        assert results == []

    def test_search_no_match(self) -> None:
        results = self._index.search("xyznonexistent")
        assert results == []

    def test_search_empty_index(self, index_path: Path) -> None:
        index = VectorIndex(index_path)
        index.load()
        results = index.search("anything")
        assert results == []

    def test_search_scoring(self) -> None:
        results = self._index.search("programming")
        assert len(results) >= 2
        assert results[0]["score"] >= results[1]["score"]

    def test_search_result_format(self) -> None:
        results = self._index.search("python")
        assert len(results) >= 1
        r = results[0]
        assert "source_id" in r
        assert "score" in r
        assert "matched_keywords" in r
        assert isinstance(r["score"], float)
        assert isinstance(r["matched_keywords"], list)


class TestVectorIndexTokenize:
    def test_tokenize_basic(self) -> None:
        tokens = VectorIndex._tokenize("Hello World Python")
        assert tokens == ["hello", "world", "python"]

    def test_tokenize_lowercase(self) -> None:
        tokens = VectorIndex._tokenize("HELLO")
        assert tokens == ["hello"]

    def test_tokenize_removes_short_tokens(self) -> None:
        tokens = VectorIndex._tokenize("a an foo")
        assert tokens == ["an", "foo"]
        assert "a" not in tokens

    def test_tokenize_special_chars(self) -> None:
        tokens = VectorIndex._tokenize("hello-world! python3")
        assert "hello" in tokens
        assert "world" in tokens
        assert "python3" in tokens

    def test_tokenize_empty_string(self) -> None:
        tokens = VectorIndex._tokenize("")
        assert tokens == []


# =========================================================================
# SearchAPI
# =========================================================================


class TestSearchAPIConversations:
    def test_search_conversations_finds_messages(
        self, search_api: SearchAPI, sqlite_store: SQLiteStore
    ) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Python programming"))
        sqlite_store.store_message("s1", Message(role="assistant", content="I love Python"))
        results = search_api.search_conversations("Python")
        assert len(results) >= 1

    def test_search_conversations_by_session(
        self, search_api: SearchAPI, sqlite_store: SQLiteStore
    ) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Python"))
        sqlite_store.store_message("s2", Message(role="user", content="Python"))
        results = search_api.search_conversations("Python", session_id="s1")
        assert len(results) >= 1
        for r in results:
            assert r.source_id == "s1"

    def test_search_conversations_no_match(
        self, search_api: SearchAPI
    ) -> None:
        results = search_api.search_conversations("nonexistent")
        assert results == []

    def test_search_conversations_result_format(
        self, search_api: SearchAPI, sqlite_store: SQLiteStore
    ) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Hello world"))
        results = search_api.search_conversations("Hello")
        assert len(results) >= 1
        r = results[0]
        assert isinstance(r, SearchResult)
        assert r.source_id == "s1"
        assert "Hello" in r.content
        assert r.score == 1.0
        assert r.metadata["match_type"] == "substring"


class TestSearchAPISemantic:
    def test_search_semantic_returns_results(
        self, search_api: SearchAPI, vector_index: VectorIndex
    ) -> None:
        vector_index.index(["python", "programming"], "s1")
        results = search_api.search_semantic("python")
        assert len(results) >= 1

    def test_search_semantic_empty_index(
        self, search_api: SearchAPI
    ) -> None:
        results = search_api.search_semantic("anything")
        assert results == []

    def test_search_semantic_scored(
        self, search_api: SearchAPI, vector_index: VectorIndex
    ) -> None:
        vector_index.index(["python"], "s1")
        vector_index.index(["java"], "s2")
        results = search_api.search_semantic("python")
        assert len(results) >= 1
        assert results[0].source_id == "s1"
        assert results[0].score > 0


class TestSearchAPICombined:
    def test_combined_search_deduplicates(
        self, search_api: SearchAPI, sqlite_store: SQLiteStore, vector_index: VectorIndex
    ) -> None:
        sqlite_store.store_message("s1", Message(role="user", content="Python programming"))
        vector_index.index(["python", "programming"], "s1")
        results = search_api.combined_search("python")
        assert len(results) >= 1

    def test_combined_search_respects_top_k(
        self, search_api: SearchAPI, sqlite_store: SQLiteStore, vector_index: VectorIndex
    ) -> None:
        for i in range(5):
            sid = f"s{i}"
            sqlite_store.store_message(sid, Message(role="user", content=f"Python topic {i}"))
            vector_index.index(["python"], sid)
        results = search_api.combined_search("python", top_k=3)
        assert len(results) <= 3


# =========================================================================
# MemoryManager — ModuleInterface lifecycle
# =========================================================================


class TestMemoryManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = MemoryManager()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_async_init(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        idx = tmp_path / "test.json"
        mgr = MemoryManager(db_path=db, index_path=idx)
        await mgr.async_init()
        assert mgr.degraded is False
        assert db.exists()
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_async_init_creates_db_file(self, tmp_path: Path) -> None:
        db = tmp_path / "new.db"
        idx = tmp_path / "new.json"
        mgr = MemoryManager(db_path=db, index_path=idx)
        await mgr.async_init()
        assert db.exists()
        assert db.stat().st_size > 0
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_shutdown_closes_store(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        idx = tmp_path / "test.json"
        mgr = MemoryManager(db_path=db, index_path=idx)
        await mgr.async_init()
        await mgr.async_shutdown()
        assert mgr.degraded is False
        assert mgr._store.is_open is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        idx = tmp_path / "test.json"
        mgr = MemoryManager(db_path=db, index_path=idx)
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()
        assert mgr._store.is_open is False

    @pytest.mark.asyncio
    async def test_degrade_closes_store_and_sets_flag(self, tmp_path: Path) -> None:
        db = tmp_path / "test.db"
        idx = tmp_path / "test.json"
        mgr = MemoryManager(db_path=db, index_path=idx)
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded is True
        assert mgr._store.is_open is False

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = MemoryManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        import logging
        logger = logging.getLogger("test.memory")
        mgr = MemoryManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_init_failure_sets_degraded(self, tmp_path: Path) -> None:
        db = tmp_path / "nope" / "test.db"
        idx = tmp_path / "test.json"
        mgr = MemoryManager(db_path=db, index_path=idx)
        await mgr.async_init()
        assert mgr.degraded is True


class TestMemoryManagerAPI:
    @pytest.mark.asyncio
    async def test_store_and_get_message(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        await mgr.store_message("s1", Message(role="user", content="Hello"))
        history = await mgr.get_history("s1")
        assert len(history) == 1
        assert history[0].content == "Hello"
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_store_and_get_setting(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        await mgr.store_setting("theme", "dark")
        assert await mgr.get_setting("theme") == "dark"
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_get_all_sessions(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        await mgr.store_message("s1", Message(role="user", content="Hi"))
        await mgr.store_message("s2", Message(role="user", content="Hey"))
        sessions = await mgr.get_all_sessions()
        assert set(sessions) == {"s1", "s2"}
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_archive_session(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        await mgr.store_message("s1", Message(role="user", content="Hi"))
        await mgr.archive_session("s1")
        history = await mgr.get_history("s1")
        assert history == []
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_delete_session(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        await mgr.store_message("s1", Message(role="user", content="Hi"))
        await mgr.delete_session("s1")
        history = await mgr.get_history("s1")
        assert history == []
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_index_and_save_keywords(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        await mgr.index_keywords(["python", "code"], "s1")
        await mgr.save_index()
        assert mgr._index.document_count == 1
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_vacuum(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        await mgr.store_message("s1", Message(role="user", content="Hello"))
        await mgr.vacuum()
        assert mgr.degraded is False
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_search_property(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        assert isinstance(mgr.search, SearchAPI)
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_degraded_raises_on_operation(self) -> None:
        mgr = MemoryManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.get_history("s1")

    @pytest.mark.asyncio
    async def test_degraded_raises_on_adapter_access(self) -> None:
        mgr = MemoryManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            _ = mgr.memory_adapter

    @pytest.mark.asyncio
    async def test_degraded_raises_on_search_access(self) -> None:
        mgr = MemoryManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            _ = mgr.search


class TestMemoryManagerAdapters:
    @pytest.mark.asyncio
    async def test_memory_adapter_is_sqlite_adapter(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        adapter = mgr.memory_adapter
        assert isinstance(adapter, SQLiteMemoryAdapter)
        mgr._store.close()

    @pytest.mark.asyncio
    async def test_vector_index_adapter(self, tmp_path: Path) -> None:
        mgr = MemoryManager(db_path=tmp_path / "test.db", index_path=tmp_path / "test.json")
        await mgr.async_init()
        adapter = mgr.vector_index_adapter
        assert isinstance(adapter, JSONVectorIndexAdapter)
        mgr._store.close()


# =========================================================================
# SQLiteMemoryAdapter — MemoryPort conformance
# =========================================================================


class TestSQLiteMemoryAdapterConformance:
    @pytest.mark.asyncio
    async def test_implements_memory_port(self, sqlite_store: SQLiteStore) -> None:
        adapter = SQLiteMemoryAdapter(sqlite_store)
        assert isinstance(adapter, MemoryPort)

    @pytest.mark.asyncio
    async def test_store_and_get_message(self, sqlite_store: SQLiteStore) -> None:
        adapter = SQLiteMemoryAdapter(sqlite_store)
        msg = Message(role="user", content="Hello adapter")
        await adapter.store_message("s1", msg)
        history = await adapter.get_history("s1")
        assert len(history) == 1
        assert history[0].content == "Hello adapter"

    @pytest.mark.asyncio
    async def test_store_and_get_setting(self, sqlite_store: SQLiteStore) -> None:
        adapter = SQLiteMemoryAdapter(sqlite_store)
        await adapter.store_setting("adapter_key", "adapter_val")
        assert await adapter.get_setting("adapter_key") == "adapter_val"

    @pytest.mark.asyncio
    async def test_health_check(self, sqlite_store: SQLiteStore) -> None:
        adapter = SQLiteMemoryAdapter(sqlite_store)
        assert await adapter.health_check() is True


# =========================================================================
# JSONVectorIndexAdapter — VectorIndexPort conformance
# =========================================================================


class TestJSONVectorIndexAdapterConformance:
    @pytest.mark.asyncio
    async def test_implements_vector_index_port(
        self, vector_index: VectorIndex
    ) -> None:
        adapter = JSONVectorIndexAdapter(vector_index)
        assert isinstance(adapter, VectorIndexPort)

    @pytest.mark.asyncio
    async def test_index_and_search(self, vector_index: VectorIndex) -> None:
        adapter = JSONVectorIndexAdapter(vector_index)
        await adapter.index(["python", "code"], "doc_1")
        results = await adapter.search("python")
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)

    @pytest.mark.asyncio
    async def test_search_result_format(self, vector_index: VectorIndex) -> None:
        adapter = JSONVectorIndexAdapter(vector_index)
        await adapter.index(["programming"], "doc_1")
        results = await adapter.search("programming")
        assert len(results) >= 1
        r = results[0]
        assert isinstance(r.source_id, str)
        assert isinstance(r.score, float)

    @pytest.mark.asyncio
    async def test_search_empty(self, vector_index: VectorIndex) -> None:
        adapter = JSONVectorIndexAdapter(vector_index)
        results = await adapter.search("nonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_top_k(self, vector_index: VectorIndex) -> None:
        adapter = JSONVectorIndexAdapter(vector_index)
        for i in range(5):
            await adapter.index([f"topic_{i}"], f"doc_{i}")
        results = await adapter.search("topic", top_k=2)
        assert len(results) <= 2


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_memory_manager_conforms_to_protocol(self) -> None:
        assert isinstance(MemoryManager(), ModuleInterface)

    def test_memory_manager_has_required_methods(self) -> None:
        mgr = MemoryManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
