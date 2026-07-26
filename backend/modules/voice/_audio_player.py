"""
AudioPlayer — audio playback using sounddevice.

Supports WAV playback with configurable sample rates,
non-blocking playback, and stream interruption.
"""

from __future__ import annotations

import asyncio
import io
import logging
import threading
import time

from backend.modules.voice._exceptions import VoiceAudioError
from backend.modules.voice._types import AudioData

_LOG = logging.getLogger("naira.voice.audio_player")

# Global thread-safe interrupt event for 0-latency voice barge-in
audio_interrupt_event = threading.Event()

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
    """Audio playback using sounddevice with barge-in support.

    Provides:
    - Blocking playback via ``play()`` (chunked, interruptible)
    - Non-blocking playback via ``play_async()`` (chunked, interruptible)
    - Playback interruption via ``stop()`` or setting ``audio_interrupt_event``
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
        """Play audio data through speakers (blocking, chunked for barge-in).

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

            async with self._lock:
                self._playing = True
                audio_interrupt_event.clear()
                channels = data.shape[1] if data.ndim > 1 else 1
                chunk_samples = max(100, int(sample_rate * 0.05))

                stream = sd.OutputStream(
                    samplerate=sample_rate,
                    channels=channels,
                    dtype=data.dtype,
                )
                self._current_stream = stream
                stream.start()

            try:
                start_time = time.time()
                total_samples = len(data)
                for idx in range(0, total_samples, chunk_samples):
                    if audio_interrupt_event.is_set():
                        self._logger.info("Audio playback interrupted by barge-in event")
                        audio_interrupt_event.clear()
                        break
                    if timeout > 0 and (time.time() - start_time) > timeout:
                        self._logger.warning("Audio playback timed out")
                        break

                    chunk = data[idx : idx + chunk_samples]
                    await asyncio.to_thread(stream.write, chunk)
            finally:
                async with self._lock:
                    try:
                        if self._current_stream is not None:
                            self._current_stream.stop()
                            self._current_stream.close()
                    except Exception:
                        pass
                    if sd:
                        sd.stop()
                    self._current_stream = None
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
        Call ``stop()`` or set ``audio_interrupt_event`` to interrupt.
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
                    try:
                        self._current_stream.stop()
                        self._current_stream.close()
                    except Exception:
                        pass

                channels = data.shape[1] if data.ndim > 1 else 1
                stream = sd.OutputStream(
                    samplerate=sample_rate,
                    channels=channels,
                    dtype=data.dtype,
                )
                self._current_stream = stream
                self._playing = True
                audio_interrupt_event.clear()

                async def _background_writer() -> None:
                    chunk_samples = max(100, int(sample_rate * 0.05))
                    try:
                        stream.start()
                        for idx in range(0, len(data), chunk_samples):
                            if audio_interrupt_event.is_set():
                                self._logger.info("Async audio playback interrupted by barge-in event")
                                audio_interrupt_event.clear()
                                break
                            chunk = data[idx : idx + chunk_samples]
                            await asyncio.to_thread(stream.write, chunk)
                    except Exception as exc:
                        self._logger.debug("Background playback writer exception: %s", exc)
                    finally:
                        try:
                            stream.stop()
                            stream.close()
                        except Exception:
                            pass
                        if sd:
                            sd.stop()
                        self._current_stream = None
                        self._playing = False

                asyncio.create_task(_background_writer())

        except Exception as exc:
            self._playing = False
            raise VoiceAudioError(
                f"Async playback failed: {exc}",
                context={"operation": "play_async"},
            ) from exc

    async def stop(self) -> None:
        """Stop current playback immediately."""
        audio_interrupt_event.set()
        async with self._lock:
            if self._current_stream is not None:
                try:
                    self._current_stream.stop()
                    self._current_stream.close()
                except Exception:
                    pass
                self._current_stream = None
            if sd:
                sd.stop()
            self._playing = False

    def interrupt(self) -> None:
        """Signal an immediate playback interrupt."""
        audio_interrupt_event.set()

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
