"""EdgeTTSProvider — edge-tts text-to-speech provider.
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

_LOG = logging.getLogger("naira.voice.edge_tts")

_HAS_EDGE_TTS = False
try:
    import edge_tts
    _HAS_EDGE_TTS = True
except ImportError:
    _HAS_EDGE_TTS = False


class EdgeTTSProvider(TTSPort):
    """Edge-TTS provider for sweet female voice text-to-speech.
    """

    def __init__(
        self,
        *,
        voice: str = "hi-IN-SwaraNeural",
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._voice = voice
        self._timeout = timeout
        self._logger = logger or _LOG

    @property
    def is_available(self) -> bool:
        return _HAS_EDGE_TTS

    @property
    def provider_name(self) -> str:
        return "edge-tts"

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        if not _HAS_EDGE_TTS:
            raise VoiceSynthesisError(
                "edge-tts package not installed",
                context={"provider": "edge-tts"},
            )

        start = time.monotonic()
        # Handle sweet female voice selection (hi-IN-SwaraNeural)
        effective_voice = voice_id or self._voice or "hi-IN-SwaraNeural"

        try:
            communicate = edge_tts.Communicate(text, effective_voice)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            duration_ms = (time.monotonic() - start) * 1000

            audio = AudioData(
                source_type="bytes",
                format="mp3",
                sample_rate=24000,
                channels=1,
                duration_ms=duration_ms,
                size_bytes=len(audio_bytes),
                data=audio_bytes,
            )

            return SynthesisResult(
                audio=audio,
                text=text,
                voice_id=effective_voice,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            raise VoiceTimeoutError(
                f"Edge-TTS synthesis timed out after {timeout}s",
                context={"provider": "edge-tts", "timeout": timeout},
            ) from None
        except Exception as exc:
            self._logger.error("Edge-TTS synthesis failed: %s", exc)
            raise VoiceSynthesisError(
                f"Edge-TTS synthesis failed: {exc}",
                context={"provider": "edge-tts"},
            ) from exc

    async def close(self) -> None:
        pass
