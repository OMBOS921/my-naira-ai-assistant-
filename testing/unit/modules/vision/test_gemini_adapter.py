"""Comprehensive tests for the GeminiVisionAdapter.

Covers:
- Adapter initialization and is_available
- OCR (with mocked Gemini API)
- Object detection (with mocked Gemini API)
- Face detection (with mocked Gemini API)
- Image captioning
- Scene description
- UI understanding
- Image analysis (structured)
- Timeout handling
- Retry logic
- Backoff computation
- Error mapping (provider failures)
- JSON response parsing
- Image loading (file, bytes, PIL)
- Image preprocessing (resize, RGB, aspect ratio)
- Capture screen (not implemented)
- Close (no-op)
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image as PILImage

from backend.modules.vision._exceptions import (
    VisionLoadError,
    VisionProcessingError,
    VisionTimeoutError,
)
from backend.modules.vision._gemini_adapter import (
    GeminiVisionAdapter,
    RetryPolicy,
    _parse_analysis_response,
    _parse_detection_json,
)
from backend.modules.vision._types import (
    ImageData,
)


def _make_image() -> ImageData:
    """Create a small valid PNG ImageData for testing."""
    img = PILImage.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ImageData(
        source_type="bytes",
        source_path=None,
        width=10,
        height=10,
        format="png",
        size_bytes=buf.tell(),
        data=buf.getvalue(),
    )


def _make_adapter(**kwargs: object) -> GeminiVisionAdapter:
    """Create a GeminiVisionAdapter without calling the real constructor."""
    adapter = object.__new__(GeminiVisionAdapter)
    adapter._api_key = "test-api-key"
    adapter._model = "gemini-2.0-flash"
    adapter._default_timeout = kwargs.get("timeout", 30.0)
    adapter._retry_policy = kwargs.get("retry_policy", RetryPolicy())
    adapter._logger = kwargs.get("logger", MagicMock())
    adapter._client = MagicMock()
    adapter._image_loader = MagicMock()
    adapter._image_preprocessor = MagicMock()
    return adapter


def _mock_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


# =========================================================================
# RetryPolicy
# =========================================================================


class TestRetryPolicy:
    def test_defaults(self) -> None:
        rp = RetryPolicy()
        assert rp.max_retries == 3
        assert rp.base_delay == 1.0
        assert rp.max_delay == 30.0
        assert rp.exponential_base == 2.0

    def test_custom(self) -> None:
        rp = RetryPolicy(max_retries=5, base_delay=0.5, max_delay=10.0)
        assert rp.max_retries == 5
        assert rp.base_delay == 0.5
        assert rp.max_delay == 10.0


# =========================================================================
# Adapter initialization
# =========================================================================


class TestGeminiVisionAdapterInit:
    def test_is_available(self) -> None:
        adapter = _make_adapter()
        assert adapter.is_available is True

    def test_inherits_vision_port(self) -> None:
        from backend.modules.vision.ports.vision_port import VisionPort
        assert issubclass(GeminiVisionAdapter, VisionPort)


# =========================================================================
# OCR
# =========================================================================


class TestGeminiOCR:
    @pytest.mark.asyncio
    async def test_ocr_returns_text(self) -> None:
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(side_effect=["Hello World", "0.95"])
        image = _make_image()
        result = await adapter.run_ocr(image, language="en")
        assert result.text == "Hello World"
        assert result.confidence == 0.95
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_ocr_empty_response(self) -> None:
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(return_value="")
        image = _make_image()
        result = await adapter.run_ocr(image)
        assert result.text == ""
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_ocr_confidence_parse_error(self) -> None:
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(side_effect=["text", "not_a_number"])
        image = _make_image()
        result = await adapter.run_ocr(image)
        assert result.text == "text"
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_ocr_language_hint(self) -> None:
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(side_effect=["Bonjour", "0.9"])
        image = _make_image()
        result = await adapter.run_ocr(image, language="fr")
        assert result.language == "fr"


# =========================================================================
# Object Detection
# =========================================================================


class TestGeminiObjectDetection:
    @pytest.mark.asyncio
    async def test_detect_objects(self) -> None:
        adapter = _make_adapter()
        json_response = (
            '[{"label": "person", "confidence": 0.9}, '
            '{"label": "car", "confidence": 0.8}]'
        )
        adapter._do_gemini_call = AsyncMock(return_value=json_response)
        image = _make_image()
        results = await adapter.detect_objects(image)
        assert len(results) == 2
        assert results[0].output is not None
        assert "person" in results[0].output
        assert "car" in results[1].output

    @pytest.mark.asyncio
    async def test_detect_objects_empty_response(self) -> None:
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(return_value="[]")
        image = _make_image()
        results = await adapter.detect_objects(image)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_detect_objects_threshold(self) -> None:
        adapter = _make_adapter()
        json_response = '[{"label": "person", "confidence": 0.3}]'
        adapter._do_gemini_call = AsyncMock(return_value=json_response)
        image = _make_image()
        results = await adapter.detect_objects(image, confidence_threshold=0.5)
        assert len(results) == 0


# =========================================================================
# Face Detection
# =========================================================================


class TestGeminiFaceDetection:
    @pytest.mark.asyncio
    async def test_detect_faces(self) -> None:
        adapter = _make_adapter()
        json_response = '[{"label": "face_1", "confidence": 0.95}]'
        adapter._do_gemini_call = AsyncMock(return_value=json_response)
        image = _make_image()
        results = await adapter.detect_faces(image)
        assert len(results) == 1
        assert "face_1" in (results[0].output or "")

    @pytest.mark.asyncio
    async def test_detect_faces_empty(self) -> None:
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(return_value="[]")
        image = _make_image()
        results = await adapter.detect_faces(image)
        assert len(results) == 0


# =========================================================================
# Captioning
# =========================================================================


class TestGeminiCaptioning:
    @pytest.mark.asyncio
    async def test_caption_image(self) -> None:
        adapter = _make_adapter()
        adapter._call_gemini = AsyncMock(return_value="A red square")
        image = _make_image()
        result = await adapter.caption_image(image)
        assert result == "A red square"
        adapter._call_gemini.assert_called_once()

    @pytest.mark.asyncio
    async def test_describe_scene(self) -> None:
        adapter = _make_adapter()
        adapter._call_gemini = AsyncMock(
            return_value="A living room with a couch and a table.",
        )
        image = _make_image()
        result = await adapter.describe_scene(image)
        assert "living room" in result

    @pytest.mark.asyncio
    async def test_understand_ui(self) -> None:
        adapter = _make_adapter()
        adapter._call_gemini = AsyncMock(
            return_value="A login form with email and password fields.",
        )
        image = _make_image()
        result = await adapter.understand_ui(image)
        assert "login" in result


# =========================================================================
# Image Analysis (structured)
# =========================================================================


class TestGeminiImageAnalysis:
    @pytest.mark.asyncio
    async def test_analyze_image_json(self) -> None:
        adapter = _make_adapter()
        json_response = (
            '{"description": "A cat", "objects": ["cat"], '
            '"text": "", "scenes": "indoor"}'
        )
        adapter._call_gemini = AsyncMock(return_value=json_response)
        image = _make_image()
        result = await adapter.analyze_image(image)
        assert result["description"] == "A cat"
        assert "cat" in result["objects"]

    @pytest.mark.asyncio
    async def test_analyze_image_non_json(self) -> None:
        adapter = _make_adapter()
        adapter._call_gemini = AsyncMock(return_value="Just some text")
        image = _make_image()
        result = await adapter.analyze_image(image)
        assert result["description"] == "Just some text"
        assert result["objects"] == []


# =========================================================================
# Timeout
# =========================================================================


class TestGeminiTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises_vision_timeout_error(self) -> None:
        adapter = _make_adapter(timeout=0.01)

        async def slow_call(*args: object, **kwargs: object) -> str:
            await asyncio.sleep(10)
            return "should not reach"

        adapter._do_gemini_call = slow_call
        image = _make_image()
        with pytest.raises(VisionTimeoutError):
            await adapter._call_gemini("test", image, timeout=0.01)

    @pytest.mark.asyncio
    async def test_timeout_retries_before_failing(self) -> None:
        rp = RetryPolicy(max_retries=2, base_delay=0.01)
        adapter = _make_adapter(retry_policy=rp, timeout=0.01)

        async def slow_call(*args: object, **kwargs: object) -> str:
            await asyncio.sleep(10)
            return "slow"

        adapter._do_gemini_call = slow_call
        image = _make_image()
        with pytest.raises(VisionTimeoutError):
            await adapter._call_gemini("test", image, timeout=0.01)


# =========================================================================
# Retry
# =========================================================================


class TestGeminiRetry:
    @pytest.mark.asyncio
    async def test_retry_on_error(self) -> None:
        rp = RetryPolicy(max_retries=2, base_delay=0.01)
        adapter = _make_adapter(retry_policy=rp)

        call_count = 0

        async def fail_then_succeed(*args: object, **kwargs: object) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return "success"

        adapter._do_gemini_call = fail_then_succeed
        image = _make_image()
        result = await adapter._call_gemini("test", image, timeout=5.0)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self) -> None:
        rp = RetryPolicy(max_retries=1, base_delay=0.01)
        adapter = _make_adapter(retry_policy=rp)

        async def always_fail(*args: object, **kwargs: object) -> str:
            raise RuntimeError("permanent error")

        adapter._do_gemini_call = always_fail
        image = _make_image()
        with pytest.raises(VisionProcessingError, match="permanent error"):
            await adapter._call_gemini("test", image, timeout=5.0)


# =========================================================================
# Backoff computation
# =========================================================================


class TestBackoffComputation:
    def test_backoff_basic(self) -> None:
        adapter = _make_adapter(retry_policy=RetryPolicy(
            base_delay=1.0, max_delay=30.0, exponential_base=2.0,
        ))
        assert adapter._compute_backoff(0) == 1.0
        assert adapter._compute_backoff(1) == 2.0
        assert adapter._compute_backoff(2) == 4.0
        assert adapter._compute_backoff(3) == 8.0

    def test_backoff_capped(self) -> None:
        adapter = _make_adapter(retry_policy=RetryPolicy(
            base_delay=1.0, max_delay=5.0, exponential_base=2.0,
        ))
        assert adapter._compute_backoff(10) == 5.0


# =========================================================================
# Error mapping
# =========================================================================


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_load_image_file_not_found(self) -> None:
        adapter = _make_adapter()
        adapter._image_loader.load = AsyncMock(side_effect=VisionLoadError("not found"))
        with pytest.raises(VisionLoadError):
            await adapter.load_image("/nonexistent.png")

    @pytest.mark.asyncio
    async def test_load_image_generic_error(self) -> None:
        adapter = _make_adapter()
        adapter._image_loader.load = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(VisionLoadError):
            await adapter.load_image("/some.png")

    @pytest.mark.asyncio
    async def test_preprocess_error(self) -> None:
        adapter = _make_adapter()
        adapter._image_preprocessor.preprocess = AsyncMock(
            side_effect=RuntimeError("bad image"),
        )
        image = _make_image()
        with pytest.raises(VisionProcessingError):
            await adapter.preprocess(image)

    @pytest.mark.asyncio
    async def test_capture_screen_not_implemented(self) -> None:
        from backend.modules.vision._exceptions import VisionNotImplementedError
        adapter = _make_adapter()
        with pytest.raises(VisionNotImplementedError):
            await adapter.capture_screen()


# =========================================================================
# Close
# =========================================================================


class TestClose:
    @pytest.mark.asyncio
    async def test_close_is_noop(self) -> None:
        adapter = _make_adapter()
        await adapter.close()
        adapter._logger.debug.assert_called_once()


# =========================================================================
# JSON response parsing (module-level helpers)
# =========================================================================


class TestJsonParsing:
    def test_extract_json_array(self) -> None:
        text = 'Here are the objects: [{"label": "car"}]'
        result = _parse_detection_json(text, 0.0)
        assert len(result) == 1
        assert result[0].label == "car"

    def test_extract_json_no_array(self) -> None:
        text = "No objects detected."
        result = _parse_detection_json(text, 0.0)
        assert result == []

    def test_parse_json_invalid(self) -> None:
        result = _parse_detection_json("not json at all", 0.5)
        assert result == []

    def test_parse_json_non_list(self) -> None:
        result = _parse_detection_json('{"label": "car"}', 0.5)
        assert result == []

    def test_parse_json_missing_confidence(self) -> None:
        result = _parse_detection_json('[{"label": "car"}]', 0.0)
        assert len(result) == 1
        assert result[0].confidence == 0.0

    def test_parse_analysis_json(self) -> None:
        response = '{"description": "A scene", "objects": [], "text": "", "scenes": "outdoor"}'
        result = _parse_analysis_response(response)
        assert result["description"] == "A scene"

    def test_parse_analysis_non_json(self) -> None:
        response = "Just a description"
        result = _parse_analysis_response(response)
        assert result["description"] == "Just a description"
        assert result["objects"] == []


# =========================================================================
# Image preprocessing with real PIL
# =========================================================================


class TestImagePreprocessingWithPIL:
    @pytest.mark.asyncio
    async def test_preprocess_real_image(self) -> None:
        from backend.modules.vision._image_preprocessor import ImagePreprocessor
        img = PILImage.new("RGB", (4000, 3000), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image = ImageData(
            source_type="bytes",
            width=4000,
            height=3000,
            format="png",
            data=buf.getvalue(),
        )
        result = await ImagePreprocessor.preprocess(image, max_width=2048, max_height=2048)
        assert result.width <= 2048
        assert result.height <= 2048

    @pytest.mark.asyncio
    async def test_preprocess_rgb_conversion(self) -> None:
        from backend.modules.vision._image_preprocessor import ImagePreprocessor
        img = PILImage.new("L", (100, 100), color=128)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image = ImageData(
            source_type="bytes",
            data=buf.getvalue(),
        )
        result = await ImagePreprocessor.preprocess(image)
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_preprocess_aspect_ratio(self) -> None:
        from backend.modules.vision._image_preprocessor import ImagePreprocessor
        img = PILImage.new("RGB", (2000, 1000), color="green")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image = ImageData(
            source_type="bytes",
            data=buf.getvalue(),
        )
        result = await ImagePreprocessor.preprocess(
            image, max_width=1000, max_height=1000, preserve_aspect_ratio=True,
        )
        assert result.width <= 1000
        assert result.height <= 1000
        ratio = result.width / result.height
        assert abs(ratio - 2.0) < 0.1


# =========================================================================
# Image loading with real PIL
# =========================================================================


class TestImageLoadingWithPIL:
    @pytest.mark.asyncio
    async def test_load_pil_image(self) -> None:
        from backend.modules.vision._image_loader import ImageLoader
        img = PILImage.new("RGB", (50, 50), color="yellow")
        result = await ImageLoader.load(img)
        assert result.source_type == "bytes"
        assert result.width == 50
        assert result.height == 50

    @pytest.mark.asyncio
    async def test_load_valid_png_file(self, tmp_path: Path) -> None:
        from backend.modules.vision._image_loader import ImageLoader
        img = PILImage.new("RGB", (20, 20), color="blue")
        path = tmp_path / "test.png"
        img.save(path)
        result = await ImageLoader.load(str(path))
        assert result.source_type == "file"
        assert result.width == 20
        assert result.height == 20
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_load_valid_jpg_file(self, tmp_path: Path) -> None:
        from backend.modules.vision._image_loader import ImageLoader
        img = PILImage.new("RGB", (20, 20), color="red")
        path = tmp_path / "test.jpg"
        img.save(path)
        result = await ImageLoader.load(str(path))
        assert result.source_type == "file"
        assert result.format == "jpeg"
        assert result.data is not None


# =========================================================================
# _to_pil fallback
# =========================================================================


class TestToPilFallback:
    @pytest.mark.asyncio
    async def test_to_pil_with_data(self) -> None:
        adapter = _make_adapter()
        image = _make_image()
        pil = await adapter._to_pil(image)
        assert pil.size == (10, 10)

    @pytest.mark.asyncio
    async def test_to_pil_no_data_with_path(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        img = PILImage.new("RGB", (30, 30), color="green")
        path = tmp_path / "test.png"
        img.save(path)
        image = ImageData(
            source_type="file",
            source_path=str(path),
        )
        pil = await adapter._to_pil(image)
        assert pil.size == (30, 30)

    @pytest.mark.asyncio
    async def test_to_pil_no_data_no_path(self) -> None:
        adapter = _make_adapter()
        image = ImageData(source_type="bytes")
        pil = await adapter._to_pil(image)
        assert pil.size == (100, 100)


# =========================================================================
# Full VisionExecutor + Gemini adapter integration
# =========================================================================


class TestVisionExecutorWithGemini:
    @pytest.mark.asyncio
    async def test_ocr_success_via_executor(self) -> None:
        from backend.modules.vision._executor import VisionExecutor
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(side_effect=["Hello", "0.9"])
        exe = VisionExecutor(adapter=adapter)
        image = _make_image()
        result = await exe.run_ocr(image)
        assert result.status == "success"
        assert result.output == "Hello"

    @pytest.mark.asyncio
    async def test_ocr_empty_via_executor(self) -> None:
        from backend.modules.vision._executor import VisionExecutor
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(return_value="")
        exe = VisionExecutor(adapter=adapter)
        image = _make_image()
        result = await exe.run_ocr(image)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_detect_objects_via_executor(self) -> None:
        from backend.modules.vision._executor import VisionExecutor
        adapter = _make_adapter()
        json_response = '[{"label": "person", "confidence": 0.9}]'
        adapter._do_gemini_call = AsyncMock(return_value=json_response)
        exe = VisionExecutor(adapter=adapter)
        image = _make_image()
        result = await exe.detect_objects(image)
        assert result.status == "success"
        assert "Detected" in result.output

    @pytest.mark.asyncio
    async def test_detect_faces_via_executor(self) -> None:
        from backend.modules.vision._executor import VisionExecutor
        adapter = _make_adapter()
        json_response = '[{"label": "face_1", "confidence": 0.9}]'
        adapter._do_gemini_call = AsyncMock(return_value=json_response)
        exe = VisionExecutor(adapter=adapter)
        image = _make_image()
        result = await exe.detect_faces(image)
        assert result.status == "success"
        assert "Detected" in result.output


# =========================================================================
# VisionManager + Gemini adapter integration
# =========================================================================


class TestVisionManagerWithGemini:
    @pytest.mark.asyncio
    async def test_ocr_success_via_manager(self) -> None:
        from backend.modules.vision.vision_module import VisionManager
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(side_effect=["Hello World", "0.9"])
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = _make_image()
        result = await mgr.run_ocr(image)
        assert result.status == "success"
        assert result.output == "Hello World"

    @pytest.mark.asyncio
    async def test_detect_objects_via_manager(self) -> None:
        from backend.modules.vision.vision_module import VisionManager
        adapter = _make_adapter()
        json_response = '[{"label": "car", "confidence": 0.85}]'
        adapter._do_gemini_call = AsyncMock(return_value=json_response)
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = _make_image()
        result = await mgr.detect_objects(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_faces_via_manager(self) -> None:
        from backend.modules.vision.vision_module import VisionManager
        adapter = _make_adapter()
        json_response = '[{"label": "face_1", "confidence": 0.92}]'
        adapter._do_gemini_call = AsyncMock(return_value=json_response)
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = _make_image()
        result = await mgr.detect_faces(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_manager_events_emitted(self) -> None:
        from backend.modules.vision.vision_module import VisionManager
        adapter = _make_adapter()
        adapter._do_gemini_call = AsyncMock(side_effect=["OCR text", "0.9"])
        emitted_events: list[tuple[str, dict]] = []

        class FakeEventBus:
            async def emit(self, event_type: str, data: dict) -> None:
                emitted_events.append((event_type, data))

        mgr = VisionManager(adapter=adapter, event_bus=FakeEventBus())
        await mgr.async_init()
        image = _make_image()
        await mgr.run_ocr(image)
        event_names = [e[0] for e in emitted_events]
        assert "vision.ocr.start" in event_names
        assert "vision.ocr.complete" in event_names
