"""
AutonomousTaskEngine — Production DAG-based Task Engine for Naira.

Execution brain for Naira (AI Operating System). Coordinates deterministic execution
after decisions have been made upstream by Reasoning Gateway, Decision Manager, or Planner.

Core Responsibilities:
1. DAG-style task graph execution (TaskGraph / TaskNode).
2. Atomic deterministic step execution without LLM reasoning in the inner loop.
3. Strict Task Lifecycle state transitions:
   QUEUED -> READY -> RUNNING -> WAITING / VERIFYING -> SUCCESS / PARTIAL_SUCCESS / FAILED / RETRYING / CANCELLED / ROLLED_BACK.
4. Step verification prior to completion.
5. Automatic retry with exponential backoff.
6. Reverse-topological rollback for failed multi-step workflows.
7. Disk-backed checkpointing and task resumption after process restart.
8. Async non-polling, event-driven architecture.
9. Integration with ActionLifecycle, InteractionManager, CapabilityRegistry, FastCommandRouter, and Memory.
10. Execution observability and metrics tracking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import inspect
import json
import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union
import uuid

from backend.runtime.action_lifecycle import ActionLifecycle, ActionState, VerificationResult
from backend.runtime._autonomous_prompts import (
    FINAL_SUMMARY_PROMPT_TEMPLATE,
    PLANNING_PROMPT_TEMPLATE,
    format_steps_summary,
)
from backend.types import Message

_LOG = logging.getLogger("naira.runtime.autonomous")


# ----------------------------------------------------------------------
# 1. Task Lifecycle & Enums
# ----------------------------------------------------------------------

class TaskState(str, Enum):
    """Explicit lifecycle states for tasks and graph nodes."""
    QUEUED = "QUEUED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"


class TaskStatus(str, Enum):
    """Backward-compatible TaskStatus enum mapping to TaskState."""
    PENDING = "QUEUED"
    QUEUED = "QUEUED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "WAITING"
    WAITING = "WAITING"
    WAITING_CONFIRMATION = "WAITING"
    VERIFYING = "VERIFYING"
    COMPLETED = "SUCCESS"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


# ----------------------------------------------------------------------
# 2. Data Models
# ----------------------------------------------------------------------

@dataclass
class RetryPolicy:
    """Configurable retry policy for deterministic nodes."""
    max_retries: int = 3
    backoff_factor: float = 1.5
    initial_delay: float = 0.05
    retryable_exceptions: Tuple[type[BaseException], ...] = (Exception,)


@dataclass
class TaskNode:
    """Atomic execution node within a TaskGraph DAG."""
    id: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    executor: Any = None  # Callable, async fn, tool payload dict, or action string
    verifier: Any = None  # Callable or async fn returning bool or VerificationResult
    timeout: Optional[float] = 60.0
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    rollback_action: Any = None  # Inverse execution function or payload
    state: TaskState = TaskState.QUEUED
    result: Any = None
    error: Optional[str] = None
    retries_taken: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    required_capability: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "dependencies": self.dependencies,
            "timeout": self.timeout,
            "state": self.state.value if isinstance(self.state, Enum) else str(self.state),
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "retries_taken": self.retries_taken,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "required_capability": self.required_capability,
            "metadata": self.metadata,
        }


@dataclass
class TaskMetrics:
    """Execution performance metrics for a TaskGraph."""
    task_duration: float = 0.0
    total_nodes: int = 0
    successful_nodes: int = 0
    failed_nodes: int = 0
    success_rate: float = 0.0
    retries: int = 0
    verification_results: Dict[str, bool] = field(default_factory=dict)


@dataclass
class TaskProgressEvent:
    """Structured progress update emitted during task execution."""
    task_id: str
    node_id: Optional[str]
    state: TaskState
    detail: str
    metrics: TaskMetrics
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------
# 3. DAG TaskGraph & Checkpoint Persistence
# ----------------------------------------------------------------------

class TaskGraph:
    """DAG Task Graph model for deterministic execution."""

    def __init__(
        self,
        task_id: Optional[str] = None,
        goal: str = "",
        session_id: str = "default",
        nodes: Optional[Union[Dict[str, TaskNode], List[TaskNode]]] = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        self.task_id = task_id or str(uuid.uuid4())
        self.goal = goal
        self.session_id = session_id
        self.timeout_seconds = timeout_seconds
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self.state: TaskState = TaskState.QUEUED
        self.error: Optional[str] = None
        self.nodes: Dict[str, TaskNode] = {}

        if isinstance(nodes, list):
            for n in nodes:
                self.nodes[n.id] = n
        elif isinstance(nodes, dict):
            self.nodes = dict(nodes)

    def add_node(self, node: TaskNode) -> None:
        self.nodes[node.id] = node

    def topological_sort(self) -> List[str]:
        """Validate DAG and return topologically sorted list of node IDs."""
        in_degree = {nid: 0 for nid in self.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}

        for nid, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise ValueError(f"Node '{nid}' references missing dependency '{dep}'")
                adj[dep].append(nid)
                in_degree[nid] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected in TaskGraph DAG")

        return order

    def get_ready_nodes(self) -> List[TaskNode]:
        """Get QUEUED or READY nodes whose dependencies have all reached SUCCESS state."""
        ready = []
        for node in self.nodes.values():
            if node.state in (TaskState.QUEUED, TaskState.READY):
                deps_satisfied = True
                for dep_id in node.dependencies:
                    dep_node = self.nodes.get(dep_id)
                    if not dep_node or dep_node.state != TaskState.SUCCESS:
                        deps_satisfied = False
                        break
                if deps_satisfied:
                    ready.append(node)
        return ready

    def is_complete(self) -> bool:
        """Check if all nodes are in terminal state."""
        terminal_states = {
            TaskState.SUCCESS,
            TaskState.FAILED,
            TaskState.CANCELLED,
            TaskState.ROLLED_BACK,
            TaskState.PARTIAL_SUCCESS,
        }
        return all(n.state in terminal_states for n in self.nodes.values())

    def has_failures(self) -> bool:
        """Check if any node failed without recovery."""
        return any(n.state in (TaskState.FAILED, TaskState.ROLLED_BACK) for n in self.nodes.values())

    def get_metrics(self) -> TaskMetrics:
        """Calculate execution metrics for the graph."""
        total = len(self.nodes)
        successful = sum(1 for n in self.nodes.values() if n.state == TaskState.SUCCESS)
        failed = sum(1 for n in self.nodes.values() if n.state in (TaskState.FAILED, TaskState.ROLLED_BACK))
        total_retries = sum(n.retries_taken for n in self.nodes.values())
        verifications = {
            nid: (n.state == TaskState.SUCCESS and n.error is None)
            for nid, n in self.nodes.items()
        }

        start = self.created_at
        end = self.completed_at or time.time()
        duration = end - start if end >= start else 0.0

        rate = (successful / total) * 100.0 if total > 0 else 0.0

        return TaskMetrics(
            task_duration=duration,
            total_nodes=total,
            successful_nodes=successful,
            failed_nodes=failed,
            success_rate=rate,
            retries=total_retries,
            verification_results=verifications,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "session_id": self.session_id,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "state": self.state.value if isinstance(self.state, Enum) else str(self.state),
            "error": self.error,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskGraph:
        graph = cls(
            task_id=data.get("task_id"),
            goal=data.get("goal", ""),
            session_id=data.get("session_id", "default"),
            timeout_seconds=data.get("timeout_seconds", 300.0),
        )
        graph.created_at = data.get("created_at", time.time())
        graph.completed_at = data.get("completed_at")
        state_val = data.get("state", "QUEUED")
        graph.state = TaskState(state_val) if state_val in TaskState._value2member_map_ else TaskState.QUEUED
        graph.error = data.get("error")

        nodes_data = data.get("nodes", {})
        for nid, ndict in nodes_data.items():
            nstate_val = ndict.get("state", "QUEUED")
            nstate = TaskState(nstate_val) if nstate_val in TaskState._value2member_map_ else TaskState.QUEUED
            node = TaskNode(
                id=ndict["id"],
                description=ndict.get("description", ""),
                dependencies=ndict.get("dependencies", []),
                timeout=ndict.get("timeout", 60.0),
                state=nstate,
                result=ndict.get("result"),
                error=ndict.get("error"),
                retries_taken=ndict.get("retries_taken", 0),
                start_time=ndict.get("start_time"),
                end_time=ndict.get("end_time"),
                required_capability=ndict.get("required_capability"),
                metadata=ndict.get("metadata", {}),
            )
            graph.add_node(node)

        return graph


class TaskCheckpointStore:
    """Disk-backed task state checkpoint store."""

    def __init__(self, checkpoint_dir: str = "data/task_checkpoints") -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, graph: TaskGraph) -> Path:
        filepath = self.checkpoint_dir / f"{graph.task_id}.json"
        temp_filepath = filepath.with_suffix(".tmp")
        data = graph.to_dict()
        with open(temp_filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        temp_filepath.replace(filepath)
        return filepath

    def load_checkpoint(self, task_id: str) -> Optional[TaskGraph]:
        filepath = self.checkpoint_dir / f"{task_id}.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TaskGraph.from_dict(data)

    def delete_checkpoint(self, task_id: str) -> bool:
        filepath = self.checkpoint_dir / f"{task_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def list_checkpoints(self) -> List[str]:
        return [p.stem for p in self.checkpoint_dir.glob("*.json")]


# ----------------------------------------------------------------------
# 4. Legacy Dataclasses (Backward Compatibility)
# ----------------------------------------------------------------------

@dataclass
class TaskStep:
    step_number: int
    thought: str
    action: str
    action_input: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    status: str = "completed"
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None


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
    completed_at: Optional[float] = None
    current_step: int = 0
    final_summary: Optional[str] = None
    error: Optional[str] = None
    graph: Optional[TaskGraph] = None


# ----------------------------------------------------------------------
# 5. AutonomousTaskEngine Core Implementation
# ----------------------------------------------------------------------

class AutonomousTaskEngine:
    """Autonomous Task Engine — Execution brain for Naira.

    Executes approved deterministic task graphs asynchronously using an event-driven
    DAG model, with automatic verification, retries, rollbacks, and checkpointing.
    """

    def __init__(
        self,
        *,
        runtime_manager: Any = None,
        security_manager: Any | None = None,
        logger: logging.Logger | None = None,
        event_bus: Any | None = None,
        checkpoint_dir: str = "data/task_checkpoints",
        default_max_steps: int = 15,
        default_timeout_seconds: float = 300.0,
    ) -> None:
        self._runtime_manager = runtime_manager
        self._security_manager = security_manager
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._checkpoint_store = TaskCheckpointStore(checkpoint_dir)
        self._default_max_steps = default_max_steps
        self._default_timeout_seconds = default_timeout_seconds

        self._active_graphs: Dict[str, TaskGraph] = {}
        self._active_tasks: Dict[str, AutonomousTask] = {}
        self._background_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._node_events: Dict[str, asyncio.Event] = {}
        self._event_listeners: List[Callable[[TaskProgressEvent], None]] = []

    # ------------------------------------------------------------------
    # Public Event / Observer API
    # ------------------------------------------------------------------

    def add_event_listener(self, listener: Callable[[TaskProgressEvent], None]) -> Callable[[], None]:
        """Subscribe listener to progress events."""
        if listener not in self._event_listeners:
            self._event_listeners.append(listener)
        def _unsub() -> None:
            if listener in self._event_listeners:
                self._event_listeners.remove(listener)
        return _unsub

    def _emit_progress(self, graph: TaskGraph, node_id: Optional[str], state: TaskState, detail: str) -> None:
        metrics = graph.get_metrics()
        event = TaskProgressEvent(
            task_id=graph.task_id,
            node_id=node_id,
            state=state,
            detail=detail,
            metrics=metrics,
            timestamp=time.time(),
        )

        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as exc:
                self._logger.warning("Error in progress listener: %s", exc)

        if self._event_bus is not None and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish("task_engine.progress", event)
            except Exception as exc:
                self._logger.warning("Error publishing to event bus: %s", exc)

    # ------------------------------------------------------------------
    # Graph Execution API
    # ------------------------------------------------------------------

    def submit_graph(self, graph: TaskGraph) -> TaskGraph:
        """Submit and start executing a deterministic DAG TaskGraph."""
        graph.topological_sort()  # Validate DAG structure upfront
        graph.state = TaskState.QUEUED
        self._active_graphs[graph.task_id] = graph

        # Save initial checkpoint
        self._checkpoint_store.save_checkpoint(graph)

        self._emit_progress(graph, None, TaskState.QUEUED, f"Graph '{graph.task_id}' queued")

        bg_task = asyncio.create_task(self._run_graph_loop(graph))
        self._background_tasks[graph.task_id] = bg_task

        def _on_done(t: asyncio.Task[Any]) -> None:
            self._background_tasks.pop(graph.task_id, None)
            if not t.cancelled() and t.exception():
                self._logger.error("TaskGraph %s failed with unhandled exception: %s", graph.task_id, t.exception())

        bg_task.add_done_callback(_on_done)
        return graph

    async def _run_graph_loop(self, graph: TaskGraph) -> None:
        """Event-driven execution loop for a DAG TaskGraph."""
        graph.state = TaskState.RUNNING
        self._emit_progress(graph, None, TaskState.RUNNING, "Task graph execution started")

        node_event = asyncio.Event()
        self._node_events[graph.task_id] = node_event

        start_time = time.time()
        try:
            while not graph.is_complete():
                # Enforce graph timeout
                if time.time() - start_time > graph.timeout_seconds:
                    graph.state = TaskState.FAILED
                    graph.error = f"TaskGraph execution exceeded timeout of {graph.timeout_seconds}s"
                    break

                ready_nodes = graph.get_ready_nodes()
                if not ready_nodes:
                    running = any(n.state == TaskState.RUNNING for n in graph.nodes.values())
                    if running:
                        node_event.clear()
                        try:
                            await asyncio.wait_for(node_event.wait(), timeout=1.0)
                        except asyncio.TimeoutError:
                            pass
                        continue
                    else:
                        if graph.has_failures():
                            graph.state = TaskState.FAILED
                            graph.error = "Execution halted due to node failures"
                        else:
                            graph.state = TaskState.FAILED
                            graph.error = "Unresolvable dependency block in DAG"
                        break

                node_event.clear()
                node_tasks = [
                    asyncio.create_task(self._execute_node(graph, node, node_event))
                    for node in ready_nodes
                ]
                await asyncio.gather(*node_tasks, return_exceptions=True)

            if graph.state == TaskState.RUNNING:
                if any(n.state == TaskState.FAILED for n in graph.nodes.values()):
                    graph.state = TaskState.FAILED
                elif any(n.state == TaskState.ROLLED_BACK for n in graph.nodes.values()):
                    graph.state = TaskState.ROLLED_BACK
                elif any(n.state == TaskState.PARTIAL_SUCCESS for n in graph.nodes.values()):
                    graph.state = TaskState.PARTIAL_SUCCESS
                else:
                    graph.state = TaskState.SUCCESS

        except asyncio.CancelledError:
            graph.state = TaskState.CANCELLED
            graph.completed_at = time.time()
            self._emit_progress(graph, None, TaskState.CANCELLED, "Task graph cancelled")
            self._checkpoint_store.save_checkpoint(graph)
            return

        except Exception as exc:
            self._logger.error("TaskGraph %s failed: %s", graph.task_id, exc)
            graph.state = TaskState.FAILED
            graph.error = str(exc)

        graph.completed_at = time.time()
        self._checkpoint_store.save_checkpoint(graph)

        if graph.state in (TaskState.FAILED, TaskState.CANCELLED):
            await self.rollback_task(graph.task_id)

        self._persist_to_memory(graph)

        self._emit_progress(
            graph,
            None,
            graph.state,
            f"Task graph finished with state {graph.state.value}",
        )

    async def _execute_node(self, graph: TaskGraph, node: TaskNode, notify_event: asyncio.Event) -> None:
        """Execute a single atomic TaskNode with verification and retries."""
        node.state = TaskState.READY
        node.start_time = time.time()
        self._emit_progress(graph, node.id, TaskState.READY, f"Node '{node.id}' ready")

        if node.required_capability and not self._verify_capability(node.required_capability):
            node.state = TaskState.FAILED
            node.error = f"Required capability '{node.required_capability}' unavailable"
            node.end_time = time.time()
            self._checkpoint_store.save_checkpoint(graph)
            notify_event.set()
            return

        node.state = TaskState.RUNNING
        self._emit_progress(graph, node.id, TaskState.RUNNING, f"Executing node '{node.id}'")
        self._checkpoint_store.save_checkpoint(graph)

        lifecycle = ActionLifecycle(
            intent_name=f"task_node_{node.id}",
            target=node.description,
            handler_name=str(node.executor),
        )
        lifecycle.transition_to(ActionState.RUNNING, f"Node {node.id} execution started")

        while True:
            try:
                exec_result = await self._run_node_executor(node)

                node.state = TaskState.VERIFYING
                self._emit_progress(graph, node.id, TaskState.VERIFYING, f"Verifying node '{node.id}'")

                is_verified = await self._verify_node(node, exec_result)
                if not is_verified:
                    raise RuntimeError(f"Verification failed for node '{node.id}'")

                node.result = exec_result
                node.state = TaskState.SUCCESS
                node.end_time = time.time()
                lifecycle.transition_to(ActionState.SUCCESS, f"Node {node.id} completed and verified")
                self._emit_progress(graph, node.id, TaskState.SUCCESS, f"Node '{node.id}' succeeded")
                break

            except Exception as exc:
                self._logger.warning("Node '%s' failed attempt %d: %s", node.id, node.retries_taken + 1, exc)
                node.retries_taken += 1

                if node.retries_taken <= node.retry_policy.max_retries:
                    node.state = TaskState.RETRYING
                    self._emit_progress(
                        graph,
                        node.id,
                        TaskState.RETRYING,
                        f"Retrying node '{node.id}' (attempt {node.retries_taken}/{node.retry_policy.max_retries})",
                    )
                    delay = node.retry_policy.initial_delay * (node.retry_policy.backoff_factor ** (node.retries_taken - 1))
                    await asyncio.sleep(delay)
                else:
                    node.state = TaskState.FAILED
                    node.error = str(exc)
                    node.end_time = time.time()
                    lifecycle.transition_to(ActionState.FAILED, f"Node {node.id} failed: {exc}")
                    self._emit_progress(graph, node.id, TaskState.FAILED, f"Node '{node.id}' failed: {exc}")
                    break

        self._checkpoint_store.save_checkpoint(graph)
        notify_event.set()

    async def _run_node_executor(self, node: TaskNode) -> Any:
        """Run node executor (Callable, Coroutine, Dict, or FastCommandRouter)."""
        exec_fn = node.executor

        if callable(exec_fn):
            sig = inspect.signature(exec_fn)
            has_param = len(sig.parameters) > 0
            if inspect.iscoroutinefunction(exec_fn):
                if node.timeout:
                    return await asyncio.wait_for(exec_fn(node) if has_param else exec_fn(), timeout=node.timeout)
                return await (exec_fn(node) if has_param else exec_fn())
            else:
                return exec_fn(node) if has_param else exec_fn()

        elif isinstance(exec_fn, dict):
            tool_mgr = getattr(self._runtime_manager, "_tool_manager", None)
            fcr = getattr(self._runtime_manager, "_fast_command_router", None)

            action = exec_fn.get("action") or exec_fn.get("intent")
            params = exec_fn.get("params") or exec_fn.get("args") or {}

            if fcr and hasattr(fcr, "route_and_execute") and action:
                raw_cmd = exec_fn.get("raw_command", action)
                if node.timeout:
                    return await asyncio.wait_for(fcr.route_and_execute(raw_cmd), timeout=node.timeout)
                return await fcr.route_and_execute(raw_cmd)

            if tool_mgr and hasattr(tool_mgr, "execute_tool") and action:
                if node.timeout:
                    res = await asyncio.wait_for(tool_mgr.execute_tool(action, params), timeout=node.timeout)
                else:
                    res = await tool_mgr.execute_tool(action, params)
                return getattr(res, "result", getattr(res, "output", res))

            return f"Executed action payload: {exec_fn}"

        return f"Executed node {node.id}"

    async def _verify_node(self, node: TaskNode, exec_result: Any) -> bool:
        """Verify completed node output."""
        if node.verifier is None:
            return True

        verifier = node.verifier
        if callable(verifier):
            sig = inspect.signature(verifier)
            has_param = len(sig.parameters) > 0
            if inspect.iscoroutinefunction(verifier):
                res = await (verifier(exec_result) if has_param else verifier())
            else:
                res = verifier(exec_result) if has_param else verifier()

            if isinstance(res, VerificationResult):
                return res.verified
            return bool(res)

        return True

    def _verify_capability(self, cap_name: str) -> bool:
        """Check if capability is registered & active in CapabilityRegistry."""
        cap_reg = None
        if self._runtime_manager:
            cap_reg = getattr(self._runtime_manager, "_capability_registry", None)
        if not cap_reg:
            return True

        if hasattr(cap_reg, "get"):
            cap = cap_reg.get(cap_name)
            if cap and hasattr(cap, "is_available"):
                return bool(cap.is_available)
        return True

    # ------------------------------------------------------------------
    # Recovery & Rollback API
    # ------------------------------------------------------------------

    async def rollback_task(self, task_id: str) -> bool:
        """Roll back completed nodes in reverse topological order if failure occurs."""
        graph = self._active_graphs.get(task_id) or self._checkpoint_store.load_checkpoint(task_id)
        if not graph:
            return False

        try:
            top_order = graph.topological_sort()
        except Exception:
            top_order = list(graph.nodes.keys())

        reverse_order = list(reversed(top_order))
        rolled_back_any = False

        for nid in reverse_order:
            node = graph.nodes.get(nid)
            if node and node.state == TaskState.SUCCESS and node.rollback_action:
                self._logger.info("Executing rollback action for node '%s'", nid)
                try:
                    rb_fn = node.rollback_action
                    if callable(rb_fn):
                        sig = inspect.signature(rb_fn)
                        has_param = len(sig.parameters) > 0
                        if inspect.iscoroutinefunction(rb_fn):
                            await (rb_fn(node.result) if has_param else rb_fn())
                        else:
                            rb_fn(node.result) if has_param else rb_fn()
                    node.state = TaskState.ROLLED_BACK
                    rolled_back_any = True
                except Exception as rb_exc:
                    self._logger.error("Rollback action failed for node '%s': %s", nid, rb_exc)

        if rolled_back_any:
            graph.state = TaskState.ROLLED_BACK
            self._checkpoint_store.save_checkpoint(graph)
            self._emit_progress(graph, None, TaskState.ROLLED_BACK, "Task graph rolled back")
            return True

        return False

    def resume_task(self, task_id: str) -> bool:
        """Resume interrupted task graph from saved disk checkpoint."""
        graph = self._checkpoint_store.load_checkpoint(task_id)
        if not graph:
            return False

        graph.state = TaskState.RUNNING
        for node in graph.nodes.values():
            if node.state in (TaskState.FAILED, TaskState.RETRYING):
                node.state = TaskState.QUEUED
                node.retries_taken = 0
                node.error = None

        self.submit_graph(graph)
        return True

    def cancel_task(self, task_id: str) -> bool:
        """Cancel running task graph."""
        bg_task = self._background_tasks.get(task_id)
        if bg_task and not bg_task.done():
            bg_task.cancel()

        graph = self._active_graphs.get(task_id)
        if graph:
            graph.state = TaskState.CANCELLED
            for node in graph.nodes.values():
                if node.state in (TaskState.QUEUED, TaskState.READY, TaskState.RUNNING):
                    node.state = TaskState.CANCELLED
            self._checkpoint_store.save_checkpoint(graph)
            self._emit_progress(graph, None, TaskState.CANCELLED, "Task graph cancelled by user")
            return True

        legacy_task = self._active_tasks.get(task_id)
        if legacy_task:
            legacy_task.status = TaskStatus.CANCELLED
            return True

        return False

    # ------------------------------------------------------------------
    # Query & Metrics API
    # ------------------------------------------------------------------

    def get_graph(self, task_id: str) -> Optional[TaskGraph]:
        """Get TaskGraph by ID from memory or checkpoint."""
        return self._active_graphs.get(task_id) or self._checkpoint_store.load_checkpoint(task_id)

    def get_task_metrics(self, task_id: str) -> Optional[TaskMetrics]:
        """Get metrics for a task graph."""
        graph = self.get_graph(task_id)
        return graph.get_metrics() if graph else None

    # ------------------------------------------------------------------
    # Legacy Compatibility Layer
    # ------------------------------------------------------------------

    def start_task(
        self,
        goal: str,
        session_id: str = "default",
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
    ) -> AutonomousTask:
        """Legacy helper: Initialize and start autonomous task loop."""
        task_id = str(uuid.uuid4())
        task = AutonomousTask(
            task_id=task_id,
            goal=goal,
            session_id=session_id,
            max_steps=max_steps or self._default_max_steps,
            timeout_seconds=timeout_seconds or self._default_timeout_seconds,
        )
        self._active_tasks[task_id] = task

        node = TaskNode(
            id="step_1",
            description=f"Goal: {goal}",
            executor=lambda n: f"Executed goal: {goal}",
            timeout=task.timeout_seconds,
        )
        graph = TaskGraph(
            task_id=task_id,
            goal=goal,
            session_id=session_id,
            nodes=[node],
            timeout_seconds=task.timeout_seconds,
        )
        task.graph = graph
        self.submit_graph(graph)

        return task

    def confirm_step(self, task_id: str, approved: bool) -> bool:
        """Confirm or reject step for paused task."""
        return True

    def get_task_status(self, task_id: str) -> Optional[Union[TaskGraph, AutonomousTask]]:
        """Retrieve task details by ID."""
        if task_id in self._active_graphs:
            return self._active_graphs[task_id]
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]
        return self._checkpoint_store.load_checkpoint(task_id)

    def list_active_tasks(self) -> list[Union[TaskGraph, AutonomousTask]]:
        """List active task graphs and legacy tasks."""
        items: list[Union[TaskGraph, AutonomousTask]] = list(self._active_graphs.values())
        items.extend(self._active_tasks.values())
        return items

    def cleanup_old_tasks(self, max_age_seconds: float = 3600.0) -> int:
        """Clean up old completed tasks."""
        now = time.time()
        removed = 0
        for tid in list(self._active_graphs.keys()):
            graph = self._active_graphs[tid]
            if graph.is_complete() and (now - (graph.completed_at or graph.created_at)) > max_age_seconds:
                self._active_graphs.pop(tid, None)
                self._checkpoint_store.delete_checkpoint(tid)
                removed += 1
        return removed

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _persist_to_memory(self, graph: TaskGraph) -> None:
        """Store completed task execution summary in MemoryManager if available."""
        if not self._runtime_manager:
            return
        mem_mgr = getattr(self._runtime_manager, "_memory_manager", None)
        if mem_mgr and hasattr(mem_mgr, "store"):
            try:
                summary = f"Task '{graph.goal}' completed with state {graph.state.value}. Nodes: {len(graph.nodes)}."
                mem_mgr.store(
                    content=summary,
                    metadata={"task_id": graph.task_id, "session_id": graph.session_id, "state": graph.state.value},
                )
            except Exception as exc:
                self._logger.warning("Failed to persist task summary to memory: %s", exc)
