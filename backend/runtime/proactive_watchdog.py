"""
ProactiveWatchdog — Background engine giving Naira-OS autonomous 'alive' traits.

Periodically monitors system health, memory, and scheduled events, and proactively
pushes alerts or recommendations to connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

try:
    from fastapi import WebSocket
except ImportError:
    WebSocket = Any  # type: ignore[assignment,misc]

_LOG = logging.getLogger("naira.proactive_watchdog")


class ProactiveWatchdog:
    """Background watchdog monitoring system state and pushing proactive alerts.

    Parameters
    ----------
    active_websockets : set[WebSocket] | None
        Reference to active FastAPI WebSocket clients.
    check_interval : float
        Frequency of health & anomaly checks in seconds (default 60.0).
    cpu_threshold : float
        CPU load percentage threshold for proactive alert (default 80.0).
    memory_threshold : float
        Memory load percentage threshold for proactive alert (default 85.0).
    logger : logging.Logger | None
        Module logger.
    """

    def __init__(
        self,
        active_websockets: set[WebSocket] | None = None,
        check_interval: float = 60.0,
        cpu_threshold: float = 80.0,
        memory_threshold: float = 85.0,
        logger: logging.Logger | None = None,
        llm_manager: object | None = None,
    ) -> None:
        self._websockets = active_websockets if active_websockets is not None else set()
        self._check_interval = check_interval
        self._cpu_threshold = cpu_threshold
        self._memory_threshold = memory_threshold
        self._logger = logger or _LOG
        self._llm_manager = llm_manager
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_alert_time: float = 0.0
        self._alert_cooldown_seconds: float = 300.0  # 5 min cooldown between alerts
        # Warm up psutil.cpu_percent so initial measurement is not 0.0
        try:
            import psutil
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    async def start(self) -> None:
        """Start the background proactive loop."""
        if self._running:
            return
        self._running = True
        try:
            import psutil
            psutil.cpu_percent(interval=None)
        except Exception:
            pass
        self._task = asyncio.create_task(self._watchdog_loop())
        self._logger.info("[WATCHDOG] ProactiveWatchdog started (interval=%.0fs).", self._check_interval)

    async def stop(self) -> None:
        """Stop the background proactive loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._logger.info("[WATCHDOG] ProactiveWatchdog stopped.")

    async def _watchdog_loop(self) -> None:
        """Core periodic watchdog loop."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                await self.check_and_notify()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.warning("[WATCHDOG] Exception during watchdog check: %s", exc)

    async def check_and_notify(self) -> None:
        """Inspect system metrics and dispatch proactive alerts if thresholds breached."""
        now = time.time()
        if now - self._last_alert_time < self._alert_cooldown_seconds:
            return

        metrics = self._get_system_metrics()
        cpu_pct = metrics.get("cpu_percent", 0.0)
        mem_pct = metrics.get("memory_percent", 0.0)

        proactive_msg = None
        if cpu_pct >= self._cpu_threshold:
            proactive_msg = f"Boss, I noticed the CPU load is high ({cpu_pct:.1f}%), should I run a diagnostic?"
        elif mem_pct >= self._memory_threshold:
            proactive_msg = f"Boss, system RAM usage is at {mem_pct:.1f}%. Would you like me to optimize background processes?"

        if proactive_msg and self._websockets:
            self._last_alert_time = now
            synthesized_msg = await self._synthesize_alert(proactive_msg)
            await self.broadcast(synthesized_msg)

    async def _synthesize_alert(self, raw_alert: str) -> str:
        """Synthesise system metrics alert into a natural voice notification."""
        if self._llm_manager is None or not hasattr(self._llm_manager, "generate"):
            return raw_alert
        try:
            from backend.types import Message
            prompt = (
                "You are Naira, a friendly, intelligent AI assistant. Rephrase this system alert into a single, natural, "
                "conversational sentence starting with 'Boss, ' or a warm greeting. Keep it concise."
            )
            resp = await self._llm_manager.generate(
                prompt=prompt, context=[Message(role="user", content=f"Alert: {raw_alert}")], tools=None, )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as exc:
            self._logger.warning("[WATCHDOG] Alert synthesis failed: %s", exc)
        return raw_alert

    def _get_system_metrics(self) -> dict[str, float]:
        """Gather CPU and Memory usage."""
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=None), "memory_percent": psutil.virtual_memory().percent, }
        except ImportError:
            return {"cpu_percent": 0.0, "memory_percent": 0.0}

    async def broadcast(self, message_text: str) -> None:
        """Send a proactive message to all connected WebSocket clients."""
        if not self._websockets:
            return

        payload = {
            "sender": "naira", "text": message_text, "proactive": True, "timestamp": time.time(), }

        self._logger.info("[WATCHDOG] Broadcasting proactive alert to %d clients: %s", len(self._websockets), message_text)
        disconnected = set()
        for ws in list(self._websockets):
            try:
                await ws.send_json(payload)
            except Exception as exc:
                self._logger.warning("[WATCHDOG] Failed to send message to websocket client: %s", exc)
                disconnected.add(ws)

        for ws in disconnected:
            self._websockets.discard(ws)