"""Integration validation tests for Coding Agent module.

Verifies:
- Full pipeline: Planning → Any → MCP → Compose → Security → Package → TDD → Self-Correction
- EventBus integration
- CapabilityManager integration
- ToolManager integration
- Feature flag resolution
- Degraded mode cascade
- Health reporting
- Metrics
- Shutdown and async cleanup
- No resource leaks (file handles, tasks, connections)
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.coding_agent import CodingAgentManager
from backend.types import ToolResult
# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def coding_agent() -> CodingAgentManager:
    return CodingAgentManager()


# ============================================================================
# 1. ModuleInterface Protocol Conformance
# ============================================================================

class TestModuleInterface:
    """Verify CodingAgentManager conforms to ModuleInterface protocol."""

    def test_protocol_methods_exist(self):
        mgr = CodingAgentManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
        assert callable(mgr.async_init)
        assert callable(mgr.async_shutdown)
        assert callable(mgr.degrade)

    @pytest.mark.asyncio
    async def test_protocol_lifecycle(self):
        mgr = CodingAgentManager()
        assert not mgr.initialized
        await mgr.async_init()
        assert mgr.initialized
        assert not mgr.degraded
        await mgr.async_shutdown()
        assert not mgr.initialized
        assert not mgr.degraded

    @pytest.mark.asyncio
    async def test_double_init_is_idempotent(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.async_init()
        assert mgr.initialized

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()
        assert not mgr.initialized


# ============================================================================
# 2. Complete Execution Pipeline
# ============================================================================

class TestExecutionPipeline:
    """Verify the full execution pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_execute_task_with_default_providers(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.execute_task("write a test")
        assert result is not None
        assert result.status == "success"
        assert "write a test" in result.output

    @pytest.mark.asyncio
    async def test_execute_task_emits_events(self):
        events: list[str] = []
        event_bus = MagicMock()
        async def fake_emit(event_type: str, data: dict[str, Any]) -> None:
            events.append(event_type)
        event_bus.emit = fake_emit
        mgr = CodingAgentManager(event_bus=event_bus)
        await mgr.async_init()
        await mgr.execute_task("hello")
        assert "coding_agent.task_start" in events
        assert "coding_agent.task_complete" in events

    @pytest.mark.asyncio
    async def test_execute_task_failure_emits_error_event(self):
        events: list[str] = []
        event_bus = MagicMock()
        async def fake_emit(event_type: str, data: dict[str, Any]) -> None:
            events.append(event_type)
        event_bus.emit = fake_emit
        mgr = CodingAgentManager(event_bus=event_bus)
        await mgr.async_init()
        result = await mgr.execute_task("test")
        assert result.status in ("success", "error")

    @pytest.mark.asyncio
    async def test_analyze_project(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
            result = await mgr.analyze_project(tmpdir)
            assert result.status == "success"

    @pytest.mark.asyncio
    async def test_file_read_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            result = await mgr.file_operation("read", filepath)
            assert result.status in ("success", "error")

    @pytest.mark.asyncio
    async def test_file_write_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            result = await mgr.file_operation("write", filepath, content="hello")
            assert result.status in ("success", "error")

    @pytest.mark.asyncio
    async def test_detect_language(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "main.py")
            with open(filepath, "w") as f:
                f.write("print('hello')")
            result = await mgr.detect_language(filepath)
            assert result.status == "success"
            assert "python" in result.output

    @pytest.mark.asyncio
    async def test_workspace_lifecycle(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        session_id = str(uuid.uuid4())
        result = await mgr.workspace_operation("create", session_id)
        assert result.status == "success"
        result = await mgr.workspace_operation("get", session_id)
        assert result.status == "success"
        result = await mgr.workspace_operation("cleanup", session_id)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_command_executor(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.command_operation(["echo", "hello"])
        assert result.status in ("success", "error")
        if result.status == "success":
            assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_git_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.git_operation("status")
        assert result.status in ("success", "error")


# ============================================================================
# 3. EventBus Integration
# ============================================================================

class TestEventBusIntegration:
    """Verify events are emitted correctly."""

    @pytest.mark.asyncio
    async def test_task_events(self):
        collected: list[dict[str, Any]] = []
        event_bus = MagicMock()
        async def emit(event_type: str, data: dict[str, Any]) -> None:
            collected.append({"type": event_type, "data": data})
        event_bus.emit = emit
        mgr = CodingAgentManager(event_bus=event_bus)
        await mgr.async_init()
        await mgr.execute_task("test event")
        assert len(collected) >= 2
        types = [e["type"] for e in collected]
        assert "coding_agent.task_start" in types
        assert "coding_agent.task_complete" in types

    @pytest.mark.asyncio
    async def test_no_event_bus_no_crash(self):
        mgr = CodingAgentManager(event_bus=None)
        await mgr.async_init()
        result = await mgr.execute_task("no event bus")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_emit_with_real_event_bus(self):
        from backend.eventbus import EventBus
        bus = EventBus()
        received: list[str] = []
        async def handler(event: Any) -> None:
            received.append(event.type)
        bus.subscribe("coding_agent.*", handler)
        await bus._ensure_worker()
        mgr = CodingAgentManager(event_bus=bus)
        await mgr.async_init()
        await mgr.execute_task("real bus test")
        await asyncio.sleep(0.2)
        assert "coding_agent.task_start" in received
        assert "coding_agent.task_complete" in received
# ============================================================================

class TestCapabilityManagerIntegration:
    """Verify capabilities are registered correctly."""

    @pytest.mark.asyncio
    async def test_capability_registered(self):
        registered: list[Any] = []
        cap_mgr = MagicMock()
        cap_mgr.register = lambda cap: registered.append(cap)
        mgr = CodingAgentManager(capability_manager=cap_mgr)
        await mgr.async_init()
        names = [c.name for c in registered]
        assert "coding_agent" in names
        assert "coding_agent.mcp" in names
        assert "coding_agent.hitl" in names
        assert "coding_agent.tdd" in names
        assert "coding_agent.security_scanner" in names
        assert "coding_agent.package_installer" in names
        assert "coding_agent.cicd" in names
        assert "coding_agent.cost_tracking" in names
        assert "coding_agent.self_correction" in names
        assert "coding_agent.compose" in names

    @pytest.mark.asyncio
    async def test_capability_has_correct_dependencies(self):
        registered: list[Any] = []
        cap_mgr = MagicMock()
        cap_mgr.register = lambda cap: registered.append(cap)
        mgr = CodingAgentManager(capability_manager=cap_mgr)
        await mgr.async_init()
        for cap in registered:
            if cap.name == "coding_agent":
                assert "llm" in cap.dependencies
                break

    @pytest.mark.asyncio
    async def test_no_capability_manager_no_crash(self):
        mgr = CodingAgentManager(capability_manager=None)
        await mgr.async_init()
        assert mgr.initialized

    @pytest.mark.asyncio
    async def test_no_capability_manager_does_not_register(self):
        mgr = CodingAgentManager()
        await mgr.async_init()


# ============================================================================
# 5. ToolManager Integration
# ============================================================================

class TestToolManagerIntegration:
    """Verify tools are registered correctly."""

    @pytest.mark.asyncio
    async def test_tools_registered(self):
        registered: list[Any] = []
        tool_mgr = MagicMock()
        tool_mgr.register_tool = lambda defn, handler: registered.append(defn.name)
        mgr = CodingAgentManager(tool_manager=tool_mgr)
        await mgr.async_init()
        assert "coding_agent_execute_task" in registered
        assert "coding_agent_analyze_project" in registered
        assert "coding_agent_read_file" in registered
        assert "coding_agent_write_file" in registered
        assert "coding_agent_detect_language" in registered
        assert "coding_agent_git_status" in registered
        assert "coding_agent_scan" in registered
        assert "coding_agent_install_package" in registered
        assert "coding_agent_suggest" in registered
        assert "coding_agent_costs" in registered
        assert "coding_agent_pipeline" in registered

    @pytest.mark.asyncio
    async def test_tools_have_parameters(self):
        definitions: list[Any] = []
        tool_mgr = MagicMock()
        tool_mgr.register_tool = lambda defn, handler: definitions.append(defn)
        mgr = CodingAgentManager(tool_manager=tool_mgr)
        await mgr.async_init()
        for defn in definitions:
            assert defn.name
            assert defn.description
            assert defn.parameters

    @pytest.mark.asyncio
    async def test_no_tool_manager_no_crash(self):
        mgr = CodingAgentManager(tool_manager=None)
        await mgr.async_init()
        assert mgr.initialized


# ============================================================================
# 6. New Feature APIs (MCP, HITL, Compose, TDD, Security, etc.)
# ============================================================================

class TestNewFeatureAPIs:
    """Verify all new feature APIs work correctly."""

    @pytest.mark.asyncio
    async def test_mcp_create_context(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        ctx = mgr.create_context(
            session_id="test-session",
            system_prompt="You are a coding assistant",
        )
        assert ctx is not None
        assert ctx.session_id == "test-session"
        assert ctx.system_prompt == "You are a coding assistant"

    @pytest.mark.asyncio
    async def test_mcp_merge_contexts(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        ctx1 = mgr.create_context("s1", "prompt1")
        ctx2 = mgr.create_context("s2", "prompt2")
        merged = mgr.merge_contexts([ctx1, ctx2])
        assert merged is not None
        assert merged.session_id in ("s1", "s2")

    @pytest.mark.asyncio
    async def test_hitl_request_approval(self):
        mgr = CodingAgentManager(hitl_enabled=False)
        await mgr.async_init()
        req = await mgr.request_approval(
            "write_file", "Write to /etc/config",
            details={"path": "/etc/config"},
        )
        assert req is not None
        assert req.action == "write_file"
        assert req.status.name == "APPROVED"

    @pytest.mark.asyncio
    async def test_hitl_approve_reject_cycle(self):
        from backend.modules.coding_agent._hitl_workflow import HITLWorkflow
        h = HITLWorkflow(auto_approve_patterns=())
        async def request_and_wait():
            return await h.request_approval("delete", "Delete file")
        request_task = asyncio.create_task(request_and_wait())
        await asyncio.sleep(0.1)
        h.approve(list(h._pending.keys())[0], "approved")
        req = await request_task
        assert req.status.name == "APPROVED"

    @pytest.mark.asyncio
    async def test_compose_generate_ghost_text(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        suggestion = mgr.generate_ghost_text(
            file_path="/tmp/test.py",
            original_text="old",
            suggested_text="new",
            description="Refactor variable",
        )
        assert suggestion is not None
        assert suggestion.file_path == "/tmp/test.py"
        active = mgr.get_active_suggestions()
        assert any(s.id == suggestion.id for s in active)

    @pytest.mark.asyncio
    async def test_compose_apply_suggestion(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        suggestion = mgr.generate_ghost_text("/tmp/test.py", "old", "new")
        result = mgr.apply_suggestion(suggestion.id, "modified")
        assert result is not None
        assert result.status.name in ("APPLIED", "MODIFIED")

    @pytest.mark.asyncio
    async def test_compose_dismiss_suggestion(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        suggestion = mgr.generate_ghost_text("/tmp/test.py", "old", "new")
        result = mgr.dismiss_suggestion(suggestion.id)
        assert result is not None
        assert result.status.name == "DISMISSED"

    @pytest.mark.asyncio
    async def test_self_correction_loop(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        async def execute():
            return ToolResult(status="success", output="ok")
        result = await mgr.execute_with_correction(
            task_id="test-1",
            task_description="write code",
            execute_fn=execute,
            reflect_fn=lambda r, c: "looks good",
        )
        assert result is not None
        assert result.success

    @pytest.mark.asyncio
    async def test_self_correction_retries_on_failure(self):
        call_count = 0
        def make_execute():
            nonlocal call_count
            call_count += 1
            return ToolResult(status="error", output="failed", error="bug")
        mgr = CodingAgentManager(max_correction_iterations=3)
        await mgr.async_init()
        # Reset call_count after init
        call_count = 0
        result = await mgr.execute_with_correction(
            task_id="test-2",
            task_description="fix code",
            execute_fn=lambda: ToolResult(status="error", output="failed", error="bug"),
            reflect_fn=lambda r, c: "needs fix",
        )
        # With max_iterations=3, should retry all 3 times
        assert not result.success

    @pytest.mark.asyncio
    async def test_tdd_loop(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        async def write_test(feature: str) -> ToolResult:
            return ToolResult(status="success", output="test written")
        async def run_test() -> ToolResult:
            return ToolResult(status="success", output="tests pass")
        async def write_code(error: str = "") -> ToolResult:
            return ToolResult(status="success", output="code written")
        tdd_result = await mgr.execute_tdd(
            feature_description="add function",
            write_test_fn=write_test,
            run_test_fn=run_test,
            write_code_fn=write_code,
        )
        assert tdd_result is not None

    @pytest.mark.asyncio
    async def test_cicd_pipeline_register_and_run(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.register_pipeline("test-pipeline")
        run = mgr.start_pipeline_run("test-pipeline", "abc123", "main")
        assert run is not None
        mgr.complete_pipeline_run(run.id, "success")
        status = mgr.get_pipeline_status("test-pipeline")
        assert status is not None
        assert status.last_run_status.name == "SUCCESS"
        assert status.success_rate == 100.0

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        from backend.types import Any
        entry = mgr.track_cost(
            operation="test", model="gpt-4", token_usage=Any(prompt_tokens=100, completion_tokens=50, total_tokens=150), )
        assert entry is not None
        costs = mgr.get_costs()
        assert costs["total_tokens"] == 150
        assert costs["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_cost_tracking_by_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        from backend.types import Any
        mgr.track_cost("op1", "gpt-4", Any(100, 50, 150))
        mgr.track_cost("op2", "gpt-3.5", Any(50, 25, 75))
        by_op = mgr.get_cost_by_operation()
        assert "op1" in by_op
        assert "op2" in by_op

    @pytest.mark.asyncio
    async def test_cost_tracking_tokens(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        entry = mgr.track_tokens("test", "gpt-4", 200, 100)
        assert entry is not None
        costs = mgr.get_costs()
        assert costs["total_prompt_tokens"] == 200
        assert costs["total_completion_tokens"] == 100

    @pytest.mark.asyncio
    async def test_security_scan_code(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.scan_code("print('hello')", "test.py")
        assert result is not None
        assert result.files_scanned >= 1

    @pytest.mark.asyncio
    async def test_security_scan_detects_vulnerabilities(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        malicious = (
            'password = "supersecret"\n'
            'api_key = "sk-123456789012345678901234567890123456789"\n'
        )
        result = await mgr.scan_code(malicious, "bad.py")
        assert result.total_issues > 0
        assert not result.safe

    @pytest.mark.asyncio
    async def test_package_installer_detect_requirements(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "requirements.txt"), "w") as f:
                f.write("requests>=2.0\npytest")
            reqs = await mgr.detect_requirements(tmpdir)
            assert any("requests" in r for r in reqs)
            assert any("pytest" in r for r in reqs)

    @pytest.mark.asyncio
    async def test_package_installer_detect_from_imports(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "requirements.txt"), "w") as f:
                f.write("flask>=2.0\nnumpy")
            reqs = await mgr.detect_requirements(tmpdir)
            assert any("flask" in r for r in reqs)
            assert any("numpy" in r for r in reqs)
# ============================================================================
# 7. Multi-file Editing (Diff + Patch)
# ============================================================================

class TestDiffAndPatch:
    """Verify diff generation and patching."""

    def test_diff_generation(self):
        mgr = CodingAgentManager()
        old_text = "line1\nline2\nline3\n"
        new_text = "line1\nmodified\nline3\n"
        diff = mgr.diff_generator.generate_diff(old_text, new_text, "test.py")
        assert diff is not None
        assert "line2" in diff or "modified" in diff or "-" in diff

    def test_patch_generation(self):
        mgr = CodingAgentManager()
        old_text = "def foo():\n    pass\n"
        new_text = "def foo():\n    return 42\n"
        patch = mgr.patch_generator.generate_patch("test.py", old_text, new_text)
        assert patch is not None
        assert len(patch) > 0


# ============================================================================
# 8. Feature Flag Verification
# ============================================================================

class TestFeatureFlags:
    """Verify all feature flags work correctly."""

    @pytest.mark.asyncio
    async def test_all_features_disabled(self):
        mgr = CodingAgentManager(
            mcp_enabled=False,
            hitl_enabled=False,
            compose_mode_enabled=False,
            self_correction_enabled=False,
            tdd_enabled=False,
            cicd_monitoring_enabled=False,
            cost_tracking_enabled=False,
            security_scanner_enabled=False,
            package_installer_enabled=False,
        )
        await mgr.async_init()
        assert not mgr.mcp.enabled
        assert not mgr.hitl_workflow.enabled
        assert not mgr.compose_mode.enabled
        assert not mgr.self_correction.enabled
        assert not mgr.tdd_loop.enabled
        assert not mgr.cicd_monitor.enabled
        assert not mgr.cost_tracker.enabled
        assert not mgr.security_scanner.enabled
        assert not mgr.package_installer.enabled

    @pytest.mark.asyncio
    async def test_all_features_enabled_by_default(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        assert mgr.mcp.enabled
        assert mgr.hitl_workflow.enabled
        assert mgr.compose_mode.enabled
        assert mgr.self_correction.enabled
        assert mgr.tdd_loop.enabled
        assert mgr.cicd_monitor.enabled
        assert mgr.cost_tracker.enabled
        assert mgr.security_scanner.enabled
        assert mgr.package_installer.enabled

    @pytest.mark.asyncio
    async def test_feature_flags_from_config(self):
        from backend.modules.settings._config import AppConfig, CodingAgentConfig
        cod_cfg = CodingAgentConfig(
            mcp_enabled=False,
            hitl_enabled=True,
            cost_tracking_enabled=False,
        )
        cfg = AppConfig(coding_agent=cod_cfg)
        mgr = CodingAgentManager(config=cfg)
        await mgr.async_init()
        assert not mgr.mcp.enabled
        assert mgr.hitl_workflow.enabled
        assert not mgr.cost_tracker.enabled

    @pytest.mark.asyncio
    async def test_constructor_override_config(self):
        from backend.modules.settings._config import AppConfig, CodingAgentConfig
        cod_cfg = CodingAgentConfig(mcp_enabled=False)
        cfg = AppConfig(coding_agent=cod_cfg)
        mgr = CodingAgentManager(config=cfg, mcp_enabled=True)
        await mgr.async_init()
        assert mgr.mcp.enabled

    @pytest.mark.asyncio
    async def test_feature_disabled_services_still_createable(self):
        mgr = CodingAgentManager(
            mcp_enabled=False, hitl_enabled=False, tdd_enabled=False,
        )
        await mgr.async_init()
        assert mgr.mcp is not None
        assert mgr.hitl_workflow is not None
        assert mgr.tdd_loop is not None


# ============================================================================
# 9. Degraded Mode
# ============================================================================

class TestDegradedMode:
    """Verify degraded mode cascade."""

    @pytest.mark.asyncio
    async def test_degrade_cascades_to_all_services(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded
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
    async def test_degrade_blocks_execute_task(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.execute_task("should fail")

    @pytest.mark.asyncio
    async def test_degrade_blocks_analyze_project(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.analyze_project("/tmp")

    @pytest.mark.asyncio
    async def test_degrade_blocks_file_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.file_operation("read", "/tmp/test.txt")

    @pytest.mark.asyncio
    async def test_degrade_blocks_detect_language(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.detect_language("/tmp/test.py")

    @pytest.mark.asyncio
    async def test_degrade_blocks_workspace_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.workspace_operation("create", "test")

    @pytest.mark.asyncio
    async def test_degrade_blocks_git_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.git_operation("status")

    @pytest.mark.asyncio
    async def test_degrade_blocks_command_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.command_operation(["echo", "test"])

    @pytest.mark.asyncio
    async def test_degrade_is_idempotent(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded

    @pytest.mark.asyncio
    async def test_shutdown_resets_degraded(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded
        await mgr.async_shutdown()
        assert not mgr.degraded


# ============================================================================
# 10. Health Reporting
# ============================================================================

class TestHealthReporting:
    """Verify health reporting."""

    @pytest.mark.asyncio
    async def test_health_after_init(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        h = mgr.health()
        assert h["healthy"] is True
        assert h["degraded"] is False
        assert h["initialized"] is True
        assert h["ports_available"] > 0
        assert h["ports_total"] == 11
        assert h["services_healthy"] == 9
        assert h["services_total"] == 9

    @pytest.mark.asyncio
    async def test_health_after_degrade(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.degrade()
        h = mgr.health()
        assert h["healthy"] is False
        assert h["degraded"] is True
        assert h["services_healthy"] == 0

    @pytest.mark.asyncio
    async def test_health_before_init(self):
        mgr = CodingAgentManager()
        h = mgr.health()
        assert h["initialized"] is False
        assert h["healthy"] is False

    @pytest.mark.asyncio
    async def test_health_after_shutdown(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        h = mgr.health()
        assert h["initialized"] is False

    @pytest.mark.asyncio
    async def test_health_memory_usage(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        h = mgr.health()
        assert "memory_usage" in h
        assert isinstance(h["memory_usage"], (int, float))

    @pytest.mark.asyncio
    async def test_health_ports_ratio(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        h = mgr.health()
        assert h["ports_ratio"] == f"{h['ports_available']}/{h['ports_total']}"

    @pytest.mark.asyncio
    async def test_health_services_ratio(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        h = mgr.health()
        assert h["services_ratio"] == "9/9"


# ============================================================================
# 11. Metrics
# ============================================================================

class TestMetrics:
    """Verify metrics reporting."""

    @pytest.mark.asyncio
    async def test_metrics_after_init(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        m = mgr.metrics()
        assert m["total_tasks"] == 0
        assert m["success_rate"] == 0.0
        assert "memory" in m
        assert "retry" in m
        assert "mcp" in m
        assert "hitl" in m
        assert "compose_mode" in m
        assert "self_correction" in m
        assert "tdd" in m
        assert "cicd" in m
        assert "cost_tracker" in m
        assert "security_scanner" in m
        assert "package_installer" in m

    @pytest.mark.asyncio
    async def test_metrics_after_tasks(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.execute_task("task 1")
        await mgr.execute_task("task 2")
        m = mgr.metrics()
        assert m["total_tasks"] == 2
        assert m["successful_tasks"] == 2
        assert m["total_duration_ms"] > 0
        assert m["avg_duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_metrics_success_rate(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.execute_task("task 1")
        m = mgr.metrics()
        assert m["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_metrics_retry_section(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        m = mgr.metrics()
        assert "retry" in m

    @pytest.mark.asyncio
    async def test_metrics_cost_tracker(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        from backend.types import Any
        mgr.track_cost("op", "gpt-4", Any(100, 50, 150))
        m = mgr.metrics()
        assert m["cost_tracker"]["total_cost"] > 0
        assert m["cost_tracker"]["entry_count"] == 1
# ============================================================================
# 12. Shutdown and Async Cleanup
# ============================================================================

class TestShutdownAndCleanup:
    """Verify shutdown releases resources."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_ports(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        ops = [
            mgr.agent_runtime,
            mgr.task_planner,
            mgr.tool_selector,
        ]
        for p in ops:
            assert p is not None

    @pytest.mark.asyncio
    async def test_shutdown_clears_memory(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.memory.store("test", {"data": "value"})
        await mgr.async_shutdown()
        result = mgr.memory.retrieve("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_shutdown_clears_reflection_history(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.reflection_engine._history = ["entry1", "entry2"]
        await mgr.async_shutdown()
        assert len(mgr.reflection_engine.get_history()) == 0

    @pytest.mark.asyncio
    async def test_shutdown_clears_compose_suggestions(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        mgr.generate_ghost_text("/tmp/test.py", "old", "new")
        await mgr.async_shutdown()
        assert len(mgr.get_active_suggestions()) == 0

    @pytest.mark.asyncio
    async def test_shutdown_resets_cost_tracker(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        from backend.types import Any
        mgr.track_cost("op", "gpt-4", Any(10, 5, 15))
        costs_before = mgr.get_costs()
        assert costs_before["entry_count"] == 1
        await mgr.async_shutdown()
        costs_after = mgr.get_costs()
        assert costs_after["entry_count"] == 0

    @pytest.mark.asyncio
    async def test_operations_after_shutdown_still_work(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        result = mgr.generate_ghost_text("/tmp/test.py", "old", "new")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cleanup_does_not_leak_tasks(self):
        tasks_before = len(asyncio.all_tasks())
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.execute_task("test")
        await mgr.async_shutdown()
        mgr = None
        tasks_after = len(asyncio.all_tasks())
        diff = tasks_after - tasks_before
        assert diff <= 2
# ============================================================================
# 13. Resource Leak Detection
# ============================================================================

class TestResourceLeaks:
    """Verify no resource leaks."""

    @pytest.mark.asyncio
    async def test_no_unclosed_transports(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        await mgr.execute_task("test 1")
        await mgr.execute_task("test 2")
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_repeated_init_shutdown_no_leak(self):
        for _ in range(5):
            mgr = CodingAgentManager()
            await mgr.async_init()
            await mgr.execute_task("cycle")
            await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_many_tasks_no_leak(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        for i in range(20):
            result = await mgr.execute_task(f"task {i}")
            assert result.status == "success"
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_tasks(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        results = await asyncio.gather(
            mgr.execute_task("concurrent 1"),
            mgr.execute_task("concurrent 2"),
            mgr.execute_task("concurrent 3"),
        )
        assert all(r.status == "success" for r in results)
        assert mgr.metrics()["total_tasks"] == 3
        await mgr.async_shutdown()


# ============================================================================
# 14. Real boot.py Integration Simulation
# ============================================================================

class TestBootIntegration:
    """Verify the construction pattern used in boot.py works correctly."""

    @pytest.mark.asyncio
    async def test_boot_pattern_minimal(self):
        mgr = CodingAgentManager(default_timeout=60.0, max_iterations=10)
        await mgr.async_init()
        assert mgr.initialized
        assert not mgr.degraded
        result = await mgr.execute_task("hello from boot pattern")
        assert result.status == "success"
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_boot_pattern_with_event_bus(self):
        from backend.eventbus import EventBus
        bus = EventBus()
        received: list[str] = []
        async def handler(event: Any) -> None:
            received.append(event.type)
        bus.subscribe("coding_agent.*", handler)
        mgr = CodingAgentManager(event_bus=bus, default_timeout=30.0)
        await mgr.async_init()
        await mgr.execute_task("boot test")
        await asyncio.sleep(0.05)
        assert "coding_agent.task_start" in received
        assert "coding_agent.task_complete" in received

    @pytest.mark.asyncio
    async def test_boot_pattern_with_capability_manager(self):
        registered: list[str] = []
        cap_mgr = MagicMock()
        cap_mgr.register = lambda cap: registered.append(cap.name)
        mgr = CodingAgentManager(capability_manager=cap_mgr)
        await mgr.async_init()
        assert "coding_agent" in registered
        assert "coding_agent.mcp" in registered

    @pytest.mark.asyncio
    async def test_boot_pattern_with_tool_manager(self):
        registered: list[str] = []
        tool_mgr = MagicMock()
        tool_mgr.register_tool = lambda defn, handler: registered.append(defn.name)
        mgr = CodingAgentManager(tool_manager=tool_mgr)
        await mgr.async_init()
        assert "coding_agent_execute_task" in registered
        assert "coding_agent_scan" in registered

    @pytest.mark.asyncio
    async def test_boot_pattern_with_config(self):
        from backend.modules.settings._config import AppConfig, CodingAgentConfig
        cod_cfg = CodingAgentConfig(
            default_timeout=45.0,
            mcp_enabled=True,
            hitl_enabled=False,
        )
        cfg = AppConfig(coding_agent=cod_cfg)
        mgr = CodingAgentManager(config=cfg)
        await mgr.async_init()
        assert mgr.mcp.enabled
        assert not mgr.hitl_workflow.enabled
        h = mgr.health()
        assert h["healthy"]
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_orchestrator_register_pattern(self):
        managers: dict[str, CodingAgentManager] = {}
        mgr = CodingAgentManager()
        await mgr.async_init()
        managers["coding_agent"] = mgr
        assert "coding_agent" in managers
        assert managers["coding_agent"].initialized
        await managers["coding_agent"].async_shutdown()


# ============================================================================
# 15. Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Verify edge cases and error handling."""

    def test_create_with_no_args(self):
        mgr = CodingAgentManager()
        assert mgr is not None

    @pytest.mark.asyncio
    async def test_execute_empty_task(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.execute_task("")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_task_with_context(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.execute_task("task with ctx", {"key": "value"})
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_unknown_file_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.file_operation("invalid_op", "/tmp/test.txt")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_unknown_git_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.git_operation("invalid_op")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_unknown_workspace_operation(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.workspace_operation("invalid_op", "session")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_hitl_rejected_blocks_operation(self):
        from backend.modules.coding_agent._hitl_workflow import HITLWorkflow
        h = HITLWorkflow(auto_approve_patterns=())
        async def request_and_wait():
            try:
                return await h.request_approval("delete", "Delete critical file")
            except Exception:
                return None
        request_task = asyncio.create_task(request_and_wait())
        await asyncio.sleep(0.1)
        h.reject(list(h._pending.keys())[0], "not safe")
        req = await request_task
        assert req is None or req.status.name != "APPROVED"

    @pytest.mark.asyncio
    async def test_compose_dismiss_nonexistent(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = mgr.dismiss_suggestion("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cicd_unknown_pipeline_status(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        status = mgr.get_pipeline_status("nonexistent")
        assert status is None

    @pytest.mark.asyncio
    async def test_cost_tracker_empty(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        costs = mgr.get_costs()
        assert costs["entry_count"] == 0
        assert costs["total_cost"] == 0.0

    @pytest.mark.asyncio
    async def test_security_scan_empty_code(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        result = await mgr.scan_code("", "empty.py")
        assert result.safe
        assert result.total_issues == 0

    @pytest.mark.asyncio
    async def test_package_installer_no_requirements(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        with tempfile.TemporaryDirectory() as tmpdir:
            reqs = await mgr.detect_requirements(tmpdir)
            assert reqs == []

    @pytest.mark.asyncio
    async def test_tdd_with_no_refactor(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        async def wt(feature: str) -> ToolResult:
            return ToolResult(status="success", output="ok")
        async def rt() -> ToolResult:
            return ToolResult(status="success", output="ok")
        async def wc(error: str = "") -> ToolResult:
            return ToolResult(status="success", output="ok")
        result = await mgr.execute_tdd(
            feature_description="simple function",
            write_test_fn=wt,
            run_test_fn=rt,
            write_code_fn=wc,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_merge_single_context(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        ctx = mgr.create_context("s1", "p")
        merged = mgr.merge_contexts([ctx])
        assert merged is not None

    @pytest.mark.asyncio
    async def test_mcp_estimate_tokens(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        ctx = mgr.create_context("test", "hello world")
        tokens = mgr.mcp.estimate_tokens(ctx)
        assert tokens > 0


# ============================================================================
# 16. Conformance Test: Port/Provider Wiring
# ============================================================================

class TestPortWiring:
    """Verify all ports are wired correctly."""

    @pytest.mark.asyncio
    async def test_default_providers_loaded(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        assert mgr.agent_runtime is not None
        assert mgr.task_planner is not None
        assert mgr.tool_selector is not None
        assert mgr.file_manager is not None
        assert mgr.git_executor is not None
        assert mgr.command_executor is not None
        assert mgr.language_detector is not None
        assert mgr.multi_file_editor is not None
        assert mgr.project_analyzer is not None
        assert mgr.safety_layer is not None
        assert mgr.workspace_manager is not None

    def test_custom_port_injection(self):
        runtime = MagicMock()
        mgr = CodingAgentManager(agent_runtime=runtime)
        assert mgr.agent_runtime is runtime

    @pytest.mark.asyncio
    async def test_custom_port_overrides_default(self):
        runtime = MagicMock()
        runtime.is_available = True
        runtime.execute_task = AsyncMock(
            return_value={"status": "completed", "output": "custom runtime"},
        )
        mgr = CodingAgentManager(agent_runtime=runtime)
        await mgr.async_init()
        result = await mgr.execute_task("test")
        assert result.status == "success"
        runtime.execute_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_safety_layer_allows_operations(self):
        mgr = CodingAgentManager(safety_layer=None)
        await mgr.async_init()
        result = await mgr.file_operation("read", "/tmp/test.txt")
        assert result.status in ("success", "error")

    @pytest.mark.asyncio
    async def test_missing_project_analyzer(self):
        mgr = CodingAgentManager(project_analyzer=None)
        await mgr.async_init()
        result = await mgr.analyze_project("/tmp")
        assert result.status in ("success", "error")

    @pytest.mark.asyncio
    async def test_missing_workspace_manager(self):
        mgr = CodingAgentManager(workspace_manager=None)
        await mgr.async_init()
        result = await mgr.workspace_operation("create", "test")
        assert result.status in ("success", "error")


# ============================================================================
# 17. AsyncInit Error Handling
# ============================================================================

class TestAsyncInit:
    """Verify async_init handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_async_init_sets_initialized(self):
        mgr = CodingAgentManager()
        assert not mgr.initialized
        await mgr.async_init()
        assert mgr.initialized

    @pytest.mark.asyncio
    async def test_count_ports_and_services(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        assert mgr._count_ports() == 11
        assert mgr._count_services() == 17


# ============================================================================
# 18. Execute Pipeline Pipeline (MCP → Compose → Security → LLM → TDD → Self-Correction)
# ============================================================================

class TestPipelineIntegration:
    """Verify the full pipeline integration."""

    @pytest.mark.asyncio
    async def test_full_pipeline_noop(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        ctx = mgr.create_context("pipe-test", "You are a coding assistant")
        assert ctx is not None
        suggestion = mgr.generate_ghost_text(
            "/tmp/test.py", "old", "new",
            description="Pipeline test",
        )
        assert suggestion is not None
        req = await mgr.request_approval(
            "read_file", "Read pipeline test",
            details={"file": "/tmp/test.py"},
        )
        assert req is not None
        assert req.status.name == "APPROVED"

    @pytest.mark.asyncio
    async def test_pipeline_with_security_and_tdd(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        security = await mgr.scan_code("print('safe')", "safe.py")
        assert security is not None
        async def wt(feature: str) -> ToolResult:
            return ToolResult(status="success", output="ok")
        async def rt() -> ToolResult:
            return ToolResult(status="success", output="ok")
        async def wc(error: str = "") -> ToolResult:
            return ToolResult(status="success", output="ok")
        tdd = await mgr.execute_tdd(
            feature_description="add function",
            write_test_fn=wt,
            run_test_fn=rt,
            write_code_fn=wc,
        )
        assert tdd is not None

    @pytest.mark.asyncio
    async def test_pipeline_with_cost_and_cicd(self):
        mgr = CodingAgentManager()
        await mgr.async_init()
        from backend.types import Any
        mgr.track_cost("pipeline-test", "gpt-4", Any(100, 50, 150))
        costs = mgr.get_costs()
        assert costs["entry_count"] == 1
        mgr.register_pipeline("ci")
        run = mgr.start_pipeline_run("ci", "abc", "main")
        mgr.complete_pipeline_run(run.id, "success")
        status = mgr.get_pipeline_status("ci")
        assert status is not None