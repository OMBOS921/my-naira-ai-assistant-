"""
ProactiveEventEngine — JARVIS-style proactive interruption system.

Monitors system events (battery, disk, network, time-based triggers)
and pushes proactive messages to the user without being prompted.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import platform
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Awaitable

_LOG = logging.getLogger("naira.proactive")


class Priority(StrEnum):
    """Proactive notification priority levels."""
    URGENT = "urgent"    # Immediate — interrupt anything
    NORMAL = "normal"    # Show next opportunity
    LOW = "low"          # Queue for idle time


@dataclass
class ProactiveEvent:
    """A proactive notification to push to the user."""
    message: str
    priority: Priority = Priority.NORMAL
    source: str = "system"
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ProactiveEventEngine:
    """Monitors system state and generates proactive notifications.

    Integrates with WebSocket to push JARVIS-style interruptions.
    """

    def __init__(
        self,
        push_callback: Callable[[ProactiveEvent], Awaitable[None]] | None = None,
        check_interval: float = 30.0,
        event_bus: Any = None,
    ) -> None:
        self._push_callback = push_callback
        self._check_interval = check_interval
        self._event_bus = event_bus
        self._logger = _LOG
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # State tracking to avoid duplicate notifications
        self._last_battery_warning: float = 0
        self._last_disk_warning: float = 0
        self._last_greeting: str = ""
        self._reminders: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Start the proactive monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self._logger.info("[PROACTIVE] Event engine started (interval=%.0fs)", self._check_interval)

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._logger.info("[PROACTIVE] Event engine stopped.")

    def add_reminder(self, message: str, trigger_time: datetime.datetime) -> str:
        """Add a time-based reminder."""
        import uuid
        reminder_id = str(uuid.uuid4())[:8]
        self._reminders.append({
            "id": reminder_id,
            "message": message,
            "trigger_time": trigger_time.timestamp(),
            "fired": False,
        })
        self._logger.info("[PROACTIVE] Reminder added: %s at %s", message, trigger_time)
        return reminder_id

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a pending reminder."""
        self._reminders = [r for r in self._reminders if r["id"] != reminder_id]
        return True

    async def _monitor_loop(self) -> None:
        """Background loop that checks for proactive events."""
        import time as _time

        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                now = _time.time()

                # Check battery level (Windows)
                await self._check_battery(now)

                # Check disk space
                await self._check_disk_space(now)

                # Check reminders
                await self._check_reminders(now)

                # Time-based greetings
                await self._check_time_greeting()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.warning("[PROACTIVE] Monitor loop error: %s", exc)

    async def _check_battery(self, now: float) -> None:
        """Check battery level and warn if low."""
        if now - self._last_battery_warning < 300:  # Don't warn more than every 5 min
            return

        try:
            if platform.system() != "Windows":
                return

            battery = await asyncio.to_thread(self._get_battery_info)
            if battery is None:
                return

            percent, plugged = battery

            if percent <= 10 and not plugged:
                await self._push(ProactiveEvent(
                    message=f"⚡ Sir, battery critically low — sirf {percent}% bacha hai! Charger lagao warna shutdown ho jayega.",
                    priority=Priority.URGENT,
                    source="battery",
                    timestamp=now,
                    metadata={"percent": percent, "plugged": plugged},
                ))
                self._last_battery_warning = now
            elif percent <= 20 and not plugged:
                await self._push(ProactiveEvent(
                    message=f"🔋 Battery {percent}% pe hai. Charger kab lagaoge?",
                    priority=Priority.NORMAL,
                    source="battery",
                    timestamp=now,
                    metadata={"percent": percent, "plugged": plugged},
                ))
                self._last_battery_warning = now

        except Exception as exc:
            self._logger.debug("[PROACTIVE] Battery check failed: %s", exc)

    async def _check_disk_space(self, now: float) -> None:
        """Check disk space and warn if low."""
        if now - self._last_disk_warning < 3600:  # Don't warn more than hourly
            return

        try:
            import shutil
            usage = shutil.disk_usage("C:/")
            free_gb = usage.free / (1024 ** 3)

            if free_gb < 5:
                await self._push(ProactiveEvent(
                    message=f"💾 C: drive mein sirf {free_gb:.1f}GB space bacha hai. Kuch cleanup kar dein?",
                    priority=Priority.NORMAL,
                    source="disk",
                    timestamp=now,
                    metadata={"free_gb": round(free_gb, 1)},
                ))
                self._last_disk_warning = now

        except Exception as exc:
            self._logger.debug("[PROACTIVE] Disk check failed: %s", exc)

    async def _check_reminders(self, now: float) -> None:
        """Fire any due reminders."""
        for reminder in self._reminders:
            if reminder["fired"]:
                continue
            if now >= reminder["trigger_time"]:
                reminder["fired"] = True
                await self._push(ProactiveEvent(
                    message=f"⏰ Reminder: {reminder['message']}",
                    priority=Priority.NORMAL,
                    source="reminder",
                    timestamp=now,
                ))

        # Clean up fired reminders
        self._reminders = [r for r in self._reminders if not r["fired"]]

    async def _check_time_greeting(self) -> None:
        """Send contextual greetings at appropriate times."""
        now = datetime.datetime.now()
        greeting_key = f"{now.date()}_{now.hour // 6}"  # 4 greeting slots per day

        if greeting_key == self._last_greeting:
            return

        # Only greet at transition points
        if now.hour in (6, 12, 18, 22) and now.minute < 2:
            greetings = {
                6: "🌅 Good morning! Nayi subah, naye tasks. Kya plan hai aaj ka?",
                12: "☀️ Lunch time! Thoda break lo — machine bhi rest karti hai.",
                18: "🌆 Shaam ho gayi. Aaj ka kaam kaisa raha?",
                22: "🌙 Raat ho gayi, neend ka time. Kya save karna hai kuch?",
            }
            msg = greetings.get(now.hour)
            if msg:
                await self._push(ProactiveEvent(
                    message=msg,
                    priority=Priority.LOW,
                    source="greeting",
                    timestamp=now.timestamp(),
                ))
                self._last_greeting = greeting_key

    async def _push(self, event: ProactiveEvent) -> None:
        """Push a proactive event through the callback."""
        self._logger.info(
            "[PROACTIVE] Pushing: [%s] %s",
            event.priority.value, event.message[:60],
        )
        if self._push_callback:
            try:
                await self._push_callback(event)
            except Exception as exc:
                self._logger.error("[PROACTIVE] Push callback failed: %s", exc)

        # Also emit via event bus
        if self._event_bus and hasattr(self._event_bus, "emit"):
            await self._event_bus.emit("proactive_notification", {
                "message": event.message,
                "priority": event.priority.value,
                "source": event.source,
            })

    @staticmethod
    def _get_battery_info() -> tuple[int, bool] | None:
        """Get battery percentage and plugged status."""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                return None
            return int(battery.percent), battery.power_plugged
        except ImportError:
            return None
