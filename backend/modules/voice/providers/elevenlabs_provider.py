"""ElevenLabsTTSProvider — ElevenLabs cloud TTS provider.

Lazy-loads the elevenlabs library. If unavailable, returns is_available=False
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

_LOG = logging.getLogger("naira.voice.elevenlabs")

_HAS_ELEVENLABS = False
_elevenlabs: Any = None

try:
    import elevenlabs as _elevenlabs
    _HAS_ELEVENLABS = True
except ImportError:
    _elevenlabs = None


class ElevenLabsTTSProvider(TTSPort):
    """ElevenLabs TTS provider using elevenlabs API.

    Parameters
    ----------
    api_key : str
        ElevenLabs API key.
    voice_id : str
        Default voice ID.
    model : str
        ElevenLabs model name.
    timeout : float
        Default timeout for synthesis operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel voice
        model: str = "eleven_monolingual_v1",
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api_key = api_key
        self._default_voice_id = voice_id
        self._model = model
        self._timeout = timeout
        self._logger = logger or _LOG

        if not _HAS_ELEVENLABS:
            self._logger.warning(
                "ElevenLabs package not installed — provider unavailable"
            )
            return

        if not api_key:
            self._logger.warning(
                "ElevenLabs API key not provided — provider unavailable"
            )

    @property
    def is_available(self) -> bool:
        """Return True if elevenlabs is installed and API key is set."""
        return _HAS_ELEVENLABS and bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        """Synthesize speech using ElevenLabs API.

        Parameters
        ----------
        text : str
            Text to synthesize.
        voice_id : str
            Voice ID to use (empty = default).
        language : str
            Language code (not used by ElevenLabs).
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        SynthesisResult
            Synthesized audio data.
        """
        if not _HAS_ELEVENLABS:
            raise VoiceSynthesisError(
                "ElevenLabs package not installed",
                context={"provider": "elevenlabs"},
            )

        if not self._api_key:
            raise VoiceSynthesisError(
                "ElevenLabs API key not provided",
                context={"provider": "elevenlabs"},
            )

        start = time.monotonic()
        effective_voice_id = voice_id or self._default_voice_id

        try:
            # Call ElevenLabs API
            _elevenlabs.set_api_key(self._api_key)

            audio_bytes = await asyncio.wait_for(
                asyncio.to_thread(
                    _elevenlabs.generate,
                    text=text,
                    voice=effective_voice_id,
                    model=self._model,
                ),
                timeout=timeout,
            )

            duration_ms = (time.monotonic() - start) * 1000

            # Convert generator to bytes if needed
            if hasattr(audio_bytes, "__iter__") and not isinstance(audio_bytes, bytes):
                audio_bytes = b"".join(audio_bytes)

            audio = AudioData(
                source_type="bytes",
                format="mp3",
                sample_rate=22050,
                channels=1,
                duration_ms=duration_ms,
                size_bytes=len(audio_bytes),
                data=audio_bytes,
            )

            return SynthesisResult(
                audio=audio,
                text=text,
                voice_id=effective_voice_id,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            raise VoiceTimeoutError(
                f"ElevenLabs synthesis timed out after {timeout}s",
                context={"provider": "elevenlabs", "timeout": timeout},
            ) from None
        except Exception as exc:
            self._logger.error("ElevenLabs synthesis failed: %s", exc)
            raise VoiceSynthesisError(
                f"ElevenLabs synthesis failed: {exc}",
                context={"provider": "elevenlabs"},
            ) from exc

    async def close(self) -> None:
        """Release resources."""
        self._logger.debug("ElevenLabs provider closed")
