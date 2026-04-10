"""
ZIP Extractor — unpacks a BRAT/BGP Connect ZIP file.

Extracts:
  - XML string (required — the main order data)
  - PDF bytes (optional — only present if this is a new template order)
  - template_id (extracted from <Asset><Name> inside the XML)
"""
import io
import zipfile
from dataclasses import dataclass
from typing import Optional

import lxml.etree as ET


@dataclass
class ZipContents:
    xml_string: str
    template_id: str          # e.g. "HM30105" — from <Asset><Name> in XML
    pdf_bytes: Optional[bytes] = None
    pdf_filename: Optional[str] = None


def extract_zip(zip_bytes: bytes) -> ZipContents:
    """
    Extract XML and optional PDF from a BRAT ZIP file.

    Args:
        zip_bytes: Raw bytes of the uploaded .zip file

    Returns:
        ZipContents with xml_string, template_id and optional pdf_bytes

    Raises:
        ValueError: If no XML file found in ZIP
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()

        # ── Find the XML file ──────────────────────────────────────────────
        xml_names = [n for n in names if n.lower().endswith(".xml")]
        if not xml_names:
            raise ValueError(
                "No XML file found in the ZIP. "
                "Please include the BGP Connect BRAT XML file."
            )
        # Take first XML found (BRAT ZIPs only contain one)
        xml_bytes = zf.read(xml_names[0])
        xml_string = xml_bytes.decode("utf-8", errors="replace")

        # ── Extract template_id from XML <Asset><Name> ──────────────────────
        template_id = _extract_template_id(xml_string)

        # ── Find optional PDF file ──────────────────────────────────────────
        pdf_names = [n for n in names if n.lower().endswith(".pdf")]
        pdf_bytes = None
        pdf_filename = None
        if pdf_names:
            pdf_filename = pdf_names[0]
            pdf_bytes = zf.read(pdf_names[0])

    return ZipContents(
        xml_string=xml_string,
        template_id=template_id,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_filename,
    )


def _extract_template_id(xml_string: str) -> str:
    """
    Parse the XML and return the template identifier.

    Checks (in order):
      1. <Asset><Name> — the design/template code (e.g. "HM30105")
      2. <DesignCode>  — explicit design code if present
      3. Falls back to <OrderID> so orders are never blocked
    """
    try:
        root = ET.fromstring(xml_string.encode("utf-8"))

        # Primary: Asset Name
        asset_name = root.findtext(".//Asset/Name")
        if asset_name and asset_name.strip():
            return asset_name.strip()

        # Secondary: DesignCode element
        design_code = root.findtext("DesignCode")
        if design_code and design_code.strip():
            return design_code.strip()

        # Fallback: OrderID (ensures we always have something)
        order_id = root.findtext("OrderID")
        if order_id and order_id.strip():
            return f"ORDER_{order_id.strip()}"

    except ET.XMLSyntaxError:
        pass

    return "UNKNOWN_TEMPLATE"
