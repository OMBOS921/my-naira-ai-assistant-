"""PorcupineWakeWordProvider — Porcupine wake word detection provider.

Lazy-loads the pvporcupine library. If unavailable, returns is_available=False
and raises appropriate errors when detect_wake_word() is called.

21_System_Contracts.md §15 — Provider contracts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.modules.voice._exceptions import (
    VoiceWakeWordError,
    VoiceTimeoutError,
)
from backend.modules.voice._types import AudioData, WakeWordResult
from backend.modules.voice.providers._wake_word_port import WakeWordPort

_LOG = logging.getLogger("naira.voice.porcupine")

_HAS_PORCUPINE = False
_pvporcupine: Any = None

try:
    import pvporcupine as _pvporcupine
    _HAS_PORCUPINE = True
except ImportError:
    _pvporcupine = None


class PorcupineWakeWordProvider(WakeWordPort):
    """Porcupine wake word detection provider.

    Parameters
    ----------
    access_key : str
        Picovoice access key.
    keywords : tuple[str, ...]
        Wake words to detect.
    sensitivity : float
        Detection sensitivity (0.0-1.0).
    timeout : float
        Default timeout for detection operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        access_key: str = "",
        keywords: tuple[str, ...] = ("naira",),
        sensitivity: float = 0.5,
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._access_key = access_key
        self._keywords = keywords
        self._sensitivity = sensitivity
        self._timeout = timeout
        self._logger = logger or _LOG
        self._porcupine: Any = None

        if not _HAS_PORCUPINE:
            self._logger.warning(
                "Porcupine package not installed — provider unavailable"
            )
            return

        if not access_key:
            self._logger.warning(
                "Porcupine access key not provided — provider unavailable"
            )

    @property
    def is_available(self) -> bool:
        """Return True if pvporcupine is installed and access key is set."""
        return _HAS_PORCUPINE and bool(self._access_key)

    @property
    def provider_name(self) -> str:
        return "porcupine"

    async def detect_wake_word(
        self,
        audio: AudioData,
        *,
        wake_word: str = "",
        timeout: float = 30.0,
    ) -> WakeWordResult:
        """Detect wake word using Porcupine.

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
        """
        if not _HAS_PORCUPINE:
            raise VoiceWakeWordError(
                "Porcupine package not installed",
                context={"provider": "porcupine"},
            )

        if not self._access_key:
            raise VoiceWakeWordError(
                "Porcupine access key not provided",
                context={"provider": "porcupine"},
            )

        try:
            # Initialize Porcupine if not already done
            if self._porcupine is None:
                keywords_list = list(self._keywords)
                sensitivities = [self._sensitivity] * len(keywords_list)

                self._porcupine = await asyncio.wait_for(
                    asyncio.to_thread(
                        _pvporcupine.create,
                        access_key=self._access_key,
                        keywords=keywords_list,
                        sensitivities=sensitivities,
                    ),
                    timeout=timeout,
                )

            if audio.data is None:
                raise VoiceWakeWordError(
                    "Audio data is None",
                    context={"provider": "porcupine"},
                )

            # Process audio frames
            # Porcupine expects 16-bit PCM audio
            import numpy as np

            audio_array = np.frombuffer(audio.data, dtype=np.int16)

            # Process in frame chunks
            frame_length = self._porcupine.frame_length
            detected = False
            detected_keyword = ""

            for i in range(0, len(audio_array), frame_length):
                frame = audio_array[i:i + frame_length]
                if len(frame) < frame_length:
                    break

                keyword_index = await asyncio.wait_for(
                    asyncio.to_thread(self._porcupine.process, frame),
                    timeout=timeout,
                )

                if keyword_index >= 0:
                    detected = True
                    detected_keyword = self._keywords[keyword_index]
                    break

            return WakeWordResult(
                detected=detected,
                wake_word=detected_keyword,
                confidence=self._sensitivity if detected else 0.0,
            )

        except asyncio.TimeoutError:
            raise VoiceTimeoutError(
                f"Porcupine detection timed out after {timeout}s",
                context={"provider": "porcupine", "timeout": timeout},
            ) from None
        except Exception as exc:
            self._logger.error("Porcupine detection failed: %s", exc)
            raise VoiceWakeWordError(
                f"Porcupine detection failed: {exc}",
                context={"provider": "porcupine"},
            ) from exc

    async def close(self) -> None:
        """Release Porcupine resources."""
        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception as exc:
                self._logger.warning("Error closing Porcupine: %s", exc)
            self._porcupine = None
        self._logger.debug("Porcupine provider closed")
