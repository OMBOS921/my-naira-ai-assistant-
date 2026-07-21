"""ImagePreprocessor — image resize, format conversion, and normalization.

Uses Pillow for actual image processing when pixel data is available.
Falls back to metadata-only dimension clamping when data is None.
"""

from __future__ import annotations

import io
import logging

from PIL import Image

from backend.modules.vision._types import ImageData, ImageFormat

_LOG = logging.getLogger("naira.vision.preprocessor")


class ImagePreprocessor:
    """Preprocess images (resize, normalize, format convert).

    Supports:
    - resize with preserved aspect ratio
    - max dimensions
    - RGB conversion
    - compression when needed
    - metadata-only dimension clamping (no pixel data)
    """

    @staticmethod
    async def preprocess(
        image: ImageData,
        *,
        max_width: int = 0,
        max_height: int = 0,
        preserve_aspect_ratio: bool = True,
        timeout: float = 30.0,
    ) -> ImageData:
        """Preprocess an image.

        Parameters
        ----------
        image : ImageData
            The source image data.
        max_width : int
            Maximum width in pixels (0 = no limit).
        max_height : int
            Maximum height in pixels (0 = no limit).
        preserve_aspect_ratio : bool
            Whether to maintain aspect ratio when resizing.
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        ImageData
            The preprocessed image data.
        """
        if image.data is None:
            return ImagePreprocessor._clamp_metadata(image, max_width, max_height)

        pil_image = Image.open(io.BytesIO(image.data))
        pil_image.load()

        pil_image = ImagePreprocessor._ensure_rgb(pil_image)

        if (max_width > 0 or max_height > 0) and preserve_aspect_ratio:
            pil_image = ImagePreprocessor._resize_with_aspect_ratio(
                pil_image, max_width, max_height,
            )
        elif max_width > 0 and pil_image.width > max_width:
            h = int(pil_image.height * (max_width / pil_image.width))
            pil_image = pil_image.resize((max_width, h), Image.LANCZOS)
        elif max_height > 0 and pil_image.height > max_height:
            w = int(pil_image.width * (max_height / pil_image.height))
            pil_image = pil_image.resize((w, max_height), Image.LANCZOS)

        buf = io.BytesIO()
        save_format = "PNG"
        pil_image.save(buf, format=save_format)
        raw_bytes = buf.getvalue()

        fmt: ImageFormat = "png"
        return ImageData(
            source_type=image.source_type,
            source_path=image.source_path,
            width=pil_image.width,
            height=pil_image.height,
            format=fmt,
            size_bytes=len(raw_bytes),
            data=raw_bytes,
        )

    @staticmethod
    def _clamp_metadata(
        image: ImageData,
        max_width: int,
        max_height: int,
    ) -> ImageData:
        """Clamp dimensions on metadata-only ImageData (no pixel data)."""
        if max_width <= 0 and max_height <= 0:
            return image
        new_w = image.width
        new_h = image.height
        if max_width > 0 and image.width > 0:
            new_w = min(image.width, max_width)
        if max_height > 0 and image.height > 0:
            new_h = min(image.height, max_height)
        return ImageData(
            source_type=image.source_type,
            source_path=image.source_path,
            width=new_w,
            height=new_h,
            format=image.format,
            size_bytes=image.size_bytes,
            data=image.data,
        )

    @staticmethod
    def _ensure_rgb(pil_image: Image.Image) -> Image.Image:
        if pil_image.mode != "RGB":
            return pil_image.convert("RGB")
        return pil_image

    @staticmethod
    def _resize_with_aspect_ratio(
        pil_image: Image.Image,
        max_width: int,
        max_height: int,
    ) -> Image.Image:
        src_w, src_h = pil_image.size
        if max_width <= 0:
            max_width = src_w
        if max_height <= 0:
            max_height = src_h
        if src_w <= max_width and src_h <= max_height:
            return pil_image
        ratio = min(max_width / src_w, max_height / src_h)
        new_w = int(src_w * ratio)
        new_h = int(src_h * ratio)
        return pil_image.resize((new_w, new_h), Image.LANCZOS)
