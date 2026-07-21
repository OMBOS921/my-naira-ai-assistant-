"""Provider interfaces for pluggable vision sub-components.

OCRProvider, ObjectDetectionProvider, and FaceDetectionProvider are
abstract bases that let the Gemini adapter (or any future adapter)
delegate to specialised backends (Tesseract, EasyOCR, YOLO, MediaPipe).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.vision._types import Detection, ImageData, OCRResult


class OCRProvider(ABC):
    """Abstract OCR engine.

    Default implementation: Gemini Vision OCR.
    Future: Tesseract, EasyOCR.
    """

    @abstractmethod
    async def run_ocr(
        self,
        image: ImageData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> OCRResult:
        """Extract text from *image*.

        Parameters
        ----------
        image : ImageData
            Source image data.
        language : str
            Expected language hint.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        OCRResult
            Extracted text with confidence metadata.
        """


class ObjectDetectionProvider(ABC):
    """Abstract object detection engine.

    Default implementation: Gemini Vision.
    Future: YOLO, MediaPipe.
    """

    @abstractmethod
    async def detect_objects(
        self,
        image: ImageData,
        *,
        confidence_threshold: float = 0.5,
        timeout: float = 30.0,
    ) -> tuple[Detection, ...]:
        """Detect objects in *image*.

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
            Detected objects with labels and bounding boxes.
        """


class FaceDetectionProvider(ABC):
    """Abstract face detection engine.

    Default implementation: Gemini Vision.
    Future: MediaPipe, OpenCV Haar Cascades.
    """

    @abstractmethod
    async def detect_faces(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> tuple[Detection, ...]:
        """Detect faces in *image*.

        Parameters
        ----------
        image : ImageData
            Source image data.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        tuple[Detection, ...]
            Detected faces with bounding boxes.
        """
