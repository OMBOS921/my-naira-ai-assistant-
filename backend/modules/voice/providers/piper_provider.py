"""PiperTTSProvider — Piper offline text-to-speech provider.

Lazy-loads the piper library. If unavailable, returns is_available=False
and raises appropriate errors when synthesize() is called.

21_System_Contracts.md §15 — Provider contracts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.modules.voice._exceptions import (
    VoiceSynthesisError,
    VoiceTimeoutError,
)
from backend.modules.voice._types import AudioData, SynthesisResult
from backend.modules.voice.providers._tts_port import TTSPort

_LOG = logging.getLogger("naira.voice.piper")

_HAS_PIPER = False

try:
    # Piper doesn't have a standard Python package yet.
    # When available, import it here.
    import piper  # type: ignore[import]  # noqa: F401
    _HAS_PIPER = True
except ImportError:
    _HAS_PIPER = False


class PiperTTSProvider(TTSPort):
    """Piper TTS provider for offline speech synthesis.

    Parameters
    ----------
    voice : str
        Piper voice model name.
    sample_rate : int
        Output sample rate in Hz.
    speed : float
        Speech speed multiplier.
    timeout : float
        Default timeout for synthesis operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        voice: str = "en_US-lessac-medium",
        sample_rate: int = 22050,
        speed: float = 1.0,
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._voice = voice
        self._sample_rate = sample_rate
        self._speed = speed
        self._timeout = timeout
        self._logger = logger or _LOG

        if not _HAS_PIPER:
            self._logger.warning(
                "Piper package not installed — provider unavailable"
            )

    @property
    def is_available(self) -> bool:
        """Return True if piper is installed."""
        return _HAS_PIPER

    @property
    def provider_name(self) -> str:
        return "piper"

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        """Synthesize speech using Piper.

        Raises VoiceSynthesisError as Piper Python package is not yet
        publicly available. The provider is ready for integration when
        the library becomes available.
        """
        if not _HAS_PIPER:
            raise VoiceSynthesisError(
                "Piper package not installed",
                context={"provider": "piper"},
            )

        raise VoiceSynthesisError(
            "Piper Python package not yet available",
            context={"provider": "piper"},
        )

    async def close(self) -> None:
        """Release resources."""
        self._logger.debug("Piper provider closed")
