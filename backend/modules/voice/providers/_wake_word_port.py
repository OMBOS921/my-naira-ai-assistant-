"""Wake Word Provider Port — abstract base for wake word detection.

20_Dependency_Rules.md §2 — Port/Adapter pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.voice._types import AudioData, WakeWordResult


class WakeWordPort(ABC):
    """Abstract port for wake word detection providers.

    Each provider (Porcupine, etc.) implements this interface.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider's dependencies are available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'porcupine')."""

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
            If the operation exceeds timeout.
        """

    async def close(self) -> None:
        """Release provider resources.

        Default implementation is a no-op.
        """
