"""
LocalVoiceAdapter — local voice adapter using sounddevice and providers.

Provides real implementations for:
- Audio recording (sounddevice with VAD)
- Audio playback (sounddevice)
- STT (via provider delegation)
- TTS (via provider delegation)
- Wake word detection (via provider delegation)
"""

from __future__ import annotations

import logging

from backend.modules.voice._audio_recorder import AudioRecorder
from backend.modules.voice._audio_player import AudioPlayer
from backend.modules.voice._speech_to_text import SpeechToText
from backend.modules.voice._text_to_speech import TextToSpeech
from backend.modules.voice._types import (
    AudioData,
    SynthesisResult,
    TranscriptionResult,
    WakeWordResult,
)
from backend.modules.voice._wake_word import WakeWord
from backend.modules.voice.ports.voice_port import VoicePort

_LOG = logging.getLogger("naira.voice.adapter")


class LocalVoiceAdapter(VoicePort):
    """Local voice adapter using sounddevice and provider chain.

    Provides real implementations for all voice operations,
    delegating STT/TTS/wake-word to the registered providers.
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        stt_providers: dict[str, object] | None = None,
        tts_providers: dict[str, object] | None = None,
        wake_word_providers: dict[str, object] | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._stt_providers = stt_providers or {}
        self._tts_providers = tts_providers or {}
        self._wake_word_providers = wake_word_providers or {}

        self._audio_recorder = AudioRecorder(logger=logger)
        self._audio_player = AudioPlayer(logger=logger)

        stt_provider = next(iter(self._stt_providers.values()), None)
        self._stt = SpeechToText(
            logger=logger,
            providers=self._stt_providers,
        )
        self._tts = TextToSpeech(
            logger=logger,
            providers=self._tts_providers,
        )
        self._wake_word = WakeWord(
            logger=logger,
            providers=self._wake_word_providers,
            stt_provider=stt_provider,
        )

    @property
    def is_available(self) -> bool:
        return (
            self._audio_recorder.is_available
            or self._audio_player.is_available
            or self._stt.is_available
            or self._tts.is_available
            or self._wake_word.is_available
        )

    async def transcribe(
        self,
        audio: AudioData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> TranscriptionResult:
        return await self._stt.transcribe(
            audio, language=language, timeout=timeout,
        )

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        return await self._tts.synthesize(
            text, voice_id=voice_id, language=language, timeout=timeout,
        )

    async def detect_wake_word(
        self,
        audio: AudioData,
        *,
        wake_word: str = "",
        timeout: float = 30.0,
    ) -> WakeWordResult:
        return await self._wake_word.detect(
            audio, wake_word=wake_word, timeout=timeout,
        )

    async def start_recording(
        self,
        *,
        timeout: float = 30.0,
    ) -> AudioData:
        return await self._audio_recorder.record_until_silence(
            max_duration=timeout,
        )

    async def play_audio(
        self,
        audio: AudioData,
        *,
        timeout: float = 30.0,
    ) -> None:
        await self._audio_player.play(audio, timeout=timeout)

    async def close(self) -> None:
        await self._audio_recorder.close()
        await self._audio_player.close()
        self._logger.debug("LocalVoiceAdapter closed")

    @property
    def stt(self) -> SpeechToText:
        return self._stt

    @property
    def tts(self) -> TextToSpeech:
        return self._tts

    @property
    def wake_word_detector(self) -> WakeWord:
        return self._wake_word
