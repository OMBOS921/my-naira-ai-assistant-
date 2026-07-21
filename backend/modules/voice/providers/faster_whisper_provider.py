"""FasterWhisperSTTProvider — Faster-Whisper speech-to-text provider.

Lazy-loads the faster-whisper library. If unavailable, returns
is_available=False and raises appropriate errors when transcribe() is called.

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

_LOG = logging.getLogger("naira.voice.faster_whisper")

_HAS_FASTER_WHISPER = False
_WhisperModel: Any = None

try:
    from faster_whisper import WhisperModel as _WhisperModel
    _HAS_FASTER_WHISPER = True
except ImportError:
    _WhisperModel = None


class FasterWhisperSTTProvider(STTPort):
    """Faster-Whisper STT provider using faster-whisper package.

    Parameters
    ----------
    model : str
        Faster-Whisper model name (tiny, base, small, medium, large-v2).
    device : str
        Device to use (cpu, cuda, auto).
    compute_type : str
        Compute type (int8, float16, float32).
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
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
        timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._timeout = timeout
        self._logger = logger or _LOG
        self._model: Any = None

        if not _HAS_FASTER_WHISPER:
            self._logger.warning(
                "Faster-Whisper package not installed — provider unavailable"
            )
            return

        # Lazy-load the model on first use
        self._model_loaded = False

    @property
    def is_available(self) -> bool:
        """Return True if faster-whisper is installed."""
        return _HAS_FASTER_WHISPER

    @property
    def provider_name(self) -> str:
        return "faster-whisper"

    async def transcribe(
        self,
        audio: AudioData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> TranscriptionResult:
        """Transcribe audio using Faster-Whisper.

        Loads the model on first use (lazy loading).
        """
        if not _HAS_FASTER_WHISPER:
            raise VoiceTranscriptionError(
                "Faster-Whisper package not installed",
                context={"provider": "faster-whisper"},
            )

        start = time.monotonic()

        try:
            # Lazy-load model on first use
            if not self._model_loaded:
                self._logger.info(
                    "Loading Faster-Whisper model '%s' (first use, device=%s, compute_type=%s)",
                    self._model_name,
                    self._device,
                    self._compute_type,
                )
                self._model = await asyncio.wait_for(
                    asyncio.to_thread(
                        _WhisperModel,
                        self._model_name,
                        device=self._device,
                        compute_type=self._compute_type,
                    ),
                    timeout=timeout,
                )
                self._model_loaded = True

            # Transcribe audio
            if audio.data is None:
                raise VoiceTranscriptionError(
                    "Audio data is None",
                    context={"provider": "faster-whisper"},
                )

            # Save audio to temporary file for Faster-Whisper
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio.data)
                tmp_path = tmp.name

            try:
                segments_iter, info = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._model.transcribe,
                        tmp_path,
                        language=language,
                    ),
                    timeout=timeout,
                )

                # Collect all segments
                segments = []
                full_text = []
                for segment in segments_iter:
                    segments.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                    })
                    full_text.append(segment.text)

            finally:
                Path(tmp_path).unlink(missing_ok=True)

            duration_ms = (time.monotonic() - start) * 1000

            text = " ".join(full_text).strip()

            return TranscriptionResult(
                text=text,
                confidence=1.0,  # Faster-Whisper doesn't provide per-word confidence
                language=language,
                duration_ms=duration_ms,
                segments=tuple(segments),
            )

        except asyncio.TimeoutError:
            raise VoiceTimeoutError(
                f"Faster-Whisper transcription timed out after {timeout}s",
                context={"provider": "faster-whisper", "timeout": timeout},
            ) from None
        except Exception as exc:
            self._logger.error("Faster-Whisper transcription failed: %s", exc)
            raise VoiceTranscriptionError(
                f"Faster-Whisper transcription failed: {exc}",
                context={"provider": "faster-whisper"},
            ) from exc

    async def close(self) -> None:
        """Release model resources."""
        self._model = None
        self._model_loaded = False
        self._logger.debug("Faster-Whisper provider closed")
