"""
FaceDetection — face detection placeholder.

Future implementations will integrate MediaPipe or OpenCV for
face detection.
"""

from __future__ import annotations

import logging

from backend.modules.vision._types import Detection, ImageData

_LOG = logging.getLogger("naira.vision.face_detection")


class FaceDetection:
    """Face detection placeholder.

    Returns an empty detection tuple.  Will be replaced with
    MediaPipe or OpenCV Haar Cascades in Phase 2.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    async def detect(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> tuple[Detection, ...]:
        """Run face detection on *image*.

        Parameters
        ----------
        image : ImageData
            Source image data.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        tuple[Detection, ...]
            Detected faces (empty in placeholder mode).
        """
        self._logger.debug(
            "FaceDetection placeholder — no detections (image: %s)",
            image.source_path or "bytes",
        )
        return ()
