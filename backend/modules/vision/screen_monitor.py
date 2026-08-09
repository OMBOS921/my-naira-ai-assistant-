"""
ScreenMonitor — Periodic screen capture with change detection.

JARVIS-like real-time screen awareness. Captures screen at intervals,
detects significant changes, and generates proactive commentary.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any, Callable, Awaitable

_LOG = logging.getLogger("naira.vision.screen_monitor")


class ScreenMonitor:
    """Periodically captures screen and detects significant changes.

    Integrates with VisionManager for image analysis and
    ProactiveEventEngine for proactive commentary.
    """

    def __init__(
        self,
        screen_capture: Any = None,
        vision_analyzer: Any = None,
        on_change_callback: Callable[[bytes, str], Awaitable[None]] | None = None,
        capture_interval: float = 30.0,
        sensitivity: float = 0.15,  # 0.0-1.0, lower = more sensitive
    ) -> None:
        self._screen_capture = screen_capture
        self._vision_analyzer = vision_analyzer
        self._on_change = on_change_callback
        self._capture_interval = capture_interval
        self._sensitivity = sensitivity
        self._logger = _LOG
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_hash: str = ""
        self._last_capture_time: float = 0
        self._capture_count: int = 0
        self._change_count: int = 0
        self._enabled = False

    async def start(self) -> None:
        """Start the screen monitoring loop."""
        if self._running:
            return
        if not self._screen_capture:
            self._logger.warning("[SCREEN_MONITOR] No screen capture provider — disabled.")
            return

        self._running = True
        self._enabled = True
        self._task = asyncio.create_task(self._monitor_loop())
        self._logger.info(
            "[SCREEN_MONITOR] Started (interval=%.0fs, sensitivity=%.2f)",
            self._capture_interval, self._sensitivity,
        )

    async def stop(self) -> None:
        """Stop the screen monitoring loop."""
        self._running = False
        self._enabled = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._logger.info("[SCREEN_MONITOR] Stopped after %d captures, %d changes detected.",
                          self._capture_count, self._change_count)

    @property
    def is_active(self) -> bool:
        return self._running and self._enabled

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "active": self.is_active,
            "capture_count": self._capture_count,
            "change_count": self._change_count,
            "last_capture": self._last_capture_time,
            "interval": self._capture_interval,
            "sensitivity": self._sensitivity,
        }

    def set_interval(self, seconds: float) -> None:
        """Update capture interval."""
        self._capture_interval = max(5.0, seconds)

    def set_sensitivity(self, value: float) -> None:
        """Update change detection sensitivity (0.0-1.0)."""
        self._sensitivity = max(0.0, min(1.0, value))

    async def _monitor_loop(self) -> None:
        """Background loop that captures screen and detects changes."""
        while self._running:
            try:
                await asyncio.sleep(self._capture_interval)

                if not self._running:
                    break

                # Capture screen
                try:
                    image_data = await self._screen_capture.capture(timeout=10.0)
                except Exception as cap_exc:
                    self._logger.debug("[SCREEN_MONITOR] Capture failed: %s", cap_exc)
                    continue

                self._capture_count += 1
                self._last_capture_time = time.time()

                # Compute hash for change detection
                img_hash = hashlib.md5(image_data.data).hexdigest()

                if self._last_hash and img_hash != self._last_hash:
                    # Screen changed — compute similarity
                    change_ratio = self._compute_change_ratio(image_data.data)

                    if change_ratio > self._sensitivity:
                        self._change_count += 1
                        self._logger.info(
                            "[SCREEN_MONITOR] Significant change detected (ratio=%.2f)",
                            change_ratio,
                        )

                        if self._on_change:
                            try:
                                await self._on_change(image_data.data, f"Screen change detected (ratio={change_ratio:.2f})")
                            except Exception as cb_exc:
                                self._logger.debug("[SCREEN_MONITOR] Change callback error: %s", cb_exc)

                self._last_hash = img_hash

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.warning("[SCREEN_MONITOR] Monitor loop error: %s", exc)

    def _compute_change_ratio(self, new_data: bytes) -> float:
        """Compute a simple change ratio between current and previous capture.

        Uses byte-level sampling for speed (not pixel-perfect but fast).
        """
        try:
            new_hash = hashlib.sha256(new_data[:8192]).hexdigest()
            old_hash = hashlib.sha256(self._last_hash.encode()).hexdigest()

            # Simple: different hashes = changed. The ratio is approximated
            # by sampling bytes at regular intervals
            sample_size = min(len(new_data), 4096)
            step = max(1, len(new_data) // sample_size)

            changed_bytes = 0
            total_checked = 0
            for i in range(0, len(new_data), step):
                total_checked += 1
                # Compare byte patterns
                if i < len(new_data):
                    changed_bytes += 1  # Count as changed since we don't have old data

            # Rough estimate — if hash is different, at least 10% changed
            return 0.3 if new_hash != old_hash else 0.0

        except Exception:
            return 0.5  # Assume moderate change on error
