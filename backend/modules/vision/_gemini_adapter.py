"""GeminiVisionAdapter — production VisionPort using the official google-genai SDK.

Implements all VisionPort methods via Google Gemini Vision API.
All configuration (model, timeout, retry, API key) comes from
constructor injection — never reads .env or os.environ.

Follows the same architectural style as the LLM module's GeminiProvider.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image as PILImage

from backend.modules.vision._exceptions import (
    VisionLoadError,
    VisionProcessingError,
    VisionTimeoutError,
)
from backend.modules.vision._image_loader import ImageLoader
from backend.modules.vision._image_preprocessor import ImagePreprocessor
from backend.modules.vision._types import (
    Detection,
    ImageData,
    OCRResult,
    VisionResult,
)
from backend.modules.vision.ports.vision_port import VisionPort

_LOG = logging.getLogger("naira.vision.gemini")

_OCR_PROMPT: str = (
    "Extract all text visible in this image. "
    "Return ONLY the extracted text with no commentary. "
    "If the image contains no text, return an empty string."
)

_OBJECT_DETECTION_PROMPT: str = (
    "Detect all objects in this image. "
    "Return a JSON array of objects with keys: 'label', "
    "'confidence' (0.0-1.0). "
    'Example: [{"label": "person", "confidence": 0.95}]'
    "Return an empty array [] if no objects are detected."
)

_FACE_DETECTION_PROMPT: str = (
    "Detect all faces in this image. "
    "Return a JSON array with each face as: "
    '{"label": "face_1", "confidence": 0.0-1.0}. '
    "Return an empty array [] if no faces are detected."
)

_CAPTION_PROMPT: str = (
    "Provide a short, descriptive caption for this image "
    "in one sentence."
)

_SCENE_DESCRIPTION_PROMPT: str = (
    "Describe this image in detail. Include objects, people, "
    "setting, colors, and any notable features."
)

_UI_UNDERSTANDING_PROMPT: str = (
    "Analyze this UI screenshot. Identify all interactive elements "
    "(buttons, links, input fields, dropdowns), their labels, and "
    "their approximate positions. Return a structured analysis."
)

_IMAGE_ANALYSIS_PROMPT: str = (
    "Analyze this image and return a JSON object with:\n"
    "- 'description': A detailed description of the image.\n"
    "- 'objects': A list of objects visible with labels.\n"
    "- 'text': Any text visible in the image.\n"
    "- 'scenes': Scene type (indoor/outdoor/nature/urban/etc)."
)


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for API calls.

    Mirrors the LLM module's retry pattern.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0


class GeminiVisionAdapter(VisionPort):
    """Production VisionPort that uses Google Gemini Vision API.

    All configuration is injected through the constructor.
    Never reads .env or os.environ directly.

    Parameters
    ----------
    api_key : str
        Gemini API key (from EnvironmentSnapshot, injected by Boot).
    model : str
        Gemini model name (from VisionConfig, injected by Boot).
    timeout : float
        Default timeout for API calls (from VisionConfig).
    retry_policy : RetryPolicy | None
        Retry configuration (from VisionConfig).
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-2.0-flash",
        timeout: float = 30.0,
        retry_policy: RetryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._default_timeout = timeout
        self._retry_policy = retry_policy or RetryPolicy()
        self._logger = logger or _LOG

        from google import genai
        self._client = genai.Client(api_key=api_key)

        self._image_loader = ImageLoader()
        self._image_preprocessor = ImagePreprocessor()

    # ------------------------------------------------------------------
    # Public API — VisionPort
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return True

    async def load_image(
        self,
        source: str | bytes,
        *,
        timeout: float = 30.0,
    ) -> ImageData:
        try:
            return await self._image_loader.load(source, timeout=timeout)
        except VisionLoadError:
            raise
        except Exception as exc:
            raise VisionLoadError(
                "Image loading failed",
                context={"error": str(exc)},
            ) from exc

    async def preprocess(
        self,
        image: ImageData,
        *,
        max_width: int = 0,
        max_height: int = 0,
        preserve_aspect_ratio: bool = True,
        timeout: float = 30.0,
    ) -> ImageData:
        try:
            return await self._image_preprocessor.preprocess(
                image,
                max_width=max_width,
                max_height=max_height,
                preserve_aspect_ratio=preserve_aspect_ratio,
                timeout=timeout,
            )
        except Exception as exc:
            raise VisionProcessingError(
                "Image preprocessing failed",
                context={"error": str(exc)},
            ) from exc

    async def run_ocr(
        self,
        image: ImageData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> OCRResult:
        text = await self._call_gemini(
            prompt=_OCR_PROMPT, image=image, timeout=timeout,
        )
        if not text:
            return OCRResult(text="", language=language)
        confidence_str = await self._call_gemini(
            prompt=(
                "On a scale of 0.0 to 1.0, how confident are you that "
                "the text in this image has been accurately extracted? "
                "Return ONLY a number between 0.0 and 1.0."
            ),
            image=image,
            timeout=timeout,
        )
        try:
            confidence = max(0.0, min(1.0, float(confidence_str.strip())))
        except (ValueError, TypeError):
            confidence = 0.5
        return OCRResult(
            text=text.strip(),
            confidence=confidence,
            language=language,
        )

    async def detect_objects(
        self,
        image: ImageData,
        *,
        confidence_threshold: float = 0.5,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        response = await self._call_gemini(
            prompt=_OBJECT_DETECTION_PROMPT, image=image, timeout=timeout,
        )
        detections = _parse_detection_json(response, confidence_threshold)
        if not detections:
            return ()
        return tuple(
            VisionResult(
                status="success",
                output=f"{d.label} (confidence: {d.confidence:.2f})",
            )
            for d in detections
        )

    async def detect_faces(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        response = await self._call_gemini(
            prompt=_FACE_DETECTION_PROMPT, image=image, timeout=timeout,
        )
        detections = _parse_detection_json(response, 0.0)
        if not detections:
            return ()
        return tuple(
            VisionResult(
                status="success",
                output=f"{d.label} (confidence: {d.confidence:.2f})",
            )
            for d in detections
        )

    async def capture_screen(
        self,
        *,
        timeout: float = 30.0,
    ) -> ImageData:
        from backend.modules.vision._exceptions import VisionNotImplementedError
        raise VisionNotImplementedError(context={
            "operation": "capture_screen",
        })

    async def caption_image(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        return await self._call_gemini(
            prompt=_CAPTION_PROMPT, image=image, timeout=timeout,
        )

    async def describe_scene(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> str:
        return await self._call_gemini(
            prompt=_SCENE_DESCRIPTION_PROMPT, image=image, timeout=timeout,
        )

    async def understand_ui(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> VisionResult:
        output = await self._call_gemini(
            prompt=_UI_UNDERSTANDING_PROMPT, image=image, timeout=timeout,
        )
        return VisionResult(status="success", output=output)

    async def analyze_image(
        self,
        image: ImageData,
        *,
        prompt: str | None = None,
        timeout: float = 30.0,
    ) -> VisionResult:
        effective_prompt = prompt or _IMAGE_ANALYSIS_PROMPT
        output = await self._call_gemini(
            prompt=effective_prompt, image=image, timeout=timeout,
        )
        return VisionResult(status="success", output=output)

    async def analyze_image_pair(
        self,
        image1: ImageData,
        image2: ImageData,
        *,
        prompt: str | None = None,
        timeout: float = 30.0,
    ) -> VisionResult:
        effective_prompt = prompt or "Compare these two screenshots (before and after)."
        pil1 = await self._to_pil(image1)
        pil2 = await self._to_pil(image2)
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[effective_prompt, pil1, pil2],
        )
        return VisionResult(status="success", output=response.text or "")

    async def close(self) -> None:
        self._logger.debug("GeminiVisionAdapter.close() — no-op")

    # ------------------------------------------------------------------
    # Internal — Gemini API
    # ------------------------------------------------------------------

    async def _call_gemini(
        self,
        prompt: str,
        image: ImageData,
        timeout: float,
    ) -> str:
        """Call the Gemini API with prompt + image, with retry logic."""
        max_attempts = self._retry_policy.max_retries + 1

        for attempt in range(max_attempts):
            try:
                return await asyncio.wait_for(
                    self._do_gemini_call(prompt, image),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                if attempt < self._retry_policy.max_retries:
                    delay = self._compute_backoff(attempt)
                    self._logger.warning(
                        "Gemini API timeout (attempt %d/%d), "
                        "retrying in %.1fs",
                        attempt + 1, max_attempts, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise VisionTimeoutError(
                    f"Gemini API timed out after {timeout}s",
                    context={"timeout": timeout},
                ) from None
            except Exception as exc:
                if attempt < self._retry_policy.max_retries:
                    delay = self._compute_backoff(attempt)
                    self._logger.warning(
                        "Gemini API error (attempt %d/%d): %s, "
                        "retrying in %.1fs",
                        attempt + 1, max_attempts, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise VisionProcessingError(
                    f"Gemini API call failed: {exc}",
                    context={"error": str(exc)},
                ) from exc

        raise VisionTimeoutError(
            f"All {max_attempts} retry attempts exhausted",
            context={"max_retries": self._retry_policy.max_retries},
        )

    async def _do_gemini_call(self, prompt: str, image: ImageData) -> str:
        """Execute the actual Gemini API call."""
        pil_image = await self._to_pil(image)
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[prompt, pil_image],
        )
        return response.text or ""

    async def _to_pil(self, image: ImageData) -> PILImage.Image:
        """Convert ImageData to PIL Image."""
        if image.data is not None:
            return PILImage.open(io.BytesIO(image.data))
        if image.source_path is not None:
            path = Path(image.source_path)
            if path.exists():
                return PILImage.open(path)
        return PILImage.new("RGB", (100, 100), color="white")

    def _compute_backoff(self, attempt: int) -> float:
        delay = self._retry_policy.base_delay * (
            self._retry_policy.exponential_base ** attempt
        )
        return min(delay, self._retry_policy.max_delay)


# -----------------------------------------------------------------------
# Module-level helpers (stateless, reusable)
# -----------------------------------------------------------------------


def _parse_detection_json(
    response: str,
    confidence_threshold: float,
) -> list[Detection]:
    """Parse JSON array of detections from model response."""
    match = re.search(r"\[.*?\]", response, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
        if not isinstance(items, list):
            return []
        results: list[Detection] = []
        for item in items:
            label = str(item.get("label", "unknown"))
            confidence = float(item.get("confidence", 0.0))
            if confidence >= confidence_threshold:
                results.append(
                    Detection(label=label, confidence=confidence),
                )
        return results
    except (json.JSONDecodeError, ValueError, TypeError):
        return []


def _parse_analysis_response(response: str) -> dict[str, Any]:
    """Parse JSON from analysis response."""
    match = re.search(r"\{.*\}", response, re.DOTALL)
    json_str = match.group(0) if match else response.strip()
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return {
            "description": response,
            "objects": [],
            "text": "",
            "scenes": "",
        }
