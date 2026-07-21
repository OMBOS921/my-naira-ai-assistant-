"""
Production-grade asynchronous publish/subscribe Event Bus.

04_Architecture.md §3.B — Event Bus.
07_Module_Design.md §2.A.

Provides channels, priorities, wildcards, filtering, replay,
backpressure, metrics, and graceful shutdown — all thread-safe
and asyncio-safe.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from fnmatch import fnmatch as _fnmatch
from typing import Any, Callable, Coroutine, Literal

from backend.types import Event, EventPriority

type _SubscriberCallback = Callable[[Event], Coroutine[Any, Any, None]]
type _EventFilter = Callable[[Event], bool]

_MAX_QUEUE_SIZE: int = 1000
_MAX_HISTORY: int = 1000
_SUBSCRIBER_TIMEOUT: float = 30.0


def _has_wildcard(pattern: str) -> bool:
    """Return ``True`` if *pattern* contains fnmatch wildcard characters."""
    return "*" in pattern or "?" in pattern or "[" in pattern


@dataclass
class _SubscriberEntry:
    """Internal subscriber record."""

    callback: _SubscriberCallback
    priority: int = 0
    filters: list[_EventFilter] | None = None
    one_time: bool = False
    description: str = ""


@dataclass
class _QueuedEvent:
    """An event waiting in the dispatch queue."""

    event: Event
    awaitable_future: asyncio.Future[None] | None = None


class EventBus:
    """In-memory asynchronous pub/sub event bus.

    Full channel subscription, priority queues, backpressure,
    event history, and replay.  Backward-compatible with the
    Phase-1 placeholder API.

    Parameters
    ----------
    max_queue_size:
        Maximum number of events in the internal queue before
    overflow_policy:
        ``"drop_newest"`` — silently drops the incoming event.
        ``"drop_oldest"`` — removes the oldest queued event.
        ``"block"`` — awaits until space is available.
    max_history:
        Maximum number of past events retained for replay.
    default_subscriber_timeout:
        Maximum wall-clock seconds a single subscriber may run.
    """

    def __init__(
        self,
        max_queue_size: int = _MAX_QUEUE_SIZE,
        overflow_policy: Literal["drop_newest", "drop_oldest", "block"] = "block",
        max_history: int = _MAX_HISTORY,
        default_subscriber_timeout: float = _SUBSCRIBER_TIMEOUT,
    ) -> None:
        self._logger = logging.getLogger("naira.event_bus")

        self._max_queue_size = max_queue_size
        self._overflow_policy = overflow_policy
        self._max_history = max_history
        self._default_subscriber_timeout = default_subscriber_timeout

        self._subscribers: dict[str, list[_SubscriberEntry]] = {}
        self._wildcard_subscribers: list[tuple[str, _SubscriberEntry]] = []
        self._history: deque[Event] = deque(maxlen=max_history)
        self._queue: asyncio.Queue[_QueuedEvent] | None = None

        self._shutdown_event = asyncio.Event()
        self._registry_lock = threading.RLock()
        self._worker_task: asyncio.Task[None] | None = None
        self._worker_started = False

        # Metrics
        self._total_events = 0
        self._failed_events = 0
        self._dropped_events = 0
        self._subscriber_execution_times: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_worker(self) -> None:
        if self._worker_started or self._shutdown_event.is_set():
            return
        self._worker_started = True
        self._queue = asyncio.Queue[_QueuedEvent](maxsize=self._max_queue_size)
        self._worker_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                queued = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            try:
                await self._dispatch(queued.event)
                if queued.awaitable_future is not None and not queued.awaitable_future.done():
                    queued.awaitable_future.set_result(None)
            except Exception as exc:
                self._failed_events += 1
                self._logger.exception("Event dispatch failed: %s", queued.event.type)
                if queued.awaitable_future is not None and not queued.awaitable_future.done():
                    queued.awaitable_future.set_exception(exc)

        while self._queue is not None and not self._queue.empty():
            try:
                queued = self._queue.get_nowait()
                await self._dispatch(queued.event)
                if queued.awaitable_future is not None and not queued.awaitable_future.done():
                    queued.awaitable_future.set_result(None)
            except asyncio.QueueEmpty:
                break
            except Exception as exc:
                self._failed_events += 1
                if queued.awaitable_future is not None and not queued.awaitable_future.done():
                    queued.awaitable_future.set_exception(exc)

    def _find_subscribers(self, event_type: str) -> list[_SubscriberEntry]:
        with self._registry_lock:
            subscribers: list[_SubscriberEntry] = []

            if event_type in self._subscribers:
                subscribers.extend(self._subscribers[event_type])

            for pattern, entry in self._wildcard_subscribers:
                if _fnmatch(event_type, pattern) and entry not in subscribers:
                    subscribers.append(entry)

            subscribers.sort(key=lambda e: e.priority, reverse=True)
            return subscribers

    async def _dispatch(self, event: Event) -> None:
        self._history.append(event)

        subscribers = self._find_subscribers(event.type)
        for entry in subscribers:
            if entry.filters and not all(f(event) for f in entry.filters):
                continue

            start = time.monotonic()
            try:
                await asyncio.wait_for(
                    entry.callback(event),
                    timeout=self._default_subscriber_timeout,
                )
            except asyncio.TimeoutError:
                self._failed_events += 1
                desc = entry.description or getattr(entry.callback, "__name__", "unknown")
                self._logger.warning("Subscriber '%s' timed out for '%s'", desc, event.type)
            except Exception:
                self._failed_events += 1
                desc = entry.description or getattr(entry.callback, "__name__", "unknown")
                self._logger.exception("Subscriber '%s' failed for '%s'", desc, event.type)
            else:
                elapsed = time.monotonic() - start
                key = entry.description or getattr(entry.callback, "__name__", "unknown")
                with self._registry_lock:
                    if key not in self._subscriber_execution_times:
                        self._subscriber_execution_times[key] = []
                    self._subscriber_execution_times[key].append(elapsed)

            if entry.one_time:
                self._remove_entry(event.type, entry)

    def _remove_entry(self, event_type: str, entry: _SubscriberEntry) -> None:
        with self._registry_lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    e for e in self._subscribers[event_type] if e is not entry
                ]
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]

            self._wildcard_subscribers = [
                (p, e) for p, e in self._wildcard_subscribers if e is not entry
            ]

    # ------------------------------------------------------------------
    # Public API — Subscriber management
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: str,
        callback: _SubscriberCallback,
        *,
        priority: int = 0,
        filters: list[_EventFilter] | None = None,
        one_time: bool = False,
        description: str = "",
    ) -> Callable[[], None]:
        """Register a subscriber for *event_type* (supports ``fnmatch`` wildcards).

        Returns a zero-argument callable that unsubscribes the entry.
        """
        entry = _SubscriberEntry(
            callback=callback,
            priority=priority,
            filters=filters,
            one_time=one_time,
            description=description,
        )
        with self._registry_lock:
            if _has_wildcard(event_type):
                self._wildcard_subscribers.append((event_type, entry))
            else:
                self._subscribers.setdefault(event_type, []).append(entry)

        def unsubscribe() -> None:
            self._remove_entry(event_type, entry)

        return unsubscribe

    def unsubscribe(self, event_type: str, callback: _SubscriberCallback) -> None:
        """Remove a subscriber by event type and callback identity."""
        with self._registry_lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    e for e in self._subscribers[event_type] if e.callback is not callback
                ]
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]

            self._wildcard_subscribers = [
                (p, e) for p, e in self._wildcard_subscribers if e.callback is not callback
            ]

    def subscriber_count(self, event_type: str | None = None) -> int:
        """Return the number of registered subscribers.

        If *event_type* is ``None``, returns the total across all types.
        """
        with self._registry_lock:
            if event_type is None:
                total = sum(len(subs) for subs in self._subscribers.values())
                total += len(self._wildcard_subscribers)
                return total
            count = len(self._subscribers.get(event_type, []))
            count += sum(
                1 for p, _ in self._wildcard_subscribers if _fnmatch(event_type, p)
            )
            return count

    # ------------------------------------------------------------------
    # Public API — Event publishing
    # ------------------------------------------------------------------

    async def emit(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        *,
        source: str = "",
        priority: EventPriority = "normal",
        metadata: dict[str, Any] | None = None,
        awaitable: bool = False,
    ) -> None:
        """Publish an event to the bus.

        Parameters
        ----------
        event_type:
            Dot-separated event type (e.g. ``"system.shutdown"``).
        data:
            Payload dictionary.
        source:
            Optional source identifier.
        priority:
            Event priority level.
        metadata:
            Optional arbitrary metadata attached to the event.
        awaitable:
            If ``True``, returns only after all subscribers have
            processed the event (or raised).
        """
        self._total_events += 1

        event = Event(
            id=uuid.uuid4(),
            type=event_type,
            source=source,
            data=data if data is not None else {},
            priority=priority,
            timestamp=time.time(),
            metadata=metadata if metadata is not None else {},
        )

        if self._shutdown_event.is_set():
            self._logger.debug("Event dropped (bus shut down): %s", event_type)
            self._dropped_events += 1
            return

        await self._ensure_worker()

        queued = _QueuedEvent(event=event)

        if awaitable:
            loop = asyncio.get_running_loop()
            queued.awaitable_future = loop.create_future()

        if self._overflow_policy == "block":
            await self._queue.put(queued)
        else:
            try:
                self._queue.put_nowait(queued)
            except asyncio.QueueFull:
                self._dropped_events += 1
                if self._overflow_policy == "drop_newest":
                    self._logger.warning("Queue full — dropped newest event: %s", event_type)
                    return
                if self._overflow_policy == "drop_oldest":
                    try:
                        self._queue.get_nowait()
                        self._queue.put_nowait(queued)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        self._dropped_events += 1
                    return

        if awaitable and queued.awaitable_future is not None:
            await queued.awaitable_future

    # ------------------------------------------------------------------
    # Public API — Event history & replay
    # ------------------------------------------------------------------

    def get_history(
        self,
        event_type: str | None = None,
    ) -> list[Event]:
        """Return retained event history, optionally filtered by type."""
        with self._registry_lock:
            if event_type is None:
                return list(self._history)
            return [
                e for e in self._history
                if e.type == event_type or _fnmatch(e.type, event_type)
            ]

    async def replay(
        self,
        event_type: str | None = None,
    ) -> None:
        """Re-dispatch events from history to current subscribers."""
        events = self.get_history(event_type)
        for event in events:
            await self._dispatch(event)

    # ------------------------------------------------------------------
    # Public API — Lifecycle
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully shut down the Event Bus.

        Drains the queue, cancels the background worker, and
        prevents new events from being queued.
        """
        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()

        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=10.0)
            except asyncio.TimeoutError:
                self._logger.warning("Event bus worker did not finish in time — cancelling")
                self._worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self._worker_task

        self._logger.info(
            "Event bus shut down — total=%d failed=%d dropped=%d",
            self._total_events,
            self._failed_events,
            self._dropped_events,
        )

    # ------------------------------------------------------------------
    # Public API — Metrics & health
    # ------------------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Return current metrics snapshot."""
        with self._registry_lock:
            queue_size = self._queue.qsize() if self._queue is not None else 0
            avg_times = {
                name: (sum(times) / len(times)) if times else 0.0
                for name, times in self._subscriber_execution_times.items()
            }
            return {
                "total_events": self._total_events,
                "failed_events": self._failed_events,
                "dropped_events": self._dropped_events,
                "queue_size": queue_size,
                "subscriber_count": self.subscriber_count(),
                "history_size": len(self._history),
                "subscriber_avg_execution_time": avg_times,
            }

    def health(self) -> dict[str, Any]:
        """Return health status of the event bus."""
        queue_size = self._queue.qsize() if self._queue is not None else 0
        healthy = not self._shutdown_event.is_set() and queue_size < self._max_queue_size * 0.95
        return {
            "healthy": healthy,
            "shutdown": self._shutdown_event.is_set(),
            "queue_usage_pct": (
                round(queue_size / self._max_queue_size * 100, 1)
                if self._max_queue_size > 0 else 0.0
            ),
            "total_events": self._total_events,
            "failed_events": self._failed_events,
            "dropped_events": self._dropped_events,
        }
