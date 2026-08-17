"""
VoiceExecutor — async execution layer with timeout and error isolation.

Wraps port/adapter operations so that ``VoiceManager`` never deals
with raw exceptions or hanging calls.
"""

from __future__ import annotations

import asyncio
import logging

from backend.modules.voice._exceptions import VoiceNotImplementedError
from backend.modules.voice._types import AudioData
from backend.modules.voice.ports.voice_port import VoicePort
from backend.types import ToolResult
_LOG = logging.getLogger("naira.voice.executor")


class VoiceExecutor:
    """Safe execution wrapper for voice operations.

    Parameters
    ----------
    adapter : VoicePort
        The active voice adapter (placeholder or real).
    default_timeout : float
        Default timeout for all operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        adapter: VoicePort,
        default_timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._adapter = adapter
        self._default_timeout = default_timeout
        self._logger = logger or _LOG

    async def transcribe(
        self,
        audio: AudioData,
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Transcribe speech audio to text.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            result = await asyncio.wait_for(
                self._adapter.transcribe(audio, language=language, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            if result.text:
                return ToolResult(status="success", output=result.text)
            return ToolResult(
                status="error",
                error="No speech detected in audio",
            )
        except VoiceNotImplementedError:
            return ToolResult(
                status="error",
                error="Voice adapter not configured — no STT engine available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Transcription timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Transcription failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Transcription failed: {exc}",
            )

    async def synthesize(
        self,
        text: str,
        voice_id: str = "",
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Synthesise speech from text.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            result = await asyncio.wait_for(
                self._adapter.synthesize(
                    text, voice_id=voice_id, language=language, timeout=effective_timeout,
                ),
                timeout=effective_timeout + 1.0,
            )
            if result.audio is not None and result.audio.data:
                voice_label = result.voice_id or "default"
                return ToolResult(
                    status="success",
                    output=f"Speech synthesised — {result.duration_ms:.0f}ms, voice: {voice_label}",
                )
            return ToolResult(
                status="error",
                error="No audio generated from synthesis",
            )
        except VoiceNotImplementedError:
            return ToolResult(
                status="error",
                error="Voice adapter not configured — no TTS engine available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Synthesis timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Synthesis failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Synthesis failed: {exc}",
            )

    async def detect_wake_word(
        self,
        audio: AudioData,
        wake_word: str = "",
        timeout: float | None = None,
    ) -> ToolResult:
        """Detect a wake word in audio.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            result = await asyncio.wait_for(
                self._adapter.detect_wake_word(
                    audio, wake_word=wake_word, timeout=effective_timeout,
                ),
                timeout=effective_timeout + 1.0,
            )
            if result.detected:
                ww = result.wake_word
                return ToolResult(
                    status="success",
                    output=f"Wake word '{ww}' detected (confidence: {result.confidence:.2f})",
                )
            return ToolResult(
                status="error",
                error="Wake word not detected",
            )
        except VoiceNotImplementedError:
            return ToolResult(
                status="error",
                error="Voice adapter not configured — no wake-word engine available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Wake-word detection timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Wake-word detection failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Wake-word detection failed: {exc}",
            )

    async def start_recording(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        """Start recording audio from the microphone.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            audio = await asyncio.wait_for(
                self._adapter.start_recording(timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            return ToolResult(
                status="success",
                output=f"Audio recorded — {audio.duration_ms:.0f}ms, {audio.sample_rate}Hz",
            )
        except VoiceNotImplementedError:
            return ToolResult(
                status="error",
                error="Voice adapter not configured — no microphone driver available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Recording timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Recording failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Recording failed: {exc}",
            )

    async def play_audio(
        self,
        audio: AudioData,
        timeout: float | None = None,
    ) -> ToolResult:
        """Play audio data through speakers.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            await asyncio.wait_for(
                self._adapter.play_audio(audio, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            return ToolResult(status="success", output="Audio played successfully")
        except VoiceNotImplementedError:
            return ToolResult(
                status="error",
                error="Voice adapter not configured — no audio playback driver available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Audio playback timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Audio playback failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Audio playback failed: {exc}",
            )

    @property
    def is_available(self) -> bool:
        """Return ``True`` if the underlying adapter is usable."""
        return self._adapter.is_available
