"""CoquiTTSProvider — Coqui TTS text-to-speech provider.

Lazy-loads the TTS library. If unavailable, returns is_available=False
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

_LOG = logging.getLogger("naira.voice.coqui")

_HAS_COQUI = False
_TTS: Any = None

try:
    from TTS.api import TTS as _TTS
    _HAS_COQUI = True
except ImportError:
    _TTS = None


class CoquiTTSProvider(TTSPort):
    """Coqui TTS provider using TTS library.

    Parameters
    ----------
    model : str
        Coqui TTS model name.
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
        model: str = "tts_models/en/ljspeech/tacotron2-DDC",
        sample_rate: int = 22050,
        speed: float = 1.0,
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._model_name = model
        self._sample_rate = sample_rate
        self._speed = speed
        self._timeout = timeout
        self._logger = logger or _LOG
        self._model: Any = None

        if not _HAS_COQUI:
            self._logger.warning(
                "Coqui TTS package not installed — provider unavailable"
            )
            return

        # Lazy-load the model on first use
        self._model_loaded = False

    @property
    def is_available(self) -> bool:
        """Return True if TTS is installed."""
        return _HAS_COQUI

    @property
    def provider_name(self) -> str:
        return "coqui"

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        """Synthesize speech using Coqui TTS.

        Loads the model on first use (lazy loading).
        """
        if not _HAS_COQUI:
            raise VoiceSynthesisError(
                "Coqui TTS package not installed",
                context={"provider": "coqui"},
            )

        start = time.monotonic()

        try:
            # Lazy-load model on first use
            if not self._model_loaded:
                self._logger.info(
                    "Loading Coqui TTS model '%s' (first use)", self._model_name
                )
                self._model = await asyncio.wait_for(
                    asyncio.to_thread(_TTS, model_name=self._model_name),
                    timeout=timeout,
                )
                self._model_loaded = True

            # Synthesize speech to temporary file
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        self._model.tts_to_file,
                        text=text,
                        file_path=tmp_path,
                    ),
                    timeout=timeout,
                )

                # Read synthesized audio
                audio_data = Path(tmp_path).read_bytes()
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            duration_ms = (time.monotonic() - start) * 1000

            audio = AudioData(
                source_type="bytes",
                format="wav",
                sample_rate=self._sample_rate,
                channels=1,
                duration_ms=duration_ms,
                size_bytes=len(audio_data),
                data=audio_data,
            )

            return SynthesisResult(
                audio=audio,
                text=text,
                voice_id=voice_id or self._model_name,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            raise VoiceTimeoutError(
                f"Coqui TTS synthesis timed out after {timeout}s",
                context={"provider": "coqui", "timeout": timeout},
            ) from None
        except Exception as exc:
            self._logger.error("Coqui TTS synthesis failed: %s", exc)
            raise VoiceSynthesisError(
                f"Coqui TTS synthesis failed: {exc}",
                context={"provider": "coqui"},
            ) from exc

    async def close(self) -> None:
        """Release model resources."""
        self._model = None
        self._model_loaded = False
        self._logger.debug("Coqui TTS provider closed")
