"""VisionPort — abstract port for pluggable vision adapters.

21_Dependency_Rules.md §2 — Port/Adapter pattern.

Concrete adapters (Gemini Vision, YOLO, MediaPipe, OpenAI Vision, etc.)
implement this ABC so ``VisionManager`` remains agnostic of the
underlying ML model or capture driver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.modules.vision._types import ImageData, OCRResult, VisionResult


class VisionPort(ABC):
    """Abstract vision port.

    Each method corresponds to a high-level vision capability.
    Implementations manage their own model lifecycle internally.
    """

    @abstractmethod
    async def load_image(
        self,
        source: str | bytes,
        *,
        timeout: float = 30.0,
    ) -> ImageData:
        """Load an image from a file path, URL, or raw bytes."""

    @abstractmethod
    async def preprocess(
        self,
        image: ImageData,
        *,
        max_width: int = 0,
        max_height: int = 0,
        preserve_aspect_ratio: bool = True,
        timeout: float = 30.0,
    ) -> ImageData:
        """Preprocess an image (resize, normalize, format convert)."""

    @abstractmethod
    async def run_ocr(
        self,
        image: ImageData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> OCRResult:
        """Extract text from an image via OCR."""

    @abstractmethod
    async def detect_objects(
        self,
        image: ImageData,
        *,
        confidence_threshold: float = 0.5,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        """Run object detection on an image."""

    @abstractmethod
    async def detect_faces(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        """Run face detection on an image."""

    @abstractmethod
    async def capture_screen(
        self,
        *,
        timeout: float = 30.0,
    ) -> ImageData:
        """Capture the current screen (or browser viewport)."""

    @abstractmethod
    async def caption_image(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        """Generate a short caption for the image."""

    @abstractmethod
    async def describe_scene(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        """Generate a detailed scene description."""

    @abstractmethod
    async def understand_ui(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        """Analyze a UI screenshot for interactive elements."""

    @abstractmethod
    async def analyze_image(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Full image analysis returning a structured dict."""

    @abstractmethod
    async def close(self) -> None:
        """Release adapter resources."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the adapter can be used."""
