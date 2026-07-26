"""
LLMManager — the single public class for the LLM module.

21_System_Contracts.md §15 — LLM Provider Contracts (fallback chain, context
preservation, structured errors).
21_System_Contracts.md §4.2 — ModuleInterface protocol.
21_System_Contracts.md §15.4 — Fallback chain across multiple providers.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.exceptions import (
    LLMError,
    ModuleDegradedError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from backend.modules.llm.generation_config import GenerationConfig
from backend.modules.llm.orchestrator import LLMProviderOrchestrator
from backend.modules.llm.ports.llm_port import LLMPort
from backend.modules.llm.safety import SafetyConfig
from backend.types import LLMResponse, Message, ToolDef

_LOG = logging.getLogger("naira.llm")


class LLMManager:
    """Central LLM manager — owns a collection of providers and routes
    requests through a fallback chain via LLMProviderOrchestrator.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.  If ``None``, a default logger is used.
    providers : dict[str, LLMPort] | None
        Registered providers keyed by name.  If ``None``, empty dict.
    generation_config : GenerationConfig | None
        Default generation parameters.  Falls back to ``GenerationConfig()``.
    safety_config : SafetyConfig | None
        Default safety settings.  Falls back to ``SafetyConfig()``.
    active_provider : str
        Primary provider name (default ``"gemini"``).
    fallback_chain : tuple[str, ...]
        Ordered provider names to try on failure
        (default ``("gemini", "ollama", "deepseek")``).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        providers: dict[str, LLMPort] | None = None,
        generation_config: GenerationConfig | None = None,
        safety_config: SafetyConfig | None = None,
        active_provider: str = "gemini",
        fallback_chain: tuple[str, ...] = ("gemini",),
        event_bus: object | None = None,
        interaction_manager: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._providers: dict[str, LLMPort] = providers or {}
        self._generation_config = generation_config or GenerationConfig()
        self._safety_config = safety_config or SafetyConfig()
        self._active_provider_name = active_provider
        self._fallback_chain = tuple(dict.fromkeys(fallback_chain))
        self._provider_success_count: dict[str, int] = {}
        self._provider_failure_count: dict[str, int] = {}
        self._degraded: bool = False
        self._initialized: bool = False
        self._orchestrator = LLMProviderOrchestrator(
            providers=dict(self._providers),
            fallback_chain=self._fallback_chain,
            logger=self._logger,
            interaction_manager=interaction_manager,
        )

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the LLM manager.

        Validates that at least one provider is registered.  Marks
        degraded if no provider is available.
        """
        if not self._providers:
            self._logger.warning(
                "No providers registered — LLM manager initialised in degraded state"
            )
            self._degraded = True
        else:
            active = self._providers.get(self._active_provider_name)
            if active is None:
                self._logger.warning(
                    "Active provider '%s' not found — LLM manager initialised in degraded state",
                    self._active_provider_name,
                )
                self._degraded = True

        self._initialized = True
        provider_names = ", ".join(self._providers)
        provider_types = {
            k: type(v).__name__ for k, v in self._providers.items()
        }
        self._logger.info(
            "LLM manager initialised — active=%s providers=[%s] "
            "degraded=%s fallback_chain=%s provider_types=%s",
            self._active_provider_name,
            provider_names,
            self._degraded,
            self._fallback_chain,
            provider_types,
        )

    async def async_shutdown(self) -> None:
        """Release all provider references."""
        self._providers.clear()
        self._degraded = False
        self._initialized = False
        self._logger.info("LLM manager shut down.")

    def degrade(self) -> None:
        """Mark the manager as degraded and release provider references."""
        self._providers.clear()
        self._degraded = True
        self._logger.warning("LLM manager marked degraded")

    @property
    def degraded(self) -> bool:
        """Return ``True`` if the manager is in a degraded state."""
        return self._degraded

    @property
    def initialized(self) -> bool:
        """Return ``True`` after ``async_init()`` completes."""
        return self._initialized

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    @property
    def active_provider_name(self) -> str:
        """Return the name of the currently active provider."""
        return self._active_provider_name

    @property
    def fallback_chain(self) -> tuple[str, ...]:
        """Return the ordered fallback chain."""
    @property
    def orchestrator(self) -> LLMProviderOrchestrator:
        """Return the underlying provider orchestrator."""
        return self._orchestrator

    async def register_provider(self, name: str, provider: LLMPort) -> None:
        """Register a new provider at runtime.

        Can be called even in degraded mode (recovery path).

        Parameters
        ----------
        name : str
            Provider name (e.g. ``"ollama"``).
        provider : LLMPort
            Provider instance implementing ``LLMPort``.
        """
        self._providers[name] = provider
        self._orchestrator.register_provider(name, provider)
        if self._degraded and self._providers.get(self._active_provider_name):
            self._degraded = False
        self._logger.info("Provider registered: %s", name)

    def get_health_report(self) -> dict[str, Any]:
        """Return production health information.

        Returns
        -------
        dict[str, Any]
            Health report with keys:
            - active_provider — name of active provider
            - registered_providers — list of registered provider names
            - fallback_chain — ordered fallback chain
            - degraded — whether the manager is degraded
            - provider_statistics — statistics for each provider
            - available_providers — list of available providers
            - orchestrator_metrics — list of ProviderHealthMetrics from orchestrator
        """
        provider_stats = {}
        available_providers = []

        for name, provider in self._providers.items():
            # Check if provider is available
            is_available = getattr(provider, "is_available", True)
            if is_available:
                available_providers.append(name)

            # Get statistics if provider has them
            stats = getattr(provider, "statistics", None)
            if stats:
                provider_stats[name] = {
                    "total_requests": stats.total_requests,
                    "successful_requests": stats.successful_requests,
                    "failed_requests": stats.failed_requests,
                    "retry_count": stats.retry_count,
                    "total_tokens": stats.total_tokens,
                    "input_tokens": stats.input_tokens,
                    "output_tokens": stats.output_tokens,
                    "average_latency_ms": stats.average_latency_ms,
                    "success_rate": stats.success_rate,
                    "failure_rate": stats.failure_rate,
                    "estimated_cost": stats.estimated_cost,
                    "last_error": stats.last_error,
                    "is_healthy": stats.is_healthy,
                }

        provider_runtime_metrics = {
            provider_name: {
                "success_count": self._provider_success_count.get(provider_name, 0),
                "failure_count": self._provider_failure_count.get(provider_name, 0),
            }
            for provider_name in dict.fromkeys(
                list(self._providers.keys())
                + list(self._provider_success_count.keys())
                + list(self._provider_failure_count.keys())
            )
        }

        orchestrator_metrics = [
            {
                "provider_name": m.provider_name,
                "health_score": m.health_score,
                "average_latency": m.average_latency,
                "success_rate": m.success_rate,
                "last_failure": m.last_failure,
                "current_status": m.current_status,
            }
            for m in self._orchestrator.get_health_metrics()
        ]

        return {
            "active_provider": self._active_provider_name,
            "registered_providers": list(self._providers.keys()),
            "fallback_chain": list(self._fallback_chain),
            "degraded": self._degraded,
            "provider_statistics": provider_stats,
            "available_providers": available_providers,
            "provider_runtime_metrics": provider_runtime_metrics,
            "orchestrator_metrics": orchestrator_metrics,
        }

    # ------------------------------------------------------------------
    # Generation API
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        """Generate a response using LLMProviderOrchestrator."""
        self._ensure_not_degraded()

        response = await self._orchestrator.generate(
            prompt=prompt,
            context=context,
            tools=tools,
            preferred_provider=self._active_provider_name,
        )
        if response.provider:
            self._provider_success_count[response.provider] = (
                self._provider_success_count.get(response.provider, 0) + 1
            )
        return response

    async def generate_stream(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens using LLMProviderOrchestrator."""
        self._ensure_not_degraded()

        async for chunk in self._orchestrator.generate_stream(prompt, context, tools):
            yield chunk

    async def count_tokens(self, text: str) -> int:
        """Count tokens using the active provider.

        Parameters
        ----------
        text : str
            Input text.

        Returns
        -------
        int
            Estimated token count.

        Raises
        ------
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()

        provider = self._providers.get(self._active_provider_name)
        if provider is None:
            raise LLMError(
                f"Active provider '{self._active_provider_name}' not found",
                context={"module": "llm", "provider": self._active_provider_name},
            )

        return await provider.count_tokens(text)

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def generation_config(self) -> GenerationConfig:
        """Return the default generation configuration."""
        return self._generation_config

    @property
    def safety_config(self) -> SafetyConfig:
        """Return the default safety configuration."""
        return self._safety_config

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "LLMManager is degraded",
                context={"module": "llm"},
            )
