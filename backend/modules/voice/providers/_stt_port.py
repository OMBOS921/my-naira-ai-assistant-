"""STT Provider Port — abstract base for speech-to-text providers.

20_Dependency_Rules.md §2 — Port/Adapter pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.voice._types import AudioData, TranscriptionResult


class STTPort(ABC):
    """Abstract port for speech-to-text providers.

    Each provider (Whisper, Faster-Whisper, etc.) implements this interface.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider's dependencies are available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'whisper', 'faster-whisper')."""

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
            If the operation exceeds timeout.
        """

    async def close(self) -> None:
        """Release provider resources.

        Default implementation is a no-op.
        """
