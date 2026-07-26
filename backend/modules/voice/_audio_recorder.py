"""
AudioRecorder — microphone recording using sounddevice with VAD.

Supports continuous listening, VAD-based silence detection,
noise filtering, and configurable sample rates.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from threading import Thread

from backend.modules.voice._audio_player import audio_interrupt_event
from backend.modules.voice._exceptions import VoiceAudioError
from backend.modules.voice._types import AudioData

_LOG = logging.getLogger("naira.voice.audio_recorder")

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

_VAD_THRESHOLD: float = 25.0
_SILENCE_TIMEOUT: float = 1.5
_MIN_RECORD_SEC: float = 0.5
_MAX_RECORD_SEC: float = 30.0
_SAMPLE_RATE: int = 16000
_CHANNELS: int = 1
_DTYPE: str = "int16"


class AudioRecorder:
    """Microphone recorder using sounddevice with VAD support.

    Provides:
    - Fixed-duration recording via ``record()``
    - VAD-based recording via ``record_until_silence()``
    - Continuous streaming via ``start_stream()`` / ``stop_stream()``
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG
        self._stream: sd.InputStream | None = None
        self._stream_buffer: list[np.ndarray] = []
        self._stream_active: bool = False
        self._stream_lock: asyncio.Lock = asyncio.Lock()

    async def record(
        self,
        *,
        duration: float = 4.0,
        sample_rate: int = _SAMPLE_RATE,
        timeout: float = _MAX_RECORD_SEC,
    ) -> AudioData:
        """Record audio for a fixed duration.

        Parameters
        ----------
        duration : float
            Recording duration in seconds.
        sample_rate : int
            Sample rate in Hz.
        timeout : float
            Maximum wait time.

        Returns
        -------
        AudioData
            The recorded audio data.

        Raises
        ------
        VoiceAudioError
            If recording fails or sounddevice is unavailable.
        """
        self._ensure_sounddevice()

        effective_duration = min(duration, timeout)
        try:
            recording = await asyncio.to_thread(
                sd.rec,
                int(effective_duration * sample_rate),
                samplerate=sample_rate,
                channels=_CHANNELS,
                dtype=_DTYPE,
            )
            await asyncio.sleep(effective_duration)
            sd.wait()

            wav_bytes = self._to_wav_bytes(recording, sample_rate)
            rms = float(np.sqrt(np.mean(recording.astype(np.float32) ** 2)))

            return AudioData(
                source_type="microphone",
                format="wav",
                sample_rate=sample_rate,
                channels=_CHANNELS,
                duration_ms=effective_duration * 1000,
                size_bytes=len(wav_bytes),
                data=wav_bytes,
            )
        except Exception as exc:
            raise VoiceAudioError(
                f"Recording failed: {exc}",
                context={"duration": duration, "sample_rate": sample_rate},
            ) from exc

    async def record_until_silence(
        self,
        *,
        max_duration: float = _MAX_RECORD_SEC,
        silence_timeout: float = _SILENCE_TIMEOUT,
        sample_rate: int = _SAMPLE_RATE,
    ) -> AudioData:
        """Record audio until silence detected or max duration reached.

        Uses RMS energy threshold for VAD.

        Parameters
        ----------
        max_duration : float
            Maximum recording duration.
        silence_timeout : float
            Seconds of silence before stopping.
        sample_rate : int
            Sample rate in Hz.

        Returns
        -------
        AudioData
            The recorded audio.
        """
        self._ensure_sounddevice()

        frames: list[np.ndarray] = []
        chunk_sec = 0.1
        chunk_samples = int(chunk_sec * sample_rate)
        silence_start: float | None = None
        start_time = time.time()
        recording_started = False

        def _callback(indata, _frames, _time_info, _status):
            nonlocal silence_start, recording_started
            rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
            if rms > _VAD_THRESHOLD:
                audio_interrupt_event.set()
                recording_started = True
                silence_start = None
                frames.append(indata.copy())
            elif recording_started:
                if silence_start is None:
                    silence_start = time.time()
                frames.append(indata.copy())

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=_CHANNELS,
                dtype=_DTYPE,
                blocksize=chunk_samples,
                callback=_callback,
            ):
                while True:
                    await asyncio.sleep(chunk_sec)
                    elapsed = time.time() - start_time
                    if not recording_started and elapsed > max_duration:
                        raise VoiceAudioError(
                            "No speech detected",
                            context={"max_duration": max_duration},
                        )
                    if recording_started and silence_start is not None:
                        if time.time() - silence_start > silence_timeout:
                            break
                    if elapsed > max_duration:
                        break

            if not frames:
                raise VoiceAudioError(
                    "No audio captured",
                    context={"max_duration": max_duration},
                )

            recording = np.concatenate(frames, axis=0)
            actual_duration = len(recording) / sample_rate
            wav_bytes = self._to_wav_bytes(recording, sample_rate)

            return AudioData(
                source_type="microphone",
                format="wav",
                sample_rate=sample_rate,
                channels=_CHANNELS,
                duration_ms=actual_duration * 1000,
                size_bytes=len(wav_bytes),
                data=wav_bytes,
            )
        except VoiceAudioError:
            raise
        except Exception as exc:
            raise VoiceAudioError(
                f"VAD recording failed: {exc}",
                context={"max_duration": max_duration},
            ) from exc

    async def start_stream(
        self,
        *,
        sample_rate: int = _SAMPLE_RATE,
        blocksize: int = 1600,
    ) -> None:
        """Start a continuous recording stream.

        Call ``stop_stream()`` to stop and get the accumulated audio.
        """
        self._ensure_sounddevice()
        async with self._stream_lock:
            if self._stream_active:
                return
            self._stream_buffer = []
            self._stream_active = True

            def _callback(indata, _frames, _time_info, _status):
                if self._stream_active:
                    rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
                    if rms > _VAD_THRESHOLD:
                        audio_interrupt_event.set()
                    self._stream_buffer.append(indata.copy())

            self._stream = sd.InputStream(
                samplerate=sample_rate,
                channels=_CHANNELS,
                dtype=_DTYPE,
                blocksize=blocksize,
                callback=_callback,
            )
            self._stream.start()

    async def stop_stream(self) -> AudioData:
        """Stop the recording stream and return accumulated audio."""
        async with self._stream_lock:
            if self._stream is not None:
                self._stream_active = False
                self._stream.stop()
                self._stream.close()
                self._stream = None

            if not self._stream_buffer:
                raise VoiceAudioError(
                    "No audio captured in stream",
                    context={"operation": "stop_stream"},
                )

            recording = np.concatenate(self._stream_buffer, axis=0)
            sample_rate = _SAMPLE_RATE
            wav_bytes = self._to_wav_bytes(recording, sample_rate)
            actual_duration = len(recording) / sample_rate

            self._stream_buffer = []

            return AudioData(
                source_type="microphone",
                format="wav",
                sample_rate=sample_rate,
                channels=_CHANNELS,
                duration_ms=actual_duration * 1000,
                size_bytes=len(wav_bytes),
                data=wav_bytes,
            )

    async def close(self) -> None:
        """Release resources."""
        async with self._stream_lock:
            if self._stream is not None:
                self._stream_active = False
                self._stream.stop()
                self._stream.close()
                self._stream = None
            self._stream_buffer = []

    @property
    def is_available(self) -> bool:
        return _HAS_SOUNDDEVICE

    @staticmethod
    def _ensure_sounddevice() -> None:
        if not _HAS_SOUNDDEVICE:
            raise VoiceAudioError(
                "sounddevice not installed — install with: pip install sounddevice soundfile numpy",
                context={"operation": "audio_recording"},
            )

    @staticmethod
    def _to_wav_bytes(recording: np.ndarray, sample_rate: int) -> bytes:
        buf = io.BytesIO()
        sf.write(buf, recording, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()
