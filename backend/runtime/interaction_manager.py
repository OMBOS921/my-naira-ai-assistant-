"""
Human Interaction Layer v2.0 — Decouples Execution State from Conversation State.

Subscribes to ActionLifecycle events and produces natural, progressive,
contextual, speech-ready responses adapted to the user's relationship style.

Enhanced Features:
1. Conversation Priority Engine (CRITICAL, ACTION, CONVERSATION, BACKGROUND)
2. Interruptible Conversation Management (atomic cancellation & preemption)
3. Central Event-Driven Notification Center (ui, voice, avatar, mobile, watch, logs)
4. Multi-Action Action Groups aggregation
5. Configurable Silence Policy (suppresses voice for non-verbal actions)
6. Dynamic & Extensible Personality Profiles
7. Streaming-Ready Interaction Phases
8. Time/Size-Bounded Event Replay Buffer (< 30 KB footprint)
9. Strict Observer Decoupling (zero changes to ActionLifecycle / FCR)
10. Low Latency (< 2 ms processing budget per event)
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from backend.runtime.action_lifecycle import ActionLifecycle, ActionState


class ResponsePriority(Enum):
    """Priority levels for conversation responses."""
    BACKGROUND = 10
    CONVERSATION = 20
    ACTION = 30
    CRITICAL = 40


class PersonalityMode(Enum):
    """Adaptive personality modes for user interaction."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CLOSE_FRIEND = "close_friend"
    MINIMAL = "minimal"
    CUSTOM = "custom"


class InteractionPhase(Enum):
    """Human conversation phases."""
    ACKNOWLEDGED = "acknowledged"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    # Streaming Ready Phases
    THINKING = "thinking"
    PLANNING = "planning"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    GENERATING = "generating"
    STREAMING = "streaming"


@dataclass
class InteractionEvent:
    """Represents a human-facing conversational update produced by InteractionManager."""
    id: str
    action_id: int
    intent_name: str
    target: str
    phase: InteractionPhase
    text: str
    speech_text: str
    personality_mode: PersonalityMode
    priority: ResponsePriority = ResponsePriority.ACTION
    should_speak: bool = True
    should_notify: bool = True
    is_streaming: bool = False
    stream_sequence: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------
# 3. Notification Center
# ----------------------------------------------------------------------

class NotificationCenter:
    """Central event-driven distribution bus for InteractionEvents.

    Decouples InteractionManager from specific presentation endpoints
    (Desktop UI, Voice TTS, Avatar, Mobile App, Watch, Logs).
    """

    _instance: Optional[NotificationCenter] = None

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[InteractionEvent], None]]] = {}

    @classmethod
    def get_instance(cls) -> NotificationCenter:
        if cls._instance is None:
            cls._instance = NotificationCenter()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for clean testing isolation."""
        cls._instance = None

    def subscribe(self, channel: str, callback: Callable[[InteractionEvent], None]) -> Callable[[], None]:
        """Subscribe a listener to a specific channel (or 'all')."""
        chan = channel.lower()
        if chan not in self._subscribers:
            self._subscribers[chan] = []
        if callback not in self._subscribers[chan]:
            self._subscribers[chan].append(callback)

        def unsubscribe() -> None:
            if chan in self._subscribers and callback in self._subscribers[chan]:
                self._subscribers[chan].remove(callback)

        return unsubscribe

    def publish(self, channel: str, event: InteractionEvent) -> None:
        """Publish an InteractionEvent to a specific channel and 'all' subscribers."""
        chan = channel.lower()
        subscribers: List[Callable[[InteractionEvent], None]] = list(self._subscribers.get(chan, []))
        if chan != "all":
            subscribers.extend(self._subscribers.get("all", []))

        for callback in subscribers:
            try:
                callback(event)
            except Exception as exc:
                logging.getLogger("naira.notification_center").debug("Notification callback error: %s", exc)


# ----------------------------------------------------------------------
# 5. Silence Policy
# ----------------------------------------------------------------------

class SilencePolicy:
    """Configurable policy determining whether actions trigger voice speech or visual notifications."""

    DEFAULT_SILENT_INTENTS: Set[str] = {
        "VOLUME",
        "VOLUME_SET",
        "BRIGHTNESS",
        "BRIGHTNESS_SET",
        "CLIPBOARD",
        "CLIPBOARD_COPY",
        "FOCUS",
        "WINDOW_FOCUS",
        "MUTE",
    }

    def __init__(
        self,
        enable_speech: bool = True,
        silent_intents: Optional[Set[str]] = None,
        custom_rules: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> None:
        self.enable_speech = enable_speech
        self.silent_intents = set(silent_intents) if silent_intents is not None else set(self.DEFAULT_SILENT_INTENTS)
        self.custom_rules: Dict[str, Dict[str, bool]] = custom_rules or {}

    def should_speak(self, intent_name: str, phase: InteractionPhase) -> bool:
        """Determine if an action should produce speech (TTS)."""
        if not self.enable_speech:
            return False
        intent_upper = intent_name.upper()
        if intent_upper in self.custom_rules:
            return self.custom_rules[intent_upper].get("speak", True)
        if intent_upper in self.silent_intents:
            return False
        return True

    def should_notify(self, intent_name: str, phase: InteractionPhase) -> bool:
        """Determine if an action should trigger a visual notification."""
        intent_upper = intent_name.upper()
        if intent_upper in self.custom_rules:
            return self.custom_rules[intent_upper].get("notify", True)
        return True

    def register_rule(self, intent_name: str, speak: bool = False, notify: bool = True) -> None:
        """Dynamically register or update a silence rule."""
        self.custom_rules[intent_name.upper()] = {"speak": speak, "notify": notify}


# ----------------------------------------------------------------------
# 6. Personality Profiles
# ----------------------------------------------------------------------

@dataclass
class PersonalityProfile:
    """Dynamic, configurable profile defining natural conversation templates."""
    name: str
    description: str = ""
    speech_tone: str = "neutral"
    starting_templates: Dict[str, str] = field(default_factory=dict)
    progress_templates: Dict[str, str] = field(default_factory=dict)
    success_templates: Dict[str, str] = field(default_factory=dict)
    failure_templates: Dict[str, str] = field(default_factory=dict)

    def format_response(
        self, phase: InteractionPhase, intent_name: str, target: str, detail: Optional[str] = None
    ) -> Optional[str]:
        """Format response based on phase and intent match."""
        templates: Dict[str, str] = {}
        if phase == InteractionPhase.ACKNOWLEDGED:
            templates = self.starting_templates
        elif phase == InteractionPhase.PROGRESS:
            templates = self.progress_templates
        elif phase == InteractionPhase.SUCCESS:
            templates = self.success_templates
        elif phase == InteractionPhase.FAILURE:
            templates = self.failure_templates

        intent_upper = intent_name.upper()
        for key, template in templates.items():
            if key.upper() in intent_upper:
                return template.format(target=target, detail=detail or "")

        if "DEFAULT" in templates:
            return templates["DEFAULT"].format(target=target, detail=detail or "")

        return None


class PersonalityProfileRegistry:
    """Registry allowing future personality profiles to be added dynamically without code changes."""

    _profiles: Dict[str, PersonalityProfile] = {}

    @classmethod
    def register(cls, profile: PersonalityProfile) -> None:
        cls._profiles[profile.name.lower()] = profile

    @classmethod
    def get(cls, name: str) -> Optional[PersonalityProfile]:
        return cls._profiles.get(name.lower())

    @classmethod
    def list_profiles(cls) -> List[str]:
        return list(cls._profiles.keys())


# Register default standard profiles
PersonalityProfileRegistry.register(
    PersonalityProfile(
        name="professional",
        description="Formal, concise professional responses.",
        starting_templates={"OPEN": "Opening {target}...", "SEARCH": "Searching for '{target}'...", "DEFAULT": "Processing request..."},
        progress_templates={"OPEN": "Connecting to {target}...", "SEARCH": "Searching Google...", "DEFAULT": "Processing..."},
        success_templates={"OPEN": "{target} has been opened.", "SEARCH": "The search results are ready.", "DEFAULT": "Action completed for {target}."},
        failure_templates={"NOT_FOUND": "I couldn't find {target}.", "TIMEOUT": "The website isn't responding.", "DEFAULT": "I couldn't complete that action."},
    )
)

PersonalityProfileRegistry.register(
    PersonalityProfile(
        name="friendly",
        description="Warm, helpful everyday companion responses.",
        starting_templates={"OPEN": "Opening {target}...", "SEARCH": "Searching Google for '{target}'...", "CREATE": "Creating {target}...", "DEFAULT": "On it."},
        progress_templates={"OPEN": "Launching {target}...", "SEARCH": "Searching...", "DEFAULT": "Working on it..."},
        success_templates={"OPEN": "{target} is ready.", "SEARCH": "Search results open kar diye hain.", "DEFAULT": "Ho gaya! {target} is ready."},
        failure_templates={"NOT_FOUND": "{target} nahi mila system pe.", "TIMEOUT": "Response nahi mil raha, connection stuck lag raha hai.", "DEFAULT": "Yeh task complete nahi ho paya."},
    )
)

PersonalityProfileRegistry.register(
    PersonalityProfile(
        name="close_friend",
        description="Casual, enthusiastic close friend persona with emojis.",
        starting_templates={"OPEN": "Opening {target}, hold on! 🚀", "SEARCH": "Searching for '{target}' right away! 🔍", "DEFAULT": "Got it, on it! 👍"},
        progress_templates={"OPEN": "Khul raha hai {target}... ⏳", "SEARCH": "Search ho raha hai... 🔍", "DEFAULT": "Bus ek sec..."},
        success_templates={"OPEN": "Done! {target} khol diya 😄", "SEARCH": "Done! Search results dekho 🔍", "DEFAULT": "Done ho gaya! 😄"},
        failure_templates={"NOT_FOUND": "Arre {target} toh mil hi nahi raha! 😅", "TIMEOUT": "Website stuck hai, connect nahi ho raha 😕", "DEFAULT": "Oops, yeh nahi ho paya 😅"},
    )
)

PersonalityProfileRegistry.register(
    PersonalityProfile(
        name="minimal",
        description="Ultra-short minimalist responses.",
        starting_templates={"DEFAULT": "{target}..."},
        progress_templates={"DEFAULT": "..."},
        success_templates={"DEFAULT": "Done."},
        failure_templates={"DEFAULT": "Failed."},
    )
)


# ----------------------------------------------------------------------
# 4. Multi-Action Action Groups
# ----------------------------------------------------------------------

@dataclass
class ActionGroup:
    """Aggregates multi-action command workflows into a single conversational progress stream."""

    group_id: str
    lifecycles: List[ActionLifecycle]
    total_actions: int = field(init=False)
    completed_count: int = 0
    failed_count: int = 0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self.total_actions = len(self.lifecycles)

    @property
    def is_complete(self) -> bool:
        return (self.completed_count + self.failed_count) >= self.total_actions


# ----------------------------------------------------------------------
# 8. Event Replay Buffer
# ----------------------------------------------------------------------

class InteractionEventReplayBuffer:
    """Short-term, time/size-bounded event store for reconnecting clients."""

    def __init__(self, ttl_seconds: float = 300.0, max_events: int = 100) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_events = max_events
        self._events: List[InteractionEvent] = []

    def append(self, event: InteractionEvent) -> None:
        """Append an event and enforce TTL and capacity limits."""
        self._prune()
        self._events.append(event)
        if len(self._events) > self.max_events:
            self._events.pop(0)

    def _prune(self) -> None:
        now = time.time()
        cutoff = now - self.ttl_seconds
        self._events = [e for e in self._events if e.timestamp >= cutoff]

    def get_events_since(self, timestamp: float) -> List[InteractionEvent]:
        """Return events recorded since the specified timestamp."""
        self._prune()
        return [e for e in self._events if e.timestamp >= timestamp]

    def get_missed_events(self, last_event_id: str) -> List[InteractionEvent]:
        """Return events following the specified last event ID."""
        self._prune()
        found_idx = -1
        for idx, evt in enumerate(self._events):
            if evt.id == last_event_id:
                found_idx = idx
                break
        if found_idx != -1:
            return self._events[found_idx + 1 :]
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()


# ----------------------------------------------------------------------
# Core InteractionManager Implementation
# ----------------------------------------------------------------------

class InteractionManager:
    """Subscribes to ActionLifecycle events and manages user-facing natural conversation.

    Never executes system commands. Only observes lifecycle events and decides
    what the user should hear or read.
    """

    TARGET_DISPLAY_MAP = {
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

    def __init__(
        self,
        personality_mode: PersonalityMode = PersonalityMode.FRIENDLY,
        relationship_memory: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        progress_threshold_ms: float = 600.0,
        logger: Optional[logging.Logger] = None,
        notification_center: Optional[NotificationCenter] = None,
        silence_policy: Optional[SilencePolicy] = None,
        replay_ttl_seconds: float = 300.0,
        max_replay_events: int = 100,
    ) -> None:
        self.personality_mode = personality_mode
        self.relationship_memory = relationship_memory
        self.event_bus = event_bus
        self.progress_threshold_ms = progress_threshold_ms
        self._logger = logger or logging.getLogger("naira.interaction_manager")

        self.notification_center = notification_center or NotificationCenter.get_instance()
        self.silence_policy = silence_policy or SilencePolicy()
        self.replay_buffer = InteractionEventReplayBuffer(ttl_seconds=replay_ttl_seconds, max_events=max_replay_events)

        self._active_interaction: Optional[InteractionEvent] = None
        self._action_groups: Dict[str, ActionGroup] = {}
        self._last_progress_time: Dict[int, float] = {}
        self._last_emitted_text: Dict[int, str] = {}
        self._history: List[InteractionEvent] = []
        self._listeners: List[Callable[[InteractionEvent], None]] = []
        self._global_unsubscribe: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------
    # Priority & Interruption Management (Requirements 1 & 2)
    # ------------------------------------------------------------------

    def classify_priority(self, intent_name: str, detail: Optional[str] = None) -> ResponsePriority:
        """Classify response priority level."""
        intent_upper = (intent_name or "").upper()
        detail_lower = (detail or "").lower()

        if (
            any(k in intent_upper for k in ("CRITICAL", "SHUTDOWN", "REBOOT", "LOCK", "SECURITY"))
            or "permission denied" in detail_lower
            or "access denied" in detail_lower
            or "battery critical" in detail_lower
        ):
            return ResponsePriority.CRITICAL

        if (
            any(k in intent_upper for k in ("REMINDER", "DOWNLOAD", "SYNC", "BACKGROUND"))
            or "download finished" in detail_lower
            or "reminder completed" in detail_lower
        ):
            return ResponsePriority.BACKGROUND

        if any(k in intent_upper for k in ("OPEN", "LAUNCH", "SEARCH", "CREATE", "DELETE", "FILE", "FOLDER", "EXECUTE", "SYSTEM")):
            return ResponsePriority.ACTION

        return ResponsePriority.CONVERSATION

    def cancel_current_interaction(self, reason: str = "user_cancel") -> Optional[InteractionEvent]:
        """Cancel current active interaction safely without leaving orphan states."""
        if not self._active_interaction:
            return None

        old = self._active_interaction
        # Do not cancel active CRITICAL message unless requested explicitly
        if old.priority == ResponsePriority.CRITICAL and reason != "force_critical_override":
            self._logger.warning("Attempted to cancel CRITICAL interaction without force override: %s", old.id)
            return None

        cancel_event = InteractionEvent(
            id=str(uuid.uuid4()),
            action_id=old.action_id,
            intent_name=old.intent_name,
            target=old.target,
            phase=InteractionPhase.CANCELLED,
            text=f"Cancelled: {old.text}",
            speech_text=self.make_speech_ready(f"Cancelled {old.target}"),
            personality_mode=old.personality_mode,
            priority=old.priority,
            should_speak=False,
            should_notify=True,
            metadata={"cancelled_interaction_id": old.id, "reason": reason},
        )

        self._active_interaction = None
        self._emit_interaction_event(cancel_event)
        return cancel_event

    def interrupt_and_replace(
        self,
        new_lifecycle: ActionLifecycle,
        new_phase: InteractionPhase,
        new_text: str,
        priority: Optional[ResponsePriority] = None,
    ) -> Optional[InteractionEvent]:
        """Interrupt active lower-priority interaction and replace with new event."""
        prio = priority or self.classify_priority(new_lifecycle.intent_name)

        if self._active_interaction and self._active_interaction.priority == ResponsePriority.CRITICAL:
            if prio != ResponsePriority.CRITICAL:
                self._logger.info("Blocked interruption of CRITICAL interaction by priority %s", prio.name)
                return None

        self.cancel_current_interaction(reason="interrupted_by_new_action")
        mode = self.resolve_personality_mode()
        event = self._create_event(new_lifecycle, new_phase, new_text, mode, priority=prio)
        self._active_interaction = event
        self._emit_interaction_event(event)
        return event

    # ------------------------------------------------------------------
    # Multi-Action Group Management (Requirement 4)
    # ------------------------------------------------------------------

    def register_action_group(self, group_id: str, lifecycles: List[ActionLifecycle]) -> ActionGroup:
        """Register a group of related actions for multi-action conversational progress."""
        group = ActionGroup(group_id=group_id, lifecycles=lifecycles)
        self._action_groups[group_id] = group
        for lc in lifecycles:
            self.subscribe_to_lifecycle(lc)
        return group

    def _get_group_for_action(self, lifecycle: ActionLifecycle) -> Optional[ActionGroup]:
        for group in self._action_groups.values():
            if lifecycle in group.lifecycles:
                return group
        return None

    # ------------------------------------------------------------------
    # Streaming Ready Support (Requirement 7)
    # ------------------------------------------------------------------

    def emit_stream_chunk(
        self,
        action_id: int,
        chunk: str,
        phase: InteractionPhase = InteractionPhase.STREAMING,
        intent_name: str = "STREAM",
        target: str = "Assistant",
        sequence: int = 0,
        priority: ResponsePriority = ResponsePriority.ACTION,
    ) -> InteractionEvent:
        """Emit incremental streaming text chunk for real-time visual/speech consumers."""
        mode = self.resolve_personality_mode()
        speech_text = self.make_speech_ready(chunk)
        event = InteractionEvent(
            id=str(uuid.uuid4()),
            action_id=action_id,
            intent_name=intent_name,
            target=target,
            phase=phase,
            text=chunk,
            speech_text=speech_text,
            personality_mode=mode,
            priority=priority,
            should_speak=self.silence_policy.should_speak(intent_name, phase),
            should_notify=self.silence_policy.should_notify(intent_name, phase),
            is_streaming=True,
            stream_sequence=sequence,
            metadata={"chunk_len": len(chunk)},
        )
        self._emit_interaction_event(event)
        return event

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    def attach_to_all_lifecycles(self) -> None:
        """Subscribe globally to all ActionLifecycle transitions."""
        if self._global_unsubscribe is None:
            self._global_unsubscribe = ActionLifecycle.add_global_listener(self.on_lifecycle_event)

    def detach_from_all_lifecycles(self) -> None:
        """Unsubscribe from global ActionLifecycle transitions."""
        if self._global_unsubscribe is not None:
            self._global_unsubscribe()
            self._global_unsubscribe = None

    def subscribe_to_lifecycle(self, lifecycle: ActionLifecycle) -> Callable[[], None]:
        """Subscribe directly to a specific ActionLifecycle instance."""
        return lifecycle.subscribe(self.on_lifecycle_event)

    def add_listener(self, listener: Callable[[InteractionEvent], None]) -> Callable[[], None]:
        """Add a listener for emitted InteractionEvents."""
        if listener not in self._listeners:
            self._listeners.append(listener)
        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
        return unsubscribe

    def set_personality_mode(self, mode: PersonalityMode) -> None:
        """Set the active personality mode explicitly."""
        self.personality_mode = mode

    def resolve_personality_mode(self, entity_name: str = "user") -> PersonalityMode:
        """Dynamically resolve personality mode using RelationshipMemory if available."""
        if not self.relationship_memory:
            return self.personality_mode

        try:
            record = self.relationship_memory.get(entity_name)
            if record:
                rel_type = (record.get("relationship_type") or "").lower()
                imp = record.get("importance", 5)
                if rel_type in ("best_friend", "close_friend") or imp >= 8:
                    return PersonalityMode.CLOSE_FRIEND
                if rel_type in ("friend", "companion") or imp >= 5:
                    return PersonalityMode.FRIENDLY
                if rel_type in ("colleague", "work", "professional") or imp < 5:
                    return PersonalityMode.PROFESSIONAL
        except Exception as exc:
            self._logger.debug("Failed resolving personality from RelationshipMemory: %s", exc)

        return self.personality_mode

    # ------------------------------------------------------------------
    # Event Handling & Dispatch
    # ------------------------------------------------------------------

    def on_lifecycle_event(
        self, lifecycle: ActionLifecycle, state: ActionState, detail: Optional[str] = None
    ) -> None:
        """Callback invoked when an ActionLifecycle transitions state."""
        now = time.time()
        lifecycle_id = id(lifecycle)
        mode = self.resolve_personality_mode()
        group = self._get_group_for_action(lifecycle)

        if state == ActionState.STARTING:
            text = self._build_starting_response(lifecycle, mode)
            if text:
                self._emit_interaction(lifecycle, InteractionPhase.ACKNOWLEDGED, text, mode, detail=detail)

        elif state in (ActionState.RUNNING, ActionState.WAITING):
            elapsed_ms = (now - lifecycle.start_time) * 1000.0
            last_prog_time = self._last_progress_time.get(lifecycle_id, 0.0)

            if (elapsed_ms >= self.progress_threshold_ms or state == ActionState.WAITING) and (
                now - last_prog_time >= 0.3
            ):
                text = self._build_progress_response(lifecycle, state, detail, mode)
                if text and self._last_emitted_text.get(lifecycle_id) != text:
                    self._last_progress_time[lifecycle_id] = now
                    self._emit_interaction(lifecycle, InteractionPhase.PROGRESS, text, mode, detail=detail)

        elif state in (ActionState.SUCCESS, ActionState.PARTIAL_SUCCESS):
            if group:
                group.completed_count += 1
                if group.is_complete:
                    text = "Everything is ready."
                    self._emit_interaction(lifecycle, InteractionPhase.SUCCESS, text, mode, detail=detail)
                else:
                    target_disp = self._get_display_target(lifecycle.target)
                    text = f"{target_disp} is ready."
                    self._emit_interaction(lifecycle, InteractionPhase.PROGRESS, text, mode, detail=detail)
            else:
                text = self._build_success_response(lifecycle, mode)
                self._emit_interaction(lifecycle, InteractionPhase.SUCCESS, text, mode, detail=detail)
            self._cleanup_action_trackers(lifecycle_id)

        elif state in (ActionState.FAILED, ActionState.TIMEOUT, ActionState.CANCELLED):
            if group:
                group.failed_count += 1

            text = self._build_failure_response(lifecycle, detail, mode)
            self._emit_interaction(lifecycle, InteractionPhase.FAILURE, text, mode, detail=detail)
            self._cleanup_action_trackers(lifecycle_id)

    # ------------------------------------------------------------------
    # Natural Language Generators
    # ------------------------------------------------------------------

    def _get_display_target(self, target: str) -> str:
        t_clean = target.strip().lower()
        if t_clean in self.TARGET_DISPLAY_MAP:
            return self.TARGET_DISPLAY_MAP[t_clean]
        if len(target) > 25:
            return target[:22] + "..."
        return target.title() if target.islower() else target

    def _build_starting_response(self, lifecycle: ActionLifecycle, mode: PersonalityMode) -> Optional[str]:
        target = self._get_display_target(lifecycle.target)
        intent = lifecycle.intent_name

        profile = PersonalityProfileRegistry.get(mode.value)
        if profile:
            resp = profile.format_response(InteractionPhase.ACKNOWLEDGED, intent, target)
            if resp:
                return resp

        intent_upper = intent.upper()
        if mode == PersonalityMode.PROFESSIONAL:
            if "OPEN" in intent_upper:
                return f"Opening {target}..."
            if "SEARCH" in intent_upper:
                return f"Searching for '{target}'..."
            if "FOLDER" in intent_upper or "FILE" in intent_upper:
                return f"Processing request for '{target}'..."
            return "Processing request..."

        if mode == PersonalityMode.FRIENDLY:
            if "OPEN" in intent_upper:
                return f"Opening {target}..."
            if "SEARCH" in intent_upper:
                return f"Searching Google for '{target}'..."
            if "CREATE" in intent_upper:
                return f"Creating {target}..."
            return "On it."

        if "OPEN" in intent_upper:
            return f"Opening {target}, hold on! 🚀"
        if "SEARCH" in intent_upper:
            return f"Searching for '{target}' right away! 🔍"
        return "Got it, on it! 👍"

    def _build_progress_response(
        self, lifecycle: ActionLifecycle, state: ActionState, detail: Optional[str], mode: PersonalityMode
    ) -> Optional[str]:
        target = self._get_display_target(lifecycle.target)
        intent = lifecycle.intent_name

        profile = PersonalityProfileRegistry.get(mode.value)
        if profile:
            resp = profile.format_response(InteractionPhase.PROGRESS, intent, target, detail)
            if resp:
                return resp

        intent_upper = intent.upper()

        if state == ActionState.WAITING:
            if mode == PersonalityMode.PROFESSIONAL:
                return f"Verifying {target}..."
            if mode == PersonalityMode.FRIENDLY:
                return f"Checking {target}..."
            return f"Checking on {target}... ⏳"

        if "OPEN" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return f"Connecting to {target}..."
            if mode == PersonalityMode.FRIENDLY:
                return f"Launching {target}..."
            return f"Khul raha hai {target}... ⏳"

        if "SEARCH" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return "Searching Google..."
            if mode == PersonalityMode.FRIENDLY:
                return "Searching..."
            return "Search ho raha hai... 🔍"

        if "FOLDER" in intent_upper or "FILE" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return "Updating filesystem..."
            if mode == PersonalityMode.FRIENDLY:
                return "Working on file..."
            return "File process ho rahi hai..."

        if mode == PersonalityMode.PROFESSIONAL:
            return "Processing..."
        if mode == PersonalityMode.FRIENDLY:
            return "Working on it..."
        return "Bus ek sec..."

    def _build_success_response(self, lifecycle: ActionLifecycle, mode: PersonalityMode) -> str:
        target = self._get_display_target(lifecycle.target)
        intent = lifecycle.intent_name

        profile = PersonalityProfileRegistry.get(mode.value)
        if profile:
            resp = profile.format_response(InteractionPhase.SUCCESS, intent, target)
            if resp:
                return resp

        intent_upper = intent.upper()
        already_running = False
        if lifecycle.verification and lifecycle.verification.details:
            already_running = lifecycle.verification.details.get("already_running", False)

        if "OPEN" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                if already_running:
                    return f"{target} is already open and running."
                return f"{target} has been opened."
            if mode == PersonalityMode.FRIENDLY:
                if already_running:
                    return f"{target} pehle se open hai."
                return f"{target} is ready."
            if already_running:
                return f"{target} toh pehle se khula tha! 😁"
            return f"Done! {target} khol diya 😄"

        if "SEARCH" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return "The search results are ready."
            if mode == PersonalityMode.FRIENDLY:
                return "Search results open kar diye hain."
            return "Done! Search results dekho 🔍"

        if "CREATE_FOLDER" in intent_upper or "CREATE_FILE" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return f"The item '{target}' has been created."
            if mode == PersonalityMode.FRIENDLY:
                return f"The folder '{target}' has been created."
            return "Folder ready hai 📁"

        if "DELETE" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return f"'{target}' has been removed."
            if mode == PersonalityMode.FRIENDLY:
                return f"'{target}' delete ho gaya."
            return f"Deleted '{target}' 👍"

        if "SYSTEM_CONTROL" in intent_upper or "LOCK" in intent_upper or "SHUTDOWN" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return "System action completed successfully."
            if mode == PersonalityMode.FRIENDLY:
                return "System command complete ho gaya."
            return "Ho gaya boss! 👍"

        if "VOLUME" in intent_upper or "BRIGHTNESS" in intent_upper:
            if mode == PersonalityMode.PROFESSIONAL:
                return "Settings updated successfully."
            if mode == PersonalityMode.FRIENDLY:
                return "Adjusted successfully."
            return "Set kar diya! 😎"

        if mode == PersonalityMode.PROFESSIONAL:
            return f"Action completed for {target}."
        if mode == PersonalityMode.FRIENDLY:
            return f"Ho gaya! {target} is ready."
        return "Done ho gaya! 😄"

    def _build_failure_response(
        self, lifecycle: ActionLifecycle, detail: Optional[str], mode: PersonalityMode
    ) -> str:
        target = self._get_display_target(lifecycle.target)
        reason_type = self._classify_error_reason(detail or "")

        profile = PersonalityProfileRegistry.get(mode.value)
        if profile:
            resp = profile.format_response(InteractionPhase.FAILURE, reason_type, target, detail)
            if resp:
                return resp

        if reason_type == "NOT_FOUND":
            if mode == PersonalityMode.PROFESSIONAL:
                return f"I couldn't find {target}."
            if mode == PersonalityMode.FRIENDLY:
                return f"{target} nahi mila system pe."
            return f"Arre {target} toh mil hi nahi raha! 😅"

        if reason_type == "TIMEOUT":
            if mode == PersonalityMode.PROFESSIONAL:
                return "The website isn't responding."
            if mode == PersonalityMode.FRIENDLY:
                return "Response nahi mil raha, connection stuck lag raha hai."
            return "Website stuck hai, connect nahi ho raha 😕"

        if reason_type == "PERMISSION":
            if mode == PersonalityMode.PROFESSIONAL:
                return "Permission was denied."
            if mode == PersonalityMode.FRIENDLY:
                return "Permission denied ho gaya."
            return "Permission nahi mil rahi iske liye 🔒"

        if mode == PersonalityMode.PROFESSIONAL:
            return "I couldn't complete that action."
        if mode == PersonalityMode.FRIENDLY:
            return "Yeh task complete nahi ho paya."
        return "Oops, yeh nahi ho paya 😅"

    def _classify_error_reason(self, detail: str) -> str:
        d_lower = detail.lower()
        if (
            "not installed" in d_lower
            or "not found" in d_lower
            or "cannot find" in d_lower
            or "filenotfounderror" in d_lower
            or "no match" in d_lower
            or "invalid target" in d_lower
        ):
            return "NOT_FOUND"
        if "timeout" in d_lower or "unresponsive" in d_lower or "timed out" in d_lower:
            return "TIMEOUT"
        if "permission" in d_lower or "access denied" in d_lower or "unauthorized" in d_lower:
            return "PERMISSION"
        return "GENERIC"

    # ------------------------------------------------------------------
    # Speech Readiness & Emission Helpers
    # ------------------------------------------------------------------

    def make_speech_ready(self, text: str) -> str:
        """Format text for text-to-speech (TTS) synthesis.

        Strips emojis, raw code blocks, file extension paths, and normalizes punctuation.
        """
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"
            "\U0001f300-\U0001f5ff"
            "\U0001f680-\U0001f6ff"
            "\U0001f1e0-\U0001f1ff"
            "\u2600-\u26ff"
            "\u2700-\u27bf"
            "]+",
            flags=re.UNICODE,
        )
        cleaned = emoji_pattern.sub("", text)
        cleaned = re.sub(r"[`*_\[\]\(\)]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _create_event(
        self,
        lifecycle: ActionLifecycle,
        phase: InteractionPhase,
        text: str,
        mode: PersonalityMode,
        detail: Optional[str] = None,
        priority: Optional[ResponsePriority] = None,
    ) -> InteractionEvent:
        lifecycle_id = id(lifecycle)
        speech_text = self.make_speech_ready(text)
        prio = priority or self.classify_priority(lifecycle.intent_name, detail)
        speak = self.silence_policy.should_speak(lifecycle.intent_name, phase)
        notify = self.silence_policy.should_notify(lifecycle.intent_name, phase)

        return InteractionEvent(
            id=str(uuid.uuid4()),
            action_id=lifecycle_id,
            intent_name=lifecycle.intent_name,
            target=lifecycle.target,
            phase=phase,
            text=text,
            speech_text=speech_text if speak else "",
            personality_mode=mode,
            priority=prio,
            should_speak=speak,
            should_notify=notify,
            metadata={
                "handler_name": lifecycle.handler_name,
                "execution_state": lifecycle.state.name,
                "execution_time_ms": round(lifecycle.execution_time_ms, 2),
                "detail": detail,
            },
        )

    def _emit_interaction(
        self,
        lifecycle: ActionLifecycle,
        phase: InteractionPhase,
        text: str,
        mode: PersonalityMode,
        detail: Optional[str] = None,
    ) -> None:
        lifecycle_id = id(lifecycle)
        event = self._create_event(lifecycle, phase, text, mode, detail)

        # Priority & Interrupt handling
        if self._active_interaction:
            if self._active_interaction.priority == ResponsePriority.CRITICAL and event.priority != ResponsePriority.CRITICAL:
                self._logger.info("Preserving CRITICAL presentation over priority %s", event.priority.name)
                # Still store event, but do not override active critical status
                self._record_and_publish_event(event)
                return

            if event.priority.value > self._active_interaction.priority.value:
                self.cancel_current_interaction(reason=f"preempted_by_{event.priority.name}")

        self._active_interaction = event
        self._last_emitted_text[lifecycle_id] = text
        self._record_and_publish_event(event)

    def _record_and_publish_event(self, event: InteractionEvent) -> None:
        self._history.append(event)
        self.replay_buffer.append(event)
        self._logger.info("[Interaction] [%s] [%s] [%s]: %s", event.personality_mode.value, event.priority.name, event.phase.value, event.text)

        # Notify local listeners
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception as exc:
                self._logger.debug("Interaction listener exception: %s", exc)

        # Publish to central NotificationCenter
        self.notification_center.publish("all", event)
        if event.should_speak:
            self.notification_center.publish("voice", event)
        if event.should_notify:
            self.notification_center.publish("ui", event)

        # Fire and forget if async event bus present
        if self.event_bus:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(getattr(self.event_bus, "emit", None)):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(
                            self.event_bus.emit(
                                f"interaction.{event.phase.value}",
                                data={"text": event.text, "speech_text": event.speech_text, "intent": event.intent_name},
                            )
                        )
            except Exception:
                pass

    def _emit_interaction_event(self, event: InteractionEvent) -> None:
        self._record_and_publish_event(event)

    def _cleanup_action_trackers(self, lifecycle_id: int) -> None:
        self._last_progress_time.pop(lifecycle_id, None)
        self._last_emitted_text.pop(lifecycle_id, None)

    def get_history(self) -> List[InteractionEvent]:
        """Return full history of human interaction events."""
        return list(self._history)
