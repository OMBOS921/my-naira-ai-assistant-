"""
VisionExecutor — async execution layer with timeout and error isolation.

Wraps port/adapter operations so that ``VisionManager`` never deals
with raw exceptions or hanging calls.
"""

from __future__ import annotations

import asyncio
import logging

from backend.modules.vision._exceptions import VisionNotImplementedError
from backend.modules.vision._types import ImageData
from backend.modules.vision.ports.vision_port import VisionPort
from backend.types import ToolResult

_LOG = logging.getLogger("naira.vision.executor")


class VisionExecutor:
    """Safe execution wrapper for vision operations.

    Parameters
    ----------
    adapter : VisionPort
        The active vision adapter (placeholder or real).
    default_timeout : float
        Default timeout for all operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        adapter: VisionPort,
        default_timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._adapter = adapter
        self._default_timeout = default_timeout
        self._logger = logger or _LOG

    async def load_image(
        self,
        source: str | bytes,
        timeout: float | None = None,
    ) -> ToolResult:
        """Load an image and return the result.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            image_data = await asyncio.wait_for(
                self._adapter.load_image(source, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            output = (
                f"Image loaded — source: {image_data.source_path or 'bytes'}, "
                f"format: {image_data.format}, "
                f"size: {image_data.size_bytes} bytes"
            )
            return ToolResult(status="success", output=output)
        except VisionNotImplementedError:
            return ToolResult(
                status="error",
                error="Vision adapter not configured — no image decoder available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Image loading timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Image loading failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Image loading failed: {exc}",
            )

    async def preprocess(
        self,
        image: ImageData,
        max_width: int = 0,
        max_height: int = 0,
        preserve_aspect_ratio: bool = True,
        timeout: float | None = None,
    ) -> ToolResult:
        """Preprocess an image and return the result.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            processed = await asyncio.wait_for(
                self._adapter.preprocess(
                    image,
                    max_width=max_width,
                    max_height=max_height,
                    preserve_aspect_ratio=preserve_aspect_ratio,
                    timeout=effective_timeout,
                ),
                timeout=effective_timeout + 1.0,
            )
            return ToolResult(
                status="success",
                output=f"Image preprocessed — dimensions: {processed.width}x{processed.height}",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Image preprocessing timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Image preprocessing failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Image preprocessing failed: {exc}",
            )

    async def run_ocr(
        self,
        image: ImageData,
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Run OCR on an image and return the result.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            ocr_result = await asyncio.wait_for(
                self._adapter.run_ocr(image, language=language, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            if ocr_result.text:
                return ToolResult(status="success", output=ocr_result.text)
            return ToolResult(
                status="error",
                error="No text detected in image",
            )
        except VisionNotImplementedError:
            return ToolResult(
                status="error",
                error="Vision adapter not configured — no OCR engine available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"OCR timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("OCR failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"OCR failed: {exc}",
            )

    async def detect_objects(
        self,
        image: ImageData,
        confidence_threshold: float = 0.5,
        timeout: float | None = None,
    ) -> ToolResult:
        """Run object detection on an image.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            objects = await asyncio.wait_for(
                self._adapter.detect_objects(
                    image, confidence_threshold=confidence_threshold, timeout=effective_timeout,
                ),
                timeout=effective_timeout + 1.0,
            )
            if objects:
                lines = [f"Detected {len(objects)} object(s):"]
                for obj in objects:
                    lines.append(f"  - {obj.status} (confidence: ...)")
                return ToolResult(status="success", output="\n".join(lines))
            return ToolResult(
                status="error",
                error="No objects detected",
            )
        except VisionNotImplementedError:
            return ToolResult(
                status="error",
                error="Vision adapter not configured — no object detection model available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Object detection timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Object detection failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Object detection failed: {exc}",
            )

    async def detect_faces(
        self,
        image: ImageData,
        timeout: float | None = None,
    ) -> ToolResult:
        """Run face detection on an image.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            faces = await asyncio.wait_for(
                self._adapter.detect_faces(image, timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            if faces:
                return ToolResult(
                    status="success",
                    output=f"Detected {len(faces)} face(s)",
                )
            return ToolResult(
                status="error",
                error="No faces detected",
            )
        except VisionNotImplementedError:
            return ToolResult(
                status="error",
                error="Vision adapter not configured — no face detection model available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Face detection timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Face detection failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Face detection failed: {exc}",
            )

    async def capture_screen(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        """Capture the current screen.

        Returns a ``ToolResult`` (never raises).
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            image_data = await asyncio.wait_for(
                self._adapter.capture_screen(timeout=effective_timeout),
                timeout=effective_timeout + 1.0,
            )
            return ToolResult(
                status="success",
                output=f"Screen captured — {image_data.width}x{image_data.height}",
            )
        except VisionNotImplementedError:
            return ToolResult(
                status="error",
                error="Vision adapter not configured — no screen capture driver available",
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Screen capture timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Screen capture failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Screen capture failed: {exc}",
            )

    @property
    def is_available(self) -> bool:
        """Return ``True`` if the underlying adapter is usable."""
        return self._adapter.is_available
