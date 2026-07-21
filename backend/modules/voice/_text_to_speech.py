"""
TextToSpeech — text-to-speech using the available TTS provider chain.

Delegates to registered TTS providers (edge-tts, piper, coqui, elevenlabs, etc.)
in priority order.  Returns empty result only when all providers fail.
"""

from __future__ import annotations

import asyncio
import logging

from backend.modules.voice._types import AudioData, SynthesisResult

_LOG = logging.getLogger("naira.voice.text_to_speech")


class TextToSpeech:
    """Text-to-speech using registered TTS providers.

    Accepts an optional provider dict at construction time.
    When no providers are registered, returns empty synthesis.
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        providers: dict[str, object] | None = None,
        fallback_chain: tuple[str, ...] = ("edge-tts", "piper", "coqui", "elevenlabs"),
    ) -> None:
        self._logger = logger or _LOG
        self._providers: dict[str, object] = providers or {}
        self._fallback_chain = fallback_chain

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        """Synthesise speech from *text*.

        Tries each registered provider in fallback chain order.
        Returns the first successful synthesis result.
        """
        if not self._providers:
            self._logger.debug(
                "TextToSpeech — no providers registered, returning empty result"
            )
            return SynthesisResult(text=text, voice_id=voice_id)

        errors: list[str] = []
        for provider_name in self._fallback_chain:
            provider = self._providers.get(provider_name)
            if provider is None:
                continue

            is_avail = getattr(provider, "is_available", False)
            if not is_avail:
                continue

            synthesize_fn = getattr(provider, "synthesize", None)
            if synthesize_fn is None:
                continue

            try:
                result = await asyncio.wait_for(
                    synthesize_fn(text, voice_id=voice_id, language=language, timeout=timeout),
                    timeout=timeout + 1.0,
                )
                if result and result.audio and result.audio.data:
                    return result
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                self._logger.debug(
                    "TTS provider '%s' failed: %s", provider_name, exc
                )
                continue

        if errors:
            self._logger.warning(
                "All TTS providers failed: %s", "; ".join(errors)
            )

        return SynthesisResult(text=text, voice_id=voice_id)

    @property
    def is_available(self) -> bool:
        return any(
            getattr(p, "is_available", False)
            for p in self._providers.values()
        )
