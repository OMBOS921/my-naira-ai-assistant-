"""Tests for the Orchestrator, EventBus, and FSMState
(backend/orchestrator.py).

21_System_Contracts.md §14 — Event Bus contracts and ownership.
18_Boot_Sequence.md §1 — FSM state machine.
04_Architecture.md §3.A — Mediator pattern.
"""

from __future__ import annotations

import pytest

from backend.orchestrator import EventBus, FSMState, Orchestrator

# ---------------------------------------------------------------------------
# FSMState
# ---------------------------------------------------------------------------


class TestFSMState:
    def test_values(self) -> None:
        assert FSMState.BOOTING == "BOOTING"
        assert FSMState.IDLE == "IDLE"
        assert FSMState.LISTENING == "LISTENING"
        assert FSMState.PROCESSING == "PROCESSING"
        assert FSMState.SPEAKING == "SPEAKING"
        assert FSMState.SHUTDOWN == "SHUTDOWN"

    def test_is_str_enum(self) -> None:
        assert isinstance(FSMState.IDLE, str)
        assert FSMState.IDLE.value == "IDLE"


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class TestEventBus:
    @pytest.mark.asyncio
    async def test_create(self) -> None:
        bus = EventBus()
        assert bus is not None

    @pytest.mark.asyncio
    async def test_emit_no_subscribers(self) -> None:
        bus = EventBus()
        await bus.emit("test.event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_shutdown_drains(self) -> None:
        bus = EventBus()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        bus = EventBus()
        await bus.shutdown()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_emit_after_shutdown(self) -> None:
        bus = EventBus()
        await bus.shutdown()
        await bus.emit("after.shutdown", {})


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestOrchestratorConstruction:
    def test_requires_event_bus(self) -> None:
        with pytest.raises(TypeError):
            Orchestrator()  # type: ignore[call-arg]

    def test_initial_state_is_booting(self, orchestrator: Orchestrator) -> None:
        assert orchestrator.state == FSMState.BOOTING

    def test_module_registry_empty(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._module_registry == {}


class TestOrchestratorStateMachine:
    def test_state_property(self, orchestrator: Orchestrator) -> None:
        orchestrator.state = FSMState.IDLE
        assert orchestrator.state == FSMState.IDLE

    def test_state_transition_chain(self, orchestrator: Orchestrator) -> None:
        for state in (FSMState.IDLE, FSMState.LISTENING, FSMState.PROCESSING, FSMState.SPEAKING):
            orchestrator.state = state
            assert orchestrator.state == state

    def test_shutdown_terminal_state(self, orchestrator: Orchestrator) -> None:
        orchestrator.state = FSMState.SHUTDOWN
        assert orchestrator.state == FSMState.SHUTDOWN


class TestOrchestratorModuleRegistry:
    def test_register_module(self, orchestrator: Orchestrator) -> None:
        module = object()
        orchestrator.register_module("test", module)
        assert orchestrator._module_registry["test"] is module

    def test_register_overwrites(self, orchestrator: Orchestrator) -> None:
        orchestrator.register_module("x", object())
        new_module = object()
        orchestrator.register_module("x", new_module)
        assert orchestrator._module_registry["x"] is new_module

    def test_register_multiple(self, orchestrator: Orchestrator) -> None:
        modules = {"a": object(), "b": object(), "c": object()}
        for name, mod in modules.items():
            orchestrator.register_module(name, mod)
        assert len(orchestrator._module_registry) == 3

    def test_registry_cleared_on_shutdown(self, orchestrator: Orchestrator) -> None:
        orchestrator.register_module("m1", object())
        orchestrator.register_module("m2", object())

    @pytest.mark.asyncio
    async def test_registry_cleared_after_shutdown(self, orchestrator: Orchestrator) -> None:
        orchestrator.register_module("m1", object())
        await orchestrator.shutdown()
        assert orchestrator._module_registry == {}


@pytest.mark.asyncio
class TestOrchestratorShutdown:
    async def test_shutdown_transitions_to_shutdown(self, orchestrator: Orchestrator) -> None:
        await orchestrator.shutdown()
        assert orchestrator.state == FSMState.SHUTDOWN

    async def test_double_shutdown_is_safe(self, orchestrator: Orchestrator) -> None:
        await orchestrator.shutdown()
        await orchestrator.shutdown()
        assert orchestrator.state == FSMState.SHUTDOWN

    async def test_shutdown_clears_module_registry(self, orchestrator: Orchestrator) -> None:
        orchestrator.register_module("m1", object())
        await orchestrator.shutdown()
        assert orchestrator._module_registry == {}
