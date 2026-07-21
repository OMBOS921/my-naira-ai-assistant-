"""
AudioPlayer — audio playback using sounddevice.

Supports WAV playback with configurable sample rates,
non-blocking playback, and stream interruption.
"""

from __future__ import annotations

import asyncio
import io
import logging

from backend.modules.voice._exceptions import VoiceAudioError
from backend.modules.voice._types import AudioData

_LOG = logging.getLogger("naira.voice.audio_player")

_HAS_SOUNDDEVICE = False
try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    _HAS_SOUNDDEVICE = True
except ImportError:
    np = None
    sd = None
    sf = None


class AudioPlayer:
    """Audio playback using sounddevice.

    Provides:
    - Blocking playback via ``play()``
    - Non-blocking playback via ``play_async()``
    - Playback interruption via ``stop()``
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG
        self._current_stream: sd.OutputStream | None = None
        self._playing: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()

    async def play(
        self,
        audio: AudioData,
        *,
        timeout: float = 30.0,
    ) -> None:
        """Play audio data through speakers (blocking).

        Parameters
        ----------
        audio : AudioData
            Audio data to play.
        timeout : float
            Maximum playback time.

        Raises
        ------
        VoiceAudioError
            If playback fails or sounddevice is unavailable.
        """
        self._ensure_sounddevice()

        if not audio.data:
            raise VoiceAudioError(
                "No audio data to play",
                context={"operation": "play_audio"},
            )

        try:
            data, sample_rate = self._load_audio(audio)
            duration = len(data) / sample_rate

            async with self._lock:
                self._playing = True
                await asyncio.to_thread(
                    sd.play, data, samplerate=sample_rate
                )
                await asyncio.sleep(min(duration, timeout))
                sd.stop()
                self._playing = False

        except Exception as exc:
            self._playing = False
            raise VoiceAudioError(
                f"Playback failed: {exc}",
                context={"operation": "play_audio"},
            ) from exc

    async def play_async(
        self,
        audio: AudioData,
    ) -> None:
        """Start non-blocking playback.

        Returns immediately while audio plays in background.
        Call ``stop()`` to interrupt.
        """
        self._ensure_sounddevice()

        if not audio.data:
            raise VoiceAudioError(
                "No audio data to play",
                context={"operation": "play_async"},
            )

        try:
            data, sample_rate = self._load_audio(audio)

            async with self._lock:
                if self._current_stream is not None:
                    self._current_stream.stop()
                    self._current_stream.close()

                self._current_stream = sd.OutputStream(
                    samplerate=sample_rate,
                    channels=data.shape[1] if data.ndim > 1 else 1,
                    dtype=data.dtype,
                )
                self._current_stream.start()
                self._current_stream.write(data)
                self._playing = True

        except Exception as exc:
            raise VoiceAudioError(
                f"Async playback failed: {exc}",
                context={"operation": "play_async"},
            ) from exc

    async def stop(self) -> None:
        """Stop current playback immediately."""
        async with self._lock:
            if self._current_stream is not None:
                self._current_stream.stop()
                self._current_stream.close()
                self._current_stream = None
            sd.stop()
            self._playing = False

    async def close(self) -> None:
        """Release resources."""
        await self.stop()

    @property
    def is_available(self) -> bool:
        return _HAS_SOUNDDEVICE

    @property
    def is_playing(self) -> bool:
        return self._playing

    @staticmethod
    def _ensure_sounddevice() -> None:
        if not _HAS_SOUNDDEVICE:
            raise VoiceAudioError(
                "sounddevice not installed — install with: pip install sounddevice soundfile numpy",
                context={"operation": "audio_playback"},
            )

    @staticmethod
    def _load_audio(audio: AudioData) -> tuple[np.ndarray, int]:
        if audio.format == "wav" and audio.data:
            buf = io.BytesIO(audio.data)
            data, sample_rate = sf.read(buf, dtype="int16")
            return data, sample_rate

        import numpy as np
        sample_rate = audio.sample_rate or 16000
        dtype = np.int16
        raw = np.frombuffer(audio.data, dtype=dtype)
        return raw, sample_rate
