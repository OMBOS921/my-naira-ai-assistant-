"""
Voice module — the AI's speech perception and synthesis layer.

Provides speech-to-text, text-to-speech, wake-word detection, audio
recording, and audio playback capabilities through a pluggable adapter
architecture.

All actual providers (Whisper, Piper, Coqui TTS, ElevenLabs, Google
TTS, Porcupine) will be integrated as concrete ``VoicePort``
implementations in Phase 2.
"""

from __future__ import annotations

from backend.modules.voice._audio_player import AudioPlayer
from backend.modules.voice._audio_recorder import AudioRecorder
from backend.modules.voice._executor import VoiceExecutor
from backend.modules.voice._local_adapter import LocalVoiceAdapter
from backend.modules.voice._speech_to_text import SpeechToText
from backend.modules.voice._text_to_speech import TextToSpeech
from backend.modules.voice._types import (
    AudioData,
    SynthesisResult,
    TranscriptionResult,
    VoiceResult,
    WakeWordResult,
)
from backend.modules.voice._wake_word import WakeWord
from backend.modules.voice.ports.voice_port import VoicePort
from backend.modules.voice.voice_module import VoiceManager

__all__ = [
    "VoiceManager",
    "VoicePort",
    "LocalVoiceAdapter",
    "VoiceExecutor",
    "SpeechToText",
    "TextToSpeech",
    "WakeWord",
    "AudioRecorder",
    "AudioPlayer",
    "AudioData",
    "TranscriptionResult",
    "SynthesisResult",
    "WakeWordResult",
    "VoiceResult",
]
