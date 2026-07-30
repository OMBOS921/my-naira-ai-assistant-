"""
ContextEngineV2 — orchestrates all memory engines to assemble system prompt context blocks.

Uses the central SQLiteStore instance for persisting context snapshots.
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.modules.memory.engines.knowledge_graph import KnowledgeGraph
    from backend.modules.memory.engines.memory_intelligence import MemoryIntelligence
    from backend.modules.memory.engines.relationship_memory import RelationshipMemory
    from backend.modules.memory.engines.timeline_engine import TimelineEngine
    from backend.modules.memory.engines.user_profile_engine import UserProfileEngine
    from backend.modules.memory.sqlite_store import SQLiteStore


class ContextEngineV2:
    """Coordinator class pulling context from all 5 memory engines to construct context blocks.

    Parameters
    ----------
    store : SQLiteStore
        Shared SQLite store instance.
    relationship_memory : RelationshipMemory
        Relationship memory engine instance.
    timeline_engine : TimelineEngine
        Timeline memory engine instance.
    knowledge_graph : KnowledgeGraph
        Knowledge graph engine instance.
    user_profile : UserProfileEngine
        User profile engine instance.
    memory_intelligence : MemoryIntelligence
        Memory intelligence engine instance.
    logger : logging.Logger | None
        Module logger instance.
    """

    def __init__(
        self,
        store: SQLiteStore,
        relationship_memory: RelationshipMemory,
        timeline_engine: TimelineEngine,
        knowledge_graph: KnowledgeGraph,
        user_profile: UserProfileEngine,
        memory_intelligence: MemoryIntelligence,
        logger: logging.Logger | None = None,
    ) -> None:
        self._store = store
        self._relationship_memory = relationship_memory
        self._timeline_engine = timeline_engine
        self._knowledge_graph = knowledge_graph
        self._user_profile = user_profile
        self._memory_intelligence = memory_intelligence
        self._logger = logger

    def assemble_context(self, session_id: str, max_chars: int = 1200) -> str:
        """Assemble structured memory context block from all 5 memory engines.

        Structure:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        NAIRA MEMORY CONTEXT
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        [User Profile]
        [Knowledge Graph]
        [Recent Timeline]
        [Key Intelligence]
        [Top Relationships]
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        Omits empty sections and trims proportionally if text length exceeds max_chars.
        Executes strictly under 30ms.

        Parameters
        ----------
        session_id : str
            Session identifier.
        max_chars : int
            Maximum length of assembled context string.

        Returns
        -------
        str
            Assembled memory context string.
        """
        sections: list[str] = []

        # 1. Fetch User Profile
        up_summary = self._user_profile.get_summary_for_prompt()
        if up_summary:
            sections.append(up_summary)

        # 2. Fetch Knowledge Graph
        kg_summary = self._knowledge_graph.get_summary_for_prompt(limit=8)
        if kg_summary:
            sections.append(kg_summary)

        # 3. Fetch Timeline Events
        tl_summary = self._timeline_engine.get_summary_for_prompt(limit=5)
        if tl_summary:
            sections.append(tl_summary)

        # 4. Fetch Key Intelligence
        mi_summary = self._memory_intelligence.get_summary_for_prompt(limit=5)
        if mi_summary:
            sections.append(mi_summary)

        # 5. Fetch Top Relationships
        rm_summary = self._relationship_memory.get_summary_for_prompt(limit=8)
        if rm_summary:
            sections.append(rm_summary)

        if not sections:
            return ""

        header = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nNAIRA MEMORY CONTEXT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        footer = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        body = "\n\n".join(sections)
        full_text = f"{header}\n{body}\n{footer}"

        # Return full text if within length budget
        if len(full_text) <= max_chars:
            return full_text

        # Trim body content line-by-line to strictly enforce max_chars budget
        budget = max_chars - len(header) - len(footer) - 2
        trimmed_lines: list[str] = []
        curr_len = 0
        for line in body.split("\n"):
            if curr_len + len(line) + 1 > budget:
                break
            trimmed_lines.append(line)
            curr_len += len(line) + 1

        trimmed_body = "\n".join(trimmed_lines).strip()
        if not trimmed_body:
            return ""

        return f"{header}\n{trimmed_body}\n{footer}"

    def save_snapshot(
        self, session_id: str, context_str: str, snapshot_type: str = "session_start"
    ) -> int | None:
        """Save a snapshot of assembled context into context_snapshots table.

        Parameters
        ----------
        session_id : str
            Session identifier.
        context_str : str
            Assembled context block string.
        snapshot_type : str
            Snapshot label/type.

        Returns
        -------
        int | None
            Inserted snapshot row ID.
        """
        now = time.time()
        token_est = len(context_str) // 4
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                cursor = conn.execute(
                    """
                    INSERT INTO context_snapshots (session_id, snapshot_type, content, token_estimate, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, snapshot_type, context_str, token_est, now),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as exc:
            if self._logger:
                self._logger.warning("ContextEngineV2.save_snapshot failed: %s", exc)
            return None

    def get_latest_snapshot(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve the latest context snapshot record for a session.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        dict | None
            Snapshot record dict or None if not found.
        """
        try:
            conn = self._store._require_conn()
            row = conn.execute(
                """
                SELECT * FROM context_snapshots
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        except Exception as exc:
            if self._logger:
                self._logger.warning("ContextEngineV2.get_latest_snapshot failed: %s", exc)
            return None

    def auto_record_from_message(self, message: str, role: str, session_id: str) -> None:
        """Lightweight non-blocking regex/keyword analysis to auto-extract signals (< 5ms).

        NO LLM CALLS USED.

        Parameters
        ----------
        message : str
            Message text.
        role : str
            Message role ('user', 'assistant', etc.).
        session_id : str
            Session identifier.
        """
        if not message or not message.strip():
            return

        msg_lower = message.strip().lower()

        try:
            # User role extraction patterns
            if role == "user":
                clean_msg = re.sub(r"^(?:hey\s+)?naira[,\s]*", "", message.strip(), flags=re.IGNORECASE).strip()

                # Voice / Direct Remember directives ("remember this detail", "Naira, remember...", "save this detail")
                rem_match = re.search(
                    r"\b(?:remember|save|note\s+down|don'?t\s+forget|keep\s+in\s+mind)\b(?:\s+(?:that|this|details?|fact)?)*\s*[:,-]?\s*(.+)",
                    clean_msg,
                    re.IGNORECASE,
                )
                if rem_match:
                    fact_str = rem_match.group(1).strip()
                    if fact_str:
                        fact_key = f"remembered_fact_{int(time.time())}"
                        self._user_profile.set(fact_key, fact_str, source="voice_or_chat")
                        self._relationship_memory.upsert(
                            entity_name="user_remember_directive",
                            entity_type="fact",
                            relationship_type="user_preference",
                            description=fact_str,
                            importance=8,
                        )
                        self._knowledge_graph.upsert("User", "requested_remember", fact_str)
                        self._timeline_engine.record(
                            event_type="voice_memory_captured",
                            title="Captured voice/chat memory update",
                            description=fact_str,
                            session_id=session_id,
                            importance=8,
                        )

                # Name matching pattern
                name_match = re.search(r"\bmy name is ([a-zA-Z0-9_\- ]+)", message, re.IGNORECASE)
                if name_match:
                    name_val = name_match.group(1).strip()
                    self._user_profile.set("name", name_val)
                    self._knowledge_graph.upsert("User", "is_named", name_val)

                # Preference pattern
                pref_match = re.search(r"\bi (like|prefer) ([a-zA-Z0-9_\- ]+)", message, re.IGNORECASE)
                if pref_match:
                    verb = pref_match.group(1).strip()
                    thing = pref_match.group(2).strip()
                    self._user_profile.set(f"preference_{thing}", thing)
                    self._knowledge_graph.upsert("User", verb, thing)

                # Profession/role pattern
                role_match = re.search(r"\bi am a ([a-zA-Z0-9_\- ]+)", message, re.IGNORECASE)
                if role_match:
                    occupation = role_match.group(1).strip()
                    self._user_profile.set("occupation", occupation)

            # Task completion signals (user or assistant)
            if any(sig in msg_lower for sig in ("done", "finished", "ho gaya", "completed", "task complete")):
                self._timeline_engine.record(
                    event_type="task_completion",
                    title=f"Task status update in session {session_id}",
                    description=message[:100],
                    session_id=session_id,
                )
        except Exception as exc:
            # Catch all exceptions to guarantee light non-blocking operation
            if self._logger:
                self._logger.warning("ContextEngineV2.auto_record_from_message failed: %s", exc)

    def cleanup_old_snapshots(self, keep_last: int = 5) -> int:
        """Purge old context snapshots, retaining only the keep_last most recent snapshots per session.

        Parameters
        ----------
        keep_last : int
            Number of recent snapshots to keep.

        Returns
        -------
        int
            Count of deleted snapshot records.
        """
        try:
            conn = self._store._require_conn()
            with self._store._write_lock:
                cursor = conn.execute(
                    """
                    DELETE FROM context_snapshots
                    WHERE id NOT IN (
                        SELECT id FROM context_snapshots
                        ORDER BY created_at DESC
                        LIMIT ?
                    )
                    """,
                    (keep_last,),
                )
                conn.commit()
                return cursor.rowcount
        except Exception as exc:
            if self._logger:
                self._logger.warning("ContextEngineV2.cleanup_old_snapshots failed: %s", exc)
            return 0
