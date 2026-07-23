"""
ScreenUnderstanding — vision-based screen content and UI structure analysis.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.modules.vision._screen_capture import ScreenCapture
from backend.modules.vision._types import ImageData
from backend.modules.vision.ports.vision_port import VisionPort

_LOG = logging.getLogger("naira.vision.screen_understanding")


class ScreenUnderstanding:
    """Screen understanding service for analyzing screenshots and UI elements."""

    def __init__(
        self,
        screen_capture: ScreenCapture,
        vision_provider: VisionPort,
        logger: logging.Logger | None = None,
    ) -> None:
        self._screen_capture = screen_capture
        self._vision_provider = vision_provider
        self._logger = logger or _LOG

    async def understand_screen(
        self, question: str | None = None, timeout: float = 20.0
    ) -> dict[str, Any]:
        start = time.time()
        image = await self._screen_capture.capture()

        if question:
            prompt = (
                f"Look at this screenshot and answer this question: '{question}'."
                " Be specific and concise. If the answer isn't visible, say so clearly."
            )
        else:
            prompt = (
                "Describe what is currently shown on this screen. Mention the"
                " application, key UI elements, and any important text or content"
                " visible. Be concise — 3-4 sentences max."
            )

        result = await self._vision_provider.analyze_image(
            image, prompt=prompt, timeout=timeout
        )
        duration_ms = (time.time() - start) * 1000

        output_text = getattr(result, "output", str(result))
        return {
            "description": output_text if not question else None,
            "answer": output_text if question else None,
            "elements": [],
            "duration_ms": duration_ms,
        }

    async def understand_ui(self, timeout: float = 20.0) -> dict[str, Any]:
        start = time.time()
        image = await self._screen_capture.capture()
        result = await self._vision_provider.understand_ui(image, timeout=timeout)
        duration_ms = (time.time() - start) * 1000
        output_text = getattr(result, "output", str(result))
        return {
            "elements": self._parse_elements(output_text),
            "raw_analysis": output_text,
            "duration_ms": duration_ms,
        }

    async def read_screen_text(self, timeout: float = 15.0) -> dict[str, Any]:
        start = time.time()
        image = await self._screen_capture.capture()
        ocr_result = await self._vision_provider.run_ocr(image, timeout=timeout)
        duration_ms = (time.time() - start) * 1000
        return {
            "text": ocr_result.text,
            "duration_ms": duration_ms,
        }

    async def compare_before_after(
        self, before_image: ImageData, timeout: float = 20.0
    ) -> dict[str, Any]:
        start = time.time()
        after_image = await self._screen_capture.capture()
        prompt = (
            "Compare these two screenshots (before and after). Describe what"
            " changed, if anything. Be specific about what's different."
        )
        result = await self._vision_provider.analyze_image_pair(
            before_image, after_image, prompt=prompt, timeout=timeout
        )
        duration_ms = (time.time() - start) * 1000
        output_text = getattr(result, "output", str(result))
        changed = "no change" not in (output_text or "").lower()
        return {
            "changed": changed,
            "description": output_text,
            "duration_ms": duration_ms,
        }

    def _parse_elements(self, raw_text: str) -> list[str]:
        if not raw_text:
            return []
        lines = [l.strip("- •").strip() for l in raw_text.split("\n")]
        return [l for l in lines if l]
