"""WhisperSTTProvider — OpenAI Whisper speech-to-text provider.

Lazy-loads the whisper library. If unavailable, returns is_available=False
and raises appropriate errors when transcribe() is called.

21_System_Contracts.md §15 — Provider contracts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.modules.voice._exceptions import (
    VoiceTranscriptionError,
    VoiceTimeoutError,
)
from backend.modules.voice._types import AudioData, TranscriptionResult
from backend.modules.voice.providers._stt_port import STTPort

_LOG = logging.getLogger("naira.voice.whisper")

_HAS_WHISPER = False
_whisper: Any = None

try:
    import whisper as _whisper
    _HAS_WHISPER = True
except ImportError:
    _whisper = None


class WhisperSTTProvider(STTPort):
    """Whisper STT provider using the official openai-whisper package.

    Parameters
    ----------
    model : str
        Whisper model name (tiny, base, small, medium, large).
    language : str
        Default language for transcription.
    timeout : float
        Default timeout for transcription operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        model: str = "base",
        language: str = "en",
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._model_name = model
        self._language = language
        self._timeout = timeout
        self._logger = logger or _LOG
        self._model: Any = None

        if not _HAS_WHISPER:
            self._logger.warning(
                "Whisper package not installed — provider unavailable"
            )
            return

        # Lazy-load the model on first use
        self._model_loaded = False

    @property
    def is_available(self) -> bool:
        """Return True if whisper is installed."""
        return _HAS_WHISPER

    @property
    def provider_name(self) -> str:
        return "whisper"

    async def transcribe(
        self,
        audio: AudioData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> TranscriptionResult:
        """Transcribe audio using Whisper.

        Loads the model on first use (lazy loading).
        """
        if not _HAS_WHISPER:
            raise VoiceTranscriptionError(
                "Whisper package not installed",
                context={"provider": "whisper"},
            )

        start = time.monotonic()

        try:
            # Lazy-load model on first use
            if not self._model_loaded:
                self._logger.info(
                    "Loading Whisper model '%s' (first use)", self._model_name
                )
                self._model = await asyncio.wait_for(
                    asyncio.to_thread(_whisper.load_model, self._model_name),
                    timeout=timeout,
                )
                self._model_loaded = True

            # Transcribe audio
            if audio.data is None:
                raise VoiceTranscriptionError(
                    "Audio data is None",
                    context={"provider": "whisper"},
                )

            # Save audio to temporary file for Whisper
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio.data)
                tmp_path = tmp.name

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._model.transcribe,
                        tmp_path,
                        language=language,
                    ),
                    timeout=timeout,
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            duration_ms = (time.monotonic() - start) * 1000

            text = result.get("text", "").strip()
            segments = tuple(result.get("segments", []))

            return TranscriptionResult(
                text=text,
                confidence=1.0,  # Whisper doesn't provide per-word confidence
                language=language,
                duration_ms=duration_ms,
                segments=segments,
            )

        except asyncio.TimeoutError:
            raise VoiceTimeoutError(
                f"Whisper transcription timed out after {timeout}s",
                context={"provider": "whisper", "timeout": timeout},
            ) from None
        except Exception as exc:
            self._logger.error("Whisper transcription failed: %s", exc)
            raise VoiceTranscriptionError(
                f"Whisper transcription failed: {exc}",
                context={"provider": "whisper"},
            ) from exc

    async def close(self) -> None:
        """Release model resources."""
        self._model = None
        self._model_loaded = False
        self._logger.debug("Whisper provider closed")
