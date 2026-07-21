"""
SpeechToText — speech-to-text using the available STT provider chain.

Delegates to registered STT providers (faster-whisper, whisper, etc.)
in priority order.  Returns empty result only when all providers fail.
"""

from __future__ import annotations

import asyncio
import logging

from backend.modules.voice._types import AudioData, TranscriptionResult

_LOG = logging.getLogger("naira.voice.speech_to_text")


class SpeechToText:
    """Speech-to-text using registered STT providers.

    Accepts an optional provider dict at construction time.
    When no providers are registered, returns empty transcription.
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        providers: dict[str, object] | None = None,
        fallback_chain: tuple[str, ...] = ("faster-whisper", "whisper"),
    ) -> None:
        self._logger = logger or _LOG
        self._providers: dict[str, object] = providers or {}
        self._fallback_chain = fallback_chain

    async def transcribe(
        self,
        audio: AudioData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> TranscriptionResult:
        """Transcribe speech in *audio* to text.

        Tries each registered provider in fallback chain order.
        Returns the first successful transcription.
        """
        if not self._providers:
            self._logger.debug(
                "SpeechToText — no providers registered, returning empty result"
            )
            return TranscriptionResult(text="", language=language, duration_ms=audio.duration_ms)

        errors: list[str] = []
        for provider_name in self._fallback_chain:
            provider = self._providers.get(provider_name)
            if provider is None:
                continue

            is_avail = getattr(provider, "is_available", False)
            if not is_avail:
                continue

            transcribe_fn = getattr(provider, "transcribe", None)
            if transcribe_fn is None:
                continue

            try:
                result = await asyncio.wait_for(
                    transcribe_fn(audio, language=language, timeout=timeout),
                    timeout=timeout + 1.0,
                )
                if result and result.text:
                    return result
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                self._logger.debug(
                    "STT provider '%s' failed: %s", provider_name, exc
                )
                continue

        if errors:
            self._logger.warning(
                "All STT providers failed: %s", "; ".join(errors)
            )

        return TranscriptionResult(text="", language=language, duration_ms=audio.duration_ms)

    @property
    def is_available(self) -> bool:
        return any(
            getattr(p, "is_available", False)
            for p in self._providers.values()
        )
