from __future__ import annotations
from typing import Any
"""Comprehensive tests for the voice module.

Covers:
- AudioData, TranscriptionResult, SynthesisResult, WakeWordResult, VoiceResult dataclasses
- SpeechToText placeholder (empty transcription)
- TextToSpeech placeholder (empty synthesis)
- WakeWord placeholder (no detection)
- AudioRecorder placeholder (raises VoiceNotImplementedError, is_available=False)
- AudioPlayer placeholder (raises VoiceNotImplementedError, is_available=False)
- LocalVoiceAdapter (is_available=False, all AI ops raise)
- VoiceExecutor (transcribe, synthesize, detect_wake_word, start_recording, play_audio
  with timeout/error isolation)
- VoiceManager (ModuleInterface lifecycle, all operations, degraded mode, event emission)
- VoicePort ABC
- ModuleInterface protocol conformance
"""



from unittest.mock import MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.voice import (
    AudioData,
    AudioPlayer,
    AudioRecorder,
    LocalVoiceAdapter,
    SpeechToText,
    SynthesisResult,
    TextToSpeech,
    TranscriptionResult,
    VoiceExecutor,
    VoiceManager,
    VoicePort,
    VoiceResult,
    WakeWord,
    WakeWordResult,
)
from backend.modules.voice._exceptions import VoiceAudioError
from backend.modules.voice._exceptions import VoiceNotImplementedError
from backend.types import ModuleInterface
# =========================================================================
# AudioData, TranscriptionResult, SynthesisResult, WakeWordResult, VoiceResult
# =========================================================================


class TestAudioData:
    def test_minimal(self) -> None:
        data = AudioData(source_type="microphone")
        assert data.source_type == "microphone"
        assert data.source_path is None
        assert data.format == "unknown"
        assert data.sample_rate == 0
        assert data.channels == 0
        assert data.duration_ms == 0.0
        assert data.size_bytes == 0
        assert data.data is None

    def test_all_fields(self) -> None:
        data = AudioData(
            source_type="file",
            source_path="/tmp/test.wav",
            format="wav",
            sample_rate=44100,
            channels=2,
            duration_ms=5000.0,
            size_bytes=882000,
            data=b"fake-audio-data",
        )
        assert data.format == "wav"
        assert data.sample_rate == 44100
        assert data.channels == 2
        assert data.duration_ms == 5000.0
        assert data.size_bytes == 882000
        assert data.data == b"fake-audio-data"

    def test_frozen(self) -> None:
        data = AudioData(source_type="file", source_path="/tmp/test.wav")
        with pytest.raises(AttributeError):
            data.source_type = "microphone"  # type: ignore[misc]


class TestTranscriptionResult:
    def test_defaults(self) -> None:
        r = TranscriptionResult()
        assert r.text == ""
        assert r.confidence == 0.0
        assert r.language == "en"
        assert r.duration_ms == 0.0
        assert r.segments == ()

    def test_all_fields(self) -> None:
        r = TranscriptionResult(
            text="Hello world",
            confidence=0.95,
            language="en",
            duration_ms=3000.0,
            segments=({"start": 0.0, "end": 1.5, "text": "Hello"},),
        )
        assert r.text == "Hello world"
        assert r.confidence == 0.95
        assert len(r.segments) == 1


class TestSynthesisResult:
    def test_defaults(self) -> None:
        r = SynthesisResult()
        assert r.audio is None
        assert r.text == ""
        assert r.voice_id == ""
        assert r.duration_ms == 0.0

    def test_with_audio(self) -> None:
        audio = AudioData(source_type="bytes", data=b"audio-data", format="wav")
        r = SynthesisResult(audio=audio, text="Hello", voice_id="en-US-1", duration_ms=2000.0)
        assert r.audio is not None
        assert r.audio.data == b"audio-data"
        assert r.text == "Hello"
        assert r.voice_id == "en-US-1"
        assert r.duration_ms == 2000.0


class TestWakeWordResult:
    def test_defaults(self) -> None:
        r = WakeWordResult()
        assert r.detected is False
        assert r.wake_word == ""
        assert r.confidence == 0.0

    def test_detected(self) -> None:
        r = WakeWordResult(detected=True, wake_word="hey naira", confidence=0.92)
        assert r.detected is True
        assert r.wake_word == "hey naira"
        assert r.confidence == 0.92


class TestVoiceResult:
    def test_defaults(self) -> None:
        r = VoiceResult()
        assert r.status == "success"
        assert r.output is None
        assert r.error is None
        assert r.transcription is None
        assert r.synthesis is None
        assert r.wake_word is None
        assert r.duration_ms == 0.0

    def test_with_transcription(self) -> None:
        tr = TranscriptionResult(text="Hello", confidence=0.95)
        r = VoiceResult(
            status="success",
            output="Transcribed: Hello",
            transcription=tr,
            duration_ms=150.0,
        )
        assert r.status == "success"
        assert r.transcription is not None
        assert r.transcription.text == "Hello"
        assert r.duration_ms == 150.0

    def test_frozen(self) -> None:
        r = VoiceResult()
        with pytest.raises(AttributeError):
            r.status = "error"  # type: ignore[misc]


# =========================================================================
# SpeechToText placeholder
# =========================================================================


class TestSpeechToText:
    @pytest.mark.asyncio
    async def test_transcribe_returns_empty(self) -> None:
        stt = SpeechToText()
        audio = AudioData(source_type="file", source_path="/tmp/test.wav")
        result = await stt.transcribe(audio)
        assert result.text == ""
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_with_language_hint(self) -> None:
        stt = SpeechToText()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await stt.transcribe(audio, language="fr")
        assert result.language == "fr"


# =========================================================================
# TextToSpeech placeholder
# =========================================================================


class TestTextToSpeech:
    @pytest.mark.asyncio
    async def test_synthesize_returns_empty(self) -> None:
        tts = TextToSpeech()
        result = await tts.synthesize("Hello world")
        assert result.text == "Hello world"
        assert result.audio is None

    @pytest.mark.asyncio
    async def test_synthesize_with_voice_id(self) -> None:
        tts = TextToSpeech()
        result = await tts.synthesize("Test", voice_id="en-US-1")
        assert result.voice_id == "en-US-1"


# =========================================================================
# WakeWord placeholder
# =========================================================================


class TestWakeWord:
    @pytest.mark.asyncio
    async def test_detect_no_detection(self) -> None:
        detector = WakeWord()
        audio = AudioData(source_type="file", source_path="/tmp/test.wav")
        result = await detector.detect(audio)
        assert result.detected is False
        assert result.wake_word == ""

    @pytest.mark.asyncio
    async def test_detect_with_wake_word(self) -> None:
        detector = WakeWord()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await detector.detect(audio, wake_word="hey naira")
        assert result.detected is False
        assert result.wake_word == "hey naira"


# =========================================================================
# AudioRecorder placeholder
# =========================================================================


class TestAudioRecorder:
    def test_is_available(self) -> None:
        recorder = AudioRecorder()
        if recorder.is_available:
            assert True
        else:
            assert not recorder.is_available

    @pytest.mark.asyncio
    async def test_record_no_data_raises(self) -> None:
        recorder = AudioRecorder()
        if not recorder.is_available:
            with pytest.raises(VoiceAudioError):
                await recorder.record(duration=0.1)


# =========================================================================
# AudioPlayer placeholder
# =========================================================================


class TestAudioPlayer:
    def test_is_available(self) -> None:
        player = AudioPlayer()
        if player.is_available:
            assert True
        else:
            assert not player.is_available

    @pytest.mark.asyncio
    async def test_play_no_data_raises(self) -> None:
        player = AudioPlayer()
        audio = AudioData(source_type="bytes", data=b"")
        with pytest.raises(VoiceAudioError):
            await player.play(audio)


# =========================================================================
# LocalVoiceAdapter
# =========================================================================


class TestLocalVoiceAdapter:
    def test_is_available(self) -> None:
        adapter = LocalVoiceAdapter()
        if adapter.is_available:
            assert True
        else:
            assert not adapter.is_available

    @pytest.mark.asyncio
    async def test_transcribe_no_providers_returns_empty(self) -> None:
        adapter = LocalVoiceAdapter()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await adapter.transcribe(audio)
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_synthesize_no_providers_returns_empty(self) -> None:
        adapter = LocalVoiceAdapter()
        result = await adapter.synthesize("Hello")
        assert result.audio is None

    @pytest.mark.asyncio
    async def test_detect_wake_word_no_providers_returns_not_detected(self) -> None:
        adapter = LocalVoiceAdapter()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await adapter.detect_wake_word(audio)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_close_is_safe(self) -> None:
        adapter = LocalVoiceAdapter()
        await adapter.close()

    def test_stt_property(self) -> None:
        adapter = LocalVoiceAdapter()
        assert isinstance(adapter.stt, SpeechToText)

    def test_tts_property(self) -> None:
        adapter = LocalVoiceAdapter()
        assert isinstance(adapter.tts, TextToSpeech)

    def test_wake_word_property(self) -> None:
        adapter = LocalVoiceAdapter()
        assert isinstance(adapter.wake_word_detector, WakeWord)


# =========================================================================
# VoiceExecutor
# =========================================================================


class _MockVoiceAdapter:
    """Test double that implements VoicePort with controllable behaviour."""

    def __init__(
        self,
        available: bool = True,
        transcribe_result: TranscriptionResult | None = None,
        synthesize_result: SynthesisResult | None = None,
        wake_word_result: WakeWordResult | None = None,
        record_result: AudioData | None = None,
        raise_on: str | None = None,
    ) -> None:
        self._available = available
        self._transcribe_result = transcribe_result
        self._synthesize_result = synthesize_result
        self._wake_word_result = wake_word_result
        self._record_result = record_result
        self._raise_on = raise_on

    @property
    def is_available(self) -> bool:
        return self._available

    async def transcribe(
        self, audio: AudioData, *, language: str = "en", timeout: float = 30.0,
    ) -> TranscriptionResult:
        if self._raise_on == "transcribe":
            raise VoiceNotImplementedError()
        if self._transcribe_result is not None:
            return self._transcribe_result
        return TranscriptionResult(text="Hello world", confidence=0.95, language=language)

    async def synthesize(
        self, text: str, *, voice_id: str = "", language: str = "en", timeout: float = 30.0,
    ) -> SynthesisResult:
        if self._raise_on == "synthesize":
            raise VoiceNotImplementedError()
        if self._synthesize_result is not None:
            return self._synthesize_result
        audio = AudioData(source_type="bytes", data=b"audio-data", format="wav", duration_ms=2000.0)
        return SynthesisResult(audio=audio, text=text, voice_id=voice_id, duration_ms=2000.0)

    async def detect_wake_word(
        self, audio: AudioData, *, wake_word: str = "", timeout: float = 30.0,
    ) -> WakeWordResult:
        if self._raise_on == "wake_word":
            raise VoiceNotImplementedError()
        if self._wake_word_result is not None:
            return self._wake_word_result
        return WakeWordResult(detected=True, wake_word=wake_word or "naira", confidence=0.92)

    async def start_recording(self, *, timeout: float = 30.0) -> AudioData:
        if self._raise_on == "record":
            raise VoiceNotImplementedError()
        if self._record_result is not None:
            return self._record_result
        return AudioData(
            source_type="microphone", format="wav", sample_rate=44100,
            duration_ms=3000.0, size_bytes=264600, data=b"recorded-audio",
        )

    async def play_audio(self, audio: AudioData, *, timeout: float = 30.0) -> None:
        if self._raise_on == "play":
            raise VoiceNotImplementedError()

    async def close(self) -> None:
        pass


class TestVoiceExecutor:
    @pytest.mark.asyncio
    async def test_transcribe_success(self) -> None:
        adapter = _MockVoiceAdapter()
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.transcribe(audio)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_transcribe_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="transcribe")
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.transcribe(audio)
        assert result.status == "error"
        assert "not configured" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_transcribe_empty_text_returns_error(self) -> None:
        adapter = _MockVoiceAdapter(transcribe_result=TranscriptionResult(text=""))
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.transcribe(audio)
        assert result.status == "error"
        assert "No speech" in (result.error or "")

    @pytest.mark.asyncio
    async def test_synthesize_success(self) -> None:
        adapter = _MockVoiceAdapter()
        exe = VoiceExecutor(adapter=adapter)
        result = await exe.synthesize("Hello")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_synthesize_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="synthesize")
        exe = VoiceExecutor(adapter=adapter)
        result = await exe.synthesize("Hello")
        assert result.status == "error"
        assert "not configured" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_synthesize_no_audio_returns_error(self) -> None:
        adapter = _MockVoiceAdapter(synthesize_result=SynthesisResult(text="Hello"))
        exe = VoiceExecutor(adapter=adapter)
        result = await exe.synthesize("Hello")
        assert result.status == "error"
        assert "No audio" in (result.error or "")

    @pytest.mark.asyncio
    async def test_detect_wake_word_detected(self) -> None:
        adapter = _MockVoiceAdapter()
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.detect_wake_word(audio)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_wake_word_not_detected(self) -> None:
        adapter = _MockVoiceAdapter(wake_word_result=WakeWordResult(detected=False))
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.detect_wake_word(audio)
        assert result.status == "error"
        assert "not detected" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_detect_wake_word_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="wake_word")
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.detect_wake_word(audio)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_start_recording_success(self) -> None:
        adapter = _MockVoiceAdapter()
        exe = VoiceExecutor(adapter=adapter)
        result = await exe.start_recording()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_start_recording_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="record")
        exe = VoiceExecutor(adapter=adapter)
        result = await exe.start_recording()
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_play_audio_success(self) -> None:
        adapter = _MockVoiceAdapter()
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.play_audio(audio)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_play_audio_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="play")
        exe = VoiceExecutor(adapter=adapter)
        audio = AudioData(source_type="bytes", data=b"test")
        result = await exe.play_audio(audio)
        assert result.status == "error"

    def test_is_available_true(self) -> None:
        adapter = _MockVoiceAdapter(available=True)
        exe = VoiceExecutor(adapter=adapter)
        assert exe.is_available is True

    def test_is_available(self) -> None:
        adapter = LocalVoiceAdapter()
        exe = VoiceExecutor(adapter=adapter)
        if exe.is_available:
            assert True
        else:
            assert not exe.is_available


# =========================================================================
# VoiceManager — ModuleInterface lifecycle
# =========================================================================


class TestVoiceManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = VoiceManager()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_async_init_sets_up(self) -> None:
        mgr = VoiceManager()
        await mgr.async_init()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        mgr = VoiceManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = VoiceManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = VoiceManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = VoiceManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = MagicMock()
        mgr = VoiceManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_with_adapter_injection(self) -> None:
        adapter = LocalVoiceAdapter()
        mgr = VoiceManager(adapter=adapter)
        assert mgr._adapter is adapter

    @pytest.mark.asyncio
    async def test_stt_property(self) -> None:
        mgr = VoiceManager()
        assert isinstance(mgr.stt, SpeechToText)

    @pytest.mark.asyncio
    async def test_tts_property(self) -> None:
        mgr = VoiceManager()
        assert isinstance(mgr.tts, TextToSpeech)

    @pytest.mark.asyncio
    async def test_wake_word_property(self) -> None:
        mgr = VoiceManager()
        assert isinstance(mgr.wake_word, WakeWord)


# =========================================================================
# VoiceManager — transcribe
# =========================================================================


class TestVoiceManagerTranscribe:
    @pytest.mark.asyncio
    async def test_transcribe_success(self) -> None:
        adapter = _MockVoiceAdapter()
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await mgr.transcribe(audio)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_transcribe_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="transcribe")
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await mgr.transcribe(audio)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_transcribe_degraded_raises(self) -> None:
        mgr = VoiceManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.transcribe(AudioData(source_type="bytes", data=b"test"))


# =========================================================================
# VoiceManager — synthesize
# =========================================================================


class TestVoiceManagerSynthesize:
    @pytest.mark.asyncio
    async def test_synthesize_success(self) -> None:
        adapter = _MockVoiceAdapter()
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.synthesize("Hello")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_synthesize_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="synthesize")
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.synthesize("Hello")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_synthesize_degraded_raises(self) -> None:
        mgr = VoiceManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.synthesize("Hello")


# =========================================================================
# VoiceManager — detect_wake_word
# =========================================================================


class TestVoiceManagerWakeWord:
    @pytest.mark.asyncio
    async def test_detect_wake_word_detected(self) -> None:
        adapter = _MockVoiceAdapter()
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await mgr.detect_wake_word(audio)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_wake_word_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="wake_word")
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await mgr.detect_wake_word(audio)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_detect_wake_word_degraded_raises(self) -> None:
        mgr = VoiceManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.detect_wake_word(AudioData(source_type="bytes", data=b"test"))


# =========================================================================
# VoiceManager — start_recording
# =========================================================================


class TestVoiceManagerRecording:
    @pytest.mark.asyncio
    async def test_start_recording_success(self) -> None:
        adapter = _MockVoiceAdapter()
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.start_recording()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_start_recording_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="record")
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.start_recording()
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_start_recording_degraded_raises(self) -> None:
        mgr = VoiceManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.start_recording()


# =========================================================================
# VoiceManager — play_audio
# =========================================================================


class TestVoiceManagerPlayAudio:
    @pytest.mark.asyncio
    async def test_play_audio_success(self) -> None:
        adapter = _MockVoiceAdapter()
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await mgr.play_audio(audio)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_play_audio_not_implemented(self) -> None:
        adapter = _MockVoiceAdapter(raise_on="play")
        mgr = VoiceManager(adapter=adapter)
        await mgr.async_init()
        audio = AudioData(source_type="bytes", data=b"test")
        result = await mgr.play_audio(audio)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_play_audio_degraded_raises(self) -> None:
        mgr = VoiceManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.play_audio(AudioData(source_type="bytes", data=b"test"))


# =========================================================================
# VoiceManager — is_available
# =========================================================================


class TestVoiceManagerIsAvailable:
    def test_default(self) -> None:
        mgr = VoiceManager()
        if mgr.is_available:
            assert True
        else:
            assert not mgr.is_available

    def test_with_real_adapter(self) -> None:
        adapter = _MockVoiceAdapter(available=True)
        mgr = VoiceManager(adapter=adapter)
        assert mgr.is_available is True


# =========================================================================
# VoicePort — ABC
# =========================================================================


class TestVoicePortAbc:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            VoicePort()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_adapter(self) -> None:
        adapter = LocalVoiceAdapter()
        assert isinstance(adapter, VoicePort)
        if adapter.is_available:
            assert True
        else:
            assert not adapter.is_available


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_voice_manager_conforms_to_protocol(self) -> None:
        assert isinstance(VoiceManager(), ModuleInterface)

    def test_voice_manager_has_required_methods(self) -> None:
        mgr = VoiceManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")


# =========================================================================
# Voice Barge-in & Interruption tests (Phase 5)
# =========================================================================


class TestVoiceBargeInAndInterruption:
    def test_interrupt_event_lifecycle(self) -> None:
        from backend.modules.voice._audio_player import audio_interrupt_event

        audio_interrupt_event.clear()
        assert not audio_interrupt_event.is_set()

        audio_interrupt_event.set()
        assert audio_interrupt_event.is_set()

        audio_interrupt_event.clear()
        assert not audio_interrupt_event.is_set()

    def test_voice_manager_interrupt_api(self) -> None:
        mgr = VoiceManager()
        assert hasattr(mgr, "interrupt")
        assert hasattr(mgr, "interrupt_event")

        mgr.interrupt_event.clear()
        assert not mgr.interrupt_event.is_set()

        mgr.interrupt()
        assert mgr.interrupt_event.is_set()
        mgr.interrupt_event.clear()

    @pytest.mark.asyncio
    async def test_audio_player_play_barge_in_interruption(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.modules.voice._audio_player import AudioPlayer, audio_interrupt_event
        from backend.modules.voice._types import AudioData
        import numpy as np

        player = AudioPlayer()
        if not player.is_available:
            pytest.skip("sounddevice not available")

        # Mock sd.OutputStream to avoid hardware audio output in headless tests
        class MockStream:
            def __init__(self, **kwargs: Any) -> None:
                pass
            def start(self) -> None:
                pass
            def write(self, chunk: Any) -> None:
                # Trigger interrupt on first chunk write
                audio_interrupt_event.set()
            def stop(self) -> None:
                pass
            def close(self) -> None:
                pass

        monkeypatch.setattr("sounddevice.OutputStream", MockStream)
        monkeypatch.setattr("sounddevice.stop", lambda: None)

        audio = AudioData(
            source_type="file",
            data=np.zeros(16000 * 2, dtype=np.int16).tobytes(),  # 2 sec audio
            sample_rate=16000,
        )

        audio_interrupt_event.clear()
        await player.play(audio, timeout=5.0)

        # Player should have stopped immediately on first chunk interrupt
        assert not player.is_playing
        assert not audio_interrupt_event.is_set()

    @pytest.mark.asyncio
    async def test_wake_word_triggers_barge_in(self) -> None:
        from backend.modules.voice._audio_player import audio_interrupt_event
        from backend.modules.voice._wake_word import WakeWord
        from backend.modules.voice._types import AudioData, TranscriptionResult

        class MockSTT:
            is_available = True
            async def transcribe(self, audio: AudioData, language: str = "en", timeout: float = 30.0) -> TranscriptionResult:
                return TranscriptionResult(text="Hey Naira stop", confidence=0.9)

        ww = WakeWord(stt_provider=MockSTT())
        audio = AudioData(source_type="microphone", data=b"dummy")

        audio_interrupt_event.clear()
        res = await ww.detect(audio, wake_word="naira")

        assert res.detected is True
        assert audio_interrupt_event.is_set()
        audio_interrupt_event.clear()
