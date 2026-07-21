"""Comprehensive tests for the vision module.

Covers:
- ImageData, OCRResult, Detection, VisionResult dataclasses
- ImageLoader (file, bytes, url, format detection, file-not-found)
- ImagePreprocessor (resize limits, passthrough)
- OCR placeholder (empty result)
- ObjectDetection placeholder (empty result)
- FaceDetection placeholder (empty result)
- ScreenCapture placeholder (raises VisionNotImplementedError, is_available=False)
- LocalVisionAdapter (is_available=False, load/preprocess work, ocr/detect/capture raise)
- VisionExecutor (load, preprocess, ocr, detect_objects, detect_faces, capture_screen
  with timeout/error isolation)
- VisionManager (ModuleInterface lifecycle, load_image, run_ocr, detect_objects,
  detect_faces, capture_screen, degraded mode, event emission)
- VisionPort ABC
- ModuleInterface protocol conformance
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.vision import (
    OCR,
    Detection,
    FaceDetection,
    ImageData,
    ImageLoader,
    ImagePreprocessor,
    LocalVisionAdapter,
    ObjectDetection,
    OCRResult,
    ScreenCapture,
    VisionExecutor,
    VisionManager,
    VisionPort,
    VisionResult,
)
from backend.modules.vision._exceptions import (
    VisionLoadError,
    VisionNotImplementedError,
)
from backend.types import ModuleInterface

# =========================================================================
# ImageData, OCRResult, Detection, VisionResult
# =========================================================================


class TestImageData:
    def test_minimal(self) -> None:
        data = ImageData(source_type="file")
        assert data.source_type == "file"
        assert data.source_path is None
        assert data.width == 0
        assert data.height == 0
        assert data.format == "unknown"
        assert data.size_bytes == 0
        assert data.data is None

    def test_all_fields(self) -> None:
        data = ImageData(
            source_type="bytes",
            source_path=None,
            width=1920,
            height=1080,
            format="png",
            size_bytes=65536,
            data=b"fake-image-data",
        )
        assert data.width == 1920
        assert data.height == 1080
        assert data.format == "png"
        assert data.size_bytes == 65536
        assert data.data == b"fake-image-data"

    def test_frozen(self) -> None:
        data = ImageData(source_type="file", source_path="/tmp/test.png")
        with pytest.raises(AttributeError):
            data.source_type = "bytes"  # type: ignore[misc]


class TestOCRResult:
    def test_defaults(self) -> None:
        r = OCRResult()
        assert r.text == ""
        assert r.confidence == 0.0
        assert r.language == "en"
        assert r.bounding_boxes == ()

    def test_all_fields(self) -> None:
        r = OCRResult(
            text="Hello World",
            confidence=0.95,
            language="en",
            bounding_boxes=((10.0, 20.0, 100.0, 50.0),),
        )
        assert r.text == "Hello World"
        assert r.confidence == 0.95
        assert len(r.bounding_boxes) == 1


class TestDetection:
    def test_minimal(self) -> None:
        d = Detection(label="person")
        assert d.label == "person"
        assert d.confidence == 0.0
        assert d.bbox == (0.0, 0.0, 0.0, 0.0)

    def test_all_fields(self) -> None:
        d = Detection(label="car", confidence=0.85, bbox=(10.0, 20.0, 200.0, 150.0))
        assert d.label == "car"
        assert d.confidence == 0.85
        assert d.bbox == (10.0, 20.0, 200.0, 150.0)


class TestVisionResult:
    def test_defaults(self) -> None:
        r = VisionResult()
        assert r.status == "success"
        assert r.output is None
        assert r.error is None
        assert r.image_data is None
        assert r.objects == ()
        assert r.faces == ()
        assert r.duration_ms == 0.0

    def test_with_detections(self) -> None:
        r = VisionResult(
            status="success",
            output="Detected 2 objects",
            objects=(
                Detection(label="person", confidence=0.9),
                Detection(label="car", confidence=0.8),
            ),
            duration_ms=150.0,
        )
        assert r.status == "success"
        assert len(r.objects) == 2
        assert r.duration_ms == 150.0

    def test_frozen(self) -> None:
        r = VisionResult()
        with pytest.raises(AttributeError):
            r.status = "error"  # type: ignore[misc]


# =========================================================================
# ImageLoader
# =========================================================================


class TestImageLoader:
    @pytest.mark.asyncio
    async def test_load_bytes(self) -> None:
        data = await ImageLoader.load(b"fake-bytes")
        assert data.source_type == "bytes"
        assert data.size_bytes == 10

    @pytest.mark.asyncio
    async def test_load_url(self) -> None:
        data = await ImageLoader.load("https://example.com/image.png")
        assert data.source_type == "url"
        assert data.source_path == "https://example.com/image.png"

    @pytest.mark.asyncio
    async def test_load_file_not_found(self) -> None:
        with pytest.raises(VisionLoadError, match="not found"):
            await ImageLoader.load("/nonexistent/image.png")

    @pytest.mark.asyncio
    async def test_load_file_unsupported_format(self, tmp_path: Path) -> None:
        p = tmp_path / "test.txt"
        p.write_text("not an image")
        with pytest.raises(VisionLoadError, match="(?i)unsupported"):
            await ImageLoader.load(str(p))

    @pytest.mark.asyncio
    async def test_load_file_valid(self, tmp_path: Path) -> None:
        p = tmp_path / "test.png"
        p.write_bytes(b"fake-png-data")
        data = await ImageLoader.load(str(p))
        assert data.source_type == "file"
        assert data.format == "png"
        assert data.size_bytes > 0

    @pytest.mark.asyncio
    async def test_detect_format_jpg(self) -> None:
        assert ImageLoader._detect_format(".jpg") == "jpeg"
        assert ImageLoader._detect_format(".jpeg") == "jpeg"
        assert ImageLoader._detect_format(".PNG") == "png"
        assert ImageLoader._detect_format(".webp") == "webp"
        assert ImageLoader._detect_format(".gif") == "gif"
        assert ImageLoader._detect_format(".bmp") == "bmp"
        assert ImageLoader._detect_format(".unknown") == "unknown"


# =========================================================================
# ImagePreprocessor
# =========================================================================


class TestImagePreprocessor:
    @pytest.mark.asyncio
    async def test_preprocess_passthrough(self) -> None:
        source = ImageData(source_type="file", source_path="/tmp/test.png")
        result = await ImagePreprocessor.preprocess(source)
        assert result.source_type == "file"
        assert result.source_path == "/tmp/test.png"

    @pytest.mark.asyncio
    async def test_preprocess_with_dimension_limits(self) -> None:
        source = ImageData(
            source_type="file",
            source_path="/tmp/test.png",
            width=4000,
            height=3000,
        )
        result = await ImagePreprocessor.preprocess(source, max_width=2048, max_height=2048)
        assert result.width == 2048
        assert result.height == 2048

    @pytest.mark.asyncio
    async def test_preprocess_no_limits_preserves_dims(self) -> None:
        source = ImageData(
            source_type="file",
            source_path="/tmp/test.png",
            width=800,
            height=600,
        )
        result = await ImagePreprocessor.preprocess(source)
        assert result.width == 800
        assert result.height == 600


# =========================================================================
# OCR placeholder
# =========================================================================


class TestOCR:
    @pytest.mark.asyncio
    async def test_ocr_returns_empty(self) -> None:
        ocr = OCR()
        image = ImageData(source_type="file", source_path="/tmp/test.png")
        result = await ocr.run(image)
        assert result.text == ""
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_ocr_with_language_hint(self) -> None:
        ocr = OCR()
        image = ImageData(source_type="bytes", data=b"test")
        result = await ocr.run(image, language="fr")
        assert result.language == "fr"


# =========================================================================
# ObjectDetection placeholder
# =========================================================================


class TestObjectDetection:
    @pytest.mark.asyncio
    async def test_detect_returns_empty(self) -> None:
        detector = ObjectDetection()
        image = ImageData(source_type="file", source_path="/tmp/test.png")
        result = await detector.detect(image)
        assert result == ()

    @pytest.mark.asyncio
    async def test_detect_with_confidence_threshold(self) -> None:
        detector = ObjectDetection()
        image = ImageData(source_type="bytes", data=b"test")
        result = await detector.detect(image, confidence_threshold=0.8)
        assert result == ()


# =========================================================================
# FaceDetection placeholder
# =========================================================================


class TestFaceDetection:
    @pytest.mark.asyncio
    async def test_detect_returns_empty(self) -> None:
        detector = FaceDetection()
        image = ImageData(source_type="file", source_path="/tmp/test.png")
        result = await detector.detect(image)
        assert result == ()


# =========================================================================
# ScreenCapture placeholder
# =========================================================================


class TestScreenCapture:
    def test_is_available_false(self) -> None:
        sc = ScreenCapture()
        assert sc.is_available is False

    @pytest.mark.asyncio
    async def test_capture_raises(self) -> None:
        sc = ScreenCapture()
        with pytest.raises(VisionNotImplementedError):
            await sc.capture()


# =========================================================================
# LocalVisionAdapter
# =========================================================================


class TestLocalVisionAdapter:
    def test_is_available_false(self) -> None:
        adapter = LocalVisionAdapter()
        assert adapter.is_available is False

    @pytest.mark.asyncio
    async def test_load_image_bytes(self) -> None:
        adapter = LocalVisionAdapter()
        data = await adapter.load_image(b"test")
        assert data.source_type == "bytes"

    @pytest.mark.asyncio
    async def test_preprocess(self) -> None:
        adapter = LocalVisionAdapter()
        source = ImageData(source_type="file", width=800, height=600)
        result = await adapter.preprocess(source, max_width=400, max_height=400)
        assert result.width == 400

    @pytest.mark.asyncio
    async def test_run_ocr_raises(self) -> None:
        adapter = LocalVisionAdapter()
        image = ImageData(source_type="bytes", data=b"test")
        with pytest.raises(VisionNotImplementedError):
            await adapter.run_ocr(image)

    @pytest.mark.asyncio
    async def test_detect_objects_raises(self) -> None:
        adapter = LocalVisionAdapter()
        image = ImageData(source_type="bytes", data=b"test")
        with pytest.raises(VisionNotImplementedError):
            await adapter.detect_objects(image)

    @pytest.mark.asyncio
    async def test_detect_faces_raises(self) -> None:
        adapter = LocalVisionAdapter()
        image = ImageData(source_type="bytes", data=b"test")
        with pytest.raises(VisionNotImplementedError):
            await adapter.detect_faces(image)

    @pytest.mark.asyncio
    async def test_capture_screen_raises(self) -> None:
        adapter = LocalVisionAdapter()
        with pytest.raises(VisionNotImplementedError):
            await adapter.capture_screen()

    @pytest.mark.asyncio
    async def test_close_is_noop(self) -> None:
        adapter = LocalVisionAdapter()
        await adapter.close()


# =========================================================================
# VisionExecutor
# =========================================================================


class _MockVisionAdapter:
    """Test double that implements VisionPort with controllable behaviour."""

    def __init__(
        self,
        available: bool = True,
        load_image_result: ImageData | None = None,
        preprocess_result: ImageData | None = None,
        ocr_result: OCRResult | None = None,
        objects_result: tuple[VisionResult, ...] | None = None,
        faces_result: tuple[VisionResult, ...] | None = None,
        capture_result: ImageData | None = None,
        raise_on: str | None = None,
    ) -> None:
        self._available = available
        self._load_image_result = load_image_result
        self._preprocess_result = preprocess_result
        self._ocr_result = ocr_result
        self._objects_result = objects_result
        self._faces_result = faces_result
        self._capture_result = capture_result
        self._raise_on = raise_on

    @property
    def is_available(self) -> bool:
        return self._available

    async def load_image(self, source: str | bytes, *, timeout: float = 30.0) -> ImageData:
        if self._raise_on == "load":
            raise VisionNotImplementedError()
        if self._load_image_result is not None:
            return self._load_image_result
        return ImageData(source_type="file", source_path=str(source), format="png", size_bytes=1024)

    async def preprocess(
        self,
        image: ImageData,
        *,
        max_width: int = 0,
        max_height: int = 0,
        preserve_aspect_ratio: bool = True,
        timeout: float = 30.0,
    ) -> ImageData:
        if self._raise_on == "preprocess":
            raise VisionNotImplementedError()
        if self._preprocess_result is not None:
            return self._preprocess_result
        return ImageData(
            source_type=image.source_type,
            width=min(image.width, max_width) if max_width > 0 else image.width,
            height=min(image.height, max_height) if max_height > 0 else image.height,
        )

    async def run_ocr(
        self,
        image: ImageData,
        *,
        language: str = "en",
        timeout: float = 30.0,
    ) -> OCRResult:
        if self._raise_on == "ocr":
            raise VisionNotImplementedError()
        if self._ocr_result is not None:
            return self._ocr_result
        return OCRResult(text="Extracted text", confidence=0.95, language=language)

    async def detect_objects(
        self,
        image: ImageData,
        *,
        confidence_threshold: float = 0.5,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        if self._raise_on == "objects":
            raise VisionNotImplementedError()
        if self._objects_result is not None:
            return self._objects_result
        return (
            VisionResult(status="success", output="person"),
            VisionResult(status="success", output="car"),
        )

    async def detect_faces(
        self,
        image: ImageData,
        *,
        timeout: float = 30.0,
    ) -> tuple[VisionResult, ...]:
        if self._raise_on == "faces":
            raise VisionNotImplementedError()
        if self._faces_result is not None:
            return self._faces_result
        return (VisionResult(status="success", output="face_1"),)

    async def capture_screen(self, *, timeout: float = 30.0) -> ImageData:
        if self._raise_on == "capture":
            raise VisionNotImplementedError()
        if self._capture_result is not None:
            return self._capture_result
        return ImageData(source_type="screen_capture", width=1920, height=1080, size_bytes=4096)

    async def close(self) -> None:
        pass


class TestVisionExecutor:
    @pytest.mark.asyncio
    async def test_load_image_success(self) -> None:
        adapter = _MockVisionAdapter()
        exe = VisionExecutor(adapter=adapter)
        result = await exe.load_image("/tmp/test.png")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_load_image_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="load")
        exe = VisionExecutor(adapter=adapter)
        result = await exe.load_image("/tmp/test.png")
        assert result.status == "error"
        assert "not configured" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_preprocess_success(self) -> None:
        adapter = _MockVisionAdapter()
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="file", width=4000, height=3000)
        result = await exe.preprocess(image, max_width=2048, max_height=2048)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_ocr_success(self) -> None:
        adapter = _MockVisionAdapter()
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.run_ocr(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_ocr_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="ocr")
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.run_ocr(image)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_ocr_empty_text_returns_error(self) -> None:
        adapter = _MockVisionAdapter(ocr_result=OCRResult(text=""))
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.run_ocr(image)
        assert result.status == "error"
        assert "No text" in (result.error or "")

    @pytest.mark.asyncio
    async def test_detect_objects_success(self) -> None:
        adapter = _MockVisionAdapter()
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.detect_objects(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_objects_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="objects")
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.detect_objects(image)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_detect_objects_empty_returns_error(self) -> None:
        adapter = _MockVisionAdapter(objects_result=())
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.detect_objects(image)
        assert result.status == "error"
        assert "No objects" in (result.error or "")

    @pytest.mark.asyncio
    async def test_detect_faces_success(self) -> None:
        adapter = _MockVisionAdapter()
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.detect_faces(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_faces_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="faces")
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.detect_faces(image)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_detect_faces_empty_returns_error(self) -> None:
        adapter = _MockVisionAdapter(faces_result=())
        exe = VisionExecutor(adapter=adapter)
        image = ImageData(source_type="bytes", data=b"test")
        result = await exe.detect_faces(image)
        assert result.status == "error"
        assert "No faces" in (result.error or "")

    @pytest.mark.asyncio
    async def test_capture_screen_success(self) -> None:
        adapter = _MockVisionAdapter()
        exe = VisionExecutor(adapter=adapter)
        result = await exe.capture_screen()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_capture_screen_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="capture")
        exe = VisionExecutor(adapter=adapter)
        result = await exe.capture_screen()
        assert result.status == "error"

    def test_is_available_true(self) -> None:
        adapter = _MockVisionAdapter(available=True)
        exe = VisionExecutor(adapter=adapter)
        assert exe.is_available is True

    def test_is_available_false(self) -> None:
        adapter = LocalVisionAdapter()
        exe = VisionExecutor(adapter=adapter)
        assert exe.is_available is False


# =========================================================================
# VisionManager — ModuleInterface lifecycle
# =========================================================================


class TestVisionManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = VisionManager()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_async_init_sets_up(self) -> None:
        mgr = VisionManager()
        await mgr.async_init()
        assert mgr.degraded is False
        assert mgr.is_available is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        mgr = VisionManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = VisionManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = VisionManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = VisionManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = MagicMock()
        mgr = VisionManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_with_adapter_injection(self) -> None:
        adapter = LocalVisionAdapter()
        mgr = VisionManager(adapter=adapter)
        assert mgr._active_provider is adapter

    @pytest.mark.asyncio
    async def test_image_loader_property(self) -> None:
        mgr = VisionManager()
        assert mgr.image_loader is not None

    @pytest.mark.asyncio
    async def test_preprocessor_property(self) -> None:
        mgr = VisionManager()
        assert mgr.preprocessor is not None


# =========================================================================
# VisionManager — provider routing (LLMManager pattern)
# =========================================================================


class TestVisionManagerProviderRouting:
    def test_register_provider(self) -> None:
        adapter = LocalVisionAdapter()
        mgr = VisionManager()
        mgr.register_provider("local", adapter)
        assert "local" in mgr.providers
        assert mgr.providers["local"] is adapter

    def test_active_provider_name(self) -> None:
        mgr = VisionManager(active_provider_name="gemini")
        assert mgr.active_provider_name == "gemini"

    def test_fallback_chain(self) -> None:
        mgr = VisionManager(fallback_chain=("gemini", "local"))
        assert mgr.fallback_chain == ("gemini", "local")

    def test_default_fallback_chain(self) -> None:
        mgr = VisionManager()
        assert mgr.fallback_chain == ("gemini",)

    @pytest.mark.asyncio
    async def test_providers_dict_injection(self) -> None:
        adapter = _MockVisionAdapter(available=True)
        mgr = VisionManager(
            providers={"mock": adapter},
            active_provider_name="mock",
            fallback_chain=("mock",),
        )
        await mgr.async_init()
        assert mgr.is_available is True

    @pytest.mark.asyncio
    async def test_fallback_to_available_provider(self) -> None:
        adapter = _MockVisionAdapter(available=True)
        mgr = VisionManager(
            providers={"mock": adapter},
            active_provider_name="nonexistent",
            fallback_chain=("nonexistent", "mock"),
        )
        await mgr.async_init()
        assert mgr.is_available is True
        assert mgr.active_provider_name == "mock"

    @pytest.mark.asyncio
    async def test_no_available_provider_uses_local(self) -> None:
        mgr = VisionManager(
            providers={},
            active_provider_name="nonexistent",
            fallback_chain=("nonexistent",),
        )
        await mgr.async_init()
        assert mgr.is_available is False


# =========================================================================
# VisionManager — load_image
# =========================================================================


class TestVisionManagerLoadImage:
    @pytest.mark.asyncio
    async def test_load_image_bytes(self) -> None:
        adapter = _MockVisionAdapter()
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.load_image(b"test")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_load_image_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="load")
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.load_image("/tmp/test.png")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_load_image_degraded_raises(self) -> None:
        mgr = VisionManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.load_image("/tmp/test.png")


# =========================================================================
# VisionManager — run_ocr
# =========================================================================


class TestVisionManagerOCR:
    @pytest.mark.asyncio
    async def test_ocr_success(self) -> None:
        adapter = _MockVisionAdapter()
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = ImageData(source_type="bytes", data=b"test")
        result = await mgr.run_ocr(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_ocr_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="ocr")
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = ImageData(source_type="bytes", data=b"test")
        result = await mgr.run_ocr(image)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_ocr_degraded_raises(self) -> None:
        mgr = VisionManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.run_ocr(ImageData(source_type="bytes", data=b"test"))


# =========================================================================
# VisionManager — detect_objects
# =========================================================================


class TestVisionManagerDetectObjects:
    @pytest.mark.asyncio
    async def test_detect_objects_success(self) -> None:
        adapter = _MockVisionAdapter()
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = ImageData(source_type="bytes", data=b"test")
        result = await mgr.detect_objects(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_objects_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="objects")
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = ImageData(source_type="bytes", data=b"test")
        result = await mgr.detect_objects(image)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_detect_objects_degraded_raises(self) -> None:
        mgr = VisionManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.detect_objects(ImageData(source_type="bytes", data=b"test"))


# =========================================================================
# VisionManager — detect_faces
# =========================================================================


class TestVisionManagerDetectFaces:
    @pytest.mark.asyncio
    async def test_detect_faces_success(self) -> None:
        adapter = _MockVisionAdapter()
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = ImageData(source_type="bytes", data=b"test")
        result = await mgr.detect_faces(image)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_detect_faces_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="faces")
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        image = ImageData(source_type="bytes", data=b"test")
        result = await mgr.detect_faces(image)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_detect_faces_degraded_raises(self) -> None:
        mgr = VisionManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.detect_faces(ImageData(source_type="bytes", data=b"test"))


# =========================================================================
# VisionManager — capture_screen
# =========================================================================


class TestVisionManagerCaptureScreen:
    @pytest.mark.asyncio
    async def test_capture_screen_success(self) -> None:
        adapter = _MockVisionAdapter()
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.capture_screen()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_capture_screen_not_implemented(self) -> None:
        adapter = _MockVisionAdapter(raise_on="capture")
        mgr = VisionManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.capture_screen()
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_capture_screen_degraded_raises(self) -> None:
        mgr = VisionManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.capture_screen()


# =========================================================================
# VisionManager — is_available
# =========================================================================


class TestVisionManagerIsAvailable:
    def test_default_is_false(self) -> None:
        mgr = VisionManager()
        assert mgr.is_available is False

    def test_with_real_adapter(self) -> None:
        adapter = _MockVisionAdapter(available=True)
        mgr = VisionManager(adapter=adapter)
        assert mgr.is_available is True


# =========================================================================
# VisionPort — ABC
# =========================================================================


class TestVisionPortAbc:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            VisionPort()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_adapter(self) -> None:
        adapter = LocalVisionAdapter()
        assert isinstance(adapter, VisionPort)
        assert adapter.is_available is False


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_vision_manager_conforms_to_protocol(self) -> None:
        assert isinstance(VisionManager(), ModuleInterface)

    def test_vision_manager_has_required_methods(self) -> None:
        mgr = VisionManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
