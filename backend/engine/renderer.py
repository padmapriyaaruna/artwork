"""
Renderer — converts injected SVG into PDF, PNG, and thumbnail.
Uses CairoSVG for SVG→PDF/PNG conversion.
All outputs returned as bytes (stored in Neon DB).
"""
import io
from typing import Optional

import cairosvg
from PIL import Image

from backend.config import RENDER_DPI


def render_to_pdf(svg_bytes: bytes, dpi: int = RENDER_DPI) -> bytes:
    """
    Convert SVG bytes → PDF bytes.

    Args:
        svg_bytes: UTF-8 encoded SVG content
        dpi:       Output resolution (150 for prototype, 300 for production)

    Returns:
        PDF bytes
    """
    return cairosvg.svg2pdf(bytestring=svg_bytes, dpi=dpi)


def render_to_png(svg_bytes: bytes, dpi: int = RENDER_DPI) -> bytes:
    """
    Convert SVG bytes → PNG bytes.

    Returns:
        PNG bytes
    """
    return cairosvg.svg2png(bytestring=svg_bytes, dpi=dpi)


def render_to_thumbnail(svg_bytes: bytes, max_width: int = 400) -> bytes:
    """
    Convert SVG → small PNG thumbnail for list-view previews.
    Keeps aspect ratio, max_width pixels wide.

    Returns:
        PNG bytes (thumbnail)
    """
    # Low-res PNG first
    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, dpi=72)

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    ratio = max_width / img.width
    new_height = int(img.height * ratio)
    img_resized = img.resize((max_width, new_height), Image.LANCZOS)

    buf = io.BytesIO()
    img_resized.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_all(svg_bytes: bytes, dpi: int = RENDER_DPI) -> dict[str, bytes]:
    """
    Convenience wrapper — renders PDF, full PNG, and thumbnail in one call.

    Returns:
        {"pdf": bytes, "png": bytes, "thumbnail": bytes}
    """
    pdf       = render_to_pdf(svg_bytes, dpi=dpi)
    png       = render_to_png(svg_bytes, dpi=dpi)
    thumbnail = render_to_thumbnail(svg_bytes)

    return {
        "pdf":       pdf,
        "png":       png,
        "thumbnail": thumbnail,
    }
