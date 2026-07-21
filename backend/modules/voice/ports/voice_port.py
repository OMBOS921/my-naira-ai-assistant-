"""
VoicePort — abstract port for pluggable voice adapters.

20_Dependency_Rules.md §2 — Port/Adapter pattern.

Concrete adapters (Whisper, Coqui TTS, ElevenLabs, Google TTS, etc.)
implement this ABC so ``VoiceManager`` remains agnostic of the
underlying STT/TTS engine or audio driver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.voice._types import (
    AudioData,
    SynthesisResult,
    TranscriptionResult,
    WakeWordResult,
)


class VoicePort(ABC):
    """Abstract voice port.

    Each method corresponds to a high-level voice capability.
    Implementations manage their own model lifecycle internally.
    """

    @abstractmethod
    async def transcribe(
        self,
        audio: AudioData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> TranscriptionResult:
        """Transcribe speech audio to text.

        Parameters
        ----------
        audio : AudioData
            Source audio data.
        language : str
            Expected language hint.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        TranscriptionResult
            Transcribed text with confidence metadata.

        Raises
        ------
        VoiceTranscriptionError
            If transcription fails.
        VoiceTimeoutError
            If the operation exceeds *timeout*.
        """

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        """Synthesise speech from text.

        Parameters
        ----------
        text : str
            Text to synthesise.
        voice_id : str
            Desired voice identifier (empty = default).
        language : str
            Language code for synthesis.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        SynthesisResult
            Synthesised audio data.

        Raises
        ------
        VoiceSynthesisError
            If synthesis fails.
        VoiceTimeoutError
            If the operation exceeds *timeout*.
        """

    @abstractmethod
    async def detect_wake_word(
        self,
        audio: AudioData,
        *,
        wake_word: str = "",
        timeout: float = 30.0,
    ) -> WakeWordResult:
        """Detect a wake word in audio.

        Parameters
        ----------
        audio : AudioData
            Source audio data.
        wake_word : str
            Specific wake word to detect (empty = any configured).
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        WakeWordResult
            Detection result.

        Raises
        ------
        VoiceWakeWordError
            If detection fails.
        VoiceTimeoutError
            If the operation exceeds *timeout*.
        """

    @abstractmethod
    async def start_recording(
        self,
        *,
        timeout: float = 30.0,
    ) -> AudioData:
        """Start recording audio from the microphone.

        Parameters
        ----------
        timeout : float
            Maximum recording duration in seconds.

        Returns
        -------
        AudioData
            Recorded audio data.

        Raises
        ------
        VoiceAudioError
            If recording fails or no microphone is available.
        VoiceTimeoutError
            If the recording exceeds *timeout*.
        """

    @abstractmethod
    async def play_audio(
        self,
        audio: AudioData,
        *,
        timeout: float = 30.0,
    ) -> None:
        """Play audio data through speakers.

        Parameters
        ----------
        audio : AudioData
            Audio data to play.
        timeout : float
            Maximum playback time in seconds.

        Raises
        ------
        VoiceAudioError
            If playback fails or no speakers are available.
        VoiceTimeoutError
            If playback exceeds *timeout*.
        """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the adapter can be used.

        A placeholder adapter (e.g. ``LocalVoiceAdapter``) returns
        ``False``; a fully-initialised adapter (Whisper, Coqui TTS,
        etc.) returns ``True``.
        """
