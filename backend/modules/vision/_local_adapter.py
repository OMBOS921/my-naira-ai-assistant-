"""LocalVisionAdapter — placeholder vision adapter.

Returns ``is_available=False`` and raises ``VisionNotImplementedError``
on every operation.  This adapter is used when no real vision model
(Gemini Vision, YOLO, MediaPipe, OpenAI Vision) has been configured.

When a real adapter is wired in, ``VisionManager`` will use it
in place of this placeholder with zero code changes.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modules.vision._exceptions import VisionNotImplementedError
from backend.modules.vision._image_loader import ImageLoader
from backend.modules.vision._image_preprocessor import ImagePreprocessor
from backend.modules.vision._types import ImageData, OCRResult, VisionResult
from backend.modules.vision.ports.vision_port import VisionPort

_LOG = logging.getLogger("naira.vision.adapter")


class LocalVisionAdapter(VisionPort):
    """Placeholder adapter that signals that no real vision model
    is available.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG
        self._image_loader = ImageLoader()
        self._image_preprocessor = ImagePreprocessor()

    @property
    def is_available(self) -> bool:
        return False

    async def load_image(
        self,
        source: str | bytes,
        *,
        timeout: float = 30.0,
    ) -> ImageData:
        return await self._image_loader.load(source, timeout=timeout)

    async def preprocess(
        self,
        image: ImageData,
        *,
        max_width: int = 0,
        max_height: int = 0,
        preserve_aspect_ratio: bool = True,
        timeout: float = 30.0,
    ) -> ImageData:
        return await self._image_preprocessor.preprocess(
            image,
            max_width=max_width,
            max_height=max_height,
            preserve_aspect_ratio=preserve_aspect_ratio,
            timeout=timeout,
        )

    async def run_ocr(
        self,
        image: ImageData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> OCRResult:
        raise VisionNotImplementedError(context={
            "operation": "run_ocr", "language": language,
        })

    async def detect_objects(
        self,
        image: ImageData,
        *,
        confidence_threshold: float = 0.5,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        raise VisionNotImplementedError(context={
            "operation": "detect_objects",
            "confidence_threshold": confidence_threshold,
        })

    async def detect_faces(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        raise VisionNotImplementedError(context={
            "operation": "detect_faces",
        })

    async def capture_screen(
        self,
        *,
        timeout: float = 30.0,
    ) -> ImageData:
        raise VisionNotImplementedError(context={
            "operation": "capture_screen",
        })

    async def caption_image(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        raise VisionNotImplementedError(context={
            "operation": "caption_image",
        })

    async def describe_scene(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        raise VisionNotImplementedError(context={
            "operation": "describe_scene",
        })

    async def understand_ui(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        raise VisionNotImplementedError(context={
            "operation": "understand_ui",
        })

    async def analyze_image(
        self,
        image: ImageData,
        *,
        prompt: str | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        raise VisionNotImplementedError(context={
            "operation": "analyze_image",
        })

    async def analyze_image_pair(
        self,
        image1: ImageData,
        image2: ImageData,
        *,
        prompt: str | None = None,
        timeout: float = 30.0,
    ) -> Any:
        raise VisionNotImplementedError(context={
            "operation": "analyze_image_pair",
        })

    async def close(self) -> None:
        self._logger.debug("LocalVisionAdapter.close() — no-op")
