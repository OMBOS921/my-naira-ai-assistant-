"""
ProviderBase — abstract base for LLM providers with retry, timeout, and logging.

21_System_Contracts.md §15 — LLM Provider Contracts.
21_System_Contracts.md §10.6 — Timeouts for async I/O operations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from backend.exceptions import (
    LLMError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from backend.modules.llm.ports.llm_port import LLMPort
from backend.types import LLMResponse, Message, ToolDef


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for transient provider failures.

    Parameters
    ----------
    max_retries : int
        Maximum number of retry attempts (default ``3``).
    base_delay : float
        Initial back-off delay in seconds (default ``1.0``).
    max_delay : float
        Maximum back-off delay in seconds (default ``60.0``).
    exponential_base : float
        Exponential factor for back-off growth (default ``2.0``).
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0


@dataclass
class ProviderStatistics:
    """Provider statistics and health metrics.

    Tracks requests, failures, latency, tokens, and cost.
    """

    # Request tracking
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retry_count: int = 0

    # Token tracking
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    # Performance tracking
    total_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0

    # Cost tracking (USD)
    estimated_cost: float = 0.0

    # Error tracking
    last_error: str = ""
    last_error_time: float = 0.0

    # Health status
    is_healthy: bool = True
    degraded_since: float = 0.0

    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency across all successful requests."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100.0

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as a percentage."""
        return 100.0 - self.success_rate


_LOG = logging.getLogger("naira.llm.provider")


class ProviderBase(LLMPort):
    """Abstract base for LLM providers.

    Implements ``LLMPort`` with retry logic, timeout handling, and
    structured error mapping.  Subclasses must implement
    ``_call_provider()`` and ``_count_tokens_internal()``.

    Parameters
    ----------
    provider_name : str
        Human-readable name (e.g. ``"gemini"``).
    timeout : int
        Request timeout in seconds (default ``30``).
    retry_policy : RetryPolicy | None
        Retry configuration.  If ``None``, uses ``RetryPolicy()`` defaults.
    logger : logging.Logger | None
        Module-scoped logger.  If ``None``, a default logger is used.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        timeout: int = 30,
        retry_policy: RetryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy()
        self._logger = logger or _LOG
        self._statistics = ProviderStatistics()

    # ------------------------------------------------------------------
    # Provider properties
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return self._provider_name

    @property
    def is_available(self) -> bool:
        """Return True if the provider is available.

        Default implementation returns True. Subclasses can override
        to check for API keys, dependencies, etc.
        """
        return True

    @property
    def statistics(self) -> ProviderStatistics:
        """Return a copy of the provider statistics."""
        return self._statistics

    # ------------------------------------------------------------------
    # LLMPort implementation
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        """Send a request with retry logic and timeout.

        Delegates to ``_call_provider()`` (implemented by subclasses).
        Retries on rate-limit and transient errors.  Auth errors and
        timeouts are raised immediately.
        """
        return await self._generate_with_retry(prompt, context, tools)

    async def generate_stream(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        """Default streaming: wraps the non-streaming ``generate()``.

        Subclasses that support true streaming should override this.
        """
        response = await self.generate(prompt, context, tools)
        yield response.text

    async def count_tokens(self, text: str) -> int:
        """Estimate token count via the provider's API.

        Delegates to ``_count_tokens_internal()``.
        """
        return await self._count_tokens_internal(text)

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def _call_provider(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None,
    ) -> LLMResponse:
        """Execute the actual provider API call.

        This method is called inside the retry loop.  It should raise
        ``ProviderRateLimitError``, ``ProviderAuthError``, or
        ``ProviderTimeoutError`` for the retry logic to handle correctly.
        """

    @abstractmethod
    async def _count_tokens_internal(self, text: str) -> int:
        """Execute the actual token-count API call."""

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    async def _generate_with_retry(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None,
    ) -> LLMResponse:
        max_attempts = self._retry_policy.max_retries + 1
        self._statistics.total_requests += 1
        start_time = time.monotonic()

        for attempt in range(max_attempts):
            try:
                async with asyncio.timeout(self._timeout):
                    response = await self._call_provider(prompt, context, tools)

                    # Track successful request
                    duration_ms = (time.monotonic() - start_time) * 1000
                    self._statistics.successful_requests += 1
                    self._statistics.total_latency_ms += duration_ms

                    if self._statistics.min_latency_ms == 0.0 or duration_ms < self._statistics.min_latency_ms:
                        self._statistics.min_latency_ms = duration_ms
                    if duration_ms > self._statistics.max_latency_ms:
                        self._statistics.max_latency_ms = duration_ms

                    # Track tokens
                    self._statistics.total_tokens += response.token_usage.total_tokens
                    self._statistics.input_tokens += response.token_usage.prompt_tokens
                    self._statistics.output_tokens += response.token_usage.completion_tokens

                    # Mark as healthy
                    self._statistics.is_healthy = True

                    return response

            except asyncio.TimeoutError:
                self._statistics.failed_requests += 1
                self._statistics.last_error = f"Timeout after {self._timeout}s"
                self._statistics.last_error_time = time.time()
                self._statistics.is_healthy = False
                if self._statistics.degraded_since == 0.0:
                    self._statistics.degraded_since = time.time()

                raise ProviderTimeoutError(
                    f"Provider '{self._provider_name}' timed out after {self._timeout}s",
                    context={
                        "provider": self._provider_name,
                        "timeout": self._timeout,
                    },
                ) from None

            except ProviderAuthError:
                self._statistics.failed_requests += 1
                self._statistics.last_error = "Authentication error"
                self._statistics.last_error_time = time.time()
                self._statistics.is_healthy = False
                if self._statistics.degraded_since == 0.0:
                    self._statistics.degraded_since = time.time()
                raise

            except ProviderRateLimitError:
                self._statistics.retry_count += 1
                if attempt >= self._retry_policy.max_retries:
                    self._statistics.failed_requests += 1
                    self._statistics.last_error = "Rate limit exceeded"
                    self._statistics.last_error_time = time.time()
                    raise
                delay = self._compute_backoff(attempt)
                self._logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)

            except LLMError:
                self._statistics.failed_requests += 1
                self._statistics.is_healthy = False
                if self._statistics.degraded_since == 0.0:
                    self._statistics.degraded_since = time.time()
                raise

            except Exception as exc:
                self._statistics.failed_requests += 1
                self._statistics.last_error = str(exc)
                self._statistics.last_error_time = time.time()
                self._statistics.is_healthy = False
                if self._statistics.degraded_since == 0.0:
                    self._statistics.degraded_since = time.time()

                raise LLMError(
                    f"Provider '{self._provider_name}' call failed: {exc}",
                    context={
                        "provider": self._provider_name,
                        "error": str(exc),
                    },
                ) from exc

        self._statistics.failed_requests += 1
        raise ProviderRateLimitError(
            f"All {max_attempts} retry attempts for '{self._provider_name}' exhausted",
            context={
                "provider": self._provider_name,
                "max_retries": self._retry_policy.max_retries,
            },
        )

    def _compute_backoff(self, attempt: int) -> float:
        delay = self._retry_policy.base_delay * (
            self._retry_policy.exponential_base ** attempt
        )
        return min(delay, self._retry_policy.max_delay)
