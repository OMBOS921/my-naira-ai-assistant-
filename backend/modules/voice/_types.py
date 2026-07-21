"""
Voice types — immutable result dataclasses for speech processing.

21_System_Contracts.md §15 — Tool contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type AudioFormat = Literal["wav", "mp3", "ogg", "flac", "webm", "unknown"]
"""Supported audio container formats."""

type AudioSourceType = Literal["microphone", "file", "bytes", "url"]
"""Origin of audio data loaded into the module."""

type VoiceOperation = Literal[
    "transcribe", "synthesize", "detect_wake_word",
    "start_recording", "stop_recording", "play_audio",
]
"""Types of voice operations tracked by the module."""


@dataclass(frozen=True)
class AudioData:
    """Raw audio data with source metadata.

    Parameters
    ----------
    source_type : AudioSourceType
        How the audio was obtained.
    source_path : str | None
        File path or URL the audio was loaded from.
    format : AudioFormat
        Detected or declared audio format.
    sample_rate : int
        Sample rate in Hz (0 if unknown).
    channels : int
        Number of audio channels (0 if unknown).
    duration_ms : float
        Duration in milliseconds (0.0 if unknown).
    size_bytes : int
        Uncompressed size in bytes (0 if unknown).
    data : bytes | None
        Raw audio data (bytes). ``None`` if not yet loaded.
    """

    source_type: AudioSourceType
    source_path: str | None = None
    format: AudioFormat = "unknown"
    sample_rate: int = 0
    channels: int = 0
    duration_ms: float = 0.0
    size_bytes: int = 0
    data: bytes | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    """Text transcribed from audio via STT.

    Parameters
    ----------
    text : str
        Transcribed text content.
    confidence : float
        Confidence score in range [0.0, 1.0] (0.0 if placeholder).
    language : str
        Detected language code (e.g. ``"en"``).
    duration_ms : float
        Audio duration processed.
    segments : tuple[dict, ...]
        Timestamped segments when available.
    """

    text: str = ""
    confidence: float = 0.0
    language: str = "en"
    duration_ms: float = 0.0
    segments: tuple[dict, ...] = ()


@dataclass(frozen=True)
class SynthesisResult:
    """Audio synthesised from text via TTS.

    Parameters
    ----------
    audio : AudioData | None
        Synthesised audio data.
    text : str
        Original input text that was synthesised.
    voice_id : str
        Voice identifier used for synthesis.
    duration_ms : float
        Synthesised audio duration in milliseconds.
    """

    audio: AudioData | None = None
    text: str = ""
    voice_id: str = ""
    duration_ms: float = 0.0


@dataclass(frozen=True)
class WakeWordResult:
    """Result of wake-word detection.

    Parameters
    ----------
    detected : bool
        Whether the wake word was detected.
    wake_word : str
        The wake word that was detected (empty if none).
    confidence : float
        Detection confidence in range [0.0, 1.0].
    """

    detected: bool = False
    wake_word: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class VoiceResult:
    """Complete result of a voice operation.

    Parameters
    ----------
    status : Literal["success", "error", "timeout"]
        Operation outcome.
    output : str | None
        Human-readable output text.
    error : str | None
        Error message if status is ``"error"`` or ``"timeout"``.
    transcription : TranscriptionResult | None
        STT result, if applicable.
    synthesis : SynthesisResult | None
        TTS result, if applicable.
    wake_word : WakeWordResult | None
        Wake-word detection result, if applicable.
    duration_ms : float
        Wall-clock time for the operation.
    """

    status: Literal["success", "error", "timeout"] = "success"
    output: str | None = None
    error: str | None = None
    transcription: TranscriptionResult | None = None
    synthesis: SynthesisResult | None = None
    wake_word: WakeWordResult | None = None
    duration_ms: float = 0.0
