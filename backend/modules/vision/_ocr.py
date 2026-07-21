"""
OCR — Optical Character Recognition placeholder.

Future implementations will integrate Tesseract, EasyOCR, or
Gemini Vision for text extraction.
"""

from __future__ import annotations

import logging

from backend.modules.vision._types import ImageData, OCRResult

_LOG = logging.getLogger("naira.vision.ocr")


class OCR:
    """Optical Character Recognition placeholder.

    Returns an empty ``OCRResult``.  Will be replaced with a real
    OCR engine (Tesseract / EasyOCR / Gemini Vision) in Phase 2.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    async def run(
        self,
        image: ImageData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> OCRResult:
        """Run OCR on *image*.

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
            Extracted text (empty in placeholder mode).
        """
        self._logger.debug(
            "OCR placeholder — no text extracted (image: %s, language: %s)",
            image.source_path or "bytes", language,
        )
        return OCRResult(text="", language=language)
