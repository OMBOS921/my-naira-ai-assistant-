"""
Vision types — immutable result dataclasses for image processing.

21_System_Contracts.md §15 — Tool contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type ImageFormat = Literal["png", "jpeg", "webp", "bmp", "gif", "unknown"]
"""Supported/source image formats."""

type ImageSourceType = Literal["file", "bytes", "url", "screen_capture"]
"""Origin of an image loaded into the module."""

type DetectionClass = Literal[
    "person", "car", "dog", "cat", "book", "screen", "text_block", "unknown"
]
"""Placeholder detection classes for future YOLO integration."""


@dataclass(frozen=True)
class ImageData:
    """Raw image data with source metadata.

    Parameters
    ----------
    source_type : ImageSourceType
        How the image was obtained.
    source_path : str | None
        File path or URL the image was loaded from.
    width : int
        Image width in pixels (0 if unknown).
    height : int
        Image height in pixels (0 if unknown).
    format : ImageFormat
        Detected or declared image format.
    size_bytes : int
        Uncompressed size in bytes (0 if unknown).
    data : bytes | None
        Raw pixel data (bytes). ``None`` if not yet loaded.
    """

    source_type: ImageSourceType
    source_path: str | None = None
    width: int = 0
    height: int = 0
    format: ImageFormat = "unknown"
    size_bytes: int = 0
    data: bytes | None = None


@dataclass(frozen=True)
class OCRResult:
    """Text extracted from an image via OCR.

    Parameters
    ----------
    text : str
        Extracted text content.
    confidence : float
        Confidence score in range [0.0, 1.0] (0.0 if placeholder).
    language : str
        Detected language code (e.g. ``"en"``).
    bounding_boxes : tuple[tuple[float, float, float, float], ...]
        Bounding boxes (x1, y1, x2, y2) for each text region.
    """

    text: str = ""
    confidence: float = 0.0
    language: str = "en"
    bounding_boxes: tuple[tuple[float, float, float, float], ...] = ()


@dataclass(frozen=True)
class Detection:
    """A single detected object or face.

    Parameters
    ----------
    label : str
        Class label (e.g. ``"person"``, ``"face_1"``).
    confidence : float
        Detection confidence in range [0.0, 1.0].
    bbox : tuple[float, float, float, float]
        Bounding box (x1, y1, x2, y2) in normalized or pixel coords.
    """

    label: str
    confidence: float = 0.0
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class VisionResult:
    """Complete result of a vision operation.

    Parameters
    ----------
    status : Literal["success", "error", "timeout"]
        Operation outcome.
    output : str | None
        Human-readable output text.
    error : str | None
        Error message if status is ``"error"`` or ``"timeout"``.
    image_data : ImageData | None
        Source image data, if applicable.
    ocr : OCRResult | None
        OCR extraction result.
    objects : tuple[Detection, ...]
        Object detection results.
    faces : tuple[Detection, ...]
        Face detection results.
    duration_ms : float
        Wall-clock time for the operation.
    """

    status: Literal["success", "error", "timeout"] = "success"
    output: str | None = None
    error: str | None = None
    image_data: ImageData | None = None
    ocr: OCRResult | None = None
    objects: tuple[Detection, ...] = ()
    faces: tuple[Detection, ...] = ()
    duration_ms: float = 0.0


type VisionOperation = Literal[
    "load_image", "preprocess", "run_ocr", "detect_objects",
    "detect_faces", "capture_screen",
]
"""Types of vision operations tracked by the module."""
