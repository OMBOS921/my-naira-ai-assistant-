"""Unit tests for Jarvis Phase 3 (Pillar 5 Activation - Deep Contextual Memory).

Tests:
1. Timeline & UserProfileEngine activation in MemoryManager and SQLiteMemoryAdapter.
2. Dynamic Context Injection in ContextBuilder and ContextManager.
3. search_memory tool definition, handler execution, and tool registry integration.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from backend.modules.context._builder import ContextBuilder
from backend.modules.context.context_module import ContextManager
from backend.modules.memory.memory_module import MemoryManager
from backend.modules.tools.tools_module import ToolManager
from backend.types import Message


@pytest.fixture
def tmp_memory_mgr(tmp_path: Path) -> MemoryManager:
    db = tmp_path / "jarvis_memory.db"
    idx = tmp_path / "jarvis_index.json"
    return MemoryManager(db_path=db, index_path=idx)


@pytest.fixture
def tmp_tool_mgr() -> ToolManager:
    return ToolManager()


class TestJarvisPhase3Memory:
    @pytest.mark.asyncio
    async def test_timeline_and_user_profile_persistence(self, tmp_memory_mgr: MemoryManager) -> None:
        await tmp_memory_mgr.async_init()

        # Set user preference
        await tmp_memory_mgr.set_user_profile("theme", "dark_mode")
        await tmp_memory_mgr.set_user_profile("user_name", "Jarvis Lead")

        # Record timeline events
        await tmp_memory_mgr.record_event(
            event_type="milestone",
            title="Fixed FCR timestamp bug",
            description="Resolved timestamp issue in Fast Command Router",
            importance=8,
        )

        # Retrieve dynamic historical context summary
        summary = await tmp_memory_mgr.get_dynamic_historical_context(limit_events=3)
        assert "theme: dark_mode" in summary or "user_name: Jarvis Lead" in summary
        assert "Fixed FCR timestamp bug" in summary

        await tmp_memory_mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_dynamic_context_injection(self, tmp_memory_mgr: MemoryManager) -> None:
        await tmp_memory_mgr.async_init()

        # Seed profile and timeline
        await tmp_memory_mgr.set_user_profile("developer_mode", "enabled")
        await tmp_memory_mgr.record_event(
            event_type="coding",
            title="Activated Pillar 5 Deep Memory",
            description="Pillar 5 context injection completed successfully",
            importance=9,
        )

        context_mgr = ContextManager(memory_manager=tmp_memory_mgr)
        await context_mgr.async_init()

        ctx = context_mgr.build_context(
            session_id="session_test",
            text="Hello Naira, do you remember our work?",
            system_prompt="You are Naira, an autonomous OS.",
        )

        assert "[DYNAMIC HISTORICAL CONTEXT]" in ctx.system_prompt
        assert "Activated Pillar 5 Deep Memory" in ctx.system_prompt
        assert "developer_mode: enabled" in ctx.system_prompt

        await context_mgr.async_shutdown()
        await tmp_memory_mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_search_memory_tool(
        self, tmp_memory_mgr: MemoryManager, tmp_tool_mgr: ToolManager
    ) -> None:
        await tmp_memory_mgr.async_init()
        await tmp_tool_mgr.async_init()

        # Register search_memory tool
        tmp_memory_mgr.register_tools(tmp_tool_mgr)
        assert tmp_tool_mgr.has_tool("search_memory")

        # Seed data
        await tmp_memory_mgr.store_message("sess_101", Message(role="user", content="git checkout -b feature/jarvis-phase-3"))
        await tmp_memory_mgr.record_event(
            event_type="terminal_cmd",
            title="Ran git command",
            description="git checkout -b feature/jarvis-phase-3",
        )

        # Execute search_memory tool call
        res = await tmp_tool_mgr.execute_tool(
            name="search_memory",
            arguments={"query": "git checkout", "search_type": "all", "limit": 5},
        )

        assert res.status == "success"
        assert "git checkout" in str(res.output)

        await tmp_tool_mgr.async_shutdown()
        await tmp_memory_mgr.async_shutdown()
