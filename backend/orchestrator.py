"""
Orchestrator — central mediator, Event Bus, and Finite State Machine.

04_Architecture.md §3.A (mediator) & §3.B (Event Bus).
07_Module_Design.md §2.A.
18_Boot_Sequence.md §1 (FSM) & §4 (shutdown).
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import TYPE_CHECKING

from backend.eventbus import EventBus
from backend.types import UserRequest, UserResponse

if TYPE_CHECKING:
    from backend.modules.settings import AppConfig, EnvironmentSnapshot

# ---------------------------------------------------------------------------
# FSM
# ---------------------------------------------------------------------------


class FSMState(StrEnum):
    """Orchestrator Finite State Machine states.

    07_Module_Design.md §2.A; extended in 18_Boot_Sequence.md §1.
    """

    BOOTING = "BOOTING"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    SHUTDOWN = "SHUTDOWN"


# ---------------------------------------------------------------------------
# Orchestrator  (04_Architecture.md §3.A, 07_Module_Design.md §2.A)
# ---------------------------------------------------------------------------


class Orchestrator:
    """Central mediator — owns the FSM, Event Bus, and module registry."""

    def __init__(self, event_bus: EventBus, config: AppConfig, env: EnvironmentSnapshot) -> None:
        self._state: FSMState = FSMState.BOOTING
        self._event_bus = event_bus
        self._config = config
        self._env = env
        self._logger = logging.getLogger("naira.orchestrator")
        self._module_registry: dict[str, object] = {}
        self._module_init_order: list[str] = []

    @property
    def state(self) -> FSMState:
        return self._state

    @state.setter
    def state(self, new_state: FSMState) -> None:
        prev = self._state
        self._state = new_state
        self._logger.info("FSM transition: %s → %s", prev.value, new_state.value)

    def register_module(self, name: str, instance: object) -> None:
        """Register a module and track its initialisation order.

        18_Boot_Sequence.md §2 Step 7.
        """
        self._module_registry[name] = instance
        if name not in self._module_init_order:
            self._module_init_order.append(name)
        self._logger.debug("Module registered: %s", name)

    def get_module(self, name: str) -> object | None:
        """Retrieve a registered module instance by name."""
        return self._module_registry.get(name)

    async def process_user_request(self, request: UserRequest) -> UserResponse:
        """Mediate a user request through FSM transitions and delegate execution to Runtime."""
        if self._state == FSMState.SHUTDOWN:
            return UserResponse(
                request_id=request.id,
                text="[System Error]: Orchestrator is shut down.",
                source=request.source,
            )

        self.state = FSMState.PROCESSING

        try:
            runtime_mgr = self._module_registry.get("runtime")
            if runtime_mgr is not None and hasattr(runtime_mgr, "process_request"):
                response = await runtime_mgr.process_request(request)
                return response
            else:
                self._logger.warning("Runtime module not registered in orchestrator — fallback path triggered")
                return UserResponse(
                    request_id=request.id,
                    text="[System Warning]: Core AI runtime module is unavailable.",
                    source=request.source,
                )
        except Exception as exc:
            self._logger.error("Error during request orchestration: %s", exc)
            return UserResponse(
                request_id=request.id,
                text=f"[System Error]: Failed to process request ({exc}).",
                source=request.source,
            )
        finally:
            if self._state != FSMState.SHUTDOWN:
                self.state = FSMState.IDLE

    async def shutdown(self) -> None:
        """Execute the shutdown sequence (18_Boot_Sequence.md §4).

        Shuts down the Event Bus.  Module shutdown is handled by
        ``shutdown_modules()`` in ``boot.py`` (called from ``main.py``
        before orchestrator shutdown) to avoid double-shutdown.
        """
        self.state = FSMState.SHUTDOWN

        await self._event_bus.shutdown()

        self._logger.info(
            "Orchestrator shut down. %d modules unregistered.",
            len(self._module_registry),
        )
        self._module_registry.clear()
        self._module_init_order.clear()

