"""
PDF to SVG Converter — uses poppler-utils (pdftosvg binary) installed in Docker.

Takes raw PDF bytes and returns an SVG string representing page 1 of the PDF.
This SVG is then passed to smart_field_mapper for variable detection.
"""
import io
import subprocess
import tempfile
import os
from pathlib import Path


def pdf_bytes_to_svg(pdf_bytes: bytes, page: int = 1) -> str:
    """
    Convert a PDF file (as bytes) to SVG markup string using poppler pdftosvg.

    Args:
        pdf_bytes: Raw PDF bytes (the template PDF from the customer)
        page:      Page number to convert (1-indexed). Defaults to 1 (label front).

    Returns:
        SVG content as a string

    Raises:
        RuntimeError: If poppler is not installed or conversion fails
    """
    # Write PDF to a temp file — pdftosvg requires a real file path
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "template.pdf"
        svg_path = Path(tmpdir) / "template.svg"

        pdf_path.write_bytes(pdf_bytes)

        # pdftosvg syntax: pdftosvg -f <first_page> -l <last_page> input.pdf output.svg
        result = subprocess.run(
            [
                "pdftosvg",
                "-f", str(page),
                "-l", str(page),
                str(pdf_path),
                str(svg_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"pdftosvg failed (exit {result.returncode}): {result.stderr}"
            )

        # pdftosvg outputs page1.svg for single pages
        # Check both possible output filenames
        if svg_path.exists():
            return svg_path.read_text(encoding="utf-8")

        # Multi-page naming: template1.svg
        alt_svg = Path(tmpdir) / "template1.svg"
        if alt_svg.exists():
            return alt_svg.read_text(encoding="utf-8")

        raise RuntimeError(
            "pdftosvg ran successfully but produced no output SVG file."
        )


def is_poppler_available() -> bool:
    """Check if poppler pdftosvg binary is available in the system PATH."""
    try:
        result = subprocess.run(
            ["pdftosvg", "-v"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
