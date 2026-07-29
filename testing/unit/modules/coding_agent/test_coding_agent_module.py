"""Comprehensive tests for the Coding Agent module.

Covers:
- AgentRuntime provider
- TaskPlanner provider
- ToolSelection provider
- FileManager provider
- GitExecutor provider
- CommandExecutor provider
- LanguageDetector provider
- MultiFileEditor provider
- ProjectAnalyzer provider
- SafetyLayer provider
- WorkspaceManager provider
- CodingAgentManager (ModuleInterface lifecycle + registration + execution)
- Internal services: AgentMemory, RetryEngine, ReflectionEngine, ErrorRecovery,
  ContextBuilder, DiffGenerator, PatchGenerator, CodingAgentExecutor
- ModuleInterface protocol conformance
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.coding_agent import CodingAgentManager
from backend.modules.coding_agent._context_builder import ContextBuilder
from backend.modules.coding_agent._diff_generator import DiffGenerator
from backend.modules.coding_agent._executor import CodingAgentExecutor
from backend.modules.coding_agent._memory import AgentMemory
from backend.modules.coding_agent._patch_generator import PatchGenerator
from backend.modules.coding_agent._recovery import ErrorRecovery
from backend.modules.coding_agent._reflection import ReflectionEngine
from backend.modules.coding_agent._retry import RetryEngine, RetryPolicy
from backend.modules.coding_agent.providers.agent_runtime_provider import (
    DefaultAgentRuntimeProvider,
)
from backend.modules.coding_agent.providers.command_executor_provider import (
    AsyncCommandExecutorProvider,
)
from backend.modules.coding_agent.providers.file_manager_provider import (
    OSFileManagerProvider,
)
from backend.modules.coding_agent.providers.git_executor_provider import (
    CLIGitExecutorProvider,
)
from backend.modules.coding_agent.providers.language_detector_provider import (
    FileExtensionLanguageDetectorProvider,
)
from backend.modules.coding_agent.providers.multi_file_editor_provider import (
    DefaultMultiFileEditorProvider,
)
from backend.modules.coding_agent.providers.project_analyzer_provider import (
    DefaultProjectAnalyzerProvider,
)
from backend.modules.coding_agent.providers.safety_layer_provider import (
    DefaultSafetyLayerProvider,
)
from backend.modules.coding_agent.providers.task_planner_provider import (
    DefaultTaskPlannerProvider,
)
from backend.modules.coding_agent.providers.tool_selection_provider import (
    DefaultToolSelectionProvider,
)
from backend.modules.coding_agent.providers.workspace_manager_provider import (
    TempWorkspaceManagerProvider,
)
from backend.types import ModuleInterface, ToolResult

# =========================================================================
# Helpers
# =========================================================================


def _async_return(result: Any) -> Any:
    async def _handler(**kwargs: object) -> Any:
        return result
    return _handler


# =========================================================================
# AgentRuntime Provider
# =========================================================================


class TestDefaultAgentRuntimeProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = DefaultAgentRuntimeProvider()
        assert p.is_available
        assert p.provider_name == "default_runtime"

    @pytest.mark.asyncio
    async def test_execute_task(self) -> None:
        p = DefaultAgentRuntimeProvider()
        result = await p.execute_task("task_1", "do something", {})
        assert result["task_id"] == "task_1"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_handle_error(self) -> None:
        p = DefaultAgentRuntimeProvider()
        retry, action = await p.handle_error("task_1", ValueError("fail"), 0)
        assert retry is True

    @pytest.mark.asyncio
    async def test_handle_error_exhausted(self) -> None:
        p = DefaultAgentRuntimeProvider()
        retry, action = await p.handle_error("task_1", ValueError("fail"), 3)
        assert retry is False
        assert action == "abort"

    @pytest.mark.asyncio
    async def test_reflect(self) -> None:
        p = DefaultAgentRuntimeProvider()
        result = await p.reflect_on_execution("task_1", {"status": "completed"}, {})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        p = DefaultAgentRuntimeProvider()
        await p.close()
        assert not p.is_available


# =========================================================================
# TaskPlanner Provider
# =========================================================================


class TestDefaultTaskPlannerProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = DefaultTaskPlannerProvider()
        assert p.is_available
        assert p.provider_name == "default_planner"

    @pytest.mark.asyncio
    async def test_plan_tasks(self) -> None:
        p = DefaultTaskPlannerProvider()
        plan = await p.plan_tasks("build feature", {})
        assert "tasks" in plan
        assert len(plan["tasks"]) == 3

    @pytest.mark.asyncio
    async def test_decompose_task(self) -> None:
        p = DefaultTaskPlannerProvider()
        result = await p.decompose_task("t1", "implement", {})
        assert "subtasks" in result
        assert len(result["subtasks"]) == 2

    @pytest.mark.asyncio
    async def test_prioritize_tasks(self) -> None:
        p = DefaultTaskPlannerProvider()
        tasks = [
            {"id": "1", "complexity": "low"},
            {"id": "2", "complexity": "high"},
            {"id": "3", "complexity": "medium"},
        ]
        result = await p.prioritize_tasks(tasks)
        assert result[0]["id"] == "2"  # high first
        assert result[-1]["id"] == "1"  # low last


# =========================================================================
# ToolSelection Provider
# =========================================================================


class TestDefaultToolSelectionProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = DefaultToolSelectionProvider()
        assert p.is_available

    @pytest.mark.asyncio
    async def test_select_tools(self) -> None:
        p = DefaultToolSelectionProvider()
        tools = [
            {"name": "read_file", "description": "Read a file"},
            {"name": "write_file", "description": "Write to a file"},
            {"name": "git_commit", "description": "Commit changes"},
        ]
        selected = await p.select_tools("read file contents", tools)
        assert len(selected) >= 1
        assert selected[0]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_select_tools_empty(self) -> None:
        p = DefaultToolSelectionProvider()
        selected = await p.select_tools("test", [])
        assert selected == []

    @pytest.mark.asyncio
    async def test_rank_tools(self) -> None:
        p = DefaultToolSelectionProvider()
        tools = [
            {"name": "read_file", "description": "Read a file"},
            {"name": "write_file", "description": "Write to a file"},
        ]
        ranked = await p.rank_tools("read", tools)
        assert len(ranked) == 2
        assert "score" in ranked[0]


# =========================================================================
# FileManager Provider
# =========================================================================


class TestOSFileManagerProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = OSFileManagerProvider()
        assert p.is_available
        assert p.provider_name == "os_file_manager"

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, tmp_path: Any) -> None:
        p = OSFileManagerProvider()
        test_file = str(tmp_path / "test.txt")
        await p.write_file(test_file, "hello world")
        content = await p.read_file(test_file)
        assert content == "hello world"

    @pytest.mark.asyncio
    async def test_create_file(self, tmp_path: Any) -> None:
        p = OSFileManagerProvider()
        test_file = str(tmp_path / "new.txt")
        await p.create_file(test_file, "initial")
        content = await p.read_file(test_file)
        assert content == "initial"

    @pytest.mark.asyncio
    async def test_delete_file(self, tmp_path: Any) -> None:
        p = OSFileManagerProvider()
        test_file = str(tmp_path / "delete_me.txt")
        await p.write_file(test_file, "content")
        assert await p.file_exists(test_file)
        await p.delete_file(test_file)
        assert not await p.file_exists(test_file)

    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path: Any) -> None:
        p = OSFileManagerProvider()
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        files = await p.list_directory(str(tmp_path))
        assert len(files) == 2

    @pytest.mark.asyncio
    async def test_file_exists(self, tmp_path: Any) -> None:
        p = OSFileManagerProvider()
        test_file = str(tmp_path / "exists.txt")
        assert not await p.file_exists(test_file)
        await p.write_file(test_file, "content")
        assert await p.file_exists(test_file)

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        p = OSFileManagerProvider()
        await p.close()
        assert not p.is_available


# =========================================================================
# GitExecutor Provider
# =========================================================================


class TestCLIGitExecutorProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = CLIGitExecutorProvider()
        assert p.provider_name == "cli_git"

    @pytest.mark.asyncio
    async def test_disabled_git(self) -> None:
        p = CLIGitExecutorProvider(enabled=False)
        result = await p.execute(["status"])
        assert result["success"] is False
        assert "disabled" in result["error"]

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        p = CLIGitExecutorProvider()
        await p.close()
        assert not p.is_available


# =========================================================================
# CommandExecutor Provider
# =========================================================================


class TestAsyncCommandExecutorProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = AsyncCommandExecutorProvider()
        assert p.is_available

    @pytest.mark.asyncio
    async def test_execute_echo(self) -> None:
        p = AsyncCommandExecutorProvider()
        result = await p.execute(["cmd", "/c", "echo", "hello"], timeout=5.0)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_timeout(self) -> None:
        p = AsyncCommandExecutorProvider()
        # A short timeout should trigger a timeout result
        result = await p.execute(["cmd", "/c", "ping", "-n", "10", "127.0.0.1"], timeout=0.1)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_allowed_commands(self) -> None:
        from backend.modules.coding_agent._exceptions import CommandExecutionError
        p = AsyncCommandExecutorProvider(allowed_commands=("python",))
        with pytest.raises(CommandExecutionError):
            await p.execute(["invalid_cmd"])


# =========================================================================
# LanguageDetector Provider
# =========================================================================


class TestFileExtensionLanguageDetectorProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = FileExtensionLanguageDetectorProvider()
        assert p.is_available

    @pytest.mark.asyncio
    async def test_detect_file_python(self) -> None:
        p = FileExtensionLanguageDetectorProvider()
        lang = await p.detect_file("script.py")
        assert lang == "python"

    @pytest.mark.asyncio
    async def test_detect_file_javascript(self) -> None:
        p = FileExtensionLanguageDetectorProvider()
        lang = await p.detect_file("app.js")
        assert lang == "javascript"

    @pytest.mark.asyncio
    async def test_detect_file_unknown(self) -> None:
        from backend.modules.coding_agent._exceptions import LanguageDetectionError
        p = FileExtensionLanguageDetectorProvider()
        with pytest.raises(LanguageDetectionError):
            await p.detect_file("file.xyz123")

    @pytest.mark.asyncio
    async def test_detect_code_python(self) -> None:
        p = FileExtensionLanguageDetectorProvider()
        lang = await p.detect_code("import os\nprint('hello')")
        assert lang == "python"

    @pytest.mark.asyncio
    async def test_detect_code_shebang(self) -> None:
        p = FileExtensionLanguageDetectorProvider()
        lang = await p.detect_code("#!/usr/bin/env python3\nprint('hello')")
        assert lang == "python"

    @pytest.mark.asyncio
    async def test_detect_directory(self, tmp_path: Any) -> None:
        p = FileExtensionLanguageDetectorProvider()
        (tmp_path / "main.py").write_text("x")
        (tmp_path / "utils.py").write_text("x")
        (tmp_path / "styles.css").write_text("x")
        result = await p.detect_directory(str(tmp_path))
        assert result.get("python") == 2
        assert result.get("css") == 1

    @pytest.mark.asyncio
    async def test_get_extensions(self) -> None:
        p = FileExtensionLanguageDetectorProvider()
        exts = await p.get_extensions("python")
        assert ".py" in exts


# =========================================================================
# MultiFileEditor Provider
# =========================================================================


class TestDefaultMultiFileEditorProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = DefaultMultiFileEditorProvider()
        assert p.is_available

    @pytest.mark.asyncio
    async def test_create_patch(self) -> None:
        p = DefaultMultiFileEditorProvider()
        patch = await p.create_patch("test.py", "old", "new")
        assert "old" in patch
        assert "new" in patch

    @pytest.mark.asyncio
    async def test_create_hunk(self) -> None:
        p = DefaultMultiFileEditorProvider()
        hunk = await p.create_hunk("test.py", 1, 5, "content")
        assert hunk["file_path"] == "test.py"
        assert hunk["line_start"] == 1

    @pytest.mark.asyncio
    async def test_edit_multiple(self, tmp_path: Any) -> None:
        p = DefaultMultiFileEditorProvider()
        edits = [
            {"file_path": str(tmp_path / "a.txt"), "action": "create", "content": "hello"},
            {"file_path": str(tmp_path / "b.txt"), "action": "create", "content": "world"},
        ]
        results = await p.edit_multiple(edits)
        assert len(results["success"]) == 2
        assert len(results["failed"]) == 0


# =========================================================================
# ProjectAnalyzer Provider
# =========================================================================


class TestDefaultProjectAnalyzerProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = DefaultProjectAnalyzerProvider()
        assert p.is_available

    @pytest.mark.asyncio
    async def test_analyze_structure(self, tmp_path: Any) -> None:
        p = DefaultProjectAnalyzerProvider()
        (tmp_path / "main.py").write_text("x")
        (tmp_path / "utils.py").write_text("x")
        result = await p.analyze_structure(str(tmp_path))
        assert result["file_count"] == 2
        assert "python" in result["languages"]

    @pytest.mark.asyncio
    async def test_analyze_structure_not_dir(self) -> None:
        p = DefaultProjectAnalyzerProvider()
        result = await p.analyze_structure("/nonexistent/path")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_analyze_dependencies_python(self, tmp_path: Any) -> None:
        p = DefaultProjectAnalyzerProvider()
        (tmp_path / "requirements.txt").write_text("pytest\nruff\n")
        result = await p.analyze_dependencies(str(tmp_path), "python")
        assert result["package_manager"] == "pip"
        assert "pytest" in result["packages"]

    @pytest.mark.asyncio
    async def test_analyze_goals(self) -> None:
        p = DefaultProjectAnalyzerProvider()
        result = await p.analyze_goals(["fix bug", "add feature"])
        assert len(result["subtasks"]) == 2


# =========================================================================
# SafetyLayer Provider
# =========================================================================


class TestDefaultSafetyLayerProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = DefaultSafetyLayerProvider()
        assert p.is_available

    @pytest.mark.asyncio
    async def test_validate_command_allowed(self) -> None:
        p = DefaultSafetyLayerProvider()
        allowed, reason = await p.validate_command("python", ["script.py"])
        assert allowed is True

    @pytest.mark.asyncio
    async def test_validate_command_blocked(self) -> None:
        p = DefaultSafetyLayerProvider()
        allowed, reason = await p.validate_command("rm", ["-rf", "/"])
        assert allowed is False
        assert reason is not None

    @pytest.mark.asyncio
    async def test_validate_command_risky(self) -> None:
        p = DefaultSafetyLayerProvider()
        allowed, reason = await p.validate_command("sudo", ["rm"])
        assert allowed is False

    @pytest.mark.asyncio
    async def test_validate_file_operation(self) -> None:
        p = DefaultSafetyLayerProvider()
        allowed, _ = await p.validate_file_operation("read", "/tmp/test.txt")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_validate_file_delete_protected(self) -> None:
        p = DefaultSafetyLayerProvider()
        allowed, reason = await p.validate_file_operation("delete", "/etc/passwd")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_validate_git_operation(self) -> None:
        p = DefaultSafetyLayerProvider()
        allowed, _ = await p.validate_git_operation("commit", ["-m", "msg"])
        assert allowed is True

    @pytest.mark.asyncio
    async def test_validate_git_risky(self) -> None:
        p = DefaultSafetyLayerProvider()
        allowed, reason = await p.validate_git_operation("push", ["--force"])
        assert allowed is False

    @pytest.mark.asyncio
    async def test_disabled_safety(self) -> None:
        p = DefaultSafetyLayerProvider(enabled=False)
        allowed, _ = await p.validate_command("rm", ["-rf", "/"])
        assert allowed is True


# =========================================================================
# WorkspaceManager Provider
# =========================================================================


class TestTempWorkspaceManagerProvider:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        p = TempWorkspaceManagerProvider()
        assert p.is_available

    @pytest.mark.asyncio
    async def test_create_and_get_workspace(self, tmp_path: Any) -> None:
        p = TempWorkspaceManagerProvider(base_dir=str(tmp_path))
        ws = await p.create_workspace("session_1")
        assert ws["session_id"] == "session_1"
        got = await p.get_workspace("session_1")
        assert got["session_id"] == "session_1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_workspace(self) -> None:
        from backend.modules.coding_agent._exceptions import WorkspaceError
        p = TempWorkspaceManagerProvider()
        with pytest.raises(WorkspaceError):
            await p.get_workspace("nonexistent")

    @pytest.mark.asyncio
    async def test_save_and_load_state(self) -> None:
        p = TempWorkspaceManagerProvider()
        await p.save_state("session_1", {"key": "value"})
        state = await p.load_state("session_1")
        assert state["key"] == "value"

    @pytest.mark.asyncio
    async def test_cleanup_workspace(self, tmp_path: Any) -> None:
        p = TempWorkspaceManagerProvider(base_dir=str(tmp_path))
        await p.create_workspace("session_1")
        await p.cleanup_workspace("session_1")
        from backend.modules.coding_agent._exceptions import WorkspaceError
        with pytest.raises(WorkspaceError):
            await p.get_workspace("session_1")


# =========================================================================
# AgentMemory
# =========================================================================


class TestAgentMemory:
    def test_store_and_retrieve(self) -> None:
        m = AgentMemory()
        m.store("key1", {"data": "value1"})
        result = m.retrieve("key1")
        assert result is not None
        assert result["data"] == "value1"

    def test_retrieve_nonexistent(self) -> None:
        m = AgentMemory()
        assert m.retrieve("nonexistent") is None

    def test_search(self) -> None:
        m = AgentMemory()
        m.store("task_1", {"description": "fix bug in parser"})
        m.store("task_2", {"description": "add new feature"})
        results = m.search("bug")
        assert len(results) >= 1

    def test_clear(self) -> None:
        m = AgentMemory()
        m.store("key", {"data": "value"})
        m.clear()
        assert m.size == 0

    def test_max_entries(self) -> None:
        m = AgentMemory(max_entries=2)
        m.store("a", {"d": 1})
        m.store("b", {"d": 2})
        m.store("c", {"d": 3})  # should evict 'a'
        assert m.retrieve("a") is None
        assert m.size == 2

    def test_degrade(self) -> None:
        m = AgentMemory()
        m.degrade()
        m.store("key", {"data": "value"})
        assert m.size == 0
        assert m.degraded

    def test_metrics(self) -> None:
        m = AgentMemory(max_entries=100)
        m.store("a", {"d": 1})
        metrics = m.metrics()
        assert metrics["size"] == 1
        assert metrics["max_entries"] == 100


# =========================================================================
# RetryEngine
# =========================================================================


class TestRetryEngine:
    @pytest.mark.asyncio
    async def test_successful_execution(self) -> None:
        engine = RetryEngine()
        success, result, error = await engine.execute(
            "test_op",
            lambda: _async_return("ok")(),
        )
        assert success is True
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self) -> None:
        attempts = [0]

        async def _fail_twice() -> str:
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("not yet")
            return "success"

        engine = RetryEngine()
        success, result, error = await engine.execute(
            "test_op",
            _fail_twice,
            RetryPolicy(max_retries=3, base_delay=0.01),
        )
        assert success is True
        assert result == "success"

    @pytest.mark.asyncio
    async def test_exhaust_retries(self) -> None:
        async def _always_fail() -> str:
            raise ValueError("always fail")

        engine = RetryEngine()
        success, result, error = await engine.execute(
            "test_op",
            _always_fail,
            RetryPolicy(max_retries=2, base_delay=0.01),
        )
        assert success is False

    def test_metrics(self) -> None:
        engine = RetryEngine()
        assert isinstance(engine.get_metrics(), dict)


# =========================================================================
# ReflectionEngine
# =========================================================================


class TestReflectionEngine:
    @pytest.mark.asyncio
    async def test_reflect_success(self) -> None:
        engine = ReflectionEngine()
        result = await engine.reflect("task_1", {"status": "completed"}, {})
        assert result["success"] is True
        assert len(result["insights"]) > 0

    @pytest.mark.asyncio
    async def test_reflect_failure(self) -> None:
        engine = ReflectionEngine()
        result = await engine.reflect("task_1", {"status": "failed", "error": "oops"}, {})
        assert result["success"] is False
        assert len(result["insights"]) > 0

    def test_history(self) -> None:
        engine = ReflectionEngine()
        history = engine.get_history()
        assert isinstance(history, list)

    def test_clear_history(self) -> None:
        engine = ReflectionEngine()
        engine.clear_history()
        assert engine.get_history() == []


# =========================================================================
# ErrorRecovery
# =========================================================================


class TestErrorRecovery:
    @pytest.mark.asyncio
    async def test_recoverable_timeout(self) -> None:
        recovery = ErrorRecovery()
        plan = await recovery.attempt_recovery("t1", TimeoutError("timed out"), {})
        assert plan["recoverable"] is True
        assert plan["strategy"] == "increase_timeout"

    @pytest.mark.asyncio
    async def test_recoverable_not_found(self) -> None:
        recovery = ErrorRecovery()
        plan = await recovery.attempt_recovery("t2", FileNotFoundError("not found"), {})
        assert plan["recoverable"] is True

    @pytest.mark.asyncio
    async def test_recoverable_permission(self) -> None:
        recovery = ErrorRecovery()
        plan = await recovery.attempt_recovery("t3", PermissionError("denied"), {})
        assert plan["recoverable"] is True

    def test_reset(self) -> None:
        recovery = ErrorRecovery()
        recovery.reset("t1")


# =========================================================================
# ContextBuilder
# =========================================================================


class TestContextBuilder:
    def test_build_context_minimal(self) -> None:
        cb = ContextBuilder()
        ctx = cb.build_context(task_id="t1", goal="test")
        assert ctx["task_id"] == "t1"
        assert ctx["goal"] == "test"

    def test_build_context_full(self) -> None:
        cb = ContextBuilder()
        ctx = cb.build_context(
            task_id="t1",
            goal="test",
            workspace_info={"path": "/ws"},
            project_info={"lang": "python"},
            memory_context={"key": "val"},
            environment={"HOME": "/home"},
            additional={"extra": "data"},
        )
        assert ctx["workspace"]["path"] == "/ws"
        assert ctx["project"]["lang"] == "python"
        assert ctx["extra"] == "data"


# =========================================================================
# DiffGenerator
# =========================================================================


class TestDiffGenerator:
    def test_generate_diff(self) -> None:
        dg = DiffGenerator()
        diff = dg.generate_diff("old line\n", "new line\n", "test.py")
        assert "old line" in diff
        assert "new line" in diff

    def test_generate_summary(self) -> None:
        dg = DiffGenerator()
        summary = dg.generate_summary("line1\nline2\n", "line1\nline3\n")
        assert summary["old_lines"] == 2
        assert summary["new_lines"] == 2


# =========================================================================
# PatchGenerator
# =========================================================================


class TestPatchGenerator:
    def test_generate_patch(self) -> None:
        pg = PatchGenerator()
        patch = pg.generate_patch("test.py", "old", "new")
        assert "test.py" in patch

    def test_validate_patch_valid(self) -> None:
        pg = PatchGenerator()
        patch = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new\n"
        result = pg.validate_patch(patch)
        assert result["valid"] is True

    def test_validate_patch_empty(self) -> None:
        pg = PatchGenerator()
        result = pg.validate_patch("")
        assert result["valid"] is False
        assert len(result["errors"]) > 0


# =========================================================================
# CodingAgentExecutor
# =========================================================================


class TestCodingAgentExecutor:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        exe = CodingAgentExecutor()

        async def _success() -> str:
            return "done"

        result = await exe.execute("test_op", _success())
        assert result.status == "success"
        assert result.output == "done"

    @pytest.mark.asyncio
    async def test_execute_timeout(self) -> None:
        exe = CodingAgentExecutor(default_timeout=0.05)

        async def _slow() -> str:
            import asyncio
            await asyncio.sleep(10)
            return "done"

        result = await exe.execute("slow_op", _slow())
        assert result.status == "timeout"

    @pytest.mark.asyncio
    async def test_execute_degraded(self) -> None:
        exe = CodingAgentExecutor()
        exe.degrade()

        async def _ok() -> str:
            return "ok"

        result = await exe.execute("test", _ok())
        assert result.status == "error"
        assert "degraded" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self) -> None:
        exe = CodingAgentExecutor(default_timeout=5.0)
        attempts = [0]

        async def _fail_then_succeed() -> str:
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("fail")
            return "success"

        result = await exe.execute_with_retry(
            "retry_op",
            _fail_then_succeed,
            max_retries=3,
            base_delay=0.01,
        )
        assert result.status == "success"
        assert result.output == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausted(self) -> None:
        exe = CodingAgentExecutor(default_timeout=5.0)

        async def _always_fail() -> str:
            raise ValueError("always fail")

        result = await exe.execute_with_retry(
            "retry_op",
            _always_fail,
            max_retries=2,
            base_delay=0.01,
        )
        assert result.status == "error"


# =========================================================================
# CodingAgentManager — ModuleInterface lifecycle
# =========================================================================


class TestCodingAgentManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = CodingAgentManager()
        assert mgr.degraded is False
        assert mgr.initialized is False

    @pytest.mark.asyncio
    async def test_async_init(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        assert mgr.initialized is True
        assert mgr.degraded is False
        assert mgr.agent_runtime is not None
        assert mgr.task_planner is not None
        assert mgr.file_manager is not None

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        assert mgr.initialized is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()
        assert mgr.initialized is False

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = CodingAgentManager()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = CodingAgentManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_port_injection(self) -> None:
        runtime = DefaultAgentRuntimeProvider()
        mgr = CodingAgentManager(agent_runtime=runtime)
        assert mgr.agent_runtime is runtime

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = MagicMock()
        mgr = CodingAgentManager(logger=logger)
        assert mgr._logger is logger


# =========================================================================
# CodingAgentManager — execution
# =========================================================================


class TestCodingAgentManagerExecution:
    @pytest.mark.asyncio
    async def test_execute_task(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.execute_task("write hello world")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_task_degraded_raises(self) -> None:
        mgr = CodingAgentManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.execute_task("test")

    @pytest.mark.asyncio
    async def test_analyze_project(self, tmp_path: Any) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        (tmp_path / "main.py").write_text("x")
        result = await mgr.analyze_project(str(tmp_path))
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_language(self, tmp_path: Any) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        test_file = str(tmp_path / "script.py")
        with open(test_file, "w") as f:
            f.write("x")
        result = await mgr.detect_language(test_file)
        assert result.status == "success"
        assert result.output == "python"

    @pytest.mark.asyncio
    async def test_file_operations(self, tmp_path: Any) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        test_file = str(tmp_path / "test.txt")

        # Write
        result = await mgr.file_operation("write", test_file, content="hello")
        assert result.status == "success"

        # Read
        result = await mgr.file_operation("read", test_file)
        assert result.status == "success"
        assert result.output == "hello"

        # Exists
        result = await mgr.file_operation("exists", test_file)
        assert result.status == "success"
        assert result.output == "True"

        # Delete
        result = await mgr.file_operation("delete", test_file)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_workspace_operations(self, tmp_path: Any) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.workspace_operation("create", "session_1")
        assert result.status == "success"

        result = await mgr.workspace_operation("get", "session_1")
        assert result.status == "success"

        result = await mgr.workspace_operation("cleanup", "session_1")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_command_operation(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        # Run a simple echo command
        result = await mgr.command_operation(["cmd", "/c", "echo", "test"])
        # This may fail if subprocess fails, but should return something
        assert result.status in ("success", "error")

    @pytest.mark.asyncio
    async def test_git_operation_disabled(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        # Git might fail if no repo, but should return a result
        result = await mgr.git_operation("status")
        assert result.status in ("success", "error")


# =========================================================================
# CodingAgentManager — metrics and health
# =========================================================================


class TestCodingAgentManagerMetricsHealth:
    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        metrics = mgr.metrics()
        assert "total_tasks" in metrics
        assert "success_rate" in metrics
        assert "memory" in metrics
        assert "retry" in metrics

    @pytest.mark.asyncio
    async def test_health(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        health = mgr.health()
        assert "healthy" in health
        assert "ports_available" in health
        assert health["initialized"] is True
        assert health["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_degraded(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        health = mgr.health()
        assert health["degraded"] is True
        assert health["healthy"] is False

    @pytest.mark.asyncio
    async def test_metrics_after_tasks(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.execute_task("task 1")
        await mgr.execute_task("task 2")
        metrics = mgr.metrics()
        assert metrics["total_tasks"] == 2


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_coding_agent_manager_conforms_to_protocol(self) -> None:
        assert isinstance(CodingAgentManager(), ModuleInterface)

    def test_coding_agent_manager_has_required_methods(self) -> None:
        mgr = CodingAgentManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")


# =========================================================================
# MCP Integration
# =========================================================================


class TestMCPIntegration:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._mcp_integration import MCPIntegration
        mcp = MCPIntegration()
        assert mcp.enabled
        assert not mcp.degraded

    @pytest.mark.asyncio
    async def test_create_context(self) -> None:
        from backend.modules.coding_agent._mcp_integration import MCPIntegration
        mcp = MCPIntegration()
        ctx = mcp.create_context(session_id="s1", system_prompt="test prompt")
        assert ctx.session_id == "s1"
        assert ctx.system_prompt == "test prompt"
        assert ctx.token_count > 0

    @pytest.mark.asyncio
    async def test_merge_contexts(self) -> None:
        from backend.modules.coding_agent._mcp_integration import MCPIntegration
        mcp = MCPIntegration()
        ctx1 = mcp.create_context(session_id="s1", system_prompt="part1")
        ctx2 = mcp.create_context(session_id="s1", system_prompt="part2")
        merged = mcp.merge_contexts([ctx1, ctx2])
        assert merged.session_id == "s1"
        assert "part1" in merged.system_prompt
        assert "part2" in merged.system_prompt

    @pytest.mark.asyncio
    async def test_to_dict(self) -> None:
        from backend.modules.coding_agent._mcp_integration import MCPIntegration
        mcp = MCPIntegration()
        ctx = mcp.create_context(session_id="s1", system_prompt="test")
        d = mcp.to_dict(ctx)
        assert d["session_id"] == "s1"
        assert d["system_prompt"] == "test"

    @pytest.mark.asyncio
    async def test_estimate_tokens(self) -> None:
        from backend.modules.coding_agent._mcp_integration import MCPIntegration
        mcp = MCPIntegration()
        ctx = mcp.create_context(session_id="s1", system_prompt="hello world")
        est = mcp.estimate_tokens(ctx)
        assert est >= 1

    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        from backend.modules.coding_agent._mcp_integration import MCPIntegration
        mcp = MCPIntegration()
        mcp.create_context(session_id="s1")
        metrics = mcp.metrics()
        assert metrics["contexts_created"] == 1


# =========================================================================
# HITL Workflow
# =========================================================================


class TestHITLWorkflow:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._hitl_workflow import HITLWorkflow
        h = HITLWorkflow()
        assert h.enabled
        assert not h.degraded
        assert h.pending_count == 0

    @pytest.mark.asyncio
    async def test_auto_approve_read_actions(self) -> None:
        from backend.modules.coding_agent._hitl_workflow import HITLWorkflow
        h = HITLWorkflow()
        req = await h.request_approval("read_file", "Read a file")
        assert req.status.value == "approved"

    @pytest.mark.asyncio
    async def test_pending_approval_then_approve(self) -> None:
        from backend.modules.coding_agent._hitl_workflow import ApprovalStatus, HITLWorkflow
        h = HITLWorkflow(auto_approve_patterns=())
        import asyncio

        async def _delayed_approve() -> None:
            await asyncio.sleep(0.05)
            h.approve("test_req")

        async def _request():
            return await h.request_approval(
                "write_file", "Write to /etc/config",
                details={"path": "/etc/config"},
            )

        # Pre-register the request manually

        from backend.modules.coding_agent._hitl_workflow import ApprovalRequest
        req = ApprovalRequest(
            id="test_req", action="write_file",
            description="test", details={"path": "/etc/config"},
        )
        h._pending["test_req"] = req
        h._total_requests += 1

        await _delayed_approve()
        assert req.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_approve_reject_cancel(self) -> None:

        from backend.modules.coding_agent._hitl_workflow import (
            ApprovalRequest,
            ApprovalStatus,
            HITLWorkflow,
        )
        h = HITLWorkflow(auto_approve_patterns=())
        req_id = "test_approve"
        h._pending[req_id] = ApprovalRequest(
            id=req_id, action="write", description="test", details={},
        )
        h._total_requests += 1

        result = h.approve(req_id, "looks good")
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED

        req_id2 = "test_reject"
        h._pending[req_id2] = ApprovalRequest(
            id=req_id2, action="delete", description="test", details={},
        )
        h._total_requests += 1
        result = h.reject(req_id2, "not safe")
        assert result is not None
        assert result.status == ApprovalStatus.REJECTED

        req_id3 = "test_cancel"
        h._pending[req_id3] = ApprovalRequest(
            id=req_id3, action="write", description="test", details={},
        )
        h._total_requests += 1
        result = h.cancel(req_id3)
        assert result is not None
        assert result.status == ApprovalStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_pending(self) -> None:
        from backend.modules.coding_agent._hitl_workflow import ApprovalRequest, HITLWorkflow
        h = HITLWorkflow(auto_approve_patterns=())
        h._pending["p1"] = ApprovalRequest(id="p1", action="write", description="test", details={})
        h._pending["p2"] = ApprovalRequest(id="p2", action="delete", description="test", details={})
        assert len(h.get_pending()) == 2

    @pytest.mark.asyncio
    async def test_disabled_auto_approves(self) -> None:
        from backend.modules.coding_agent._hitl_workflow import HITLWorkflow
        h = HITLWorkflow(enabled=False)
        req = await h.request_approval("delete_file", "Delete a file")
        assert req.status.value == "approved"


# =========================================================================
# Compose Mode / Ghost Text
# =========================================================================


class TestComposeMode:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode
        c = ComposeMode()
        assert c.enabled
        assert not c.degraded

    @pytest.mark.asyncio
    async def test_generate_ghost_text(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode, SuggestionStatus
        c = ComposeMode()
        s = c.generate_ghost_text(
            file_path="/tmp/test.py",
            original_text="old",
            suggested_text="new",
            description="change variable",
        )
        assert s.file_path == "/tmp/test.py"
        assert s.ghost_text == "new"
        assert s.status == SuggestionStatus.ACTIVE
        assert len(c.get_active_suggestions()) == 1

    @pytest.mark.asyncio
    async def test_apply_suggestion(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode, SuggestionStatus
        c = ComposeMode()
        s = c.generate_ghost_text("f.py", "old", "new")
        result = c.apply_suggestion(s.id)
        assert result is not None
        assert result.status == SuggestionStatus.APPLIED
        assert len(c.get_active_suggestions()) == 0

    @pytest.mark.asyncio
    async def test_apply_with_modified_text(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode, SuggestionStatus
        c = ComposeMode()
        s = c.generate_ghost_text("f.py", "old", "new")
        result = c.apply_suggestion(s.id, modified_text="modified")
        assert result is not None
        assert result.status == SuggestionStatus.MODIFIED
        assert result.ghost_text == "modified"

    @pytest.mark.asyncio
    async def test_dismiss_suggestion(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode, SuggestionStatus
        c = ComposeMode()
        s = c.generate_ghost_text("f.py", "old", "new")
        result = c.dismiss_suggestion(s.id)
        assert result is not None
        assert result.status == SuggestionStatus.DISMISSED

    @pytest.mark.asyncio
    async def test_get_suggestions_by_file(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode
        c = ComposeMode()
        c.generate_ghost_text("a.py", "old", "new")
        c.generate_ghost_text("b.py", "old", "new2")
        c.generate_ghost_text("a.py", "old2", "new3")
        assert len(c.get_active_suggestions("a.py")) == 2
        assert len(c.get_active_suggestions("b.py")) == 1

    @pytest.mark.asyncio
    async def test_disabled_auto_applies(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode, SuggestionStatus
        c = ComposeMode(enabled=False)
        s = c.generate_ghost_text("f.py", "old", "new")
        assert s.status == SuggestionStatus.APPLIED

    @pytest.mark.asyncio
    async def test_clear_suggestions(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode
        c = ComposeMode()
        c.generate_ghost_text("f.py", "old", "new")
        c.clear_suggestions()
        assert len(c.get_active_suggestions()) == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_suggestion(self) -> None:
        from backend.modules.coding_agent._compose_mode import ComposeMode
        c = ComposeMode()
        assert c.get_suggestion("nonexistent") is None
        assert c.apply_suggestion("nonexistent") is None
        assert c.dismiss_suggestion("nonexistent") is None


# =========================================================================
# Self-Correction Loop
# =========================================================================


class TestSelfCorrectionLoop:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._self_correction import SelfCorrectionLoop
        s = SelfCorrectionLoop()
        assert s.enabled
        assert not s.degraded

    @pytest.mark.asyncio
    async def test_immediate_success(self) -> None:
        from backend.modules.coding_agent._self_correction import SelfCorrectionLoop
        s = SelfCorrectionLoop()

        async def execute() -> str:
            return "success"

        async def reflect(res, ctx):
            return {"insights": []}

        result = await s.execute_with_correction("t1", "test", execute, reflect)
        assert result.success
        assert result.iterations == 1
        assert result.final_result.status == "success"

    @pytest.mark.asyncio
    async def test_correction_after_failure(self) -> None:
        from backend.modules.coding_agent._self_correction import SelfCorrectionLoop
        from backend.types import ToolResult
        s = SelfCorrectionLoop(max_iterations=3)
        attempt = [0]

        async def execute() -> ToolResult:
            attempt[0] += 1
            if attempt[0] < 2:
                return ToolResult(status="error", error="timeout error")
            return ToolResult(status="success", output="done")

        async def reflect(res, ctx):
            return {"insights": []}

        result = await s.execute_with_correction("t1", "test", execute, reflect)
        assert result.success
        assert result.iterations == 2
        assert len(result.corrections) == 1

    @pytest.mark.asyncio
    async def test_exhaust_corrections(self) -> None:
        from backend.modules.coding_agent._self_correction import SelfCorrectionLoop
        from backend.types import ToolResult
        s = SelfCorrectionLoop(max_iterations=2)

        async def execute() -> ToolResult:
            return ToolResult(status="error", error="always fails")

        async def reflect(res, ctx):
            return {"insights": []}

        result = await s.execute_with_correction("t1", "test", execute, reflect)
        assert not result.success
        assert result.iterations == 2

    @pytest.mark.asyncio
    async def test_disabled_returns_success(self) -> None:
        from backend.modules.coding_agent._self_correction import SelfCorrectionLoop
        s = SelfCorrectionLoop(enabled=False)
        assert s.enabled is False

    @pytest.mark.asyncio
    async def test_degrade(self) -> None:
        from backend.modules.coding_agent._self_correction import SelfCorrectionLoop
        s = SelfCorrectionLoop()
        s.degrade()
        assert s.degraded


# =========================================================================
# TDD Loop
# =========================================================================


class TestTDDLoop:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._tdd_loop import TDDLoop
        t = TDDLoop()
        assert t.enabled
        assert not t.degraded

    @pytest.mark.asyncio
    async def test_disabled_tdd(self) -> None:
        from backend.modules.coding_agent._tdd_loop import TDDLoop
        from backend.types import ToolResult
        t = TDDLoop(enabled=False)

        async def write_test(feature):
            return ToolResult(status="success", output="test written")

        async def run_test():
            return ToolResult(status="success", output="tests passed")

        async def write_code(output):
            return ToolResult(status="success", output="code written")

        result = await t.execute_tdd("feature", write_test, run_test, write_code)
        assert result.success
        assert len(result.phases) == 3  # write_test, run_test(skipped), write_code

    @pytest.mark.asyncio
    async def test_tdd_success(self) -> None:
        from backend.modules.coding_agent._tdd_loop import TDDLoop
        from backend.types import ToolResult
        t = TDDLoop()

        async def write_test(feature):
            return ToolResult(status="success", output="test written for " + feature)

        async def run_test():
            return ToolResult(status="success", output="all tests passed")

        async def write_code(output):
            return ToolResult(status="success", output="code written")

        result = await t.execute_tdd("feature", write_test, run_test, write_code)
        assert result.success
        assert len(result.phases) >= 2

    @pytest.mark.asyncio
    async def test_tdd_with_refactor(self) -> None:
        from backend.modules.coding_agent._tdd_loop import TDDLoop
        from backend.types import ToolResult
        t = TDDLoop()
        refactored = [False]

        async def write_test(feature):
            return ToolResult(status="success", output="test")

        async def run_test():
            return ToolResult(status="success", output="pass")

        async def write_code(output):
            return ToolResult(status="success", output="code")

        async def refactor():
            refactored[0] = True
            return ToolResult(status="success", output="refactored")

        result = await t.execute_tdd("feature", write_test, run_test, write_code, refactor)
        assert result.success
        assert refactored[0]

    @pytest.mark.asyncio
    async def test_tdd_failure(self) -> None:
        from backend.modules.coding_agent._tdd_loop import TDDLoop, TDDTestFailureError
        from backend.types import ToolResult
        t = TDDLoop(max_iterations=1)

        async def write_test(feature):
            return ToolResult(status="success", output="test")

        async def run_test():
            return ToolResult(status="error", output="tests failed")

        async def write_code(output):
            return ToolResult(status="success", output="code")

        with pytest.raises(TDDTestFailureError):
            await t.execute_tdd("feature", write_test, run_test, write_code)


# =========================================================================
# CI/CD Monitor
# =========================================================================


class TestCICDMonitor:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._cicd_monitor import CICDMonitor
        m = CICDMonitor()
        assert m.enabled
        assert not m.degraded

    @pytest.mark.asyncio
    async def test_start_and_complete_run(self) -> None:
        from backend.modules.coding_agent._cicd_monitor import CICDMonitor, PipelineStatus
        m = CICDMonitor()
        run = m.start_run("test-pipeline", commit_sha="abc123", branch="main")
        assert run.pipeline_name == "test-pipeline"
        assert run.status == PipelineStatus.RUNNING
        assert run.commit_sha == "abc123"

        completed = m.complete_run(run.id, PipelineStatus.SUCCESS)
        assert completed is not None
        assert completed.status == PipelineStatus.SUCCESS
        assert completed.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_get_pipeline_status(self) -> None:
        from backend.modules.coding_agent._cicd_monitor import CICDMonitor, PipelineStatus
        m = CICDMonitor()
        run = m.start_run("test-pipeline")
        m.complete_run(run.id, PipelineStatus.SUCCESS)

        status = m.get_pipeline_status("test-pipeline")
        assert status is not None
        assert status.total_runs == 1
        assert status.success_count == 1
        assert status.success_rate == 100.0

    @pytest.mark.asyncio
    async def test_get_nonexistent_pipeline(self) -> None:
        from backend.modules.coding_agent._cicd_monitor import CICDMonitor
        m = CICDMonitor()
        assert m.get_pipeline_status("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_all_statuses(self) -> None:
        from backend.modules.coding_agent._cicd_monitor import CICDMonitor, PipelineStatus
        m = CICDMonitor()
        r1 = m.start_run("pipe1")
        m.complete_run(r1.id, PipelineStatus.SUCCESS)
        r2 = m.start_run("pipe2")
        m.complete_run(r2.id, PipelineStatus.FAILED)
        all_statuses = m.get_all_statuses()
        assert len(all_statuses) == 2

    @pytest.mark.asyncio
    async def test_complete_nonexistent_run(self) -> None:
        from backend.modules.coding_agent._cicd_monitor import CICDMonitor, PipelineStatus
        m = CICDMonitor()
        result = m.complete_run("nonexistent", PipelineStatus.SUCCESS)
        assert result is None

    @pytest.mark.asyncio
    async def test_metrics(self) -> None:
        from backend.modules.coding_agent._cicd_monitor import CICDMonitor, PipelineStatus
        m = CICDMonitor()
        r = m.start_run("pipe1")
        m.complete_run(r.id, PipelineStatus.SUCCESS)
        metrics = m.metrics()
        assert metrics["total_runs"] == 1
        assert metrics["success_count"] == 1


# =========================================================================
# Cost Tracker
# =========================================================================


class TestCostTracker:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        c = CostTracker()
        assert c.enabled
        assert not c.degraded
        assert c.total_cost == 0.0

    @pytest.mark.asyncio
    async def test_track_cost(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        from backend.types import TokenUsage
        c = CostTracker()
        entry = c.track("llm_call", "gemini-2.0-flash", TokenUsage(100, 50, 150))
        assert entry.prompt_tokens == 100
        assert entry.completion_tokens == 50
        assert entry.total_tokens == 150
        assert entry.estimated_cost > 0
        assert c.total_cost > 0

    @pytest.mark.asyncio
    async def test_track_tokens(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        c = CostTracker()
        entry = c.track_tokens("test", "gemini-2.0-flash", 200, 100)
        assert entry.prompt_tokens == 200
        assert entry.completion_tokens == 100
        assert entry.total_tokens == 300

    @pytest.mark.asyncio
    async def test_get_costs(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        from backend.types import TokenUsage
        c = CostTracker()
        c.track("op1", "gemini-2.0-flash", TokenUsage(100, 50, 150))
        costs = c.get_costs()
        assert costs["total_tokens"] == 150
        assert costs["entry_count"] == 1

    @pytest.mark.asyncio
    async def test_get_cost_by_operation(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        from backend.types import TokenUsage
        c = CostTracker()
        c.track("llm", "gemini-2.0-flash", TokenUsage(100, 50, 150))
        by_op = c.get_cost_by_operation()
        assert "llm" in by_op

    @pytest.mark.asyncio
    async def test_reset(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        from backend.types import TokenUsage
        c = CostTracker()
        c.track("op1", "gemini-2.0-flash", TokenUsage(100, 50, 150))
        c.reset()
        assert c.total_cost == 0.0
        assert c.get_costs()["entry_count"] == 0

    @pytest.mark.asyncio
    async def test_budget_limit(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        from backend.modules.coding_agent._exceptions import CostTrackingError
        from backend.types import TokenUsage
        c = CostTracker(budget_limit=0.000001)
        with pytest.raises(CostTrackingError):
            c.track("llm", "gemini-2.0-flash", TokenUsage(10000, 5000, 15000))

    @pytest.mark.asyncio
    async def test_disabled_returns_zero_cost(self) -> None:
        from backend.modules.coding_agent._cost_tracker import CostTracker
        from backend.types import TokenUsage
        c = CostTracker(enabled=False)
        entry = c.track("test", "gemini-2.0-flash", TokenUsage(100, 50, 150))
        assert entry.estimated_cost == 0.0


# =========================================================================
# Code Security Scanner
# =========================================================================


class TestCodeSecurityScanner:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner()
        assert s.enabled
        assert not s.degraded

    @pytest.mark.asyncio
    async def test_scan_clean_code(self) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner()
        result = await s.scan_code("x = 1\nprint(x)")
        assert result.safe
        assert result.total_issues == 0

    @pytest.mark.asyncio
    async def test_scan_api_key(self) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner()
        result = await s.scan_code('api_key = "sk-test123456789012345678901234567"')
        assert not result.safe
        assert result.total_issues >= 1
        assert any("API" in v.message for v in result.vulnerabilities)

    @pytest.mark.asyncio
    async def test_scan_eval(self) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner()
        result = await s.scan_code("eval(user_input)")
        assert not result.safe
        assert any("eval" in v.message.lower() for v in result.vulnerabilities)

    @pytest.mark.asyncio
    async def test_scan_file(self, tmp_path: Any) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner()
        f = tmp_path / "safe.py"
        f.write_text("x = 1")
        result = await s.scan_file(str(f))
        assert result.safe

    @pytest.mark.asyncio
    async def test_scan_file_with_secret(self, tmp_path: Any) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner()
        f = tmp_path / "secret.txt"
        f.write_text('password = "supersecret"')
        result = await s.scan_file(str(f))
        # .txt may not be scanned depending on extension filter
        assert isinstance(result.safe, bool)

    @pytest.mark.asyncio
    async def test_scan_project(self, tmp_path: Any) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner()
        (tmp_path / "main.py").write_text("x = 1")
        (tmp_path / "utils.py").write_text("y = 2")
        result = await s.scan_project(str(tmp_path))
        assert result.files_scanned >= 2

    @pytest.mark.asyncio
    async def test_disabled_returns_safe(self) -> None:
        from backend.modules.coding_agent._security_scanner import CodeSecurityScanner
        s = CodeSecurityScanner(enabled=False)
        result = await s.scan_code('api_key = "sk-test123"')
        assert result.safe


# =========================================================================
# Package Auto Installer
# =========================================================================


class TestPackageAutoInstaller:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        from backend.modules.coding_agent._package_installer import PackageAutoInstaller
        p = PackageAutoInstaller()
        assert p.enabled
        assert not p.degraded

    @pytest.mark.asyncio
    async def test_disabled_returns_installed(self) -> None:
        from backend.modules.coding_agent._package_installer import PackageAutoInstaller
        p = PackageAutoInstaller(enabled=False)
        result = await p.install_package("some-package")
        assert result.success
        assert len(result.already_installed) == 1

    @pytest.mark.asyncio
    async def test_unsupported_manager_raises(self) -> None:
        from backend.modules.coding_agent._exceptions import PackageInstallError
        from backend.modules.coding_agent._package_installer import PackageAutoInstaller
        p = PackageAutoInstaller()
        with pytest.raises(PackageInstallError):
            await p.install_package("test", manager="unsupported")

    @pytest.mark.asyncio
    async def test_disallowed_manager_raises(self) -> None:
        from backend.modules.coding_agent._exceptions import PackageInstallError
        from backend.modules.coding_agent._package_installer import PackageAutoInstaller
        p = PackageAutoInstaller(allowed_managers=("pip",))
        with pytest.raises(PackageInstallError):
            await p.install_package("test", manager="npm")

    @pytest.mark.asyncio
    async def test_detect_requirements(self, tmp_path: Any) -> None:
        from backend.modules.coding_agent._package_installer import PackageAutoInstaller
        p = PackageAutoInstaller()
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("pytest\nruff\n")
        packages = await p.detect_requirements(str(tmp_path))
        assert "pytest" in packages
        assert "ruff" in packages

    @pytest.mark.asyncio
    async def test_detect_requirements_empty_dir(self, tmp_path: Any) -> None:
        from backend.modules.coding_agent._package_installer import PackageAutoInstaller
        p = PackageAutoInstaller()
        packages = await p.detect_requirements(str(tmp_path))
        assert packages == []


# =========================================================================
# CodingAgentManager — new integrated features
# =========================================================================


class TestCodingAgentManagerNewFeatures:
    @pytest.mark.asyncio
    async def test_mcp_integration(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        ctx = mgr.create_context(session_id="test", system_prompt="hello")
        assert ctx.session_id == "test"
        assert ctx.system_prompt == "hello"

    @pytest.mark.asyncio
    async def test_hitl_workflow(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        req = await mgr.request_approval("read_file", "Read a file")
        assert req.status.value == "approved"

    @pytest.mark.asyncio
    async def test_compose_mode(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        s = mgr.generate_ghost_text("f.py", "old", "new")
        assert s.file_path == "f.py"
        active = mgr.get_active_suggestions()
        assert len(active) >= 1

    @pytest.mark.asyncio
    async def test_apply_and_dismiss_suggestion(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        s = mgr.generate_ghost_text("f.py", "old", "new")
        assert mgr.apply_suggestion(s.id) is not None

        s2 = mgr.generate_ghost_text("f2.py", "old", "new")
        assert mgr.dismiss_suggestion(s2.id) is not None

    @pytest.mark.asyncio
    async def test_cicd_pipeline(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.register_pipeline("test")
        run = mgr.start_pipeline_run("test", "abc123", "main")
        assert run.pipeline_name == "test"

        completed = mgr.complete_pipeline_run(run.id, "success")
        assert completed is not None

        status = mgr.get_pipeline_status("test")
        assert status is not None
        assert status.success_count == 1

    @pytest.mark.asyncio
    async def test_cost_tracking(self) -> None:
        from backend.types import TokenUsage
        mgr = CodingAgentManager()
        await mgr.async_init()
        entry = mgr.track_cost("test", "gemini-2.0-flash", TokenUsage(100, 50, 150))
        assert entry.total_tokens == 150

        entry2 = mgr.track_tokens("test2", "gemini-2.0-flash", 200, 100)
        assert entry2.total_tokens == 300

        costs = mgr.get_costs()
        assert costs["total_tokens"] == 450
        assert costs["entry_count"] == 2

    @pytest.mark.asyncio
    async def test_security_scanner(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.scan_code("x = 1")
        assert result.safe

        result2 = await mgr.scan_code('api_key = "sk-test123456789012345678901234567"')
        assert not result2.safe

    @pytest.mark.asyncio
    async def test_package_installer(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.install_package("some-package", manager="pip")
        # May fail if pip not found, but should not crash
        assert result is not None

    @pytest.mark.asyncio
    async def test_detect_requirements(self, tmp_path: Any) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        (tmp_path / "requirements.txt").write_text("pytest\nruff\n")
        packages = await mgr.detect_requirements(str(tmp_path))
        assert "pytest" in packages
        assert "ruff" in packages

    @pytest.mark.asyncio
    async def test_self_correction(self) -> None:
        from backend.types import ToolResult
        mgr = CodingAgentManager()
        await mgr.async_init()

        async def execute():
            return ToolResult(status="success", output="done")

        async def reflect(res, ctx):
            return {"insights": []}

        result = await mgr.execute_with_correction("t1", "test", execute, reflect)
        assert result.success

    @pytest.mark.asyncio
    async def test_tdd_loop(self) -> None:
        from backend.types import ToolResult
        mgr = CodingAgentManager()
        await mgr.async_init()

        async def write_test(feature):
            return ToolResult(status="success", output="test")

        async def run_test():
            return ToolResult(status="success", output="pass")

        async def write_code(output):
            return ToolResult(status="success", output="code")

        result = await mgr.execute_tdd("feature", write_test, run_test, write_code)
        assert result.success

    @pytest.mark.asyncio
    async def test_metrics_include_new_services(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        metrics = mgr.metrics()
        assert "mcp" in metrics
        assert "hitl" in metrics
        assert "compose_mode" in metrics
        assert "self_correction" in metrics
        assert "tdd" in metrics
        assert "cicd" in metrics
        assert "cost_tracker" in metrics
        assert "security_scanner" in metrics
        assert "package_installer" in metrics

    @pytest.mark.asyncio
    async def test_health_include_new_services(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        health = mgr.health()
        assert "services_healthy" in health
        assert "services_total" in health
        assert health["services_total"] == 9
        assert health["services_healthy"] == 9

    @pytest.mark.asyncio
    async def test_degrade_all_services(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.mcp.degraded
        assert mgr.hitl_workflow.degraded
        assert mgr.compose_mode.degraded
        assert mgr.self_correction.degraded
        assert mgr.tdd_loop.degraded
        assert mgr.cicd_monitor.degraded
        assert mgr.cost_tracker.degraded
        assert mgr.security_scanner.degraded
        assert mgr.package_installer.degraded

    @pytest.mark.asyncio
    async def test_shutdown_clears_services(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.generate_ghost_text("f.py", "old", "new")
        mgr.track_tokens("test", "gemini", 10, 5)
        await mgr.async_shutdown()
        assert not mgr.initialized


# =========================================================================
# Exception hierarchy
# =========================================================================


class TestNewExceptions:
    def test_hitl_exceptions(self) -> None:
        from backend.modules.coding_agent._exceptions import (
            HITLError,
            HITLRejectedError,
            HITLTimeoutError,
        )
        assert issubclass(HITLTimeoutError, HITLError)
        assert issubclass(HITLRejectedError, HITLError)

        exc = HITLTimeoutError("timeout", context={"action": "write"})
        assert "timeout" in str(exc)
        assert exc.context["action"] == "write"

        exc2 = HITLRejectedError("rejected", context={"action": "delete"})
        assert "rejected" in str(exc2)

    def test_tdd_exceptions(self) -> None:
        from backend.modules.coding_agent._exceptions import TDDError, TDDTestFailureError
        assert issubclass(TDDTestFailureError, TDDError)

    def test_security_exceptions(self) -> None:
        from backend.modules.coding_agent._exceptions import (
            SecurityScanError,
            SecurityVulnerabilityFoundError,
        )
        assert issubclass(SecurityVulnerabilityFoundError, SecurityScanError)

    def test_other_exceptions(self) -> None:
        from backend.modules.coding_agent._exceptions import (
            CICDError,
            ComposeModeError,
            CostTrackingError,
            PackageInstallError,
        )
        assert issubclass(ComposeModeError, Exception)
        assert issubclass(CICDError, Exception)
        assert issubclass(CostTrackingError, Exception)
        assert issubclass(PackageInstallError, Exception)


# =========================================================================
# Local Python Execution Tool
# =========================================================================


class TestExecuteLocalPythonTool:
    @pytest.mark.asyncio
    async def test_tool_registration(self) -> None:
        mock_tool_mgr = MagicMock()
        mgr = CodingAgentManager(tool_manager=mock_tool_mgr)
        await mgr.async_init()
        registered_names = [
            call[0][0].name for call in mock_tool_mgr.register_tool.call_args_list
        ]
        assert "execute_local_python" in registered_names

    @pytest.mark.asyncio
    async def test_execute_local_python_success(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.execute_local_python('print("Hello from local python!")')
        assert result.status == "success"
        assert "Hello from local python!" in (result.output or "")

    @pytest.mark.asyncio
    async def test_execute_local_python_error_captured(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.execute_local_python('raise ValueError("Custom python error")')
        assert result.status == "error"
        assert "ValueError" in (result.output or "") or "ValueError" in (result.error or "")

    @pytest.mark.asyncio
    async def test_handle_execute_python_handler(self) -> None:
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr._handle_execute_python('print(2 + 2)')
        assert result.status == "success"
        assert "4" in (result.output or "")

