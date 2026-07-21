"""TTS Provider Port — abstract base for text-to-speech providers.

20_Dependency_Rules.md §2 — Port/Adapter pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.voice._types import SynthesisResult


class TTSPort(ABC):
    """Abstract port for text-to-speech providers.

    Each provider (Piper, Coqui, ElevenLabs) implements this interface.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider's dependencies are available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'piper', 'coqui', 'elevenlabs')."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        """Synthesize speech from text.

        Parameters
        ----------
        text : str
            Text to synthesize.
        voice_id : str
            Desired voice identifier (empty = default).
        language : str
            Language code for synthesis.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        SynthesisResult
            Synthesized audio data.

        Raises
        ------
        VoiceSynthesisError
            If synthesis fails.
        VoiceTimeoutError
            If the operation exceeds timeout.
        """

    async def close(self) -> None:
        """Release provider resources.

        Default implementation is a no-op.
        """
