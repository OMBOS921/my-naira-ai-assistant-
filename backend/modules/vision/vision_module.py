"""
VisionManager — the single public class for the vision module.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §15 — Tool contracts.
21_System_Contracts.md §4.2 — ModuleInterface protocol.

Mirrors LLMManager pattern: providers dict, active_provider,
fallback_chain, register_provider().
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.vision._executor import VisionExecutor
from backend.modules.vision._face_detection import FaceDetection
from backend.modules.vision._image_loader import ImageLoader
from backend.modules.vision._image_preprocessor import ImagePreprocessor
from backend.modules.vision._local_adapter import LocalVisionAdapter
from backend.modules.vision._object_detection import ObjectDetection
from backend.modules.vision._ocr import OCR
from backend.modules.vision._screen_capture import ScreenCapture
from backend.modules.vision._screen_understanding import ScreenUnderstanding
from backend.modules.vision._types import ImageData
from backend.modules.vision.ports.vision_port import VisionPort
from backend.types import ToolResult

_LOG = logging.getLogger("naira.vision")


class VisionManager:
    """Central vision manager — image loading, OCR, detection, screen capture.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Mirrors ``LLMManager`` pattern: supports multiple registered
    providers, an active provider, and a fallback chain.

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        ``EventBus`` instance for event emission.
    capability_manager : object | None
        ``CapabilityManager`` instance for capability registration.
    tool_manager : object | None
        ``ToolManager`` instance for tool registration.
    adapter : VisionPort | None
        Legacy single adapter parameter (backward compat).
    providers : dict[str, VisionPort] | None
        Registered vision providers keyed by name.
    active_provider_name : str | None
        Name of the active provider (from VisionConfig).
    fallback_chain : tuple[str, ...] | None
        Ordered fallback chain of provider names.
    default_timeout : float
        Default timeout for vision operations (default 30.0).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        tool_manager: object | None = None,
        adapter: VisionPort | None = None,
        providers: dict[str, VisionPort] | None = None,
        active_provider_name: str | None = None,
        fallback_chain: tuple[str, ...] | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._degraded: bool = False
        self._default_timeout = default_timeout

        # Provider registry (mirrors LLMManager pattern)
        self._providers: dict[str, VisionPort] = providers or {}
        self._active_provider_name = active_provider_name
        self._fallback_chain = fallback_chain or ("gemini",)

        # Resolve active provider — prefer providers dict, fall back to adapter
        if self._providers and self._active_provider_name:
            self._active_provider = (
                self._providers.get(self._active_provider_name)
                or self._resolve_fallback()
                or LocalVisionAdapter(logger=logger)
            )
        else:
            self._active_provider = adapter or LocalVisionAdapter(logger=logger)

        # Internal components
        self._executor = VisionExecutor(
            adapter=self._active_provider,
            default_timeout=default_timeout,
            logger=logger,
        )
        self._image_loader = ImageLoader()
        self._image_preprocessor = ImagePreprocessor()
        self._ocr = OCR(logger=logger)
        self._object_detection = ObjectDetection(logger=logger)
        self._face_detection = FaceDetection(logger=logger)
        self._screen_capture = ScreenCapture(logger=logger)
        self._screen_capture_real = ScreenCapture(logger=logger)
        self._screen_understanding = ScreenUnderstanding(
            screen_capture=self._screen_capture_real,
            vision_provider=self._active_provider,
            logger=self._logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the vision module.

        Registers the ``vision`` capability and system tools for
        image loading, OCR, detection, and screen capture.
        """
        self._register_capability()
        self._register_tools()
        provider_name = self._active_provider_name or "local"
        adapter_name = type(self._active_provider).__name__
        available = self._executor.is_available
        self._logger.info(
            "Vision manager initialised — adapter=%s provider_name=%s "
            "adapter_available=%s fallback_chain=%s",
            adapter_name,
            provider_name,
            available,
            self._fallback_chain,
        )

    async def async_shutdown(self) -> None:
        """Release vision adapter resources."""
        try:
            await self._active_provider.close()
        except Exception as exc:
            self._logger.warning("Error closing vision provider: %s", exc)
        self._degraded = False
        self._logger.info("Vision manager shut down.")

    def degrade(self) -> None:
        """Mark the module as degraded."""
        self._degraded = True
        self._logger.warning("Vision manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Provider management  (mirrors LLMManager pattern)
    # ------------------------------------------------------------------

    def register_provider(self, name: str, provider: VisionPort) -> None:
        """Register a vision provider under the given name."""
        self._providers[name] = provider
        self._logger.debug("Registered vision provider: %s", name)

    @property
    def active_provider_name(self) -> str | None:
        return self._active_provider_name

    @property
    def providers(self) -> dict[str, VisionPort]:
        return dict(self._providers)

    @property
    def fallback_chain(self) -> tuple[str, ...]:
        return self._fallback_chain

    def _resolve_fallback(self) -> VisionPort | None:
        """Walk the fallback chain to find an available provider."""
        for name in self._fallback_chain:
            provider = self._providers.get(name)
            if provider is not None and provider.is_available:
                self._logger.info(
                    "Fallback provider selected: %s", name,
                )
                self._active_provider_name = name
                return provider
        return None

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def load_image(
        self,
        source: str | bytes,
        timeout: float | None = None,
    ) -> ToolResult:
        """Load an image from a file path, URL, or raw bytes."""
        self._ensure_not_degraded()
        await self._emit_event_async("vision.load.start", {
            "source": self._sanitise_source(source),
        })
        result = await self._executor.load_image(source, timeout=timeout)
        if result.status == "error":
            await self._emit_event_async("vision.error", {
                "operation": "load", "status": result.status,
            })
        await self._emit_event_async("vision.load.complete", {
            "status": result.status,
        })
        return result

    async def run_ocr(
        self,
        image: ImageData,
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        """Run OCR on an image."""
        self._ensure_not_degraded()
        await self._emit_event_async("vision.ocr.start", {
            "language": language,
        })
        result = await self._executor.run_ocr(
            image, language=language, timeout=timeout,
        )
        if result.status == "error":
            await self._emit_event_async("vision.error", {
                "operation": "ocr", "status": result.status,
            })
        await self._emit_event_async("vision.ocr.complete", {
            "status": result.status,
        })
        return result

    async def detect_objects(
        self,
        image: ImageData,
        confidence_threshold: float = 0.5,
        timeout: float | None = None,
    ) -> ToolResult:
        """Run object detection on an image."""
        self._ensure_not_degraded()
        await self._emit_event_async("vision.detect.start", {
            "confidence_threshold": confidence_threshold,
        })
        result = await self._executor.detect_objects(
            image, confidence_threshold=confidence_threshold, timeout=timeout,
        )
        if result.status == "error":
            await self._emit_event_async("vision.error", {
                "operation": "detect", "status": result.status,
            })
        await self._emit_event_async("vision.detect.complete", {
            "status": result.status,
        })
        return result

    async def detect_faces(
        self,
        image: ImageData,
        timeout: float | None = None,
    ) -> ToolResult:
        """Run face detection on an image."""
        self._ensure_not_degraded()
        await self._emit_event_async("vision.face.start", {})
        result = await self._executor.detect_faces(image, timeout=timeout)
        if result.status == "error":
            await self._emit_event_async("vision.error", {
                "operation": "face", "status": result.status,
            })
        await self._emit_event_async("vision.face.complete", {
            "status": result.status,
        })
        return result

    async def capture_screen(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        """Capture the current screen."""
        self._ensure_not_degraded()
        await self._emit_event_async("vision.capture.start", {})
        result = await self._executor.capture_screen(timeout=timeout)
        if result.status == "error":
            await self._emit_event_async("vision.error", {
                "operation": "capture", "status": result.status,
            })
        await self._emit_event_async("vision.capture.complete", {
            "status": result.status,
        })
        return result

    async def understand_screen(
        self,
        question: str | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        """Understand current screen content or answer a question about it."""
        self._ensure_not_degraded()
        to = timeout or self._default_timeout
        res = await self._screen_understanding.understand_screen(
            question=question, timeout=to
        )
        output = res.get("answer") or res.get("description") or ""
        return ToolResult(status="success", output=output)

    async def understand_ui(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        """Analyze UI interactive elements on current screen."""
        self._ensure_not_degraded()
        to = timeout or self._default_timeout
        res = await self._screen_understanding.understand_ui(timeout=to)
        return ToolResult(status="success", output=res.get("raw_analysis", ""))

    async def read_screen_text(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        """Run OCR on current screen."""
        self._ensure_not_degraded()
        to = timeout or self._default_timeout
        res = await self._screen_understanding.read_screen_text(timeout=to)
        return ToolResult(status="success", output=res.get("text", ""))

    async def capture_and_save(
        self,
        output_path: str,
        timeout: float | None = None,
    ) -> ToolResult:
        """Capture screen and save image to output_path."""
        self._ensure_not_degraded()
        to = timeout or self._default_timeout
        img_data = await self._screen_capture_real.capture(timeout=to)
        if img_data.data:
            from pathlib import Path
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(img_data.data)
            return ToolResult(
                status="success", output=f"Saved screenshot to {output_path}"
            )
        return ToolResult(status="error", error="No image data captured")

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Return ``True`` if a real vision adapter is wired."""
        return self._executor.is_available

    @property
    def image_loader(self) -> ImageLoader:
        """Expose the image loader."""
        return self._image_loader

    @property
    def preprocessor(self) -> ImagePreprocessor:
        """Expose the image preprocessor."""
        return self._image_preprocessor

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_capability(self) -> None:
        """Register the ``vision`` capability if a manager is available."""
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register", None)
            if register_cap is not None:
                from backend.modules.capability.capability import Capability
                register_cap(Capability(
                    name="vision",
                    version="0.1.0",
                    dependencies=("llm",),
                ))

    def _register_tools(self) -> None:
        """Register vision tools with the ToolManager."""
        if self._tool_manager is not None:
            register = getattr(self._tool_manager, "register_tool", None)
            if register is not None:
                from backend.modules.tools import ToolDefinition

                register(
                    ToolDefinition(
                        name="vision_load_image",
                        description="Load an image from a file path, URL, or raw bytes",
                        parameters={
                            "type": "object",
                            "properties": {
                                "source": {
                                    "type": "string",
                                    "description": "File path or URL to load the image from",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["source"],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_load_image_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_run_ocr",
                        description="Extract text from an image using OCR",
                        parameters={
                            "type": "object",
                            "properties": {
                                "image_source": {
                                    "type": "string",
                                    "description": "File path or URL of the image",
                                },
                                "language": {
                                    "type": "string",
                                    "description": "Language hint (default 'en')",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["image_source"],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_run_ocr_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_detect_objects",
                        description="Detect objects in an image",
                        parameters={
                            "type": "object",
                            "properties": {
                                "image_source": {
                                    "type": "string",
                                    "description": "File path or URL of the image",
                                },
                                "confidence_threshold": {
                                    "type": "number",
                                    "description": "Minimum confidence (default 0.5)",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["image_source"],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_detect_objects_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_detect_faces",
                        description="Detect faces in an image",
                        parameters={
                            "type": "object",
                            "properties": {
                                "image_source": {
                                    "type": "string",
                                    "description": "File path or URL of the image",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["image_source"],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_detect_faces_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_capture_screen",
                        description="Capture the current screen",
                        parameters={
                            "type": "object",
                            "properties": {
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": [],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_capture_screen_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_understand_screen",
                        description="Understand current screen content or answer a question about it",
                        parameters={
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "Optional question about the screen content",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": [],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_understand_screen_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_understand_ui",
                        description="Analyze UI interactive elements on current screen",
                        parameters={
                            "type": "object",
                            "properties": {
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": [],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_understand_ui_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_read_screen_text",
                        description="Run OCR on current screen",
                        parameters={
                            "type": "object",
                            "properties": {
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": [],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_read_screen_text_tool,
                )

                register(
                    ToolDefinition(
                        name="vision_capture_and_save",
                        description="Capture screen and save image to output_path",
                        parameters={
                            "type": "object",
                            "properties": {
                                "output_path": {
                                    "type": "string",
                                    "description": "File path to save the screenshot",
                                },
                                "timeout": {
                                    "type": "number",
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["output_path"],
                        },
                        category="vision",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_capture_and_save_tool,
                )

    async def _handle_load_image_tool(
        self,
        source: str,
        timeout: float | None = None,
    ) -> ToolResult:
        return await self.load_image(source, timeout=timeout)

    async def _handle_run_ocr_tool(
        self,
        image_source: str,
        language: str = "en",
        timeout: float | None = None,
    ) -> ToolResult:
        load_result = await self.load_image(image_source, timeout=timeout)
        if load_result.status != "success":
            return load_result
        image = ImageData(
            source_type="file",
            source_path=image_source,
        )
        return await self.run_ocr(image, language=language, timeout=timeout)

    async def _handle_detect_objects_tool(
        self,
        image_source: str,
        confidence_threshold: float = 0.5,
        timeout: float | None = None,
    ) -> ToolResult:
        load_result = await self.load_image(image_source, timeout=timeout)
        if load_result.status != "success":
            return load_result
        image = ImageData(
            source_type="file",
            source_path=image_source,
        )
        return await self.detect_objects(
            image, confidence_threshold=confidence_threshold, timeout=timeout,
        )

    async def _handle_detect_faces_tool(
        self,
        image_source: str,
        timeout: float | None = None,
    ) -> ToolResult:
        load_result = await self.load_image(image_source, timeout=timeout)
        if load_result.status != "success":
            return load_result
        image = ImageData(
            source_type="file",
            source_path=image_source,
        )
        return await self.detect_faces(image, timeout=timeout)

    async def _handle_capture_screen_tool(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        return await self.capture_screen(timeout=timeout)

    async def _handle_understand_screen_tool(
        self,
        question: str | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        return await self.understand_screen(question=question, timeout=timeout)

    async def _handle_understand_ui_tool(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        return await self.understand_ui(timeout=timeout)

    async def _handle_read_screen_text_tool(
        self,
        timeout: float | None = None,
    ) -> ToolResult:
        return await self.read_screen_text(timeout=timeout)

    async def _handle_capture_and_save_tool(
        self,
        output_path: str,
        timeout: float | None = None,
    ) -> ToolResult:
        return await self.capture_and_save(output_path, timeout=timeout)

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "VisionManager is degraded",
                context={"module": "vision"},
            )

    def _sanitise_source(self, source: str | bytes) -> str:
        if isinstance(source, bytes):
            return f"bytes ({len(source)} bytes)"
        return str(source)

    def _emit_event_sync(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(event_type, data))
            except RuntimeError:
                self._logger.debug("No running loop — event not emitted: %s", event_type)

    async def _emit_event_async(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)
