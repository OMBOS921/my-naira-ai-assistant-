"""ImageLoader — image loading and metadata extraction.

Supports local file paths, raw bytes, PIL Images, PNG, JPG, JPEG, WEBP.
Uses Pillow for actual image decoding when valid image data is provided.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from backend.modules.vision._exceptions import VisionLoadError
from backend.modules.vision._types import ImageData, ImageFormat

_LOG = logging.getLogger("naira.vision.image_loader")


class ImageLoader:
    """Load images from file paths, raw bytes, or PIL Image objects.

    Uses Pillow for actual image decoding when possible.
    Falls back to returning raw bytes when PIL decoding fails.
    """

    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
        {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    )

    @staticmethod
    async def load(
        source: str | bytes | Image.Image,
        timeout: float = 30.0,
    ) -> ImageData:
        """Load an image from *source* and return metadata.

        Parameters
        ----------
        source : str | bytes | Image.Image
            File path, raw image bytes, or a PIL Image.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        ImageData
            Loaded image metadata including pixel data.

        Raises
        ------
        VisionLoadError
            If the source cannot be resolved or the format is unsupported.
        """
        if isinstance(source, Image.Image):
            return ImageLoader._from_pil(source)

        if isinstance(source, bytes):
            try:
                return ImageLoader._from_bytes(source)
            except Exception:
                return ImageData(
                    source_type="bytes",
                    source_path=None,
                    size_bytes=len(source),
                    data=source,
                )

        source_str = str(source)
        parsed = urlparse(source_str)

        if parsed.scheme in ("http", "https"):
            return ImageData(
                source_type="url",
                source_path=source_str,
                size_bytes=0,
                data=None,
            )

        path = Path(source_str)
        if not path.exists():
            raise VisionLoadError(
                f"Image file not found: {source_str}",
                context={"source": source_str},
            )
        if path.suffix.lower() not in ImageLoader.SUPPORTED_EXTENSIONS:
            raise VisionLoadError(
                f"Unsupported image format: {path.suffix}",
                context={"source": source_str, "extension": path.suffix},
            )

        try:
            return await ImageLoader._from_file(path)
        except Exception:
            return ImageData(
                source_type="file",
                source_path=str(path.resolve()),
                width=0,
                height=0,
                format=ImageLoader._detect_format(path.suffix),
                size_bytes=path.stat().st_size,
                data=None,
            )

    @staticmethod
    async def _from_file(path: Path) -> ImageData:
        """Load image from a local file with PIL decoding."""
        pil_image = Image.open(path)
        pil_image.load()
        fmt = ImageLoader._detect_format(path.suffix)
        buf = io.BytesIO()
        pil_image.save(buf, format=pil_image.format or "PNG")
        raw_bytes = buf.getvalue()
        return ImageData(
            source_type="file",
            source_path=str(path.resolve()),
            width=pil_image.width,
            height=pil_image.height,
            format=fmt,
            size_bytes=path.stat().st_size,
            data=raw_bytes,
        )

    @staticmethod
    def _from_bytes(data: bytes) -> ImageData:
        """Load image from raw bytes with PIL decoding."""
        pil_image = Image.open(io.BytesIO(data))
        pil_image.load()
        fmt = ImageLoader._detect_format_from_pil(pil_image.format)
        return ImageData(
            source_type="bytes",
            source_path=None,
            width=pil_image.width,
            height=pil_image.height,
            format=fmt,
            size_bytes=len(data),
            data=data,
        )

    @staticmethod
    def _from_pil(pil_image: Image.Image) -> ImageData:
        """Create ImageData from a PIL Image."""
        fmt = ImageLoader._detect_format_from_pil(pil_image.format)
        buf = io.BytesIO()
        save_format = pil_image.format or "PNG"
        pil_image.save(buf, format=save_format)
        raw_bytes = buf.getvalue()
        return ImageData(
            source_type="bytes",
            source_path=None,
            width=pil_image.width,
            height=pil_image.height,
            format=fmt,
            size_bytes=len(raw_bytes),
            data=raw_bytes,
        )

    @staticmethod
    def _detect_format(extension: str) -> ImageFormat:
        """Map a file extension to an ``ImageFormat`` literal."""
        ext = extension.lower()
        mapping: dict[str, ImageFormat] = {
            ".png": "png",
            ".jpg": "jpeg",
            ".jpeg": "jpeg",
            ".webp": "webp",
            ".bmp": "bmp",
            ".gif": "gif",
        }
        return mapping.get(ext, "unknown")

    @staticmethod
    def _detect_format_from_pil(pil_format: str | None) -> ImageFormat:
        if pil_format is None:
            return "unknown"
        mapping: dict[str, ImageFormat] = {
            "PNG": "png",
            "JPEG": "jpeg",
            "WEBP": "webp",
            "BMP": "bmp",
            "GIF": "gif",
        }
        return mapping.get(pil_format.upper(), "unknown")
