"""
AutonomousTaskEngine — Safe, bounded autonomous task execution engine.

Conforms to hardware constraints and safety rules:
- Dual safety ceilings: max_steps AND timeout_seconds.
- High/critical risk tools pause for human confirmation.
- CPU melting prevention: sleep(1) per loop iteration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import time
from typing import Any
import uuid

from backend.runtime._autonomous_prompts import (
    FINAL_SUMMARY_PROMPT_TEMPLATE,
    PLANNING_PROMPT_TEMPLATE,
    format_steps_summary,
)
from backend.types import Message

_LOG = logging.getLogger("naira.runtime.autonomous")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class TaskStep:
    step_number: int
    thought: str
    action: str
    action_input: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    status: str = "completed"
    timestamp: float = field(default_factory=time.time)
    error: str | None = None


@dataclass
class AutonomousTask:
    task_id: str
    goal: str
    session_id: str
    status: TaskStatus = TaskStatus.PENDING
    max_steps: int = 15
    timeout_seconds: float = 300.0
    steps: list[TaskStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    current_step: int = 0
    final_summary: str | None = None
    error: str | None = None


class AutonomousTaskEngine:
    """Autonomous task execution engine with safety ceilings and pause/confirmation hooks."""

    def __init__(
        self,
        *,
        runtime_manager: Any,
        security_manager: Any | None = None,
        logger: logging.Logger | None = None,
        event_bus: Any | None = None,
        default_max_steps: int = 15,
        default_timeout_seconds: float = 300.0,
    ) -> None:
        self._runtime_manager = runtime_manager
        self._security_manager = security_manager
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._default_max_steps = default_max_steps
        self._default_timeout_seconds = default_timeout_seconds

        self._active_tasks: dict[str, AutonomousTask] = {}
        self._pending_confirmations: dict[str, asyncio.Event] = {}
        self._confirmation_results: dict[str, bool] = {}
        self._background_tasks: dict[str, asyncio.Task[Any]] = {}

    def start_task(
        self,
        goal: str,
        session_id: str = "default",
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
    ) -> AutonomousTask:
        """Initialize and start an autonomous task execution loop in background."""
        task_id = str(uuid.uuid4())
        task = AutonomousTask(
            task_id=task_id,
            goal=goal,
            session_id=session_id,
            max_steps=max_steps or self._default_max_steps,
            timeout_seconds=timeout_seconds or self._default_timeout_seconds,
        )
        self._active_tasks[task_id] = task

        bg_task = asyncio.create_task(
            self._run_task_loop(task, task.timeout_seconds)
        )
        self._background_tasks[task_id] = bg_task

        def _on_done(t: asyncio.Task[Any]) -> None:
            self._background_tasks.pop(task_id, None)
            if not t.cancelled() and t.exception():
                self._logger.error("Autonomous task %s failed: %s", task_id, t.exception())

        bg_task.add_done_callback(_on_done)
        self._logger.info("Started autonomous task %s with goal: %r", task_id, goal)
        return task

    async def _run_task_loop(self, task: AutonomousTask, timeout_seconds: float) -> None:
        """Run execution loop protected by hard time limit and step ceiling."""
        task.status = TaskStatus.RUNNING
        try:
            await asyncio.wait_for(
                self._execute_steps(task),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            self._logger.warning("Autonomous task %s hit time limit of %fs", task.task_id, timeout_seconds)
            task.status = TaskStatus.TIMED_OUT
            task.error = f"Execution timed out after {timeout_seconds} seconds"
            task.completed_at = time.time()
        except asyncio.CancelledError:
            self._logger.info("Autonomous task %s was cancelled", task.task_id)
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
        except Exception as exc:
            self._logger.error("Autonomous task %s encountered error: %s", task.task_id, exc)
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = time.time()

    async def _execute_steps(self, task: AutonomousTask) -> None:
        """Inner execution loop for steps."""
        llm_manager = getattr(self._runtime_manager, "_llm_manager", None)
        tool_manager = getattr(self._runtime_manager, "_tool_manager", None)

        while task.current_step < task.max_steps and task.status == TaskStatus.RUNNING:
            task.current_step += 1
            step_num = task.current_step

            steps_summary = format_steps_summary(task.steps)
            prompt = PLANNING_PROMPT_TEMPLATE.format(
                goal=task.goal,
                current_step=step_num,
                max_steps=task.max_steps,
                steps_summary=steps_summary,
            )

            # Generate next step from LLM
            thought = f"Executing step {step_num}"
            action = "FINAL_ANSWER"
            action_input: dict[str, Any] = {}

            if llm_manager is not None and hasattr(llm_manager, "generate"):
                try:
                    response = await llm_manager.generate(
                        prompt=prompt,
                        context=[Message(role="user", content="Determine next step")],
                    )
                    raw_text = response.text or ""
                    parsed = self._parse_llm_json(raw_text)
                    thought = parsed.get("thought", thought)
                    action = parsed.get("action", action)
                    raw_input = parsed.get("action_input", {})
                    if isinstance(raw_input, dict):
                        action_input = raw_input
                    else:
                        action_input = {"text": str(raw_input)}
                except Exception as llm_exc:
                    self._logger.warning("LLM planning failed in step %d: %s", step_num, llm_exc)
                    thought = f"LLM error: {llm_exc}"
                    action = "FINAL_ANSWER"
                    action_input = {"summary": f"Stopped due to error: {llm_exc}"}

            # Check if task goal is complete
            if action == "FINAL_ANSWER":
                summary_text = action_input.get("summary", action_input.get("text", "Goal completed."))
                task.steps.append(
                    TaskStep(
                        step_number=step_num,
                        thought=thought,
                        action=action,
                        action_input=action_input,
                        result=summary_text,
                        status="completed",
                    )
                )
                task.final_summary = summary_text
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                break

            # High/critical risk tool call security check
            if self._is_high_risk_action(action, action_input):
                task.status = TaskStatus.WAITING_CONFIRMATION
                event = asyncio.Event()
                self._pending_confirmations[task.task_id] = event

                self._logger.info("Task %s pausing for confirmation on action '%s'", task.task_id, action)
                try:
                    await asyncio.wait_for(event.wait(), timeout=120.0)
                except asyncio.TimeoutError:
                    self._logger.warning("Confirmation timed out for task %s", task.task_id)
                    self._confirmation_results[task.task_id] = False
                finally:
                    self._pending_confirmations.pop(task.task_id, None)

                approved = self._confirmation_results.pop(task.task_id, False)
                if not approved:
                    task.steps.append(
                        TaskStep(
                            step_number=step_num,
                            thought=thought,
                            action=action,
                            action_input=action_input,
                            result="Action rejected by user or security policy",
                            status="denied",
                            error="Action confirmation denied",
                        )
                    )
                    task.status = TaskStatus.RUNNING
                    await asyncio.sleep(1)
                    continue

                task.status = TaskStatus.RUNNING

            # Execute tool call
            step_result = None
            step_error = None
            if tool_manager is not None and hasattr(tool_manager, "execute_tool"):
                try:
                    tool_res = await tool_manager.execute_tool(action, action_input)
                    if hasattr(tool_res, "result") and tool_res.result is not None:
                        step_result = tool_res.result
                    elif hasattr(tool_res, "output") and tool_res.output is not None:
                        step_result = tool_res.output
                    elif hasattr(tool_res, "error") and tool_res.error:
                        step_error = tool_res.error
                except Exception as tool_exc:
                    step_error = str(tool_exc)
            else:
                step_result = f"Simulated execution of tool '{action}'"

            task.steps.append(
                TaskStep(
                    step_number=step_num,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    result=step_result,
                    status="completed" if not step_error else "failed",
                    error=step_error,
                )
            )

            # CRITICAL: Prevent CPU melting on rapid failures
            await asyncio.sleep(1)

        if task.current_step >= task.max_steps and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.TIMED_OUT
            task.error = f"Reached maximum allowed step ceiling ({task.max_steps} steps)"
            task.completed_at = time.time()

    def confirm_step(self, task_id: str, approved: bool) -> bool:
        """Confirm or reject a pending step for a paused task."""
        self._confirmation_results[task_id] = approved
        event = self._pending_confirmations.get(task_id)
        if event is not None:
            event.set()
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or paused autonomous task."""
        task = self._active_tasks.get(task_id)
        if task is None:
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()

        bg_task = self._background_tasks.get(task_id)
        if bg_task and not bg_task.done():
            bg_task.cancel()

        event = self._pending_confirmations.get(task_id)
        if event is not None:
            event.set()

        return True

    def get_task_status(self, task_id: str) -> AutonomousTask | None:
        """Retrieve task details by ID."""
        return self._active_tasks.get(task_id)

    def list_active_tasks(self) -> list[AutonomousTask]:
        """List all tracked autonomous tasks."""
        return list(self._active_tasks.values())

    def cleanup_old_tasks(self, max_age_seconds: float = 3600.0) -> int:
        """Remove finished tasks older than max_age_seconds."""
        now = time.time()
        to_remove = []
        for task_id, task in self._active_tasks.items():
            if task.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
                TaskStatus.TIMED_OUT,
            ):
                finished_at = task.completed_at or task.created_at
                if now - finished_at > max_age_seconds:
                    to_remove.append(task_id)

        for tid in to_remove:
            self._active_tasks.pop(tid, None)

        return len(to_remove)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_high_risk_action(self, action: str, action_input: dict[str, Any]) -> bool:
        """Determine if an action represents a high/critical security risk."""
        high_risk_tools = {"terminal", "execute_command", "file_delete", "system_reboot", "shell"}
        if action.lower() in high_risk_tools:
            return True

        if self._security_manager is not None:
            check_fn = getattr(self._security_manager, "is_high_risk", None)
            if callable(check_fn):
                return bool(check_fn(action, action_input))

        return False

    def _parse_llm_json(self, text: str) -> dict[str, Any]:
        """Extract and parse JSON object from LLM response text."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = text[start : end + 1]
            try:
                return json.loads(json_str)
            except Exception:
                pass

        return {"thought": text, "action": "FINAL_ANSWER", "action_input": {"summary": text}}
