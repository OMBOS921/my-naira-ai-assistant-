"""
LLMProviderOrchestrator — core orchestrator and resilience layer for LLM execution.

Conforms to:
- Requirements 1-14 for LLM Provider Orchestrator & Resilience Layer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Sequence

from backend.exceptions import (
    LLMError,
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from backend.modules.llm.capabilities import ModelCapabilities
from backend.modules.llm.error_classifier import (
    ProviderErrorCategory,
    classify_provider_error,
)
from backend.modules.llm.health import (
    ProviderHealthMetrics,
    ProviderHealthTracker,
    ProviderStatus,
)
from backend.modules.llm.ports.llm_port import LLMPort
from backend.modules.llm.provider_base import RetryPolicy
from backend.modules.llm.selector import ProviderSelector
from backend.types import LLMResponse, Message, TokenUsage, ToolDef

_LOG = logging.getLogger("naira.llm.orchestrator")


class LLMProviderOrchestrator:
    """Provider Orchestrator responsible for reliable LLM execution.

    Parameters
    ----------
    providers : dict[str, LLMPort] | None
        Registered providers keyed by name.
    fallback_chain : tuple[str, ...]
        Initial default fallback chain.
    logger : logging.Logger | None
        Module logger.
    interaction_manager : Any | None
        Instance of InteractionManager for friendly error generation.
    """

    def __init__(
        self,
        *,
        providers: dict[str, LLMPort] | None = None,
        fallback_chain: tuple[str, ...] = ("gemini", "deepseek"),
        logger: logging.Logger | None = None,
        interaction_manager: Any | None = None,
    ) -> None:
        self._providers: dict[str, LLMPort] = providers or {}
        self._fallback_chain: list[str] = list(dict.fromkeys(fallback_chain))
        self._logger = logger or _LOG
        self._interaction_manager = interaction_manager

        self._trackers: dict[str, ProviderHealthTracker] = {}
        self._capabilities: dict[str, ModelCapabilities] = {}
        self._selector = ProviderSelector()

        # Initialize health trackers & capabilities for pre-registered providers
        for name, provider in self._providers.items():
            self._trackers[name] = ProviderHealthTracker(provider_name=name)
            self._capabilities[name] = getattr(provider, "capabilities", ModelCapabilities())

    # ------------------------------------------------------------------
    # 1. Registry & Capabilities Management
    # ------------------------------------------------------------------

    def register_provider(
        self,
        name: str,
        provider: LLMPort,
        capabilities: ModelCapabilities | None = None,
    ) -> None:
        """Register a new LLM provider at runtime."""
        self._providers[name] = provider
        self._trackers[name] = ProviderHealthTracker(provider_name=name)
        self._capabilities[name] = capabilities or getattr(provider, "capabilities", ModelCapabilities())
        if name not in self._fallback_chain:
            self._fallback_chain.append(name)
        self._logger.info("Orchestrator registered provider '%s'", name)

    def unregister_provider(self, name: str) -> None:
        """Unregister an LLM provider."""
        self._providers.pop(name, None)
        self._trackers.pop(name, None)
        self._capabilities.pop(name, None)
        if name in self._fallback_chain:
            self._fallback_chain.remove(name)
        self._logger.info("Orchestrator unregistered provider '%s'", name)

    def get_provider(self, name: str) -> LLMPort | None:
        """Retrieve registered provider by name."""
        return self._providers.get(name)

    @property
    def registered_providers(self) -> dict[str, LLMPort]:
        """Return snapshot of registered providers."""
        return dict(self._providers)

    # ------------------------------------------------------------------
    # Health Metrics & Reporting
    # ------------------------------------------------------------------

    def get_health_metrics(self) -> list[ProviderHealthMetrics]:
        """Expose list of ProviderHealthMetrics for all registered providers.

        Includes: provider_name, health_score, average_latency, success_rate,
        last_failure, current_status.
        """
        metrics = []
        for name in self._providers:
            tracker = self._trackers.get(name)
            if tracker:
                metrics.append(tracker.get_metrics())
            else:
                metrics.append(
                    ProviderHealthMetrics(
                        provider_name=name,
                        health_score=100.0,
                        average_latency=0.0,
                        success_rate=100.0,
                        last_failure="None",
                        current_status=ProviderStatus.HEALTHY.value,
                    )
                )
        return metrics

    # ------------------------------------------------------------------
    # Orchestrated Generation Execution
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
        *,
        preferred_provider: str | None = None,
        requires_vision: bool = False,
        requires_reasoning: bool = False,
    ) -> LLMResponse:
        """Dynamically select provider and execute request with retry & recovery.

        If all providers fail:
        - Do not expose stack traces or internal exceptions to end user.
        - Log detailed diagnostics in debug logs.
        - Return friendly response through InteractionManager.
        """
        requires_tools = bool(tools and len(tools) > 0)

        # Compute dynamic fallback chain based on request requirements & health
        chain = self._selector.compute_fallback_sequence(
            providers=self._providers,
            trackers=self._trackers,
            capabilities=self._capabilities,
            primary_chain=([preferred_provider] if preferred_provider else self._fallback_chain),
            requires_tools=requires_tools,
            requires_vision=requires_vision,
            requires_reasoning=requires_reasoning,
        )

        if not chain:
            return self._handle_total_provider_outage(
                "No registered providers match requested capabilities or all providers are offline.",
                diagnostics={"registered": list(self._providers.keys())},
            )

        errors_summary: dict[str, str] = {}

        for provider_name in chain:
            provider = self._providers.get(provider_name)
            tracker = self._trackers.get(provider_name)
            if not provider or not tracker:
                continue

            try:
                response = await self._execute_provider_with_retry(
                    provider_name=provider_name,
                    provider=provider,
                    tracker=tracker,
                    prompt=prompt,
                    context=context,
                    tools=tools,
                )
                return response

            except ProviderInvalidRequestError as exc:
                # Rule 9: NEVER retry invalid requests repeatedly! Fail immediately.
                self._logger.debug(
                    "Invalid request error on provider '%s': %s", provider_name, exc, exc_info=True
                )
                raise exc

            except Exception as exc:
                cat, _ = classify_provider_error(exc)
                errors_summary[provider_name] = f"{cat.value}: {exc}"
                self._logger.debug(
                    "Provider '%s' failed during orchestrator loop (%s): %s",
                    provider_name,
                    cat.value,
                    exc,
                    exc_info=True,
                )
                continue

        # If all providers fail:
        return self._handle_total_provider_outage(
            "All LLM providers failed to process request.",
            diagnostics={"errors": errors_summary, "chain": chain},
        )

    async def generate_stream(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens using the dynamic best provider."""
        requires_tools = bool(tools and len(tools) > 0)

        chain = self._selector.compute_fallback_sequence(
            providers=self._providers,
            trackers=self._trackers,
            capabilities=self._capabilities,
            primary_chain=self._fallback_chain,
            requires_tools=requires_tools,
            requires_streaming=True,
        )

        if not chain:
            yield "I'm having trouble connecting to AI services right now. Please try again shortly."
            return

        for provider_name in chain:
            provider = self._providers.get(provider_name)
            tracker = self._trackers.get(provider_name)
            if not provider or not tracker:
                continue

            start_t = time.monotonic()
            try:
                stream_iter = provider.generate_stream(prompt, context, tools)
                first_chunk = True
                async for chunk in stream_iter:
                    if first_chunk:
                        duration_ms = (time.monotonic() - start_t) * 1000
                        tracker.record_success(duration_ms)
                        first_chunk = False
                    yield chunk
                return
            except ProviderInvalidRequestError as exc:
                tracker.record_failure(str(exc), "INVALID_REQUEST")
                raise exc
            except Exception as exc:
                cat, _ = classify_provider_error(exc)
                tracker.record_failure(str(exc), cat.value)
                self._logger.debug("Streaming provider '%s' failed: %s", provider_name, exc, exc_info=True)
                continue

        yield "I'm currently unable to reach AI services. Please try again in a moment."

    # ------------------------------------------------------------------
    # Retry & Recovery Execution Logic
    # ------------------------------------------------------------------

    async def _execute_provider_with_retry(
        self,
        provider_name: str,
        provider: LLMPort,
        tracker: ProviderHealthTracker,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None,
    ) -> LLMResponse:
        """Execute a provider request with appropriate retries and health recording."""
        retry_policy: RetryPolicy = getattr(provider, "_retry_policy", RetryPolicy(max_retries=2))
        max_attempts = retry_policy.max_retries + 1

        for attempt in range(max_attempts):
            start_t = time.monotonic()
            try:
                response = await provider.generate(prompt, context, tools)
                duration_ms = (time.monotonic() - start_t) * 1000
                tracker.record_success(duration_ms)
                return response

            except Exception as exc:
                cat, is_retryable = classify_provider_error(exc)
                duration_ms = (time.monotonic() - start_t) * 1000

                # 9. Never retry invalid requests repeatedly!
                if cat == ProviderErrorCategory.INVALID_REQUEST:
                    tracker.record_failure(str(exc), cat.value)
                    raise ProviderInvalidRequestError(
                        f"Invalid request sent to provider '{provider_name}': {exc}",
                        context={"provider": provider_name, "error": str(exc)},
                    ) from exc

                # 10. Auth error -> do not retry on same provider, record failure, failover allowed
                if cat == ProviderErrorCategory.AUTH_ERROR:
                    tracker.record_failure(str(exc), cat.value)
                    raise ProviderAuthError(
                        f"Authentication failed for provider '{provider_name}'",
                        context={"provider": provider_name},
                    ) from exc

                tracker.record_failure(str(exc), cat.value)

                # Check if retries on this provider are exhausted or error is non-retryable
                if not is_retryable or attempt >= max_attempts - 1:
                    raise exc

                delay = min(
                    retry_policy.base_delay * (retry_policy.exponential_base ** attempt),
                    retry_policy.max_delay,
                )
                self._logger.debug(
                    "Retrying provider '%s' (attempt %d/%d) after %.2fs due to %s",
                    provider_name,
                    attempt + 1,
                    max_attempts,
                    delay,
                    cat.value,
                )
                await asyncio.sleep(delay)

        raise LLMError(f"Exhausted retries for provider '{provider_name}'")

    # ------------------------------------------------------------------
    # Friendly Outage Response (No Stack Traces)
    # ------------------------------------------------------------------

    def _handle_total_provider_outage(
        self,
        user_reason: str,
        diagnostics: dict[str, Any],
    ) -> LLMResponse:
        """Handle total provider outage cleanly.

        - Does NOT expose stack traces or internal exceptions to end user.
        - Logs detailed diagnostics only in debug logs.
        - Returns a friendly response via InteractionManager.
        """
        # Log detailed diagnostics only in debug/warning logs
        self._logger.debug("TOTAL PROVIDER OUTAGE DIAGNOSTICS: %s | details=%s", user_reason, diagnostics)

        friendly_text = "I'm having trouble connecting to AI services right now. Please try again in a moment."

        if self._interaction_manager:
            try:
                # Use InteractionManager personality profile if available
                mode = getattr(self._interaction_manager, "resolve_personality_mode", None)
                if mode:
                    p_mode = mode()
                    friendly_text = f"I'm currently offline or unable to reach AI services ({p_mode.value}). Please try again shortly."
            except Exception as exc:
                self._logger.debug("Failed getting friendly response from InteractionManager: %s", exc)

        return LLMResponse(
            text=friendly_text,
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            provider="orchestrator_outage_fallback",
            duration_ms=0.0,
        )
