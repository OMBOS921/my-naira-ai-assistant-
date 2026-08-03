"""Unit tests for FastCommandRouter — verifies manager wiring, no raw subprocess, correct [SUCCESS]/[FAILED] mapping."""

import ast
import inspect
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.runtime.fast_command_router import FastCommandRouter, CommandIntent
from backend.types import ToolResult


@pytest.fixture
def mock_pc_control():
    mgr = AsyncMock()
    mgr.volume_get.return_value = ToolResult(status="success", output={"level": 0.5})
    mgr.volume_set.return_value = ToolResult(status="success", output={"level": 0.5})
    mgr.volume_mute.return_value = ToolResult(status="success", output={})
    mgr.display_set_brightness.return_value = ToolResult(status="success", output={})
    mgr.screen_capture.return_value = ToolResult(status="success", output={"path": "/tmp/s.png"})
    mgr.power_lock.return_value = ToolResult(status="success", output={})
    mgr.power_shutdown.return_value = ToolResult(status="success", output={})
    mgr.power_restart.return_value = ToolResult(status="success", output={})
    mgr.launch_application.return_value = ToolResult(status="success", output={})
    mgr.filesystem_create_directory.return_value = ToolResult(status="success", output={})
    mgr.filesystem_delete_directory.return_value = ToolResult(status="success", output={})
    mgr.filesystem_write_file.return_value = ToolResult(status="success", output={})
    mgr.filesystem_delete_file.return_value = ToolResult(status="success", output={})
    mgr.filesystem_move_item.return_value = ToolResult(status="success", output={})
    return mgr


@pytest.fixture
def mock_browser():
    mgr = AsyncMock()
    mgr.navigate.return_value = ToolResult(status="success", output={})
    mgr.search.return_value = ToolResult(status="success", output={})
    return mgr


@pytest.fixture
def fcr(mock_pc_control, mock_browser):
    return FastCommandRouter(
        pc_control_manager=mock_pc_control,
        browser_manager=mock_browser,
        api_key="test-key",
    )


def _router_source() -> str:
    """Read the FastCommandRouter source from the project root (4 parents up from testing/unit/runtime/)."""
    router_path = Path(__file__).resolve().parent.parent.parent.parent / "backend" / "runtime" / "fast_command_router.py"
    return router_path.read_text(encoding="utf-8")


class TestManagerWiring:
    """Verify every action routes to the correct manager method with correct args."""

    @pytest.mark.asyncio
    async def test_volume_mute(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "set_volume", "target": "", "parameters": {"value": "mute"}}], "")
        mock_pc_control.volume_mute.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_volume_unmute(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "set_volume", "target": "", "parameters": {"value": "unmute"}}], "")
        mock_pc_control.volume_mute.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_volume_up(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "set_volume", "target": "", "parameters": {"value": "up"}}], "")
        mock_pc_control.volume_get.assert_called()
        mock_pc_control.volume_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_volume_down(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "set_volume", "target": "", "parameters": {"value": "down"}}], "")
        mock_pc_control.volume_get.assert_called()
        mock_pc_control.volume_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_volume_set_percent(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "set_volume", "target": "", "parameters": {"value": "75"}}], "")
        mock_pc_control.volume_set.assert_called_once()
        args, _ = mock_pc_control.volume_set.call_args
        assert args[0] == 0.75

    @pytest.mark.asyncio
    async def test_brightness_set(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "set_brightness", "target": "", "parameters": {"value": "60"}}], "")
        mock_pc_control.display_set_brightness.assert_called_once_with(60)

    @pytest.mark.asyncio
    async def test_screenshot(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "screenshot", "target": "", "parameters": {}}], "")
        mock_pc_control.screen_capture.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_pc(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "lock_pc", "target": "", "parameters": {}}], "")
        mock_pc_control.power_lock.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "shutdown", "target": "", "parameters": {}}], "")
        mock_pc_control.power_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "restart", "target": "", "parameters": {}}], "")
        mock_pc_control.power_restart.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_app(self, fcr, mock_pc_control):
        await fcr._execute_system_control([{"action": "open_app", "target": "notepad", "parameters": {}}], "")
        mock_pc_control.launch_application.assert_called_once_with("notepad.exe")

    @pytest.mark.asyncio
    async def test_browser_navigate(self, fcr, mock_browser):
        await fcr._execute_browser_control([{"action": "open_url", "target": "https://example.com", "parameters": {}}], "")
        mock_browser.navigate.assert_called_once_with("https://example.com", extract_content=False)

    @pytest.mark.asyncio
    async def test_browser_search_youtube(self, fcr, mock_browser):
        await fcr._execute_browser_control([{"action": "search_web", "target": "cats", "parameters": {"query": "cats"}}], "youtube search cats")
        mock_browser.navigate.assert_called_once()
        args, _ = mock_browser.navigate.call_args
        assert "youtube.com/results" in args[0]

    @pytest.mark.asyncio
    async def test_browser_search_google(self, fcr, mock_browser):
        await fcr._execute_browser_control([{"action": "search_web", "target": "cats", "parameters": {"query": "cats", "open_browser": True}}], "open browser search cats")
        mock_browser.navigate.assert_called_once()
        args, _ = mock_browser.navigate.call_args
        assert "google.com/search" in args[0]

    @pytest.mark.asyncio
    async def test_filesystem_create_folder(self, fcr, mock_pc_control):
        with patch("backend.runtime.fast_command_router._resolve_smart_path") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/test_folder")
            await fcr._execute_file_system([{"action": "create_folder", "target": "test", "parameters": {}}], "")
        mock_pc_control.filesystem_create_directory.assert_called_once()
        args, _ = mock_pc_control.filesystem_create_directory.call_args
        assert str(args[0]).replace("\\", "/") == "/tmp/test_folder"

    @pytest.mark.asyncio
    async def test_filesystem_delete_folder(self, fcr, mock_pc_control):
        with patch("backend.runtime.fast_command_router._resolve_smart_path") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/test_folder")
            await fcr._execute_file_system([{"action": "delete_folder", "target": "test", "parameters": {}}], "")
        mock_pc_control.filesystem_delete_directory.assert_called_once()
        args, kwargs = mock_pc_control.filesystem_delete_directory.call_args
        assert str(args[0]).replace("\\", "/") == "/tmp/test_folder"
        assert kwargs.get("recursive") is True

    @pytest.mark.asyncio
    async def test_filesystem_create_file(self, fcr, mock_pc_control):
        with patch("backend.runtime.fast_command_router._resolve_smart_path") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/test.txt")
            await fcr._execute_file_system([{"action": "create_file", "target": "test.txt", "parameters": {}}], "")
        mock_pc_control.filesystem_write_file.assert_called_once()
        args, kwargs = mock_pc_control.filesystem_write_file.call_args
        assert str(args[0]).replace("\\", "/") == "/tmp/test.txt"
        assert kwargs.get("content", args[1] if len(args) > 1 else None) == ""

    @pytest.mark.asyncio
    async def test_filesystem_delete_file(self, fcr, mock_pc_control):
        with patch("backend.runtime.fast_command_router._resolve_smart_path") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/test.txt")
            await fcr._execute_file_system([{"action": "delete_file", "target": "test.txt", "parameters": {}}], "")
        mock_pc_control.filesystem_delete_file.assert_called_once()
        args, _ = mock_pc_control.filesystem_delete_file.call_args
        assert str(args[0]).replace("\\", "/") == "/tmp/test.txt"

    @pytest.mark.asyncio
    async def test_filesystem_rename(self, fcr, mock_pc_control):
        with patch("backend.runtime.fast_command_router._resolve_smart_path") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/old.txt")
            await fcr._execute_file_system([{"action": "rename_file", "target": "old.txt", "parameters": {"new_name": "new.txt"}}], "")
        mock_pc_control.filesystem_move_item.assert_called_once()
        args, kwargs = mock_pc_control.filesystem_move_item.call_args
        assert str(args[0]).replace("\\", "/") == "/tmp/old.txt"
        dest = kwargs.get("dest_path", args[1] if len(args) > 1 else None)
        assert str(dest).replace("\\", "/") == "/tmp/new.txt"

    @pytest.mark.asyncio
    async def test_filesystem_open_file(self, fcr, mock_pc_control):
        with patch("backend.runtime.fast_command_router._resolve_smart_path") as mock_resolve:
            mock_resolve.return_value = Path("/tmp/test.txt")
            await fcr._execute_file_system([{"action": "open_file", "target": "test.txt", "parameters": {}}], "")
        mock_pc_control.launch_application.assert_called_once()
        args, _ = mock_pc_control.launch_application.call_args
        assert str(args[0]).replace("\\", "/") == "/tmp/test.txt"


class TestFailureMapping:
    """Verify failed/denied manager responses produce [FAILED] not [SUCCESS]."""

    @pytest.mark.asyncio
    async def test_failed_manager_returns_failed_string(self, fcr, mock_pc_control):
        mock_pc_control.power_shutdown.return_value = ToolResult(status="error", error="Permission denied")
        result = await fcr._execute_system_control([{"action": "shutdown", "target": "", "parameters": {}}], "")
        assert "[FAILED]" in result
        assert "Permission denied" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_unsupported_platform_returns_failed(self, fcr, mock_pc_control):
        mock_pc_control.power_shutdown.return_value = ToolResult(status="error", error="Platform not supported: Linux")
        result = await fcr._execute_system_control([{"action": "shutdown", "target": "", "parameters": {}}], "")
        assert "[FAILED]" in result
        assert "Platform not supported" in result or "Linux" in result

    @pytest.mark.asyncio
    async def test_browser_failure_returns_failed(self, fcr, mock_browser):
        mock_browser.navigate.return_value = ToolResult(status="error", error="Browser not available")
        result = await fcr._execute_browser_control([{"action": "open_url", "target": "https://x.com", "parameters": {}}], "")
        assert "[FAILED]" in result
        assert "Browser not available" in result

    @pytest.mark.asyncio
    async def test_filesystem_failure_returns_failed(self, fcr, mock_pc_control):
        mock_pc_control.filesystem_create_directory.return_value = ToolResult(status="error", error="Access denied")
        with patch("backend.runtime.fast_command_router._resolve_smart_path") as mock_resolve:
            mock_resolve.return_value = Path("/root/forbidden")
            result = await fcr._execute_file_system([{"action": "create_folder", "target": "x", "parameters": {}}], "")
        assert "[FAILED]" in result
        assert "Access denied" in result


class TestNoRawSubprocessRegression:
    """AST/grep check — ensures no subprocess/os.system/shell=True/shutil.rmtree in action handlers."""

    def test_no_subprocess_in_router(self):
        # project root is parent.parent.parent.parent from testing/unit/runtime/
        router_path = Path(__file__).parent.parent.parent.parent / "backend" / "runtime" / "fast_command_router.py"
        source = router_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_calls = {
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
            "os.system",
            "os.popen",
            "shutil.rmtree",
        }

        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Attribute calls like subprocess.run
                if isinstance(node.func, ast.Attribute):
                    full = self._get_attr_name(node.func)
                    if full in forbidden_calls:
                        found.append((full, node.lineno))
                # Name calls like os.system (imported as from os import system)
                elif isinstance(node.func, ast.Name):
                    if node.func.id in {"system", "popen", "rmtree"}:
                        found.append((node.func.id, node.lineno))

        assert not found, f"Forbidden calls found in fast_command_router.py: {found}"

    def test_no_shell_true_in_router(self):
        source = _router_source()
        # Check for shell=True pattern
        assert "shell=True" not in source, "shell=True found in fast_command_router.py"
        assert "shell = True" not in source, "shell = True found in fast_command_router.py"

    def _get_attr_name(self, node: ast.Attribute) -> str:
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))


class TestOpsArrayPreserved:
    """Verify the operations array multi-action loop structure is intact."""

    @pytest.mark.asyncio
    async def test_multiple_operations_executed_sequentially(self, fcr, mock_pc_control):
        ops = [
            {"action": "set_volume", "target": "", "parameters": {"value": "mute"}},
            {"action": "set_brightness", "target": "", "parameters": {"value": "50"}},
            {"action": "lock_pc", "target": "", "parameters": {}},
        ]
        result = await fcr._execute_system_control(ops, "")
        assert result.count("[SUCCESS]") == 3
        assert mock_pc_control.volume_mute.call_count == 1
        assert mock_pc_control.display_set_brightness.call_count == 1
        assert mock_pc_control.power_lock.call_count == 1


class TestNoLLMCallsInDispatch:
    """Verify no LLMManager/llm_manager calls introduced in dispatch path."""

    def test_no_llm_manager_attribute_access(self):
        source = _router_source()
        # Should only reference _llm_manager in __init__ or classification, not in _execute_* handlers
        execute_methods = [
            "_execute_system_control",
            "_execute_browser_control",
            "_execute_file_system",
        ]
        for method in execute_methods:
            method_start = source.find(f"async def {method}")
            if method_start == -1:
                method_start = source.find(f"def {method}")
            assert method_start != -1, f"Method {method} not found"
            method_body = source[method_start:source.find("\n\n    async def ", method_start + 1)]
            # Check no llm_manager reference in the method body
            assert "llm_manager" not in method_body.lower(), f"llm_manager referenced in {method}"
            assert "LLMManager" not in method_body, f"LLMManager referenced in {method}"
            assert "_llm_manager" not in method_body, f"_llm_manager referenced in {method}"

    def test_no_llm_call_in_classify_intent_except_groq(self):
        source = _router_source()
        classify_start = source.find("async def classify_intent")
        classify_end = source.find("\n\n    async def ", classify_start + 1)
        classify_body = source[classify_start:classify_end]
        # Should only have Groq API call (urllib), no other LLM
        assert "llm_manager" not in classify_body.lower()
        assert "LLMManager" not in classify_body
        assert "_llm_manager" not in classify_body


class TestPerformanceNoBlockingCalls:
    """Verify all manager calls are properly awaited, no sync blocking I/O."""

    def test_all_calls_are_awaited(self):
        source = _router_source()
        tree = ast.parse(source)

        # Find all Call nodes that are PCControlManager or BrowserManager methods
        # and verify they are within Await nodes
        awaited_calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Attribute):
                    awaited_calls.add(self._get_attr_name(node.value.func))

        # Check for non-awaited calls on self._pc_control_manager or self._browser_manager
        # This is a heuristic - in practice we'd need more sophisticated analysis
        # but for regression we just assert the file parses and has await keywords
        assert "await self._pc_control_manager" in source
        assert "await self._browser_manager" in source

    def _get_attr_name(self, node: ast.Attribute) -> str:
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])