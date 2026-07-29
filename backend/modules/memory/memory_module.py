"""
MemoryManager — the single public class for the memory module.

21_System_Contracts.md §16 — Memory Contracts (Conversation Store + Semantic Index).
21_System_Contracts.md §4.2 — ModuleInterface protocol.
18_Boot_Sequence.md §2 Steps 7, 9, 10 — Boot lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
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
from backend.modules.tools._definition import ToolDefinition
from backend.types import Message, ToolResult

_LOG = logging.getLogger("naira.memory")

DEFAULT_DB_FILENAME = "naira_memory.db"
DEFAULT_INDEX_FILENAME = "naira_vector_index.json"

REMEMBER_FACT_TOOL_DEF = ToolDefinition(
    name="remember_fact",
    description=(
        "Save an important user fact, preference, or project detail into long-term memory."
    ),
    parameters={
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Category, key, or topic of the fact (e.g., 'user_preference', 'project_name', 'favorite_color').",
            },
            "fact": {
                "type": "string",
                "description": "The exact fact, detail, or preference to remember.",
            },
        },
        "required": ["topic", "fact"],
    },
    category="memory",
)

SEARCH_MEMORY_TOOL_DEF = ToolDefinition(
    name="search_memory",
    description=(
        "Search the long-term memory/vector database for previously discussed facts, code, or context."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term or natural language query to look up in long-term memory.",
            },
            "search_type": {
                "type": "string",
                "enum": ["all", "conversations", "timeline", "semantic", "profile"],
                "description": "Optional search filter type (defaults to 'all').",
                "default": "all",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of search results to return (default 5).",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    category="memory",
)


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
    tool_manager : object | None
        ToolManager instance for registering memory tools.
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        db_path: Path | str | None = None,
        index_path: Path | str | None = None,
        event_bus: object | None = None,
        tool_manager: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._tool_manager = tool_manager
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

        self._memory_adapter = SQLiteMemoryAdapter(
            self._store,
            timeline_engine=self._timeline_engine,
            user_profile_engine=self._user_profile,
        )
        self._index_adapter = JSONVectorIndexAdapter(self._index)
        self._setup_event_subscriptions()

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

        if self._tool_manager is not None:
            self.register_tools(self._tool_manager)

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
    # Tool extraction and registration API
    # ------------------------------------------------------------------

    def register_tools(self, tool_manager: object | None = None) -> None:
        """Register the ``remember_fact`` and ``search_memory`` tools with the ToolManager."""
        if tool_manager is not None:
            self._tool_manager = tool_manager
        if self._tool_manager is None:
            return
        has_fn = getattr(self._tool_manager, "has_tool", None)
        reg_fn = getattr(self._tool_manager, "register_tool", None)
        if not callable(reg_fn):
            return

        tools_to_register = [
            ("remember_fact", REMEMBER_FACT_TOOL_DEF, self.remember_fact_tool_handler),
            ("search_memory", SEARCH_MEMORY_TOOL_DEF, self.search_memory_tool_handler),
        ]

        for name, defn, handler in tools_to_register:
            if callable(has_fn) and has_fn(name):
                continue
            try:
                reg_fn(defn, handler)
                self._logger.info("Registered %s tool with ToolManager", name)
            except Exception as exc:
                self._logger.warning("Failed to register %s tool: %s", name, exc)

    async def remember_fact_tool_handler(
        self,
        topic: str,
        fact: str,
    ) -> ToolResult:
        """Handler for the remember_fact LLM tool.

        Saves an important user fact, preference, or detail into long-term memory engines.
        """
        if self._degraded:
            return ToolResult(
                status="success",
                output="No memory saved (MemoryManager is degraded).",
            )

        try:
            # 1. User Profile Engine
            await self.set_user_profile(
                key=topic,
                value=fact,
                data_type="string",
                source="stated",
                confidence=1.0,
            )

            # 2. Relationship Memory
            await asyncio.to_thread(
                self._relationship_memory.upsert,
                entity_name=topic,
                entity_type="fact",
                relationship_type="user_preference",
                description=fact,
                importance=8,
            )

            # 3. Vector Index keyword indexing
            await self.index_keywords([topic, fact], source_id=f"user_fact:{topic}")

            # 4. Timeline Engine event
            await self.record_event(
                event_type="user_fact_remembered",
                title=f"Remembered fact: {topic}",
                description=fact,
                importance=8,
            )

            return ToolResult(
                status="success",
                output=f"Successfully remembered fact under topic '{topic}': {fact}",
            )
        except Exception as exc:
            self._logger.error("remember_fact_tool_handler failed: %s", exc)
            return ToolResult(
                status="success",
                output=f"No memory saved due to error: {exc}",
            )

    async def search_memory_tool_handler(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 5,
    ) -> ToolResult:
        """Handler for the search_memory LLM tool.

        Queries past conversation history, vector index, timeline events, and profile entries.
        """
        if self._degraded:
            return ToolResult(
                status="success",
                output="No memory found.",
            )

        try:
            results_text: list[str] = []

            # 1. Timeline Events Search
            if search_type in ("all", "timeline"):
                try:
                    tl_events = await asyncio.to_thread(
                        self._timeline_engine.search, query, limit
                    )
                    if tl_events:
                        results_text.append("=== Timeline Events ===")
                        for ev in tl_events:
                            ts = ev.get("happened_at", 0)
                            dt = (
                                time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
                                if ts
                                else ""
                            )
                            results_text.append(
                                f"• [{dt}] [{ev.get('event_type')}] {ev.get('title')}: {ev.get('description', '')}"
                            )
                except Exception as exc:
                    self._logger.debug("Timeline search failed: %s", exc)

            # 2. User Profile Search
            if search_type in ("all", "profile"):
                try:
                    profile_all = await asyncio.to_thread(self._user_profile.get_all)
                    q_low = query.lower()
                    words = [w for w in re.findall(r"\w+", q_low) if len(w) > 2]
                    matching_prof = {}
                    for k, v in profile_all.items():
                        k_low = k.lower()
                        v_low = str(v).lower()
                        if (
                            q_low in k_low
                            or q_low in v_low
                            or k_low in q_low
                            or any(w in k_low or w in v_low for w in words)
                        ):
                            matching_prof[k] = v
                    if matching_prof:
                        results_text.append("=== User Profile Entries ===")
                        for k, v in matching_prof.items():
                            results_text.append(f"• {k}: {v}")
                except Exception as exc:
                    self._logger.debug("User profile search failed: %s", exc)

            # 3. Conversation & Semantic Search
            if search_type in ("all", "conversations", "semantic"):
                try:
                    if search_type == "conversations":
                        conv_results = await asyncio.to_thread(
                            self._search.search_conversations, query, None, limit
                        )
                    elif search_type == "semantic":
                        conv_results = await asyncio.to_thread(
                            self._search.search_semantic, query, limit
                        )
                    else:
                        conv_results = await asyncio.to_thread(
                            self._search.combined_search, query, limit
                        )

                    if conv_results:
                        results_text.append("=== Past Conversations & Index ===")
                        for r in conv_results:
                            results_text.append(
                                f"• [Session: {r.source_id}] (Score: {r.score:.2f}) {r.content}"
                            )
                except Exception as exc:
                    self._logger.debug("Conversation search failed: %s", exc)

            if not results_text:
                return ToolResult(
                    status="success",
                    output=f"No memory found matching query '{query}'.",
                )

            final_output = "\n".join(results_text)
            return ToolResult(status="success", output=final_output)

        except Exception as exc:
            self._logger.error("search_memory_tool_handler failed: %s", exc)
            return ToolResult(
                status="success",
                output="No memory found.",
            )

    async def get_dynamic_historical_context(
        self, session_id: str = "default", limit_events: int = 3
    ) -> str:
        """Retrieve dynamic historical context string (user profile + recent timeline events)."""
        self._ensure_not_degraded()
        return await self._memory_adapter.get_dynamic_context_summary(session_id, limit_events)

    async def record_tool_call_success(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        session_id: str | None = None,
    ) -> int | None:
        """Record successful tool execution in the timeline engine."""
        self._ensure_not_degraded()
        res_str = str(result)
        if len(res_str) > 300:
            res_str = res_str[:300] + "..."
        return await self.record_event(
            event_type="tool_call_success",
            title=f"Executed tool: {tool_name}",
            description=f"Args: {args} | Result: {res_str}",
            session_id=session_id,
            importance=5,
            metadata={"tool_name": tool_name, "args": args},
        )

    async def record_conversation_summary(
        self,
        summary: str,
        session_id: str | None = None,
        importance: int = 7,
    ) -> int | None:
        """Record significant conversation summary in the timeline engine."""
        self._ensure_not_degraded()
        return await self.record_event(
            event_type="conversation_summary",
            title="Conversation Summary",
            description=summary,
            session_id=session_id,
            importance=importance,
        )

    # ------------------------------------------------------------------
    # EventBus Integration & Background Memory Harvester ("Subconscious")
    # ------------------------------------------------------------------

    def set_event_bus(self, event_bus: object) -> None:
        """Attach EventBus post-construction and wire subscribers."""
        self._event_bus = event_bus
        self._setup_event_subscriptions()

    def _setup_event_subscriptions(self) -> None:
        """Subscribe background MemoryHarvester to EventBus conversation events."""
        if self._event_bus is None:
            return

        sub_fn = getattr(self._event_bus, "subscribe", None)
        if not callable(sub_fn):
            return

        chat_events = [
            "conversation.message_received",
            "conversation.message_sent",
            "conversation.*",
            "runtime.request_start",
            "interaction.completed",
        ]

        for etype in chat_events:
            try:
                sub_fn(etype, self._on_chat_event)
                self._logger.info("Subscribed MemoryHarvester to event: %s", etype)
            except Exception as exc:
                self._logger.warning("Failed to subscribe MemoryHarvester to %s: %s", etype, exc)

    async def _on_chat_event(self, event: Any) -> None:
        """EventBus callback — extracts user message and spawns non-blocking harvester task."""
        try:
            data = getattr(event, "data", {}) if hasattr(event, "data") else (event if isinstance(event, dict) else {})
            text = (
                data.get("text")
                or data.get("message")
                or data.get("user_input")
                or data.get("content")
            )
            if not text or not isinstance(text, str):
                return

            # Non-blocking async background task via asyncio.create_task
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._process_harvest_background(text))
            except RuntimeError:
                try:
                    await self._process_harvest_background(text)
                except Exception:
                    pass
        except Exception as exc:
            self._logger.debug("MemoryHarvester listener error: %s", exc)

    async def _process_harvest_background(self, text: str) -> None:
        """Evaluate message in the background and silently store detected facts."""
        try:
            facts = self._extract_facts_heuristically(text)
            for topic, fact in facts:
                await self.remember_fact_tool_handler(topic=topic, fact=fact)
        except Exception as exc:
            self._logger.debug("Background memory harvesting failed: %s", exc)

    def _extract_facts_heuristically(self, text: str) -> list[tuple[str, str]]:
        """Extract facts, preferences, or system constraints from user message text."""
        facts: list[tuple[str, str]] = []
        clean = text.strip()

        # Rule 1: Hardware / System constraints ("I use a...", "I have a...", "my laptop is...")
        m_hw = re.search(
            r"\b(i use|i have|my (laptop|pc|desktop|machine|computer|system) is)\b\s+([^.?!,;]+)",
            clean,
            re.IGNORECASE,
        )
        if m_hw:
            facts.append(("system_constraint", clean))

        # Rule 2: Preferences ("I prefer...", "I like...", "my favorite...")
        m_pref = re.search(
            r"\b(i prefer|i like|my preference|my favorite)\b\s+([^.?!,;]+)",
            clean,
            re.IGNORECASE,
        )
        if m_pref:
            facts.append(("user_preference", clean))

        # Rule 3: Personal info ("My name is...", "I am a...", "I work as...")
        m_info = re.search(
            r"\b(my name is|i am a|i work as)\b\s+([^.?!,;]+)",
            clean,
            re.IGNORECASE,
        )
        if m_info:
            facts.append(("user_info", clean))

        # Rule 4: Stated facts / directives ("Remember that...", "Note that...", "Keep in mind that...")
        m_rem = re.search(
            r"\b(remember that|note that|keep in mind that)\b\s+([^.?!,;]+)",
            clean,
            re.IGNORECASE,
        )
        if m_rem:
            facts.append(("stated_fact", m_rem.group(2).strip()))

        return facts

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
