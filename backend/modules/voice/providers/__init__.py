"""Voice providers — STT, TTS, and Wake Word implementations.

Providers are lazy-loaded and gracefully handle missing dependencies.
"""

from __future__ import annotations

from backend.modules.voice.providers.whisper_provider import WhisperSTTProvider
from backend.modules.voice.providers.faster_whisper_provider import FasterWhisperSTTProvider
from backend.modules.voice.providers.piper_provider import PiperTTSProvider
from backend.modules.voice.providers.coqui_provider import CoquiTTSProvider
from backend.modules.voice.providers.elevenlabs_provider import ElevenLabsTTSProvider
from backend.modules.voice.providers.porcupine_provider import PorcupineWakeWordProvider
from backend.modules.voice.providers.edge_tts_provider import EdgeTTSProvider, _HAS_EDGE_TTS

__all__ = [
    "WhisperSTTProvider",
    "FasterWhisperSTTProvider",
    "PiperTTSProvider",
    "CoquiTTSProvider",
    "ElevenLabsTTSProvider",
    "PorcupineWakeWordProvider",
    "EdgeTTSProvider",
    "_HAS_EDGE_TTS",
]
