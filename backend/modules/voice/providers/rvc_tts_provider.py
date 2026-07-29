"""RvcTTSProvider — Retrieval-based Voice Conversion (RVC) TTS provider.

Re-exports RVCProvider from rvc_provider.py for backward compatibility.
"""

from __future__ import annotations

from backend.modules.voice.providers.rvc_provider import (
    RVCProvider,
    RvcTTSProvider,
    TTSProvider,
    _HAS_RVC_PYTHON,
)

__all__ = [
    "RVCProvider",
    "RvcTTSProvider",
    "TTSProvider",
    "_HAS_RVC_PYTHON",
]
