"""
Unit tests for AutonomousTaskEngine — execution brain of Naira.

Tests DAG task graph execution, dependency topological ordering, retry policies,
reverse rollbacks, cancellation, checkpoint resume, timeouts, step verification,
observability progress events, and backward compatibility.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import time
from typing import Any

import pytest

from backend.runtime.autonomous_task_engine import (
    AutonomousTaskEngine,
    RetryPolicy,
    TaskCheckpointStore,
    TaskGraph,
    TaskMetrics,
    TaskNode,
    TaskProgressEvent,
    TaskState,
    TaskStatus,
)


@pytest.fixture
def temp_checkpoint_dir(tmp_path: Path) -> str:
    return str(tmp_path / "checkpoints")


@pytest.fixture
def task_engine(temp_checkpoint_dir: str) -> AutonomousTaskEngine:
    return AutonomousTaskEngine(checkpoint_dir=temp_checkpoint_dir)


@pytest.mark.asyncio
async def test_dag_task_execution(task_engine: AutonomousTaskEngine) -> None:
    """Test standard multi-node DAG execution with dependencies."""
    execution_order = []

    def make_executor(name: str):
        def _exec(node: TaskNode) -> str:
            execution_order.append(name)
            return f"result_{name}"
        return _exec

    n1 = TaskNode(id="A", description="Task A", executor=make_executor("A"))
    n2 = TaskNode(id="B", description="Task B", dependencies=["A"], executor=make_executor("B"))
    n3 = TaskNode(id="C", description="Task C", dependencies=["A"], executor=make_executor("C"))
    n4 = TaskNode(id="D", description="Task D", dependencies=["B", "C"], executor=make_executor("D"))

    graph = TaskGraph(goal="Build DAG Workflow", nodes=[n1, n2, n3, n4])
    submitted = task_engine.submit_graph(graph)

    # Wait for graph completion
    await asyncio.sleep(0.5)

    res_graph = task_engine.get_graph(submitted.task_id)
    assert res_graph is not None
    assert res_graph.state == TaskState.SUCCESS
    assert execution_order[0] == "A"
    assert set(execution_order[1:3]) == {"B", "C"}
    assert execution_order[3] == "D"
    assert res_graph.nodes["D"].state == TaskState.SUCCESS


@pytest.mark.asyncio
async def test_dependency_handling_and_cycle_detection() -> None:
    """Test topological sorting, dependency validation, and cycle detection."""
    n1 = TaskNode(id="A", description="A", dependencies=["B"])
    n2 = TaskNode(id="B", description="B", dependencies=["A"])

    graph = TaskGraph(goal="Cycle Test", nodes=[n1, n2])
    with pytest.raises(ValueError, match="Cycle detected"):
        graph.topological_sort()

    n3 = TaskNode(id="X", description="X", dependencies=["MISSING"])
    invalid_graph = TaskGraph(goal="Missing Dep", nodes=[n3])
    with pytest.raises(ValueError, match="missing dependency"):
        invalid_graph.topological_sort()


@pytest.mark.asyncio
async def test_retry_policy(task_engine: AutonomousTaskEngine) -> None:
    """Test automatic retries on transient errors."""
    attempts = 0

    def flaky_executor(node: TaskNode) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Transient network glitch")
        return "Success after retries"

    node = TaskNode(
        id="flaky_node",
        description="Flaky execution",
        executor=flaky_executor,
        retry_policy=RetryPolicy(max_retries=3, initial_delay=0.01, backoff_factor=1.0),
    )

    graph = TaskGraph(goal="Retry Test", nodes=[node])
    task_engine.submit_graph(graph)

    await asyncio.sleep(0.3)

    res_graph = task_engine.get_graph(graph.task_id)
    assert res_graph is not None
    assert res_graph.state == TaskState.SUCCESS
    assert attempts == 3
    assert res_graph.nodes["flaky_node"].retries_taken == 2
    assert res_graph.nodes["flaky_node"].state == TaskState.SUCCESS


@pytest.mark.asyncio
async def test_rollback_mechanism(task_engine: AutonomousTaskEngine) -> None:
    """Test reverse-topological rollback execution when a node fails."""
    rolled_back_nodes = []

    def rollback_a(res: Any) -> None:
        rolled_back_nodes.append("A")

    def rollback_b(res: Any) -> None:
        rolled_back_nodes.append("B")

    def failing_executor(node: TaskNode) -> None:
        raise RuntimeError("Fatal node error")

    n1 = TaskNode(id="A", description="A", executor=lambda n: "A_done", rollback_action=rollback_a)
    n2 = TaskNode(id="B", description="B", dependencies=["A"], executor=lambda n: "B_done", rollback_action=rollback_b)
    n3 = TaskNode(id="C", description="C", dependencies=["B"], executor=failing_executor, retry_policy=RetryPolicy(max_retries=0))

    graph = TaskGraph(goal="Rollback Test", nodes=[n1, n2, n3])
    task_engine.submit_graph(graph)

    await asyncio.sleep(0.5)

    res_graph = task_engine.get_graph(graph.task_id)
    assert res_graph is not None
    assert res_graph.state == TaskState.ROLLED_BACK
    assert rolled_back_nodes == ["B", "A"]


@pytest.mark.asyncio
async def test_cancellation(task_engine: AutonomousTaskEngine) -> None:
    """Test in-flight task graph cancellation."""
    async def slow_executor(node: TaskNode) -> str:
        await asyncio.sleep(2.0)
        return "Done"

    n1 = TaskNode(id="slow_node", description="Long running", executor=slow_executor)
    graph = TaskGraph(goal="Cancellation Test", nodes=[n1])
    task_engine.submit_graph(graph)

    await asyncio.sleep(0.1)
    cancelled = task_engine.cancel_task(graph.task_id)
    assert cancelled is True

    await asyncio.sleep(0.2)
    res_graph = task_engine.get_graph(graph.task_id)
    assert res_graph is not None
    assert res_graph.state == TaskState.CANCELLED
    assert res_graph.nodes["slow_node"].state == TaskState.CANCELLED


@pytest.mark.asyncio
async def test_checkpoint_and_resume(temp_checkpoint_dir: str) -> None:
    """Test disk checkpointing and task graph resumption."""
    engine1 = AutonomousTaskEngine(checkpoint_dir=temp_checkpoint_dir)

    n1 = TaskNode(id="A", description="Step A", executor=lambda n: "Done A")
    graph = TaskGraph(task_id="checkpoint_test_id", goal="Checkpoint Goal", nodes=[n1])
    engine1.submit_graph(graph)

    await asyncio.sleep(0.3)

    # Instantiate new engine reading from same checkpoint directory
    engine2 = AutonomousTaskEngine(checkpoint_dir=temp_checkpoint_dir)
    resumed_graph = engine2.get_graph("checkpoint_test_id")

    assert resumed_graph is not None
    assert resumed_graph.goal == "Checkpoint Goal"
    assert resumed_graph.state == TaskState.SUCCESS


@pytest.mark.asyncio
async def test_step_verification(task_engine: AutonomousTaskEngine) -> None:
    """Test custom node verifier function."""
    def verifier(output: Any) -> bool:
        return output == "valid_data"

    n1 = TaskNode(id="V1", description="Verified Step", executor=lambda n: "valid_data", verifier=verifier)
    graph = TaskGraph(goal="Verification Test", nodes=[n1])
    task_engine.submit_graph(graph)

    await asyncio.sleep(0.3)
    res_graph = task_engine.get_graph(graph.task_id)
    assert res_graph is not None
    assert res_graph.state == TaskState.SUCCESS

    # Test failing verifier
    n2 = TaskNode(
        id="V2",
        description="Failing Verifier",
        executor=lambda n: "invalid_data",
        verifier=verifier,
        retry_policy=RetryPolicy(max_retries=0),
    )
    graph2 = TaskGraph(goal="Failing Verification Test", nodes=[n2])
    task_engine.submit_graph(graph2)

    await asyncio.sleep(0.3)
    res_graph2 = task_engine.get_graph(graph2.task_id)
    assert res_graph2 is not None
    assert res_graph2.state in (TaskState.FAILED, TaskState.ROLLED_BACK)


@pytest.mark.asyncio
async def test_progress_events_and_metrics(task_engine: AutonomousTaskEngine) -> None:
    """Test progress event listener emission and execution metrics calculation."""
    events: list[TaskProgressEvent] = []

    def on_progress(event: TaskProgressEvent) -> None:
        events.append(event)

    task_engine.add_event_listener(on_progress)

    n1 = TaskNode(id="A", description="A", executor=lambda n: "A_done")
    graph = TaskGraph(goal="Observability Test", nodes=[n1])
    task_engine.submit_graph(graph)

    await asyncio.sleep(0.3)

    assert len(events) > 0
    assert any(e.state == TaskState.QUEUED for e in events)
    assert any(e.state == TaskState.SUCCESS for e in events)

    metrics = task_engine.get_task_metrics(graph.task_id)
    assert metrics is not None
    assert metrics.total_nodes == 1
    assert metrics.successful_nodes == 1
    assert metrics.success_rate == 100.0


@pytest.mark.asyncio
async def test_backward_compatibility(task_engine: AutonomousTaskEngine) -> None:
    """Test legacy start_task interface and TaskStatus compatibility."""
    legacy_task = task_engine.start_task(goal="Legacy Goal Test")
    assert legacy_task.task_id is not None
    assert legacy_task.goal == "Legacy Goal Test"

    await asyncio.sleep(0.3)
    status = task_engine.get_task_status(legacy_task.task_id)
    assert status is not None
