"""
VoiceManager — the single public class for the voice module.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §15 — Tool contracts.
21_System_Contracts.md §4.2 — ModuleInterface protocol.

Mirrors LLMManager and VisionManager patterns: supports multiple registered
providers, an active provider for each operation type (STT, TTS, Wake Word),
and fallback chains.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.voice._audio_player import AudioPlayer, audio_interrupt_event
from backend.modules.voice._audio_recorder import AudioRecorder
from backend.modules.voice._exceptions import VoiceNotImplementedError
from backend.modules.voice._local_adapter import LocalVoiceAdapter
from backend.modules.voice._speech_to_text import SpeechToText
from backend.modules.voice._text_to_speech import TextToSpeech
from backend.modules.voice._types import AudioData
from backend.modules.voice._wake_word import WakeWord
from backend.modules.voice.ports.voice_port import VoicePort
from backend.modules.voice.providers._stt_port import STTPort
from backend.modules.voice.providers._tts_port import TTSPort
from backend.modules.voice.providers._wake_word_port import WakeWordPort
from backend.types import ToolResult

_LOG = logging.getLogger("naira.voice")


class VoiceManager:
    """Central voice manager — STT, TTS, wake-word, audio recording & playback.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Mirrors ``LLMManager`` and ``VisionManager`` patterns: supports multiple
    registered providers, active providers per operation type, and fallback chains.

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        ``EventBus`` instance for event emission.
    capability_manager : object | None
        ``CapabilityManager`` instance for capability registration.
    tool_manager : object | None
        ``ToolManager`` instance for tool registration.
    adapter : VoicePort | None
        Legacy single adapter parameter (backward compat).
    stt_providers : dict[str, STTPort] | None
        Registered STT providers keyed by name.
    tts_providers : dict[str, TTSPort] | None
        Registered TTS providers keyed by name.
    wake_word_providers : dict[str, WakeWordPort] | None
        Registered wake word providers keyed by name.
    active_stt_provider_name : str | None
        Name of the active STT provider (from VoiceConfig).
    active_tts_provider_name : str | None
        Name of the active TTS provider (from VoiceConfig).
    active_wake_word_provider_name : str | None
        Name of the active wake word provider (from VoiceConfig).
    stt_fallback_chain : tuple[str, ...] | None
        Ordered fallback chain of STT provider names.
    tts_fallback_chain : tuple[str, ...] | None
        Ordered fallback chain of TTS provider names.
    default_timeout : float
        Default timeout for voice operations (default 30.0).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        tool_manager: object | None = None,
        adapter: VoicePort | None = None,
        stt_providers: dict[str, STTPort] | None = None,
        tts_providers: dict[str, TTSPort] | None = None,
        wake_word_providers: dict[str, WakeWordPort] | None = None,
        active_stt_provider_name: str | None = None,
        active_tts_provider_name: str | None = None,
        active_wake_word_provider_name: str | None = None,
        stt_fallback_chain: tuple[str, ...] | None = None,
        tts_fallback_chain: tuple[str, ...] | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._degraded: bool = False
        self._default_timeout = default_timeout

        # Provider registries (mirrors LLMManager pattern)
        self._stt_providers: dict[str, STTPort] = stt_providers or {}
        self._tts_providers: dict[str, TTSPort] = tts_providers or {}
        self._wake_word_providers: dict[str, WakeWordPort] = wake_word_providers or {}

        self._active_stt_provider_name = active_stt_provider_name
        self._active_tts_provider_name = active_tts_provider_name
        self._active_wake_word_provider_name = active_wake_word_provider_name

        self._stt_fallback_chain = stt_fallback_chain or ("faster-whisper", "whisper")
        self._tts_fallback_chain = tts_fallback_chain or ("piper", "coqui", "elevenlabs")

        # Resolve active providers
        self._active_stt_provider = self._resolve_provider(
            self._stt_providers,
            self._active_stt_provider_name,
            self._stt_fallback_chain,
        )
        self._active_tts_provider = self._resolve_provider(
            self._tts_providers,
            self._active_tts_provider_name,
            self._tts_fallback_chain,
        )
        self._active_wake_word_provider = self._resolve_provider(
            self._wake_word_providers,
            self._active_wake_word_provider_name,
            (),
        )

        # Legacy adapter support (backward compat)
        self._legacy_adapter = adapter or LocalVoiceAdapter(logger=logger)

        # Internal components
        self._stt = SpeechToText(logger=logger)
        self._tts = TextToSpeech(logger=logger)
        self._wake_word = WakeWord(logger=logger)
        self._audio_recorder = AudioRecorder(logger=logger)
        self._audio_player = AudioPlayer(logger=logger)

        # Import VoiceExecutor here to avoid circular dependency at module level
        from backend.modules.voice._executor import VoiceExecutor

        # Create VoiceExecutor for backward compatibility
        self._executor = VoiceExecutor(
            adapter=self._legacy_adapter,
            default_timeout=default_timeout,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # Backward compatibility properties
    # ------------------------------------------------------------------

    @property
    def _adapter(self) -> VoicePort:
        """Backward compatibility property for _adapter.

        Returns the legacy adapter to maintain compatibility with existing code.
        """
        return self._legacy_adapter

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the voice module.

        Registers the ``voice`` capability and system tools for
        STT, TTS, wake-word detection, recording, and playback.
        """
        self._register_capability()
        self._register_tools()

        # Log provider status
        stt_status = self._log_provider_status("STT", self._stt_providers, self._active_stt_provider_name, self._stt_fallback_chain)
        tts_status = self._log_provider_status("TTS", self._tts_providers, self._active_tts_provider_name, self._tts_fallback_chain)
        ww_status = self._log_provider_status("WakeWord", self._wake_word_providers, self._active_wake_word_provider_name, ())

        self._logger.info(
            "Voice manager initialised — stt=%s tts=%s wake_word=%s",
            stt_status,
            tts_status,
            ww_status,
        )

    async def async_shutdown(self) -> None:
        """Release voice provider resources."""
        # Close all STT providers
        for name, provider in self._stt_providers.items():
            try:
                await provider.close()
            except Exception as exc:
                self._logger.warning("Error closing STT provider '%s': %s", name, exc)

        # Close all TTS providers
        for name, provider in self._tts_providers.items():
            try:
                await provider.close()
            except Exception as exc:
                self._logger.warning("Error closing TTS provider '%s': %s", name, exc)

        # Close all wake word providers
        for name, provider in self._wake_word_providers.items():
            try:
                await provider.close()
            except Exception as exc:
                self._logger.warning("Error closing wake word provider '%s': %s", name, exc)

        # Close legacy adapter
        try:
            await self._legacy_adapter.close()
        except Exception as exc:
            self._logger.warning("Error closing legacy adapter: %s", exc)

        self._degraded = False
        self._logger.info("Voice manager shut down.")

    def degrade(self) -> None:
        """Mark the module as degraded."""
        self._degraded = True
        self._logger.warning("Voice manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Provider management  (mirrors LLMManager pattern)
    # ------------------------------------------------------------------

    def register_stt_provider(self, name: str, provider: STTPort) -> None:
        """Register an STT provider under the given name."""
        self._stt_providers[name] = provider
        self._logger.debug("Registered STT provider: %s", name)

    def register_tts_provider(self, name: str, provider: TTSPort) -> None:
        """Register a TTS provider under the given name."""
        self._tts_providers[name] = provider
        self._logger.debug("Registered TTS provider: %s", name)

    def register_wake_word_provider(self, name: str, provider: WakeWordPort) -> None:
        """Register a wake word provider under the given name."""
        self._wake_word_providers[name] = provider
        self._logger.debug("Registered wake word provider: %s", name)

    @property
    def active_stt_provider_name(self) -> str | None:
        return self._active_stt_provider_name

    @property
    def active_tts_provider_name(self) -> str | None:
        return self._active_tts_provider_name

    @property
    def active_wake_word_provider_name(self) -> str | None:
        return self._active_wake_word_provider_name

    @property
    def stt_providers(self) -> dict[str, STTPort]:
        return dict(self._stt_providers)

    @property
    def tts_providers(self) -> dict[str, TTSPort]:
        return dict(self._tts_providers)

    @property
    def wake_word_providers(self) -> dict[str, WakeWordPort]:
        return dict(self._wake_word_providers)

    @property
    def stt_fallback_chain(self) -> tuple[str, ...]:
        return self._stt_fallback_chain

    @property
    def tts_fallback_chain(self) -> tuple[str, ...]:
        return self._tts_fallback_chain

    def get_health_report(self) -> dict[str, Any]:
        """Return production health information.

        Returns
        -------
        dict[str, Any]
            Health report with keys:
            - active_stt_provider — name of active STT provider
            - active_tts_provider — name of active TTS provider
            - active_wake_word_provider — name of active wake word provider
            - stt_providers — list of registered STT providers
            - tts_providers — list of registered TTS providers
            - wake_word_providers — list of registered wake word providers
            - stt_fallback_chain — ordered STT fallback chain
            - tts_fallback_chain — ordered TTS fallback chain
            - degraded — whether the module is degraded
            - available_stt_providers — list of available STT providers
            - available_tts_providers — list of available TTS providers
            - available_wake_word_providers — list of available wake word providers
        """
        available_stt = [name for name, p in self._stt_providers.items() if p.is_available]
        available_tts = [name for name, p in self._tts_providers.items() if p.is_available]
        available_ww = [name for name, p in self._wake_word_providers.items() if p.is_available]

        return {
            "active_stt_provider": self._active_stt_provider_name,
            "active_tts_provider": self._active_tts_provider_name,
            "active_wake_word_provider": self._active_wake_word_provider_name,
            "stt_providers": list(self._stt_providers.keys()),
            "tts_providers": list(self._tts_providers.keys()),
            "wake_word_providers": list(self._wake_word_providers.keys()),
            "stt_fallback_chain": list(self._stt_fallback_chain),
            "tts_fallback_chain": list(self._tts_fallback_chain),
            "degraded": self._degraded,
            "available_stt_providers": available_stt,
            "available_tts_providers": available_tts,
            "available_wake_word_providers": available_ww,
        }

    def _resolve_provider(
        self,
        providers: dict[str, Any],
        active_name: str | None,
        fallback_chain: tuple[str, ...],
    ) -> Any | None:
        """Resolve the active provider from a registry.

        Walks the fallback chain to find an available provider if the
        active provider is unavailable.
        """
        if active_name and active_name in providers:
            provider = providers[active_name]
            if provider.is_available:
                return provider

        # Walk fallback chain
        for name in fallback_chain:
            provider = providers.get(name)
            if provider is not None and provider.is_available:
                self._logger.info("Fallback provider selected: %s", name)
                return provider

        return None

    def _log_provider_status(
        self,
        category: str,
        providers: dict[str, Any],
        active_name: str | None,
        fallback_chain: tuple[str, ...],
    ) -> str:
        """Log provider status and return summary string."""
        if not providers:
            return "none"

        available = [name for name, p in providers.items() if p.is_available]
        unavailable = [name for name, p in providers.items() if not p.is_available]

        status = f"{len(available)}/{len(providers)} available"

        if available:
            self._logger.info(
                "[BOOT]   %s — active=%s fallback=%s available=%s",
                category,
                active_name or "none",
                fallback_chain,
                available,
            )
        else:
            self._logger.warning(
                "[BOOT]   %s — no providers available (registered=%s unavailable=%s)",
                category,
                list(providers.keys()),
                unavailable,
            )

        return status

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio: AudioData,
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Transcribe speech audio to text using the STT fallback chain.

        Falls back to legacy adapter (VoiceExecutor) if no providers available.

        Parameters
        ----------
        audio : AudioData
            The audio data to transcribe.
        language : str
            Expected language hint.
        timeout : float | None
            Per-operation timeout (defaults to module default).

        Returns
        -------
        ToolResult
            The transcription result.
        """
        self._ensure_not_degraded()
        await self._emit_event_async("voice.transcribe_start", {
            "language": language,
        })

        # If no STT providers, fall back to legacy adapter path
        if not self._stt_providers:
            result = await self._executor.transcribe(audio, language=language, timeout=timeout)
            await self._emit_event_async("voice.transcribe_complete", {
                "status": result.status,
            })
            return result

        effective_timeout = timeout if timeout is not None else self._default_timeout

        # Try STT providers in fallback chain order
        errors: dict[str, Exception] = {}
        for provider_name in self._stt_fallback_chain:
            provider = self._stt_providers.get(provider_name)
            if provider is None or not provider.is_available:
                continue

            try:
                result = await provider.transcribe(
                    audio,
                    language=language,
                    timeout=effective_timeout,
                )

                if result.text:
                    await self._emit_event_async("voice.transcribe_complete", {
                        "status": "success",
                        "provider": provider_name,
                    })
                    return ToolResult(
                        status="success",
                        output=result.text,
                    )

            except Exception as exc:
                errors[provider_name] = exc
                self._logger.warning(
                    "STT provider '%s' failed (%s), %d provider(s) remaining in chain",
                    provider_name,
                    type(exc).__name__,
                    len(self._stt_fallback_chain) - len(errors),
                )
                continue

        # All providers failed
        await self._emit_event_async("voice.transcribe_complete", {
            "status": "error",
        })

        if errors:
            error_summary = "; ".join(f"{k}: {v}" for k, v in errors.items())
            return ToolResult(
                status="error",
                error=f"All STT providers failed: {error_summary}",
            )

        return ToolResult(
            status="error",
            error="No STT providers available",
        )

    async def synthesize(
        self,
        text: str,
        voice_id: str = "",
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Synthesise speech from text using the TTS fallback chain.

        Falls back to legacy adapter (VoiceExecutor) if no providers available.

        Parameters
        ----------
        text : str
            Text to synthesise.
        voice_id : str
            Desired voice identifier.
        language : str
            Language code for synthesis.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            The synthesis result.
        """
        self._ensure_not_degraded()
        await self._emit_event_async("voice.synthesize_start", {
            "text": text[:100], "voice_id": voice_id, "language": language,
        })

        # If no TTS providers, fall back to legacy adapter path
        if not self._tts_providers:
            result = await self._executor.synthesize(
                text, voice_id=voice_id, language=language, timeout=timeout,
            )
            await self._emit_event_async("voice.synthesize_complete", {
                "status": result.status,
            })
            return result

        effective_timeout = timeout if timeout is not None else self._default_timeout

        # Try TTS providers in fallback chain order
        errors: dict[str, Exception] = {}
        for provider_name in self._tts_fallback_chain:
            provider = self._tts_providers.get(provider_name)
            if provider is None or not provider.is_available:
                continue

            try:
                result = await provider.synthesize(
                    text,
                    voice_id=voice_id,
                    language=language,
                    timeout=effective_timeout,
                )

                if result.audio is not None and result.audio.data:
                    await self._emit_event_async("voice.synthesize_complete", {
                        "status": "success",
                        "provider": provider_name,
                    })
                    voice_label = result.voice_id or "default"
                    return ToolResult(
                        status="success",
                        output=f"Speech synthesised — {result.duration_ms:.0f}ms, voice: {voice_label}, provider: {provider_name}",
                    )

            except Exception as exc:
                errors[provider_name] = exc
                self._logger.warning(
                    "TTS provider '%s' failed (%s), %d provider(s) remaining in chain",
                    provider_name,
                    type(exc).__name__,
                    len(self._tts_fallback_chain) - len(errors),
                )
                continue

        # All providers failed
        await self._emit_event_async("voice.synthesize_complete", {
            "status": "error",
        })

        if errors:
            error_summary = "; ".join(f"{k}: {v}" for k, v in errors.items())
            return ToolResult(
                status="error",
                error=f"All TTS providers failed: {error_summary}",
            )

        return ToolResult(
            status="error",
            error="No TTS providers available",
        )

    async def detect_wake_word(
        self,
        audio: AudioData,
        wake_word: str = "",
        timeout: float | None = None,
    ) -> ToolResult:
        """Detect a wake word in audio.

        Falls back to legacy adapter (VoiceExecutor) if no providers available.

        Parameters
        ----------
        audio : AudioData
            The audio data to analyse.
        wake_word : str
            Specific wake word to detect.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            The detection result.
        """
        self._ensure_not_degraded()
        await self._emit_event_async("voice.wake_word_start", {
            "wake_word": wake_word or "any",
        })

        # If no wake word providers, fall back to legacy adapter path
        if not self._wake_word_providers:
            result = await self._executor.detect_wake_word(
                audio, wake_word=wake_word, timeout=timeout,
            )
            await self._emit_event_async("voice.wake_word_complete", {
                "status": result.status,
            })
            return result

        effective_timeout = timeout if timeout is not None else self._default_timeout

        # Use active wake word provider (no fallback chain for wake word)
        if self._active_wake_word_provider is None:
            await self._emit_event_async("voice.wake_word_complete", {
                "status": "error",
            })
            return ToolResult(
                status="error",
                error="No wake word provider available",
            )

        try:
            result = await self._active_wake_word_provider.detect_wake_word(
                audio,
                wake_word=wake_word,
                timeout=effective_timeout,
            )

            if result.detected:
                await self._emit_event_async("voice.wake_word_complete", {
                    "status": "success",
                })
                ww = result.wake_word
                return ToolResult(
                    status="success",
                    output=f"Wake word '{ww}' detected (confidence: {result.confidence:.2f})",
                )

            await self._emit_event_async("voice.wake_word_complete", {
                "status": "success",
            })
            return ToolResult(
                status="success",
                output="Wake word not detected",
            )

        except Exception as exc:
            self._logger.warning("Wake word detection failed: %s", exc)
            await self._emit_event_async("voice.wake_word_complete", {
                "status": "error",
            })
            return ToolResult(
                status="error",
                error=f"Wake word detection failed: {exc}",
            )

    async def start_recording(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        """Start recording audio from the microphone.

        Uses the legacy adapter for audio I/O (backward compat).

        Parameters
        ----------
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            The recording result.
        """
        self._ensure_not_degraded()
        await self._emit_event_async("voice.recording_start", {})

        effective_timeout = timeout if timeout is not None else self._default_timeout

        try:
            audio = await self._legacy_adapter.start_recording(timeout=effective_timeout)
            await self._emit_event_async("voice.recording_complete", {
                "status": "success",
            })
            return ToolResult(
                status="success",
                output=f"Audio recorded — {audio.duration_ms:.0f}ms, {audio.sample_rate}Hz",
            )
        except VoiceNotImplementedError:
            await self._emit_event_async("voice.recording_complete", {
                "status": "error",
            })
            return ToolResult(
                status="error",
                error="Voice adapter not configured — no microphone driver available",
            )
        except Exception as exc:
            self._logger.warning("Recording failed: %s", exc)
            await self._emit_event_async("voice.recording_complete", {
                "status": "error",
            })
            return ToolResult(
                status="error",
                error=f"Recording failed: {exc}",
            )

    async def play_audio(
        self,
        audio: AudioData,
        timeout: float | None = None,
    ) -> ToolResult:
        """Play audio data through speakers.

        Uses the legacy adapter for audio I/O (backward compat).

        Parameters
        ----------
        audio : AudioData
            Audio data to play.
        timeout : float | None
            Per-operation timeout.

        Returns
        -------
        ToolResult
            The playback result.
        """
        self._ensure_not_degraded()
        await self._emit_event_async("voice.play_audio_start", {})

        effective_timeout = timeout if timeout is not None else self._default_timeout

        try:
            await self._legacy_adapter.play_audio(audio, timeout=effective_timeout)
            await self._emit_event_async("voice.play_audio_complete", {
                "status": "success",
            })
            return ToolResult(status="success", output="Audio played successfully")
        except VoiceNotImplementedError:
            await self._emit_event_async("voice.play_audio_complete", {
                "status": "error",
            })
            return ToolResult(
                status="error",
                error="Voice adapter not configured — no audio playback driver available",
            )
        except Exception as exc:
            self._logger.warning("Audio playback failed: %s", exc)
            await self._emit_event_async("voice.play_audio_complete", {
                "status": "error",
            })
            return ToolResult(
                status="error",
                error=f"Audio playback failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Return ``True`` if at least one voice provider is available.

        Falls back to checking the legacy adapter if no providers registered.
        """
        # If no providers registered, check legacy adapter
        if not self._stt_providers and not self._tts_providers:
            return self._executor.is_available

        # Otherwise check if any provider is available
        has_stt = any(p.is_available for p in self._stt_providers.values())
        has_tts = any(p.is_available for p in self._tts_providers.values())
        return has_stt or has_tts

    @property
    def stt(self) -> SpeechToText:
        """Expose the STT placeholder."""
        return self._stt

    @property
    def tts(self) -> TextToSpeech:
        """Expose the TTS placeholder."""
        return self._tts

    @property
    def wake_word(self) -> WakeWord:
        """Expose the wake-word detector."""
        return self._wake_word

    @property
    def interrupt_event(self) -> Any:
        """Expose the global audio interrupt event."""
        return audio_interrupt_event

    def interrupt(self) -> None:
        """Trigger immediate audio playback interruption (barge-in)."""
        audio_interrupt_event.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_capability(self) -> None:
        """Register the ``voice`` capability if a manager is available."""
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register", None)
            if register_cap is not None:
                from backend.modules.capability.capability import Capability
                register_cap(Capability(
                    name="voice",
                    version="0.1.0",
                    dependencies=("llm",),
                ))

    def _register_tools(self) -> None:
        """Register voice tools with the ToolManager."""
        if self._tool_manager is not None:
            register = getattr(self._tool_manager, "register_tool", None)
            if register is not None:
                from backend.modules.tools import ToolDefinition

                register(
                    ToolDefinition(
                        name="voice_transcribe",
                        description="Transcribe speech audio to text",
                        parameters={
                            "type": "object",
                            "properties": {
                                "audio_source": {
                                    "type": "string",
                                    "description": "File path or URL of the audio file",
                                },
                                "language": {
                                    "type": "string",
                                    "description": "Language hint (default 'en')",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["audio_source"],
                        },
                        category="voice",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_transcribe_tool,
                )

                register(
                    ToolDefinition(
                        name="voice_synthesize",
                        description="Synthesise speech from text",
                        parameters={
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Text to synthesise",
                                },
                                "voice_id": {
                                    "type": "string",
                                    "description": "Voice identifier (empty = default)",
                                },
                                "language": {
                                    "type": "string",
                                    "description": "Language code (default 'en')",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["text"],
                        },
                        category="voice",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_synthesize_tool,
                )

                register(
                    ToolDefinition(
                        name="voice_detect_wake_word",
                        description="Detect a wake word in audio",
                        parameters={
                            "type": "object",
                            "properties": {
                                "audio_source": {
                                    "type": "string",
                                    "description": "File path or URL of the audio file",
                                },
                                "wake_word": {
                                    "type": "string",
                                    "description": "Wake word to detect (empty = any)",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["audio_source"],
                        },
                        category="voice",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_detect_wake_word_tool,
                )

                register(
                    ToolDefinition(
                        name="voice_record",
                        description="Record audio from the microphone",
                        parameters={
                            "type": "object",
                            "properties": {
                                "duration": {
                                    "type": "number",
                                    "description": "Recording duration in seconds",
                                },
                            },
                            "required": [],
                        },
                        category="voice",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_record_tool,
                )

    async def _handle_transcribe_tool(
        self,
        audio_source: str,
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Tool handler for ``voice_transcribe``."""
        audio = AudioData(source_type="file", source_path=audio_source)
        return await self.transcribe(audio, language=language, timeout=timeout)

    async def _handle_synthesize_tool(
        self,
        text: str,
        voice_id: str = "",
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Tool handler for ``voice_synthesize``."""
        return await self.synthesize(text, voice_id=voice_id, language=language, timeout=timeout)

    async def _handle_detect_wake_word_tool(
        self,
        audio_source: str,
        wake_word: str = "",
        timeout: float | None = None,
    ) -> ToolResult:
        """Tool handler for ``voice_detect_wake_word``."""
        audio = AudioData(source_type="file", source_path=audio_source)
        return await self.detect_wake_word(audio, wake_word=wake_word, timeout=timeout)

    async def _handle_record_tool(
        self,
        duration: float | None = None,
    ) -> ToolResult:
        """Tool handler for ``voice_record``."""
        return await self.start_recording(timeout=duration)

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "VoiceManager is degraded",
                context={"module": "voice"},
            )

    def _emit_event_sync(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event from a synchronous context."""
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(event_type, data))
            except RuntimeError:
                self._logger.debug("No running loop — event not emitted: %s", event_type)

    async def _emit_event_async(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event from an async context."""
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)
