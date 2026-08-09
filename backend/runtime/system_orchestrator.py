"""
SystemOrchestrator — Cross-app orchestration for JARVIS-like OS-level control.

Chains together: open app → send keystrokes → capture screen → analyze → respond.
Integrates pc_control + vision + planning modules into coherent workflows.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

_LOG = logging.getLogger("naira.system_orchestrator")


@dataclass
class OrchestratedAction:
    """A single step in a cross-app workflow."""
    action_type: str  # "open_app", "keystroke", "capture", "analyze", "wait"
    target: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    success: bool = False
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class WorkflowResult:
    """Result of a multi-step orchestrated workflow."""
    goal: str
    steps: list[OrchestratedAction] = field(default_factory=list)
    success: bool = False
    summary: str = ""
    total_duration_ms: float = 0.0


class SystemOrchestrator:
    """Orchestrates multi-step OS-level workflows.

    Example: "Open Chrome, go to Gmail, check unread"
    → open_app(chrome) → wait(2s) → keystroke(ctrl+l, gmail.com, enter) → capture → analyze
    """

    def __init__(
        self,
        pc_control: Any = None,
        vision: Any = None,
        planning: Any = None,
        event_bus: Any = None,
    ) -> None:
        self._pc_control = pc_control
        self._vision = vision
        self._planning = planning
        self._event_bus = event_bus
        self._logger = _LOG

    async def execute_workflow(
        self,
        goal: str,
        steps: list[dict[str, Any]],
    ) -> WorkflowResult:
        """Execute a sequence of orchestrated actions.

        Parameters
        ----------
        goal : str
            Human-readable description of what we're trying to accomplish.
        steps : list[dict]
            Each step has: {"action": "open_app|keystroke|capture|wait|analyze", "target": ..., "params": {...}}
        """
        result = WorkflowResult(goal=goal)
        start = time.time()

        for step_def in steps:
            action = OrchestratedAction(
                action_type=step_def.get("action", ""),
                target=step_def.get("target", ""),
                params=step_def.get("params", {}),
            )

            step_start = time.time()
            try:
                await self._execute_step(action)
            except Exception as exc:
                action.error = str(exc)
                action.success = False
                self._logger.error("[ORCHESTRATOR] Step '%s' failed: %s", action.action_type, exc)

            action.duration_ms = (time.time() - step_start) * 1000
            result.steps.append(action)

            # Emit progress event
            if self._event_bus:
                try:
                    await self._event_bus.emit("orchestrator.step_complete", {
                        "goal": goal,
                        "step": action.action_type,
                        "target": action.target,
                        "success": action.success,
                    })
                except Exception:
                    pass

            # Abort on critical failure (unless it's a non-critical step)
            if not action.success and action.params.get("critical", True):
                result.success = False
                result.summary = f"Workflow failed at step '{action.action_type}': {action.error}"
                break

        else:
            result.success = all(s.success for s in result.steps)
            result.summary = f"Workflow completed: {len(result.steps)} steps executed."

        result.total_duration_ms = (time.time() - start) * 1000

        self._logger.info(
            "[ORCHESTRATOR] Workflow '%s' %s in %.0fms (%d steps)",
            goal,
            "succeeded" if result.success else "failed",
            result.total_duration_ms,
            len(result.steps),
        )

        return result

    async def _execute_step(self, action: OrchestratedAction) -> None:
        """Execute a single workflow step."""
        handler = {
            "open_app": self._step_open_app,
            "keystroke": self._step_keystroke,
            "type_text": self._step_type_text,
            "capture": self._step_capture_screen,
            "wait": self._step_wait,
            "analyze": self._step_analyze,
            "click": self._step_click,
            "close_app": self._step_close_app,
        }.get(action.action_type)

        if handler is None:
            raise ValueError(f"Unknown action type: {action.action_type}")

        await handler(action)

    async def _step_open_app(self, action: OrchestratedAction) -> None:
        """Open an application."""
        if not self._pc_control:
            raise RuntimeError("PCControlManager not available")

        adapter = getattr(self._pc_control, "_adapter", None)
        if adapter and hasattr(adapter, "open_application"):
            result = await adapter.open_application(action.target)
            action.result = result
            action.success = True
        else:
            raise RuntimeError("PC control adapter missing open_application")

    async def _step_keystroke(self, action: OrchestratedAction) -> None:
        """Send keyboard shortcuts."""
        if not self._pc_control:
            raise RuntimeError("PCControlManager not available")

        adapter = getattr(self._pc_control, "_adapter", None)
        keys = action.params.get("keys", action.target)
        if adapter and hasattr(adapter, "send_keystroke"):
            result = await adapter.send_keystroke(keys)
            action.result = result
            action.success = True
        else:
            raise RuntimeError("PC control adapter missing send_keystroke")

    async def _step_type_text(self, action: OrchestratedAction) -> None:
        """Type text into the active window."""
        if not self._pc_control:
            raise RuntimeError("PCControlManager not available")

        adapter = getattr(self._pc_control, "_adapter", None)
        if adapter and hasattr(adapter, "type_text"):
            result = await adapter.type_text(action.target)
            action.result = result
            action.success = True
        else:
            raise RuntimeError("PC control adapter missing type_text")

    async def _step_capture_screen(self, action: OrchestratedAction) -> None:
        """Capture the current screen."""
        if not self._vision:
            raise RuntimeError("VisionManager not available")

        screen_capture = getattr(self._vision, "_screen_capture", None)
        if screen_capture:
            image_data = await screen_capture.capture(timeout=10.0)
            action.result = image_data
            action.success = True
        else:
            raise RuntimeError("Vision screen capture not available")

    async def _step_wait(self, action: OrchestratedAction) -> None:
        """Wait for a specified duration."""
        duration = action.params.get("seconds", float(action.target or "1.0"))
        await asyncio.sleep(duration)
        action.success = True

    async def _step_analyze(self, action: OrchestratedAction) -> None:
        """Analyze a captured image using vision."""
        if not self._vision:
            raise RuntimeError("VisionManager not available")

        # Get the last capture result from workflow context
        prompt = action.params.get("prompt", "Describe what you see on screen")
        analyzer = getattr(self._vision, "analyze_image", None)
        if analyzer:
            result = await analyzer(prompt=prompt)
            action.result = result
            action.success = True
        else:
            action.result = "Vision analysis not available"
            action.success = True

    async def _step_click(self, action: OrchestratedAction) -> None:
        """Click at coordinates or UI element."""
        if not self._pc_control:
            raise RuntimeError("PCControlManager not available")

        adapter = getattr(self._pc_control, "_adapter", None)
        x = action.params.get("x", 0)
        y = action.params.get("y", 0)
        if adapter and hasattr(adapter, "click"):
            result = await adapter.click(x, y)
            action.result = result
            action.success = True
        else:
            raise RuntimeError("PC control adapter missing click")

    async def _step_close_app(self, action: OrchestratedAction) -> None:
        """Close an application."""
        if not self._pc_control:
            raise RuntimeError("PCControlManager not available")

        adapter = getattr(self._pc_control, "_adapter", None)
        if adapter and hasattr(adapter, "close_application"):
            result = await adapter.close_application(action.target)
            action.result = result
            action.success = True
        else:
            raise RuntimeError("PC control adapter missing close_application")

    def build_workflow_from_command(self, command: str) -> list[dict[str, Any]]:
        """Parse a natural language command into workflow steps.

        This is a simple rule-based parser. For complex commands,
        the LLM planning module should be used instead.
        """
        lower = command.lower()
        steps: list[dict[str, Any]] = []

        # Pattern: "open X"
        if "open " in lower:
            import re
            match = re.search(r'open\s+(\w+)', lower)
            if match:
                app = match.group(1)
                steps.append({"action": "open_app", "target": app})
                steps.append({"action": "wait", "target": "2", "params": {"seconds": 2.0}})

        # Pattern: "go to X" or "navigate to X"
        if "go to " in lower or "navigate to " in lower:
            import re
            match = re.search(r'(?:go to|navigate to)\s+(\S+)', lower)
            if match:
                url = match.group(1)
                if not url.startswith("http"):
                    url = f"https://{url}"
                steps.append({"action": "keystroke", "target": "ctrl+l", "params": {"keys": "ctrl+l"}})
                steps.append({"action": "wait", "target": "0.3", "params": {"seconds": 0.3}})
                steps.append({"action": "type_text", "target": url})
                steps.append({"action": "keystroke", "target": "enter", "params": {"keys": "enter"}})
                steps.append({"action": "wait", "target": "3", "params": {"seconds": 3.0}})

        # Pattern: "screenshot" or "capture"
        if "screenshot" in lower or "capture" in lower:
            steps.append({"action": "capture", "target": "screen"})

        # Pattern: "check" or "analyze"
        if "check" in lower or "analyze" in lower:
            steps.append({"action": "capture", "target": "screen"})
            steps.append({"action": "analyze", "params": {"prompt": f"Analyze this screen for: {command}"}})

        return steps
