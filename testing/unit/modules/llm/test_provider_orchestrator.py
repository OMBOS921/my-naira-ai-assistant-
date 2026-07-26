"""
Comprehensive unit test suite for LLMProviderOrchestrator and Resilience Layer.

Covers:
1. Provider selection (capabilities & health score dynamic ranking)
2. Failover across fallback chain
3. Retry logic on transient failures
4. Health degradation (health_score drops, status becomes DEGRADED/UNHEALTHY)
5. Circuit breaker recovery (CLOSED -> OPEN -> HALF_OPEN probe success -> CLOSED)
6. Timeout handling
7. Invalid request handling (immediate raise, NO repeated retries!)
8. Total provider outage (graceful friendly response via InteractionManager, no internal stack traces exposed)
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.exceptions import (
    LLMError,
    ProviderAuthError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from backend.modules.llm.capabilities import ModelCapabilities
from backend.modules.llm.health import ProviderHealthTracker, ProviderStatus
from backend.modules.llm.orchestrator import LLMProviderOrchestrator
from backend.modules.llm.ports.llm_port import LLMPort
from backend.modules.llm.provider_base import ProviderBase, RetryPolicy
from backend.types import LLMResponse, Message, TokenUsage, ToolDef


def _make_mock_provider(
    name: str,
    *,
    response_text: str = "Success",
    side_effect: Exception | None = None,
    supports_tools: bool = True,
    supports_vision: bool = False,
    max_retries: int = 1,
) -> MagicMock:
    provider = MagicMock(spec=ProviderBase)
    provider.provider_name = name
    provider.is_available = True
    provider._retry_policy = RetryPolicy(max_retries=max_retries, base_delay=0.01)
    provider.capabilities = ModelCapabilities(
        supports_tools=supports_tools,
        supports_vision=supports_vision,
    )

    if side_effect:
        provider.generate = AsyncMock(side_effect=side_effect)
    else:
        provider.generate = AsyncMock(
            return_value=LLMResponse(
                text=response_text,
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(10, 10, 20),
                provider=name,
                duration_ms=25.0,
            )
        )
    return provider


class TestProviderSelection:
    @pytest.mark.asyncio
    async def test_dynamic_selection_by_health_and_capabilities(self) -> None:
        p1 = _make_mock_provider("p1", response_text="p1 resp", supports_tools=True)
        p2 = _make_mock_provider("p2", response_text="p2 resp", supports_tools=True)

        orchestrator = LLMProviderOrchestrator(
            providers={"p1": p1, "p2": p2},
            fallback_chain=("p1", "p2"),
        )

        res = await orchestrator.generate("test prompt", [])
        assert res.text == "p1 resp"
        assert res.provider == "p1"

    @pytest.mark.asyncio
    async def test_capability_filtering(self) -> None:
        p1_no_vision = _make_mock_provider("p1", response_text="p1 no vision", supports_vision=False)
        p2_vision = _make_mock_provider("p2", response_text="p2 vision", supports_vision=True)

        orchestrator = LLMProviderOrchestrator(
            providers={"p1": p1_no_vision, "p2": p2_vision},
            fallback_chain=("p1", "p2"),
        )

        # Request requires vision -> should select p2
        res = await orchestrator.generate("describe image", [], requires_vision=True)
        assert res.text == "p2 vision"
        assert res.provider == "p2"


class TestFailover:
    @pytest.mark.asyncio
    async def test_failover_when_primary_fails(self) -> None:
        p1_failing = _make_mock_provider(
            "p1", side_effect=LLMError("p1 primary failure")
        )
        p2_working = _make_mock_provider("p2", response_text="p2 fallback success")

        orchestrator = LLMProviderOrchestrator(
            providers={"p1": p1_failing, "p2": p2_working},
            fallback_chain=("p1", "p2"),
        )

        res = await orchestrator.generate("test", [])
        assert res.text == "p2 fallback success"
        assert res.provider == "p2"


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self) -> None:
        mock_provider = MagicMock(spec=ProviderBase)
        mock_provider.provider_name = "retry_p"
        mock_provider.is_available = True
        mock_provider._retry_policy = RetryPolicy(max_retries=2, base_delay=0.01)

        # First call fails with rate limit, second call succeeds
        mock_provider.generate = AsyncMock(
            side_effect=[
                ProviderRateLimitError("Rate limit transient"),
                LLMResponse(
                    text="Retry success",
                    tool_calls=None,
                    finish_reason="stop",
                    token_usage=TokenUsage(5, 5, 10),
                    provider="retry_p",
                    duration_ms=15.0,
                ),
            ]
        )

        orchestrator = LLMProviderOrchestrator(
            providers={"retry_p": mock_provider},
            fallback_chain=("retry_p",),
        )

        res = await orchestrator.generate("test", [])
        assert res.text == "Retry success"
        assert mock_provider.generate.await_count == 2


class TestHealthDegradationAndRecovery:
    def test_health_tracker_score_degradation(self) -> None:
        tracker = ProviderHealthTracker("test_p", failure_threshold=3)

        assert tracker.health_score == 100.0
        assert tracker.current_status == ProviderStatus.HEALTHY

        # Record failures
        tracker.record_failure("error 1", "API_ERROR")
        assert tracker.current_status == ProviderStatus.DEGRADED
        assert tracker.health_score < 100.0

        tracker.record_failure("error 2", "API_ERROR")
        tracker.record_failure("error 3", "API_ERROR")

        # 3 failures -> circuit open / unhealthy
        assert tracker.current_status in (ProviderStatus.CIRCUIT_OPEN, ProviderStatus.UNHEALTHY)
        assert tracker.health_score == 0.0

    def test_circuit_breaker_cooldown_and_recovery(self) -> None:
        tracker = ProviderHealthTracker("recovery_p", failure_threshold=2, cooldown_seconds=0.05)

        tracker.record_failure("err 1", "API_ERROR")
        tracker.record_failure("err 2", "API_ERROR")
        assert tracker.current_status == ProviderStatus.CIRCUIT_OPEN
        assert tracker.is_available is False

        # Wait for cooldown
        time.sleep(0.06)
        assert tracker.is_half_open is True

        # Successful probe resets circuit to HEALTHY
        tracker.record_success(duration_ms=10.0)
        assert tracker.current_status == ProviderStatus.HEALTHY
        assert tracker.health_score > 0.0


class TestTimeoutHandling:
    @pytest.mark.asyncio
    async def test_provider_timeout(self) -> None:
        p1_timeout = _make_mock_provider(
            "p1", side_effect=ProviderTimeoutError("Gemini timed out after 30s")
        )
        p2_ok = _make_mock_provider("p2", response_text="p2 post-timeout success")

        orchestrator = LLMProviderOrchestrator(
            providers={"p1": p1_timeout, "p2": p2_ok},
            fallback_chain=("p1", "p2"),
        )

        res = await orchestrator.generate("test timeout", [])
        assert res.text == "p2 post-timeout success"
        assert res.provider == "p2"


class TestInvalidRequestHandling:
    @pytest.mark.asyncio
    async def test_never_retry_invalid_request_repeatedly(self) -> None:
        mock_provider = _make_mock_provider(
            "p1",
            side_effect=ProviderInvalidRequestError("HTTP 400 Bad Request: Prompt invalid"),
            max_retries=3,
        )

        orchestrator = LLMProviderOrchestrator(
            providers={"p1": mock_provider},
            fallback_chain=("p1",),
        )

        # Invalid request must raise ProviderInvalidRequestError immediately without retrying 3 times!
        with pytest.raises(ProviderInvalidRequestError):
            await orchestrator.generate("bad request prompt", [])

        # Must have been called exactly ONCE (no retries!)
        assert mock_provider.generate.await_count == 1


class TestTotalProviderOutage:
    @pytest.mark.asyncio
    async def test_total_provider_outage_graceful_response(self) -> None:
        p1 = _make_mock_provider("p1", side_effect=LLMError("p1 dead"))
        p2 = _make_mock_provider("p2", side_effect=LLMError("p2 dead"))

        mock_interaction_mgr = MagicMock()
        mock_interaction_mgr.resolve_personality_mode.return_value = MagicMock(value="friendly")

        orchestrator = LLMProviderOrchestrator(
            providers={"p1": p1, "p2": p2},
            fallback_chain=("p1", "p2"),
            interaction_manager=mock_interaction_mgr,
        )

        # Generate must NOT raise raw exception or leak stack trace to caller
        res = await orchestrator.generate("test prompt", [])

        assert res is not None
        assert "unable" in res.text.lower() or "offline" in res.text.lower() or "trouble" in res.text.lower()
        # No internal error string or stack trace in text
        assert "p1 dead" not in res.text
        assert "p2 dead" not in res.text
        assert res.provider == "orchestrator_outage_fallback"

    @pytest.mark.asyncio
    async def test_health_metrics_exposure(self) -> None:
        p1 = _make_mock_provider("p1", response_text="p1 metrics ok")
        orchestrator = LLMProviderOrchestrator(
            providers={"p1": p1},
            fallback_chain=("p1",),
        )

        await orchestrator.generate("test", [])

        metrics = orchestrator.get_health_metrics()
        assert len(metrics) == 1
        m = metrics[0]
        assert m.provider_name == "p1"
        assert m.health_score == 100.0
        assert m.average_latency > 0.0
        assert m.success_rate == 100.0
        assert m.last_failure == "None"
        assert m.current_status == "HEALTHY"
