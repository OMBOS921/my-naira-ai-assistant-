"""Comprehensive tests for the production EventBus (backend/eventbus.py).

Covers:
- Backward compatibility with placeholder API
- Subscriber registration / removal
- One-time subscribers
- Wildcard subscriptions
- Event filtering
- Priorities
- Async dispatch (fire-and-forget and awaitable)
- Queue overflow protection
- Backpressure handling
- Graceful shutdown
- Event history and replay
- Exception isolation
- Subscriber timeout
- Metrics and health
- Concurrency safety
"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.eventbus import EventBus
from backend.types import Event
# =========================================================================
# Backward compatibility (Phase 1 placeholder contract)
# =========================================================================


class TestBackwardCompatibility:
    """Existing tests must continue to pass unchanged."""

    @pytest.mark.asyncio
    async def test_create(self) -> None:
        bus = EventBus()
        assert bus is not None

    @pytest.mark.asyncio
    async def test_emit_no_subscribers(self) -> None:
        bus = EventBus()
        await bus.emit("test.event", {"key": "value"})

    @pytest.mark.asyncio
    async def test_shutdown_drains(self) -> None:
        bus = EventBus()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        bus = EventBus()
        await bus.shutdown()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_emit_after_shutdown(self) -> None:
        bus = EventBus()
        await bus.shutdown()
        await bus.emit("after.shutdown", {})


# =========================================================================
# Subscriber registration & removal
# =========================================================================


class TestSubscriberRegistration:
    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"msg": "hello"})
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0].type == "test.event"
        assert received[0].data == {"msg": "hello"}

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        unsub = bus.subscribe("test.event", handler)
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)
        assert len(received) == 1

        unsub()
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler_by_callback(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_subscriber_count(self) -> None:
        bus = EventBus()
        assert bus.subscriber_count() == 0

        async def h1(event: Event) -> None:
            pass

        async def h2(event: Event) -> None:
            pass

        bus.subscribe("a", h1)
        bus.subscribe("b", h2)
        assert bus.subscriber_count() == 2
        assert bus.subscriber_count("a") == 1
        assert bus.subscriber_count("c") == 0


# =========================================================================
# One-time subscribers
# =========================================================================


class TestOneTimeSubscribers:
    @pytest.mark.asyncio
    async def test_one_time_subscriber_fires_once(self) -> None:
        bus = EventBus()
        count = 0

        async def handler(event: Event) -> None:
            nonlocal count
            count += 1

        bus.subscribe("test.event", handler, one_time=True)
        await bus.emit("test.event", {})
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        assert count == 1

    @pytest.mark.asyncio
    async def test_one_time_multiple_subscribers(self) -> None:
        bus = EventBus()
        counts: list[int] = [0, 0]

        async def h1(event: Event) -> None:
            counts[0] += 1

        async def h2(event: Event) -> None:
            counts[1] += 1

        bus.subscribe("test.event", h1, one_time=True)
        bus.subscribe("test.event", h2)

        await bus.emit("test.event", {})
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        assert counts[0] == 1  # one-time
        assert counts[1] == 2  # persistent


# =========================================================================
# Wildcard subscriptions
# =========================================================================


class TestWildcardSubscriptions:
    @pytest.mark.asyncio
    async def test_wildcard_matches_multiple(self) -> None:
        bus = EventBus()
        received: list[str] = []

        async def handler(event: Event) -> None:
            received.append(event.type)

        bus.subscribe("system.*", handler)
        await bus.emit("system.shutdown", {})
        await bus.emit("system.error", {})
        await bus.emit("app.event", {})
        await asyncio.sleep(0.05)

        assert received == ["system.shutdown", "system.error"]

    @pytest.mark.asyncio
    async def test_wildcard_and_exact_both_trigger(self) -> None:
        bus = EventBus()
        received: list[str] = []

        async def wild(event: Event) -> None:
            received.append(f"wild:{event.type}")

        async def exact(event: Event) -> None:
            received.append(f"exact:{event.type}")

        bus.subscribe("system.*", wild)
        bus.subscribe("system.shutdown", exact)

        await bus.emit("system.shutdown", {})
        await asyncio.sleep(0.05)

        assert "wild:system.shutdown" in received
        assert "exact:system.shutdown" in received


# =========================================================================
# Event filtering
# =========================================================================


class TestEventFiltering:
    @pytest.mark.asyncio
    async def test_filter_accepts_matching(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe(
            "test.event",
            handler,
            filters=[lambda e: e.data.get("important") is True],
        )

        await bus.emit("test.event", {"important": True})
        await bus.emit("test.event", {"important": False})
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0].data["important"] is True

    @pytest.mark.asyncio
    async def test_multiple_filters_all_must_pass(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe(
            "test.event",
            handler,
            filters=[
                lambda e: e.data.get("a") == 1,
                lambda e: e.data.get("b") == 2,
            ],
        )

        await bus.emit("test.event", {"a": 1, "b": 2})
        await bus.emit("test.event", {"a": 1, "b": 3})
        await asyncio.sleep(0.05)

        assert len(received) == 1


# =========================================================================
# Subscriber priorities
# =========================================================================


class TestSubscriberPriorities:
    @pytest.mark.asyncio
    async def test_higher_priority_runs_first(self) -> None:
        bus = EventBus()
        order: list[str] = []

        async def low(event: Event) -> None:
            order.append("low")

        async def high(event: Event) -> None:
            order.append("high")

        bus.subscribe("test.event", low, priority=-10)
        bus.subscribe("test.event", high, priority=10)

        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        assert order == ["high", "low"]

    @pytest.mark.asyncio
    async def test_default_priority_is_zero(self) -> None:
        bus = EventBus()
        order: list[str] = []

        async def first(event: Event) -> None:
            order.append("first")

        async def second(event: Event) -> None:
            order.append("second")

        bus.subscribe("test.event", first, priority=0)
        bus.subscribe("test.event", second, priority=0)

        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        # With same priority, insertion order is preserved
        assert order == ["first", "second"]


# =========================================================================
# Async dispatch modes
# =========================================================================


class TestAsyncDispatch:
    @pytest.mark.asyncio
    async def test_fire_and_forget(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            await asyncio.sleep(0.01)
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"n": 1})
        # Returned immediately — wait a bit for the handler
        await asyncio.sleep(0.05)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_awaitable_mode(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            await asyncio.sleep(0.01)
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"n": 1}, awaitable=True)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_awaitable_multiple_subscribers(self) -> None:
        bus = EventBus()
        results: set[str] = set()

        async def h1(event: Event) -> None:
            await asyncio.sleep(0.01)
            results.add("h1")

        async def h2(event: Event) -> None:
            await asyncio.sleep(0.02)
            results.add("h2")

        bus.subscribe("test.event", h1)
        bus.subscribe("test.event", h2)

        before = time.monotonic()
        await bus.emit("test.event", {}, awaitable=True)
        elapsed = time.monotonic() - before

        assert results == {"h1", "h2"}
        assert elapsed >= 0.02  # both completed


# =========================================================================
# Queue overflow protection
# =========================================================================


class TestQueueOverflow:
    @pytest.mark.asyncio
    async def test_drop_newest_policy(self) -> None:
        bus = EventBus(
            max_queue_size=2,
            overflow_policy="drop_newest",
        )

        async def slow_handler(event: Event) -> None:
            await asyncio.sleep(0.002)

        bus.subscribe("test.event", slow_handler)

        for i in range(5):
            await bus.emit("test.event", {"i": i})

        await asyncio.sleep(0.05)
        assert bus.metrics()["dropped_events"] > 0

    @pytest.mark.asyncio
    async def test_drop_oldest_policy(self) -> None:
        bus = EventBus(
            max_queue_size=2,
            overflow_policy="drop_oldest",
        )

        async def slow_handler(event: Event) -> None:
            await asyncio.sleep(0.002)

        bus.subscribe("test.event", slow_handler)

        for i in range(5):
            await bus.emit("test.event", {"i": i})

        await asyncio.sleep(0.05)
        assert bus.metrics()["dropped_events"] > 0

    @pytest.mark.asyncio
    async def test_block_policy(self) -> None:
        bus = EventBus(
            max_queue_size=1,
            overflow_policy="block",
        )

        async def slow_handler(event: Event) -> None:
            await asyncio.sleep(0.02)

        bus.subscribe("test.event", slow_handler)

        tasks = [bus.emit("test.event", {"i": i}) for i in range(3)]
        start = time.monotonic()
        await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start

        assert elapsed >= 0.02


# =========================================================================
# Graceful shutdown
# =========================================================================


class TestGracefulShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_drains_queue(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            await asyncio.sleep(0.005)
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"i": 1})
        await bus.emit("test.event", {"i": 2})

        await bus.shutdown()
        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_no_new_events_after_shutdown(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.shutdown()
        await bus.emit("test.event", {})
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_double_shutdown_does_not_raise(self) -> None:
        bus = EventBus()
        await bus.shutdown()
        await bus.shutdown()


# =========================================================================
# Event history & replay
# =========================================================================


class TestEventHistory:
    @pytest.mark.asyncio
    async def test_history_retains_events(self) -> None:
        bus = EventBus(max_history=10)
        async def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"i": 1})
        await bus.emit("test.event", {"i": 2})
        await asyncio.sleep(0.05)

        history = bus.get_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_history_maxlen(self) -> None:
        bus = EventBus(max_history=3)
        async def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)
        for i in range(10):
            await bus.emit("test.event", {"i": i})
        await asyncio.sleep(0.05)

        assert len(bus.get_history()) == 3

    @pytest.mark.asyncio
    async def test_history_filtered_by_type(self) -> None:
        bus = EventBus()
        async def handler(event: Event) -> None:
            pass

        bus.subscribe("*", handler)
        await bus.emit("a.b", {})
        await bus.emit("x.y", {})
        await asyncio.sleep(0.05)

        assert len(bus.get_history("a.b")) == 1
        assert len(bus.get_history("a.*")) == 1

    @pytest.mark.asyncio
    async def test_replay_dispatches_to_current_subscribers(self) -> None:
        bus = EventBus()
        async def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"i": 1})
        await bus.emit("test.event", {"i": 2})
        await asyncio.sleep(0.05)

        received: list[Event] = []

        async def replay_handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", replay_handler)
        await bus.replay("test.event")
        await asyncio.sleep(0.05)

        assert len(received) == 2


# =========================================================================
# Exception isolation
# =========================================================================


class TestExceptionIsolation:
    @pytest.mark.asyncio
    async def test_failing_subscriber_does_not_affect_others(self) -> None:
        bus = EventBus()
        results: list[str] = []

        async def failing(event: Event) -> None:
            msg = "oops"
            raise RuntimeError(msg)

        async def working(event: Event) -> None:
            results.append("ok")

        bus.subscribe("test.event", failing)
        bus.subscribe("test.event", working)

        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        assert results == ["ok"]
        assert bus.metrics()["failed_events"] >= 1

    @pytest.mark.asyncio
    async def test_exception_increases_failed_counter(self) -> None:
        bus = EventBus()

        async def failing(event: Event) -> None:
            msg = "oops"
            raise RuntimeError(msg)

        bus.subscribe("test.event", failing)
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        assert bus.metrics()["failed_events"] >= 1


# =========================================================================
# Subscriber timeout
# =========================================================================


class TestSubscriberTimeout:
    @pytest.mark.asyncio
    async def test_subscriber_timed_out(self) -> None:
        bus = EventBus(default_subscriber_timeout=0.02)
        results: list[str] = []

        async def slow(event: Event) -> None:
            await asyncio.sleep(0.1)
            results.append("done")

        async def fast(event: Event) -> None:
            results.append("fast")

        bus.subscribe("test.event", slow)
        bus.subscribe("test.event", fast)

        await bus.emit("test.event", {}, awaitable=True)

        assert "fast" in results
        assert "done" not in results
        assert bus.metrics()["failed_events"] >= 1


# =========================================================================
# Metrics
# =========================================================================


class TestMetrics:
    @pytest.mark.asyncio
    async def test_metrics_total_events(self) -> None:
        bus = EventBus()

        async def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {})
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        assert bus.metrics()["total_events"] == 2

    @pytest.mark.asyncio
    async def test_metrics_queue_size(self) -> None:
        bus = EventBus()

        async def slow(event: Event) -> None:
            await asyncio.sleep(0.1)

        bus.subscribe("test.event", slow)

        for i in range(5):
            await bus.emit("test.event", {"i": i})

        m = bus.metrics()
        assert m["queue_size"] >= 0

    @pytest.mark.asyncio
    async def test_metrics_subscriber_count(self) -> None:
        bus = EventBus()

        async def handler(event: Event) -> None:
            pass

        assert bus.metrics()["subscriber_count"] == 0
        bus.subscribe("test.event", handler)
        assert bus.metrics()["subscriber_count"] == 1


# =========================================================================
# Health
# =========================================================================


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_healthy_when_active(self) -> None:
        bus = EventBus()
        h = bus.health()
        assert h["healthy"]
        assert not h["shutdown"]

    @pytest.mark.asyncio
    async def test_health_shutdown_after_shutdown(self) -> None:
        bus = EventBus()
        await bus.shutdown()
        h = bus.health()
        assert not h["healthy"]
        assert h["shutdown"]


# =========================================================================
# Event metadata & IDs
# =========================================================================


class TestEventMetadata:
    @pytest.mark.asyncio
    async def test_event_has_unique_id(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {})
        await bus.emit("test.event", {})
        await asyncio.sleep(0.05)

        assert len(received) == 2
        assert received[0].id != received[1].id

    @pytest.mark.asyncio
    async def test_event_has_timestamp(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        before = time.time()
        await bus.emit("test.event", {})
        after = time.time()
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert before <= received[0].timestamp <= after


# =========================================================================
# Concurrency safety
# =========================================================================


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_emits(self) -> None:
        bus = EventBus(max_queue_size=20)
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        tasks = [bus.emit("test.event", {"i": i}) for i in range(5)]
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.05)

        assert len(received) == 5

    @pytest.mark.asyncio
    async def test_concurrent_subscribe_and_emit(self) -> None:
        bus = EventBus()
        results: list[str] = []

        async def handler(event: Event) -> None:
            results.append(event.data.get("msg", ""))

        async def emitter() -> None:
            for i in range(10):
                await bus.emit("test.event", {"msg": f"e{i}"})
                await asyncio.sleep(0.001)

        async def subscriber() -> None:
            for _ in range(3):
                bus.subscribe("test.event", handler)
                await asyncio.sleep(0.001)

        await asyncio.gather(emitter(), subscriber())
        await asyncio.sleep(0.1)
        assert len(results) > 0


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_emit_with_no_data(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event")
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0].data == {}

    @pytest.mark.asyncio
    async def test_subscribe_returns_callable_unsubscribe(self) -> None:
        bus = EventBus()

        async def handler(event: Event) -> None:
            pass

        unsub = bus.subscribe("test.event", handler)
        assert callable(unsub)

    @pytest.mark.asyncio
    async def test_get_history_empty_when_no_events(self) -> None:
        bus = EventBus()
        assert bus.get_history() == []
        assert bus.get_history("test.event") == []
