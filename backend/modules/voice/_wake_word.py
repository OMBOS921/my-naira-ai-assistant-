"""
WakeWord — wake-word detection using available providers.

Delegates to registered wake word providers (Porcupine, etc.)
for real detection.  Falls back to simple keyword matching via STT
when no dedicated wake word provider is available.
"""

from __future__ import annotations

import asyncio
import logging

from backend.modules.voice._audio_player import audio_interrupt_event
from backend.modules.voice._types import AudioData, WakeWordResult

_LOG = logging.getLogger("naira.voice.wake_word")

_FALLBACK_KEYWORDS = (
    "naira", "nyra", "aira", "nira", "hey naira",
    "hi naira", "nayra", "nera", "naura",
)


class WakeWord:
    """Wake-word detection using registered providers.

    Accepts an optional provider dict and STT provider for fallback
    keyword matching when no dedicated wake word engine is available.
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        providers: dict[str, object] | None = None,
        stt_provider: object | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._providers: dict[str, object] = providers or {}
        self._stt_provider = stt_provider
        self._fallback_keywords = _FALLBACK_KEYWORDS

    async def detect(
        self,
        audio: AudioData,
        *,
        wake_word: str = "",
        timeout: float = 30.0,
    ) -> WakeWordResult:
        """Detect a wake word in *audio*.

        Tries dedicated wake word providers first.
        Falls back to STT-based keyword matching.
        """
        if self._providers:
            result = await self._try_providers(audio, wake_word, timeout)
            if result is not None:
                return result

        if self._stt_provider is not None:
            return await self._fallback_stt_detect(audio, wake_word, timeout)

        self._logger.debug(
            "WakeWord — no providers or STT fallback available"
        )
        return WakeWordResult(detected=False, wake_word=wake_word)

    async def _try_providers(
        self,
        audio: AudioData,
        wake_word: str,
        timeout: float,
    ) -> WakeWordResult | None:
        for name, provider in self._providers.items():
            is_avail = getattr(provider, "is_available", False)
            if not is_avail:
                continue
            detect_fn = getattr(provider, "detect_wake_word", None)
            if detect_fn is None:
                continue
            try:
                result = await asyncio.wait_for(
                    detect_fn(audio, wake_word=wake_word, timeout=timeout),
                    timeout=timeout + 1.0,
                )
                if result and result.detected:
                    audio_interrupt_event.set()
                    return WakeWordResult(
                        detected=True,
                        wake_word=result.wake_word or wake_word,
                        confidence=result.confidence,
                    )
            except Exception as exc:
                self._logger.debug(
                    "WakeWord provider '%s' failed: %s", name, exc
                )
                continue
        return None

    async def _fallback_stt_detect(
        self,
        audio: AudioData,
        wake_word: str,
        timeout: float,
    ) -> WakeWordResult:
        transcribe_fn = getattr(self._stt_provider, "transcribe", None)
        if transcribe_fn is None:
            return WakeWordResult(detected=False, wake_word=wake_word)

        try:
            result = await asyncio.wait_for(
                transcribe_fn(audio, language="en", timeout=timeout),
                timeout=timeout + 1.0,
            )
            if not result or not result.text:
                return WakeWordResult(detected=False, wake_word=wake_word)

            text_heard = result.text.lower().strip()
            keywords = [wake_word.lower()] if wake_word else self._fallback_keywords

            for kw in keywords:
                if kw in text_heard:
                    audio_interrupt_event.set()
                    return WakeWordResult(
                        detected=True,
                        wake_word=kw,
                        confidence=result.confidence or 0.5,
                    )

            return WakeWordResult(detected=False, wake_word=wake_word)

        except Exception as exc:
            self._logger.debug("STT fallback wake word detection failed: %s", exc)
            return WakeWordResult(detected=False, wake_word=wake_word)

    @property
    def is_available(self) -> bool:
        if any(getattr(p, "is_available", False) for p in self._providers.values()):
            return True
        if self._stt_provider is not None:
            return getattr(self._stt_provider, "is_available", False)
        return False
