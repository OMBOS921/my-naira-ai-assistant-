"""
Action Lifecycle & Verification module for FastCommandRouter (FCR).

Provides explicit state tracking for command execution:
QUEUED -> STARTING -> RUNNING -> WAITING -> SUCCESS / FAILED / PARTIAL_SUCCESS / TIMEOUT / CANCELLED.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, Optional, List


class ActionState(Enum):
    """Execution states for FCR Action Lifecycle."""
    QUEUED = auto()
    STARTING = auto()
    RUNNING = auto()
    WAITING = auto()
    SUCCESS = auto()
    FAILED = auto()
    PARTIAL_SUCCESS = auto()
    TIMEOUT = auto()
    CANCELLED = auto()


@dataclass
class VerificationResult:
    """Detailed verification payload for handler completion."""
    verified: bool
    running_process: Optional[str] = None
    window_detected: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error_reason: Optional[str] = None


class ActionLifecycle:
    """Tracks state transitions, metrics, and verification for an FCR action."""

    _global_listeners: List[Callable[["ActionLifecycle", ActionState, Optional[str]], None]] = []

    def __init__(
        self,
        intent_name: str,
        target: str,
        handler_name: str,
        confidence: float = 1.0,
        llm_used: bool = False,
        debug_mode: bool = False,
    ) -> None:
        self.intent_name = intent_name
        self.target = target
        self.handler_name = handler_name
        self.confidence = confidence
        self.llm_used = llm_used
        self.debug_mode = debug_mode

        self.state: ActionState = ActionState.QUEUED
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.verification: Optional[VerificationResult] = None
        self.history: list[tuple[ActionState, float, Optional[str]]] = [
            (ActionState.QUEUED, self.start_time, "Initial queuing")
        ]
        self._listeners: List[Callable[["ActionLifecycle", ActionState, Optional[str]], None]] = []

    @classmethod
    def add_global_listener(
        cls, listener: Callable[["ActionLifecycle", ActionState, Optional[str]], None]
    ) -> Callable[[], None]:
        """Register a global listener called for state transitions on all ActionLifecycle instances."""
        if listener not in cls._global_listeners:
            cls._global_listeners.append(listener)
        def unsubscribe() -> None:
            if listener in cls._global_listeners:
                cls._global_listeners.remove(listener)
        return unsubscribe

    @classmethod
    def remove_global_listener(
        cls, listener: Callable[["ActionLifecycle", ActionState, Optional[str]], None]
    ) -> None:
        """Remove a global listener."""
        if listener in cls._global_listeners:
            cls._global_listeners.remove(listener)

    def subscribe(
        self, listener: Callable[["ActionLifecycle", ActionState, Optional[str]], None]
    ) -> Callable[[], None]:
        """Subscribe a listener callback to state transitions on this ActionLifecycle instance."""
        if listener not in self._listeners:
            self._listeners.append(listener)
        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
        return unsubscribe

    def _notify_listeners(self, state: ActionState, detail: Optional[str]) -> None:
        """Notify all instance and global subscribers of a state transition."""
        all_listeners = list(self._listeners) + list(self._global_listeners)
        for listener in all_listeners:
            try:
                listener(self, state, detail)
            except Exception:
                pass

    def transition_to(self, new_state: ActionState, detail: Optional[str] = None) -> None:
        """Record transition to a new ActionState."""
        now = time.time()
        self.state = new_state
        self.history.append((new_state, now, detail))
        if new_state in (
            ActionState.SUCCESS,
            ActionState.FAILED,
            ActionState.PARTIAL_SUCCESS,
            ActionState.TIMEOUT,
            ActionState.CANCELLED,
        ):
            self.end_time = now

        self._notify_listeners(new_state, detail)

    @property
    def execution_time_ms(self) -> float:
        end = self.end_time if self.end_time is not None else time.time()
        return (end - self.start_time) * 1000.0

    def set_verification(
        self,
        verified: bool,
        running_process: str | None = None,
        window_detected: str | None = None,
        error: str | None = None,
        details: dict | None = None,
    ) -> None:
        self.verification = VerificationResult(
            verified=verified,
            running_process=running_process,
            window_detected=window_detected,
            details=details or {},
            error_reason=error,
        )

    def get_debug_metadata(self) -> Dict[str, Any]:
        """Return structured debug metadata dictionary."""
        return {
            "execution_state": self.state.name,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "verification_result": {
                "verified": self.verification.verified if self.verification else False,
                "running_process": self.verification.running_process if self.verification else None,
                "window_detected": self.verification.window_detected if self.verification else None,
                "error": self.verification.error_reason if self.verification else None,
            } if self.verification else None,
            "handler_name": self.handler_name,
            "confidence": self.confidence,
            "llm_used": self.llm_used,
        }


class NaturalResponseFormatter:
    """Formats natural, friendly user responses based on action outcomes and target intent."""

    INTENT_NAME_MAP = {
        "chrome": "Chrome",
        "youtube": "YouTube",
        "vscode": "VS Code",
        "code": "VS Code",
        "calculator": "Calculator",
        "calc": "Calculator",
        "notepad": "Notepad",
        "explorer": "File Explorer",
        "settings": "Settings",
        "taskmgr": "Task Manager",
        "cmd": "Command Prompt",
        "powershell": "PowerShell",
        "spotify": "Spotify",
        "whatsapp": "WhatsApp",
        "telegram": "Telegram",
        "discord": "Discord",
        "vlc": "VLC Media Player",
    }

    @classmethod
    def format_open_success(cls, target_name: str, already_running: bool = False) -> str:
        display = cls.INTENT_NAME_MAP.get(target_name.lower(), target_name.title() if len(target_name) <= 20 else target_name)
        if already_running:
            return f"Opened {display} successfully. ({display} pehle se open hai)"
        return f"Opened {display} successfully. ({display} launch ho gaya.)"

    @classmethod
    def format_open_failed(cls, target_name: str, reason: str | None = None) -> str:
        display = cls.INTENT_NAME_MAP.get(target_name.lower(), target_name.title() if len(target_name) <= 20 else target_name)
        if reason:
            return f"I couldn't open {display}: {reason}"
        return f"I couldn't open {display}."

    @classmethod
    def format_browser_fallback(cls, target_name: str) -> str:
        display = cls.INTENT_NAME_MAP.get(target_name.lower(), target_name.title() if len(target_name) <= 20 else target_name)
        return f"'{display}' locally installed nahi hai. Web search open kar diya hai."

    @classmethod
    def format_file_op_success(cls, op_type: str, item_name: str, extra: str | None = None) -> str:
        if op_type == "create_folder":
            return f"Folder '{item_name}' create ho gaya."
        if op_type == "delete_folder":
            return f"Folder '{item_name}' delete ho gaya."
        if op_type == "rename_folder":
            return f"Folder '{item_name}' rename ho gaya to '{extra}'."
        if op_type == "create_file":
            return f"File '{item_name}' create ho gayi."
        if op_type == "delete_file":
            return f"File '{item_name}' delete ho gayi."
        if op_type == "open_file":
            return f"File '{item_name}' open ho gayi."
        if op_type == "rename_file":
            return f"File '{item_name}' rename ho gayi to '{extra}'."
        return f"File action '{op_type}' successful for '{item_name}'."

    @classmethod
    def format_file_op_failed(cls, op_type: str, item_name: str, reason: str | None = None) -> str:
        r_str = f" ({reason})" if reason else ""
        return f"Could not perform {op_type} on '{item_name}'{r_str}."

    @classmethod
    def format_web_search_success(cls, query: str, platform: str = "Google") -> str:
        return f"Search results open kar diye hain for '{query}' on {platform}."

    @classmethod
    def format_system_control_success(cls, action: str) -> str:
        if action == "lock":
            return "Workstation lock kar diya hai."
        if action == "shutdown":
            return "System shutdown initiate ho gaya."
        if action == "restart":
            return "System restart initiate ho gaya."
        return f"System action '{action}' complete ho gaya."

    @classmethod
    def format_volume_success(cls, details: str) -> str:
        return f"Volume set: {details}."

    @classmethod
    def format_brightness_success(cls, level: int) -> str:
        return f"Brightness {level}% set kar di hai."

    @classmethod
    def format_multi_step_result(
        cls,
        step1_name: str,
        step1_success: bool,
        step2_name: str,
        step2_success: bool,
        step1_error: str | None = None,
        step2_error: str | None = None,
    ) -> str:
        if step1_success and step2_success:
            return f"SUCCESS: Both {step1_name} and {step2_name} completed and verified successfully."
        if step1_success and not step2_success:
            err = f": {step2_error}" if step2_error else ""
            return f"PARTIAL_SUCCESS: Step 1 ({step1_name}) succeeded, but Step 2 ({step2_name}) failed{err}."
        if not step1_success and step2_success:
            err = f": {step1_error}" if step1_error else ""
            return f"PARTIAL_SUCCESS: Step 1 ({step1_name}) failed{err}, but Step 2 ({step2_name}) succeeded."
        err1 = f": {step1_error}" if step1_error else ""
        err2 = f": {step2_error}" if step2_error else ""
        return f"FAILED: Step 1 ({step1_name}) failed{err1} and Step 2 ({step2_name}) failed{err2}."

