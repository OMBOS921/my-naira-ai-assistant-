"""
Unit tests for the Reasoning Gateway module.

Tests the 10 evaluation criteria, decision objects, routing policy rules,
lifecycle management, degradation behavior, and performance overhead.
"""

from __future__ import annotations

import asyncio
import time
import uuid
import pytest

from backend.modules.reasoning_gateway import (
    IntentCategory,
    ReasoningGateway,
    ReasoningGatewayDecision,
)
from backend.runtime._runtime_manager import RuntimeManager
from backend.types import UserRequest, UserResponse


class DummyMemoryManager:
    """Mock memory manager for testing memory lookup evaluation."""

    def search(self, query: str) -> str | None:
        if "favorite" in query or "name" in query:
            return "User favorite color is Blue; User name is Alice."
        return None


class DummyToolManager:
    """Mock tool manager for testing tool requirement evaluation."""

    def has_tool_for(self, request: str) -> bool:
        return "python script" in request or "calculator" in request


@pytest.fixture
def reasoning_gateway() -> ReasoningGateway:
    """Fixture providing an initialized ReasoningGateway instance."""
    memory_mgr = DummyMemoryManager()
    tool_mgr = DummyToolManager()
    return ReasoningGateway(memory_manager=memory_mgr, tool_manager=tool_mgr)


# ---------------------------------------------------------------------------
# 1. Module Lifecycle & Protocol Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateway_lifecycle(reasoning_gateway: ReasoningGateway) -> None:
    """Test async_init, async_shutdown, and degrade state properties."""
    assert not reasoning_gateway.initialized
    assert not reasoning_gateway.degraded

    await reasoning_gateway.async_init()
    assert reasoning_gateway.initialized

    reasoning_gateway.degrade()
    assert reasoning_gateway.degraded

    # When degraded, evaluate should safely default to requiring LLM
    decision = reasoning_gateway.evaluate("Hello")
    assert decision.llm_required is True
    assert "degraded" in decision.reasoning.lower()

    await reasoning_gateway.async_shutdown()
    assert not reasoning_gateway.initialized
    assert not reasoning_gateway.degraded


# ---------------------------------------------------------------------------
# 2. Evaluation of 10 Routing Criteria
# ---------------------------------------------------------------------------


def test_evaluator_greeting(reasoning_gateway: ReasoningGateway) -> None:
    """Test GREETING category classification and LLM bypass."""
    for text in ["hi", "hello", "good morning", "hey naira"]:
        decision = reasoning_gateway.evaluate(text)
        assert decision.category == IntentCategory.GREETING
        assert decision.llm_required is False
        assert decision.complexity_score < 20


def test_evaluator_local_capability(reasoning_gateway: ReasoningGateway) -> None:
    """Test LOCAL_CAPABILITY category classification."""
    decision = reasoning_gateway.evaluate("what time is it")
    assert decision.category == IntentCategory.LOCAL_CAPABILITY
    assert decision.local_capability_available is True
    assert decision.llm_required is False


def test_evaluator_clarification(reasoning_gateway: ReasoningGateway) -> None:
    """Test CLARIFICATION requirement for ambiguous single-word commands."""
    for text in ["do it", "run", "open", "delete!"]:
        decision = reasoning_gateway.evaluate(text)
        assert decision.clarification_required is True
        assert decision.ambiguity_level >= 0.7
        assert decision.llm_required is False


def test_evaluator_memory_recall(reasoning_gateway: ReasoningGateway) -> None:
    """Test MEMORY_RECALL category and memory_lookup routing rule."""
    decision = reasoning_gateway.evaluate("what is my favorite color?")
    assert decision.category == IntentCategory.MEMORY_RECALL
    assert decision.memory_available is True
    assert decision.memory_lookup is True
    assert decision.llm_required is False


def test_evaluator_web_search(reasoning_gateway: ReasoningGateway) -> None:
    """Test WEB_SEARCH category and web_search_only routing rule."""
    decision = reasoning_gateway.evaluate("what is the weather in Lagos?")
    assert decision.category == IntentCategory.WEB_SEARCH
    assert decision.web_search_sufficient is True
    assert decision.web_search_only is True
    assert decision.llm_required is False


def test_evaluator_coding(reasoning_gateway: ReasoningGateway) -> None:
    """Test CODING category requiring genuine LLM reasoning."""
    decision = reasoning_gateway.evaluate("def calculate_fibonacci(n: int) -> int: return n if n <= 1 else calculate_fibonacci(n-1) + calculate_fibonacci(n-2)")
    assert decision.category == IntentCategory.CODING
    assert decision.llm_required is True
    assert decision.complexity_score > 30


def test_evaluator_planning(reasoning_gateway: ReasoningGateway) -> None:
    """Test PLANNING requirement classification."""
    decision = reasoning_gateway.evaluate("build an app with multi-step plan first do X then do Y")
    assert decision.category == IntentCategory.PLANNING
    assert decision.planning_required is True
    assert decision.llm_required is True


def test_evaluator_creative_writing(reasoning_gateway: ReasoningGateway) -> None:
    """Test CREATIVE_WRITING category classification."""
    decision = reasoning_gateway.evaluate("write a poem about space exploration")
    assert decision.category == IntentCategory.CREATIVE_WRITING
    assert decision.creativity_required is True
    assert decision.llm_required is True


def test_evaluator_complex_analysis(reasoning_gateway: ReasoningGateway) -> None:
    """Test COMPLEX_ANALYSIS category classification."""
    decision = reasoning_gateway.evaluate("compare and contrast microservices and monolithic architectures")
    assert decision.category == IntentCategory.COMPLEX_ANALYSIS
    assert decision.complexity_score >= 50
    assert decision.llm_required is True


# ---------------------------------------------------------------------------
# 3. Performance Benchmark Test
# ---------------------------------------------------------------------------


def test_gateway_performance_overhead(reasoning_gateway: ReasoningGateway) -> None:
    """Benchmark ReasoningGateway evaluation speed (< 5ms overhead per call)."""
    prompts = [
        "hi",
        "what is my name?",
        "weather in Abuja",
        "def hello(): pass",
        "do it",
        "compare Python and Rust performance",
    ]
    start = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        for p in prompts:
            reasoning_gateway.evaluate(p)
    total_elapsed_ms = (time.perf_counter() - start) * 1000.0
    avg_latency_ms = total_elapsed_ms / (iterations * len(prompts))

    assert avg_latency_ms < 5.0, f"Average gateway evaluation latency ({avg_latency_ms:.3f}ms) exceeds 5ms threshold"


# ---------------------------------------------------------------------------
# 4. RuntimeManager Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_manager_gateway_integration() -> None:
    """Test RuntimeManager integration with Reasoning Gateway."""
    gateway = ReasoningGateway(memory_manager=DummyMemoryManager())
    runtime = RuntimeManager(reasoning_gateway=gateway)
    await runtime.async_init()

    # Test request that ReasoningGateway bypasses (Greeting)
    req_greeting = UserRequest(
        id=uuid.uuid4(),
        source="cli",
        text="hello",
        session_id="test_sess",
        timestamp=time.time(),
    )
    resp_greeting = await runtime.process_request(req_greeting)
    assert isinstance(resp_greeting, UserResponse)
    assert "Hello" in resp_greeting.text

    # Test request that ReasoningGateway bypasses (Ambiguous clarification)
    req_ambiguous = UserRequest(
        id=uuid.uuid4(),
        source="cli",
        text="do it",
        session_id="test_sess",
        timestamp=time.time(),
    )
    resp_ambiguous = await runtime.process_request(req_ambiguous)
    assert "User Clarification Required" in resp_ambiguous.text
