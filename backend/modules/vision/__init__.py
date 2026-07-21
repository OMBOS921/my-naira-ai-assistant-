"""Vision module — the AI's visual perception layer.

Provides image loading, preprocessing, OCR, object detection,
face detection, and screen capture capabilities through a
pluggable adapter architecture mirroring the LLM module pattern.
"""

from __future__ import annotations

from backend.modules.vision._executor import VisionExecutor
from backend.modules.vision._face_detection import FaceDetection
from backend.modules.vision._gemini_adapter import (
    GeminiVisionAdapter,
    RetryPolicy,
)
from backend.modules.vision._image_loader import ImageLoader
from backend.modules.vision._image_preprocessor import ImagePreprocessor
from backend.modules.vision._local_adapter import LocalVisionAdapter
from backend.modules.vision._object_detection import ObjectDetection
from backend.modules.vision._ocr import OCR
from backend.modules.vision._screen_capture import ScreenCapture
from backend.modules.vision._types import (
    Detection,
    ImageData,
    OCRResult,
    VisionResult,
)
from backend.modules.vision.ports.vision_port import VisionPort
from backend.modules.vision.vision_module import VisionManager

__all__ = [
    "VisionManager",
    "VisionPort",
    "LocalVisionAdapter",
    "GeminiVisionAdapter",
    "VisionExecutor",
    "ImageLoader",
    "ImagePreprocessor",
    "OCR",
    "ObjectDetection",
    "FaceDetection",
    "ScreenCapture",
    "ImageData",
    "OCRResult",
    "Detection",
    "VisionResult",
    "RetryPolicy",
]
