"""
MemoryManager — the single public class for the memory module.

21_System_Contracts.md §16 — Memory Contracts (Conversation Store + Semantic Index).
21_System_Contracts.md §4.2 — ModuleInterface protocol.
18_Boot_Sequence.md §2 Steps 7, 9, 10 — Boot lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from backend.modules.memory.adapters.json_vector_index_adapter import (
    JSONVectorIndexAdapter,
)
from backend.modules.memory.adapters.sqlite_memory_adapter import (
    SQLiteMemoryAdapter,
)
from backend.modules.memory.engines.context_engine_v2 import ContextEngineV2
from backend.modules.memory.engines.knowledge_graph import KnowledgeGraph
from backend.modules.memory.engines.memory_intelligence import MemoryIntelligence
from backend.modules.memory.engines.relationship_memory import RelationshipMemory
from backend.modules.memory.engines.timeline_engine import TimelineEngine
from backend.modules.memory.engines.user_profile_engine import UserProfileEngine
from backend.modules.memory.search import SearchAPI
from backend.modules.memory.sqlite_store import SQLiteStore
from backend.modules.memory.vector_index import VectorIndex
from backend.types import Message

_LOG = logging.getLogger("naira.memory")

DEFAULT_DB_FILENAME = "naira_memory.db"
DEFAULT_INDEX_FILENAME = "naira_vector_index.json"


class MemoryManager:
    """Central memory manager — owns SQLite store, vector index, and memory engines.

    Manages persistent conversation history and a lightweight semantic
    keyword index. Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger. If ``None``, a default logger is used.
    db_path : Path | str | None
        Path to the SQLite database file. Defaults to
        ``memory/DEFAULT_DB_FILENAME`` relative to project root.
    index_path : Path | str | None
        Path to the JSON vector index file. Defaults to
        ``memory/DEFAULT_INDEX_FILENAME`` relative to project root.
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        db_path: Path | str | None = None,
        index_path: Path | str | None = None,
        event_bus: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._degraded: bool = False

        resolved_db = (
            Path(db_path) if db_path else Path.cwd() / DEFAULT_DB_FILENAME
        )
        resolved_index = (
            Path(index_path) if index_path else Path.cwd() / DEFAULT_INDEX_FILENAME
        )

        self._store = SQLiteStore(resolved_db)
        self._index = VectorIndex(resolved_index)
        self._search = SearchAPI(self._store, self._index)
        self._memory_adapter = SQLiteMemoryAdapter(self._store)
        self._index_adapter = JSONVectorIndexAdapter(self._index)

        # Instantiate persistent memory engines using central SQLiteStore
        self._relationship_memory = RelationshipMemory(self._store, self._logger)
        self._timeline_engine = TimelineEngine(self._store, self._logger)
        self._knowledge_graph = KnowledgeGraph(self._store, self._logger)
        self._user_profile = UserProfileEngine(self._store, self._logger)
        self._memory_intelligence = MemoryIntelligence(self._store, self._logger)
        self._context_engine = ContextEngineV2(
            self._store,
            self._relationship_memory,
            self._timeline_engine,
            self._knowledge_graph,
            self._user_profile,
            self._memory_intelligence,
            self._logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Open the database connection, run migrations, load the index.

        Called once during boot (Step 10).
        """
        try:
            await asyncio.to_thread(self._store.open)
            self._logger.info(
                "SQLite store opened — path=%s", self._store._db_path
            )
        except Exception as exc:
            self._logger.error("Failed to open SQLite store: %s", exc)
            self._degraded = True
            return

        try:
            await asyncio.to_thread(self._index.load)
            self._logger.info(
                "Vector index loaded — path=%s", self._index._index_path
            )
        except Exception as exc:
            self._logger.warning("Failed to load vector index: %s", exc)

        self._logger.info("Memory manager initialised")

    async def async_shutdown(self) -> None:
        """Save the index, close the database connection."""
        try:
            if self._index.is_modified:
                await asyncio.to_thread(self._index.save)
                self._logger.info("Vector index saved")
        except Exception as exc:
            self._logger.warning("Failed to save vector index: %s", exc)

        try:
            await asyncio.to_thread(self._store.close)
            self._logger.info("SQLite store closed")
        except Exception as exc:
            self._logger.warning("Failed to close SQLite store: %s", exc)

        self._degraded = False

    def degrade(self) -> None:
        """Release database resources and mark as degraded."""
        self._store.close()
        self._degraded = True
        self._logger.warning("Memory manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public accessors for adapters (used at boot wiring)
    # ------------------------------------------------------------------

    @property
    def memory_adapter(self) -> SQLiteMemoryAdapter:
        """Return the ``SQLiteMemoryAdapter`` for Port injection.

        Wired to ``context.MemoryPort`` at boot (Step 9).
        """
        self._ensure_not_degraded()
        return self._memory_adapter

    @property
    def vector_index_adapter(self) -> JSONVectorIndexAdapter:
        """Return the ``JSONVectorIndexAdapter`` for Port injection.

        Wired to ``memory.VectorIndexPort`` at boot (Step 9).
        """
        self._ensure_not_degraded()
        return self._index_adapter

    # ------------------------------------------------------------------
    # Public accessors for persistent memory engines
    # ------------------------------------------------------------------

    @property
    def relationship_memory(self) -> RelationshipMemory:
        """Return the RelationshipMemory engine instance."""
        self._ensure_not_degraded()
        return self._relationship_memory

    @property
    def timeline_engine(self) -> TimelineEngine:
        """Return the TimelineEngine instance."""
        self._ensure_not_degraded()
        return self._timeline_engine

    @property
    def knowledge_graph(self) -> KnowledgeGraph:
        """Return the KnowledgeGraph engine instance."""
        self._ensure_not_degraded()
        return self._knowledge_graph

    @property
    def user_profile(self) -> UserProfileEngine:
        """Return the UserProfileEngine instance."""
        self._ensure_not_degraded()
        return self._user_profile

    @property
    def memory_intelligence(self) -> MemoryIntelligence:
        """Return the MemoryIntelligence engine instance."""
        self._ensure_not_degraded()
        return self._memory_intelligence

    @property
    def context_engine(self) -> ContextEngineV2:
        """Return the ContextEngineV2 coordinator instance."""
        self._ensure_not_degraded()
        return self._context_engine

    # ------------------------------------------------------------------
    # Async helper wrappers for memory operations
    # ------------------------------------------------------------------

    async def get_context_block(self, session_id: str) -> str:
        """Assemble memory context string asynchronously."""
        self._ensure_not_degraded()
        return await asyncio.to_thread(self._context_engine.assemble_context, session_id)

    async def record_message_memory(self, message: str, role: str, session_id: str) -> None:
        """Analyze and record message signals asynchronously."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._context_engine.auto_record_from_message, message, role, session_id)

    async def record_event(
        self,
        event_type: str,
        title: str,
        description: str | None = None,
        session_id: str | None = None,
        happened_at: float | None = None,
        tags: list[str] | str | None = None,
        importance: int = 5,
        metadata: dict[str, Any] | str | None = None,
    ) -> int | None:
        """Record a timeline event asynchronously."""
        self._ensure_not_degraded()
        return await asyncio.to_thread(
            self._timeline_engine.record,
            event_type,
            title,
            description,
            session_id,
            happened_at,
            tags,
            importance,
            metadata,
        )

    async def upsert_knowledge(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
        source: str = "stated",
    ) -> bool:
        """Upsert a knowledge graph triple asynchronously."""
        self._ensure_not_degraded()
        return await asyncio.to_thread(
            self._knowledge_graph.upsert, subject, predicate, object_, confidence, source
        )

    async def set_user_profile(
        self,
        key: str,
        value: object,
        data_type: str = "string",
        source: str = "stated",
        confidence: float = 1.0,
    ) -> bool:
        """Set a user profile item asynchronously."""
        self._ensure_not_degraded()
        return await asyncio.to_thread(
            self._user_profile.set, key, value, data_type, source, confidence
        )

    async def bootstrap_user_profile(self, config_path: str = "config/user.json") -> bool:
        """Bootstrap user profile from config file asynchronously."""
        self._ensure_not_degraded()
        return await asyncio.to_thread(self._user_profile.bootstrap_from_config, config_path)

    # ------------------------------------------------------------------
    # Session management API
    # ------------------------------------------------------------------

    async def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[Message]:
        """Retrieve conversation history for a session.

        Wraps the synchronous store in an async call.
        """
        self._ensure_not_degraded()
        return await asyncio.to_thread(self._store.get_history, session_id, limit)

    async def store_message(self, session_id: str, message: Message) -> None:
        """Persist a single message."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._store.store_message, session_id, message)

    async def archive_session(self, session_id: str) -> None:
        """Archive a session (data is preserved, not deleted)."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._store.archive_session, session_id)

    async def delete_session(self, session_id: str) -> None:
        """Permanently delete a session."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._store.delete_session, session_id)

    async def get_all_sessions(self) -> list[str]:
        """Return all active session IDs."""
        self._ensure_not_degraded()
        return await asyncio.to_thread(self._store.get_all_sessions)

    # ------------------------------------------------------------------
    # Settings API
    # ------------------------------------------------------------------

    async def store_setting(self, key: str, value: object) -> None:
        """Persist a key-value setting."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._store.store_setting, key, value)

    async def get_setting(self, key: str) -> object | None:
        """Retrieve a previously stored setting."""
        self._ensure_not_degraded()
        return await asyncio.to_thread(self._store.get_setting, key)

    # ------------------------------------------------------------------
    # Search API
    # ------------------------------------------------------------------

    @property
    def search(self) -> SearchAPI:
        """Access the combined search API."""
        self._ensure_not_degraded()
        return self._search

    # ------------------------------------------------------------------
    # Vector index API
    # ------------------------------------------------------------------

    async def index_keywords(
        self, keywords: list[str], source_id: str
    ) -> None:
        """Index keywords for a session or document."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._index.index, keywords, source_id)

    async def save_index(self) -> None:
        """Persist the vector index to disk."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._index.save)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def vacuum(self) -> None:
        """Reclaim SQLite storage space."""
        self._ensure_not_degraded()
        await asyncio.to_thread(self._store.vacuum)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            from backend.exceptions import ModuleDegradedError

            raise ModuleDegradedError(
                "MemoryManager is degraded",
                context={"module": "memory"},
            )
