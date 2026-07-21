"""
ObjectDetection — object detection placeholder.

Future implementations will integrate YOLO or Gemini Vision for
object detection.
"""

from __future__ import annotations

import logging

from backend.modules.vision._types import Detection, ImageData

_LOG = logging.getLogger("naira.vision.object_detection")


class ObjectDetection:
    """Object detection placeholder.

    Returns an empty detection tuple.  Will be replaced with YOLO
    or Gemini Vision in Phase 2.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    async def detect(
        self,
        image: ImageData,
        *,
        confidence_threshold: float = 0.5,
        timeout: float = 30.0,
    ) -> tuple[Detection, ...]:
        """Run object detection on *image*.

        Parameters
        ----------
        image : ImageData
            Source image data.
        confidence_threshold : float
            Minimum confidence for reported detections.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        tuple[Detection, ...]
            Detected objects (empty in placeholder mode).
        """
        self._logger.debug(
            "ObjectDetection placeholder — no detections (image: %s)",
            image.source_path or "bytes",
        )
        return ()
