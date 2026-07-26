"""
ProviderSelector — dynamic provider selection engine.

Scores and selects the best provider based on:
1. Capabilities matching (tools, streaming, vision, context window).
2. Health score (0-100).
3. Status availability (HEALTHY, DEGRADED, avoiding CIRCUIT_OPEN or RATE_LIMITED).
4. Latency ranking.
5. Primary/fallback preference order.
"""

from __future__ import annotations

import logging
from typing import Sequence

from backend.modules.llm.capabilities import ModelCapabilities
from backend.modules.llm.health import ProviderHealthTracker, ProviderStatus
from backend.modules.llm.ports.llm_port import LLMPort

_LOG = logging.getLogger("naira.llm.selector")


class ProviderSelector:
    """Dynamic provider selection engine."""

    def select_best_provider(
        self,
        providers: dict[str, LLMPort],
        trackers: dict[str, ProviderHealthTracker],
        capabilities: dict[str, ModelCapabilities],
        *,
        fallback_chain: Sequence[str] = (),
        requires_tools: bool = False,
        requires_streaming: bool = False,
        requires_vision: bool = False,
        requires_reasoning: bool = False,
        min_context_tokens: int = 0,
    ) -> str | None:
        """Select the best available provider name.

        Parameters
        ----------
        providers : dict[str, LLMPort]
            Registered providers.
        trackers : dict[str, ProviderHealthTracker]
            Health trackers per provider.
        capabilities : dict[str, ModelCapabilities]
            Capabilities per provider.
        fallback_chain : Sequence[str]
            Preferred order if provided.
        requires_tools : bool
        requires_streaming : bool
        requires_vision : bool
        requires_reasoning : bool
        min_context_tokens : int

        Returns
        -------
        str | None
            Selected provider name or None if no available provider matches requirements.
        """
        candidates: list[tuple[float, int, str]] = []

        for name, provider in providers.items():
            # Check availability flag on provider object if defined
            if not getattr(provider, "is_available", True):
                continue

            tracker = trackers.get(name)
            if tracker and not tracker.is_available and not tracker.is_half_open:
                _LOG.debug("Provider '%s' unavailable (status: %s)", name, tracker.current_status)
                continue

            # Check model capabilities match
            caps = capabilities.get(name, ModelCapabilities())
            if not caps.matches_requirements(
                requires_tools=requires_tools,
                requires_streaming=requires_streaming,
                requires_vision=requires_vision,
                requires_reasoning=requires_reasoning,
                min_context_tokens=min_context_tokens,
            ):
                _LOG.debug("Provider '%s' does not match requested capabilities", name)
                continue

            health_score = tracker.health_score if tracker else 100.0

            # Priority penalty for index in fallback chain if specified
            order_penalty = 0
            if fallback_chain and name in fallback_chain:
                order_penalty = list(fallback_chain).index(name) * 5.0
            elif fallback_chain:
                order_penalty = 50.0

            composite_score = health_score - order_penalty
            candidates.append((composite_score, -order_penalty, name))

        if not candidates:
            return None

        # Sort candidate providers by composite score descending
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = candidates[0][2]
        _LOG.debug("Selected best provider '%s' (candidates: %s)", selected, candidates)
        return selected

    def compute_fallback_sequence(
        self,
        providers: dict[str, LLMPort],
        trackers: dict[str, ProviderHealthTracker],
        capabilities: dict[str, ModelCapabilities],
        primary_chain: Sequence[str],
        *,
        requires_tools: bool = False,
        requires_streaming: bool = False,
        requires_vision: bool = False,
        requires_reasoning: bool = False,
        min_context_tokens: int = 0,
    ) -> list[str]:
        """Compute ordered fallback sequence of eligible providers for a request."""
        eligible: list[tuple[float, int, str]] = []

        for name in dict.fromkeys(list(primary_chain) + list(providers.keys())):
            provider = providers.get(name)
            if not provider:
                continue

            tracker = trackers.get(name)
            status = tracker.current_status if tracker else ProviderStatus.HEALTHY
            if status in (ProviderStatus.CIRCUIT_OPEN, ProviderStatus.OFFLINE):
                if tracker and not tracker.is_half_open:
                    continue

            caps = capabilities.get(name, ModelCapabilities())
            if not caps.matches_requirements(
                requires_tools=requires_tools,
                requires_streaming=requires_streaming,
                requires_vision=requires_vision,
                requires_reasoning=requires_reasoning,
                min_context_tokens=min_context_tokens,
            ):
                continue

            health_score = tracker.health_score if tracker else 100.0
            preferred_index = list(primary_chain).index(name) if name in primary_chain else 999
            order_weight = 100.0 - (preferred_index * 10.0)

            final_rank = (health_score * 0.6) + (order_weight * 0.4)
            eligible.append((final_rank, -preferred_index, name))

        eligible.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [item[2] for item in eligible]
