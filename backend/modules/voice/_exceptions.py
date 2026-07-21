"""
Voice exception hierarchy.

21_System_Contracts.md §3 — All application exceptions inherit from
``NairaError`` and carry a ``context`` dict.
"""

from __future__ import annotations

from typing import Any

from backend.exceptions import NairaError


class VoiceError(NairaError):
    """Base for all voice-module errors."""


class VoiceTimeoutError(VoiceError):
    """A voice operation exceeded its timeout."""


class VoiceAudioError(VoiceError):
    """Audio recording, loading, or playback failed."""


class VoiceTranscriptionError(VoiceError):
    """Speech-to-text transcription failed."""


class VoiceSynthesisError(VoiceError):
    """Text-to-speech synthesis failed."""


class VoiceWakeWordError(VoiceError):
    """Wake-word detection failed."""


class VoiceNotImplementedError(VoiceError):
    """The operation is not supported by the current adapter.

    Raised by placeholder adapters (e.g. ``LocalVoiceAdapter``)
    to signal that the real implementation has not been wired yet.
    """

    def __init__(self, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            "Voice adapter not available — no STT/TTS engine or audio driver configured",
            context=context,
        )
