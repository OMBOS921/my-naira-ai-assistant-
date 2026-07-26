"""
Unit tests for Human Interaction Layer v2.0 (InteractionManager & ActionLifecycle integration).

Tests cover:
- Baseline features: Decoupled execution state, anti-spam progress, contextual success/failure, adaptive personalities, speech readiness, global attachment, listeners, backward compatibility.
- Requirement 1: Conversation Priority Engine & Critical Message Protection
- Requirement 2: Interruptible Conversation Management & Safe Cancellation
- Requirement 3: Event-Driven Notification Center Pub/Sub
- Requirement 4: Multi-Action Conversation & Action Groups
- Requirement 5: Configurable Silence Policy
- Requirement 6: Dynamic & Extensible Personality Profiles
- Requirement 7: Streaming Ready Support
- Requirement 8: Event Replay Buffer (TTL & Memory Cap)
- Requirement 9 & 10: Zero Regression & Latency Performance Budget (< 2ms)
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from backend.runtime.action_lifecycle import ActionLifecycle, ActionState
from backend.runtime.interaction_manager import (
    ActionGroup,
    InteractionEvent,
    InteractionManager,
    InteractionPhase,
    NotificationCenter,
    PersonalityMode,
    PersonalityProfile,
    PersonalityProfileRegistry,
    ResponsePriority,
    SilencePolicy,
)


class TestHumanInteractionLayer:
    """Test suite for InteractionManager v2.0."""

    def setup_method(self) -> None:
        """Reset NotificationCenter singleton between test runs for isolation."""
        NotificationCenter.reset_instance()

    # ------------------------------------------------------------------
    # Baseline & Backward Compatibility Tests
    # ------------------------------------------------------------------

    def test_decoupled_execution_and_conversation_state(self) -> None:
        """Verify execution state and conversation state remain decoupled."""
        im = InteractionManager(personality_mode=PersonalityMode.PROFESSIONAL)
        lifecycle = ActionLifecycle("OPEN_APP", "chrome", "LaunchApplication")
        im.subscribe_to_lifecycle(lifecycle)

        lifecycle.transition_to(ActionState.STARTING, "Routing started")
        lifecycle.transition_to(ActionState.RUNNING, "Launching process")
        lifecycle.transition_to(ActionState.SUCCESS, "Launch verified successfully")

        events = im.get_history()
        assert len(events) >= 2

        phases = [e.phase for e in events]
        assert InteractionPhase.ACKNOWLEDGED in phases
        assert InteractionPhase.SUCCESS in phases

        for e in events:
            assert "SUCCESS" not in e.text
            assert "QUEUED" not in e.text
            assert "ActionState" not in e.text

        assert lifecycle.state == ActionState.SUCCESS
        assert events[-1].text == "Chrome has been opened."

    def test_progressive_responses_and_anti_spam(self) -> None:
        """Verify progressive status updates for actions > 600ms and spam prevention."""
        im = InteractionManager(
            personality_mode=PersonalityMode.FRIENDLY, progress_threshold_ms=600.0
        )
        lifecycle = ActionLifecycle("OPEN_APP", "chrome", "LaunchApplication")
        im.subscribe_to_lifecycle(lifecycle)

        lifecycle.start_time = time.time() - 0.7
        lifecycle.transition_to(ActionState.RUNNING, "Launching Chrome process")

        events = im.get_history()
        prog_events = [e for e in events if e.phase == InteractionPhase.PROGRESS]
        assert len(prog_events) == 1
        assert "Launching Chrome" in prog_events[0].text or "Chrome" in prog_events[0].text

        lifecycle.transition_to(ActionState.RUNNING, "Launching Chrome process repeat")
        events_after = im.get_history()
        assert len([e for e in events_after if e.phase == InteractionPhase.PROGRESS]) == 1

    def test_contextual_success_responses(self) -> None:
        """Verify short, natural, friendly success responses across personality modes."""
        im_prof = InteractionManager(personality_mode=PersonalityMode.PROFESSIONAL)
        lc_prof = ActionLifecycle("OPEN_APP", "youtube", "LaunchBrowser")
        im_prof.subscribe_to_lifecycle(lc_prof)
        lc_prof.transition_to(ActionState.SUCCESS)
        assert im_prof.get_history()[-1].text == "YouTube has been opened."

        im_friend = InteractionManager(personality_mode=PersonalityMode.FRIENDLY)
        lc_friend = ActionLifecycle("OPEN_APP", "youtube", "LaunchBrowser")
        im_friend.subscribe_to_lifecycle(lc_friend)
        lc_friend.transition_to(ActionState.SUCCESS)
        assert "YouTube" in im_friend.get_history()[-1].text

        im_close = InteractionManager(personality_mode=PersonalityMode.CLOSE_FRIEND)
        lc_close = ActionLifecycle("OPEN_APP", "youtube", "LaunchBrowser")
        im_close.subscribe_to_lifecycle(lc_close)
        lc_close.transition_to(ActionState.SUCCESS)
        assert "Done!" in im_close.get_history()[-1].text or "YouTube" in im_close.get_history()[-1].text

    def test_helpful_failure_responses_and_exception_masking(self) -> None:
        """Verify stack traces and internal exceptions are masked into natural failure messages."""
        im = InteractionManager(personality_mode=PersonalityMode.PROFESSIONAL)
        lifecycle = ActionLifecycle("OPEN_APP", "nonexistent_app", "LaunchApplication")
        im.subscribe_to_lifecycle(lifecycle)

        raw_exception_detail = (
            "Execution exception: FileNotFoundError: [WinError 2] The system cannot find the file specified\n"
            "Traceback (most recent call last):\n"
            "  File 'fast_command_router.py', line 1429, in execute_fast_command"
        )
        lifecycle.transition_to(ActionState.FAILED, raw_exception_detail)

        fail_event = im.get_history()[-1]
        assert fail_event.phase == InteractionPhase.FAILURE
        assert "Traceback" not in fail_event.text
        assert "FileNotFoundError" not in fail_event.text
        assert "WinError" not in fail_event.text
        assert fail_event.text == "I couldn't find Nonexistent_App."

    def test_adaptive_personality_modes(self) -> None:
        """Verify adaptive personality variations based on RelationshipMemory."""
        mock_rel_mem = MagicMock()
        mock_rel_mem.get.return_value = {
            "entity_name": "user",
            "relationship_type": "close_friend",
            "importance": 9,
        }

        im = InteractionManager(relationship_memory=mock_rel_mem)
        lifecycle = ActionLifecycle("OPEN_APP", "chrome", "LaunchApplication")
        im.subscribe_to_lifecycle(lifecycle)

        lifecycle.transition_to(ActionState.SUCCESS)

        last_event = im.get_history()[-1]
        assert last_event.personality_mode == PersonalityMode.CLOSE_FRIEND
        assert "Chrome" in last_event.text

    def test_speech_readiness_tts_formatting(self) -> None:
        """Verify text formatting is cleaned for TTS engines."""
        im = InteractionManager()
        raw_text = "Done! Chrome open hai 😄 `[PID 1234]`"
        speech_text = im.make_speech_ready(raw_text)

        assert "😄" not in speech_text
        assert "`" not in speech_text
        assert "[" not in speech_text
        assert "Done! Chrome open hai PID 1234" in speech_text

    def test_global_lifecycle_attachment(self) -> None:
        """Verify InteractionManager can attach globally to all ActionLifecycle instances."""
        im = InteractionManager(personality_mode=PersonalityMode.FRIENDLY)
        im.attach_to_all_lifecycles()

        try:
            lc1 = ActionLifecycle("OPEN_APP", "vscode", "LaunchApplication")
            lc1.transition_to(ActionState.STARTING)
            lc1.transition_to(ActionState.SUCCESS)

            lc2 = ActionLifecycle("WEB_SEARCH", "Python tutorial", "WebSearch")
            lc2.transition_to(ActionState.STARTING)
            lc2.transition_to(ActionState.SUCCESS)

            events = im.get_history()
            assert len(events) == 4
            targets = [e.target for e in events]
            assert "vscode" in targets
            assert "Python tutorial" in targets
        finally:
            im.detach_from_all_lifecycles()

    def test_event_listener_callback(self) -> None:
        """Verify external listeners receive emitted InteractionEvents."""
        im = InteractionManager()
        received_events = []

        def custom_listener(evt: InteractionEvent) -> None:
            received_events.append(evt)

        im.add_listener(custom_listener)

        lifecycle = ActionLifecycle("CREATE_FOLDER", "Projects", "FileSystem")
        im.subscribe_to_lifecycle(lifecycle)

        lifecycle.transition_to(ActionState.STARTING)
        lifecycle.transition_to(ActionState.SUCCESS)

        assert len(received_events) == 2
        assert received_events[0].phase == InteractionPhase.ACKNOWLEDGED
        assert received_events[1].phase == InteractionPhase.SUCCESS

    def test_backward_compatibility(self) -> None:
        """Verify ActionLifecycle API and debug metadata remain fully compatible."""
        lifecycle = ActionLifecycle("OPEN_APP", "notepad", "LaunchApplication", debug_mode=True)
        lifecycle.transition_to(ActionState.STARTING)
        lifecycle.set_verification(True, "notepad.exe", "Notepad")
        lifecycle.transition_to(ActionState.SUCCESS)

        meta = lifecycle.get_debug_metadata()
        assert meta["execution_state"] == "SUCCESS"
        assert meta["verification_result"]["verified"] is True
        assert meta["verification_result"]["running_process"] == "notepad.exe"

    # ------------------------------------------------------------------
    # Architectural Extensions (Requirements 1 - 10)
    # ------------------------------------------------------------------

    def test_requirement_1_priority_engine_and_critical_protection(self) -> None:
        """Requirement 1: Verify priority classification & critical message preemption protection."""
        im = InteractionManager()

        # Classify priorities
        assert im.classify_priority("SHUTDOWN_SYSTEM", "battery critical").value == ResponsePriority.CRITICAL.value
        assert im.classify_priority("OPEN_APP", "chrome").value == ResponsePriority.ACTION.value
        assert im.classify_priority("GREETING", "hello").value == ResponsePriority.CONVERSATION.value
        assert im.classify_priority("DOWNLOAD_FILE", "background").value == ResponsePriority.BACKGROUND.value

        # Trigger critical interaction
        lc_crit = ActionLifecycle("SHUTDOWN_SYSTEM", "battery critical", "SystemPower")
        im.subscribe_to_lifecycle(lc_crit)
        lc_crit.transition_to(ActionState.STARTING)

        active = im._active_interaction
        assert active is not None
        assert active.priority == ResponsePriority.CRITICAL

        # Lower/equal priority message attempts to interrupt critical presentation
        lc_act = ActionLifecycle("OPEN_APP", "chrome", "LaunchApp")
        im.subscribe_to_lifecycle(lc_act)
        lc_act.transition_to(ActionState.STARTING)

        # Active interaction must remain the CRITICAL event
        assert im._active_interaction is not None
        assert im._active_interaction.priority == ResponsePriority.CRITICAL
        assert im._active_interaction.target == "battery critical"

    def test_requirement_2_interruptible_conversation(self) -> None:
        """Requirement 2: Verify safe cancellation and preemption without orphan states."""
        im = InteractionManager()
        lc1 = ActionLifecycle("OPEN_APP", "chrome", "LaunchApp")
        im.subscribe_to_lifecycle(lc1)
        lc1.transition_to(ActionState.STARTING)

        assert im._active_interaction is not None
        assert "Opening Chrome" in im._active_interaction.text

        # User cancels
        cancel_evt = im.cancel_current_interaction(reason="user_cancel")
        assert cancel_evt is not None
        assert cancel_evt.phase == InteractionPhase.CANCELLED
        assert im._active_interaction is None

        # Interrupt and replace with Firefox action
        lc2 = ActionLifecycle("OPEN_APP", "firefox", "LaunchApp")
        new_evt = im.interrupt_and_replace(lc2, InteractionPhase.ACKNOWLEDGED, "Opening Firefox instead...")
        assert new_evt is not None
        assert im._active_interaction == new_evt
        assert "Opening Firefox" in new_evt.text

    def test_requirement_3_notification_center_pub_sub(self) -> None:
        """Requirement 3: Verify central NotificationCenter pub/sub channel isolation."""
        nc = NotificationCenter.get_instance()
        ui_received = []
        voice_received = []

        nc.subscribe("ui", lambda evt: ui_received.append(evt))
        nc.subscribe("voice", lambda evt: voice_received.append(evt))

        im = InteractionManager(notification_center=nc)
        lc = ActionLifecycle("OPEN_APP", "vscode", "LaunchApp")
        im.subscribe_to_lifecycle(lc)
        lc.transition_to(ActionState.STARTING)

        assert len(ui_received) == 1
        assert len(voice_received) == 1
        assert ui_received[0].target == "vscode"

    def test_requirement_4_multi_action_group_conversation(self) -> None:
        """Requirement 4: Verify multi-action groups produce progressive aggregate feedback."""
        im = InteractionManager()

        lc1 = ActionLifecycle("OPEN_APP", "chrome", "LaunchApp")
        lc2 = ActionLifecycle("WEB_SEARCH", "GitHub", "Search")
        lc3 = ActionLifecycle("OPEN_APP", "vscode", "LaunchApp")

        group = im.register_action_group("multi_task_1", [lc1, lc2, lc3])
        assert group.total_actions == 3

        lc1.transition_to(ActionState.STARTING)
        lc1.transition_to(ActionState.SUCCESS)

        lc2.transition_to(ActionState.STARTING)
        lc2.transition_to(ActionState.SUCCESS)

        lc3.transition_to(ActionState.STARTING)
        lc3.transition_to(ActionState.SUCCESS)

        history = im.get_history()
        # Final success event should emit group completion "Everything is ready."
        assert history[-1].text == "Everything is ready."
        assert group.is_complete is True

    def test_requirement_5_silence_policy(self) -> None:
        """Requirement 5: Verify silence policy suppresses speech for utility actions."""
        policy = SilencePolicy()
        im = InteractionManager(silence_policy=policy)

        lc_vol = ActionLifecycle("VOLUME_SET", "50%", "AudioControl")
        im.subscribe_to_lifecycle(lc_vol)
        lc_vol.transition_to(ActionState.SUCCESS)

        vol_evt = im.get_history()[-1]
        assert vol_evt.should_speak is False
        assert vol_evt.speech_text == ""
        assert vol_evt.should_notify is True

        # Custom silence rule
        policy.register_rule("CUSTOM_ACTION", speak=False, notify=False)
        lc_custom = ActionLifecycle("CUSTOM_ACTION", "target", "CustomHandler")
        im.subscribe_to_lifecycle(lc_custom)
        lc_custom.transition_to(ActionState.STARTING)

        custom_evt = im.get_history()[-1]
        assert custom_evt.should_speak is False
        assert custom_evt.should_notify is False

    def test_requirement_6_dynamic_personality_profiles(self) -> None:
        """Requirement 6: Verify future personalities can be registered without code changes."""
        custom_profile = PersonalityProfile(
            name="cyberpunk",
            description="Futuristic AI persona",
            starting_templates={"OPEN": "Booting system protocol for {target}..."},
            success_templates={"OPEN": "{target} neural interface online."},
        )

        PersonalityProfileRegistry.register(custom_profile)
        assert "cyberpunk" in PersonalityProfileRegistry.list_profiles()

        im = InteractionManager(personality_mode=PersonalityMode.CUSTOM)
        im.set_personality_mode(PersonalityMode.CUSTOM)

        # Force profile resolution check
        lc = ActionLifecycle("OPEN_APP", "cyber_net", "LaunchApp")
        resp = custom_profile.format_response(InteractionPhase.ACKNOWLEDGED, lc.intent_name, "cyber_net")
        assert resp == "Booting system protocol for cyber_net..."

    def test_requirement_7_streaming_ready_support(self) -> None:
        """Requirement 7: Verify streaming chunk emissions with sequence tracking."""
        im = InteractionManager()

        chunk_1 = im.emit_stream_chunk(action_id=999, chunk="Thinking...", phase=InteractionPhase.THINKING, sequence=1)
        chunk_2 = im.emit_stream_chunk(action_id=999, chunk="Searching web...", phase=InteractionPhase.SEARCHING, sequence=2)

        assert chunk_1.is_streaming is True
        assert chunk_1.phase == InteractionPhase.THINKING
        assert chunk_1.stream_sequence == 1

        assert chunk_2.is_streaming is True
        assert chunk_2.phase == InteractionPhase.SEARCHING
        assert chunk_2.stream_sequence == 2

    def test_requirement_8_event_replay_buffer(self) -> None:
        """Requirement 8: Verify time & size bounded event replay ring buffer."""
        im = InteractionManager(replay_ttl_seconds=5.0, max_replay_events=3)

        lc1 = ActionLifecycle("OPEN_APP", "app1", "LaunchApp")
        lc2 = ActionLifecycle("OPEN_APP", "app2", "LaunchApp")
        lc3 = ActionLifecycle("OPEN_APP", "app3", "LaunchApp")
        lc4 = ActionLifecycle("OPEN_APP", "app4", "LaunchApp")

        im.subscribe_to_lifecycle(lc1)
        im.subscribe_to_lifecycle(lc2)
        im.subscribe_to_lifecycle(lc3)
        im.subscribe_to_lifecycle(lc4)

        start_time = time.time()
        lc1.transition_to(ActionState.SUCCESS)
        lc2.transition_to(ActionState.SUCCESS)
        lc3.transition_to(ActionState.SUCCESS)
        lc4.transition_to(ActionState.SUCCESS)

        # Max capacity capped at 3
        replayed = im.replay_buffer.get_events_since(start_time)
        assert len(replayed) == 3
        assert replayed[-1].target == "app4"

        # Test miss events query
        first_evt_id = replayed[0].id
        missed = im.replay_buffer.get_missed_events(first_evt_id)
        assert len(missed) == 2

    def test_requirement_10_latency_performance_budget(self) -> None:
        """Requirement 10: Benchmark interaction latency budget (< 2.0 ms)."""
        im = InteractionManager()
        lc = ActionLifecycle("OPEN_APP", "chrome", "LaunchApp")
        im.subscribe_to_lifecycle(lc)

        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            lc.transition_to(ActionState.RUNNING)

        total_elapsed_ms = (time.perf_counter() - start) * 1000.0
        avg_latency_ms = total_elapsed_ms / iterations

        # Must be well under the 2.0 ms budget limit (typically < 0.1 ms)
        assert avg_latency_ms < 2.0, f"Average latency {avg_latency_ms:.4f} ms exceeded 2.0 ms budget"
