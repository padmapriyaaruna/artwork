"""
Dynamic Template Builder — the fully autonomous PDF→variablized SVG pipeline.

When a ZIP with XML + PDF is uploaded for the FIRST TIME:
  1. Parse the XML to extract all real field values from the first item
     (e.g. barcode="8051553298804", color="EGGNOG", selling_price="169,00")
  2. Convert PDF → SVG (via poppler pdftosvg)
  3. Walk every SVG text node and compare its content against the XML field values
  4. Where there is a match → replace the text with {{field_name}} placeholder
  5. Save the variablized SVG to the template registry under the detected design_code

No hardcoded keywords. No human input. Works for any BGP Connect PDF template.
"""
import re
from typing import Optional

import lxml.etree as ET


# ── Value extractor ────────────────────────────────────────────────────────────

def build_value_map(item_data: dict) -> dict[str, str]:
    """
    Build a reverse map: {sample_value → variable_path}
    from a NormalizedItem.to_dict() result.

    This is the key to dynamic matching — we know the real XML values,
    so we look for those exact values in the PDF text elements.

    Args:
        item_data: dict from NormalizedItem.to_dict()

    Returns:
        {text_in_pdf: dot_path_to_field}
        e.g. {"169,00": "selling_price", "EGGNOG": "color"}
    """
    value_map: dict[str, str] = {}

    # ── Scalar fields ──────────────────────────────────────────────────────────
    SCALAR_FIELDS = [
        "barcode_number",
        "selling_price",
        "currency_symbol",
        "sku_code",
        "commercial_ref",
        "color",
        "style_code",
        "supplier_style",
        "country_of_origin",
        "order_number",
        "product_number",
        "season_code",
        "department",
        "sub_department",
        "translation_code",
        "tape_color",
    ]
    for field in SCALAR_FIELDS:
        val = (item_data.get(field) or "").strip()
        if val and len(val) >= 2:            # Skip empty / single-char values
            value_map[val.upper()] = field

    # ── Sizes (nested dict) ────────────────────────────────────────────────────
    for size_name, size_val in (item_data.get("sizes") or {}).items():
        val = (size_val or "").strip()
        if val and len(val) >= 1:
            value_map[val.upper()] = f"sizes.{size_name}"

    # ── Country of origin — also match "MADE IN <country>" composite ──────────
    country = (item_data.get("country_of_origin") or "").strip()
    if country:
        value_map[f"MADE IN {country.upper()}"] = "country_of_origin"
        # Also match just country name on its own (already added above)

    # ── Fibre content strings ──────────────────────────────────────────────────
    for fibre in (item_data.get("fibre_content") or []):
        wording = (fibre.get("wording") or "").strip()
        pct     = fibre.get("percentage", 0)
        if wording:
            full = f"{pct}% {wording}".upper()
            value_map[full] = "fibre_content"
            value_map[wording.upper()] = "fibre_content"

    # ── Extra variables ────────────────────────────────────────────────────────
    for question, val in (item_data.get("extra_variables") or {}).items():
        val = (val or "").strip()
        if val and len(val) >= 2:
            safe_key = question.lower().replace(" ", "_")
            value_map[val.upper()] = f"extra.{safe_key}"

    return value_map


# ── Text collector for SVG elements ───────────────────────────────────────────

def _collect_text(el: ET._Element) -> str:
    """Get all text content from an element + its children, joined."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        parts.append(_collect_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _clear_text_children(el: ET._Element) -> None:
    """Remove all tspan children and set text directly on element."""
    el.text = None
    for child in list(el):
        el.remove(child)


# ── Core mapper ────────────────────────────────────────────────────────────────

def map_svg_to_variables(
    svg_string: str,
    value_map: dict[str, str],
    min_match_len: int = 2,
) -> tuple[str, dict[str, str]]:
    """
    Scan every text-bearing SVG element. Where its text content matches
    a known XML field value, replace it with a {{variable}} placeholder.

    Args:
        svg_string:    Raw SVG string (from pdftosvg or hand-crafted)
        value_map:     {UPPER_CASE_VALUE: "field.path"} from build_value_map()
        min_match_len: Minimum value length to attempt matching (avoids false positives)

    Returns:
        Tuple of:
          - Modified SVG string with {{field.path}} placeholders
          - field_map: {element_id: variable_path} for the template registry
    """
    try:
        root = ET.fromstring(svg_string.encode("utf-8"))
    except ET.XMLSyntaxError:
        # Try parsing without declaration
        cleaned = re.sub(r"<\?xml[^>]+\?>", "", svg_string).strip()
        root = ET.fromstring(cleaned.encode("utf-8"))

    field_map: dict[str, str] = {}
    id_counter = [0]

    def _ensure_id(el: ET._Element) -> str:
        el_id = el.get("id")
        if not el_id:
            id_counter[0] += 1
            el_id = f"field_{id_counter[0]}"
            el.set("id", el_id)
        return el_id

    TEXT_TAGS = {"text", "tspan", "flowPara", "flowRoot"}

    for el in root.iter():
        # Normalize tag name (strip namespace)
        local_tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if local_tag not in TEXT_TAGS:
            continue

        # Collect full visible text of this element
        full_text = _collect_text(el).strip()
        if len(full_text) < min_match_len:
            continue

        full_upper = full_text.upper()

        # ── Exact match ────────────────────────────────────────────────────────
        if full_upper in value_map:
            var_path = value_map[full_upper]
            el_id = _ensure_id(el)
            field_map[el_id] = var_path
            _clear_text_children(el)
            el.text = f"{{{{{var_path}}}}}"
            continue

        # ── Contains match (for composite strings like "MADE IN INDIA") ────────
        matched_var = None
        matched_val = None
        for sample_val, var_path in value_map.items():
            if len(sample_val) < min_match_len:
                continue
            if sample_val in full_upper:
                # Prefer longer / more specific match
                if matched_val is None or len(sample_val) > len(matched_val):
                    matched_var  = var_path
                    matched_val  = sample_val

        if matched_var:
            el_id = _ensure_id(el)
            field_map[el_id] = matched_var
            _clear_text_children(el)
            el.text = f"{{{{{matched_var}}}}}"

    modified_svg = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return modified_svg, field_map


# ── Public entry point ─────────────────────────────────────────────────────────

def build_variablized_svg(
    pdf_bytes: bytes,
    item_data: dict,
) -> tuple[str, dict[str, str]]:
    """
    Full pipeline: PDF bytes + XML item data → variablized SVG + field_map.

    This is the ONLY function called from the orders API.
    It chains together:
      pdf_bytes → pdf_to_svg → build_value_map → map_svg_to_variables

    Args:
        pdf_bytes: Raw PDF bytes from the ZIP
        item_data: dict from NormalizedItem.to_dict() — the first item is used
                   since all items share the same template; only values differ

    Returns:
        (variablized_svg_string, field_map)

    Raises:
        RuntimeError if PDF conversion fails (poppler not available or bad PDF)
    """
    from backend.engine.pdf_to_svg import pdf_bytes_to_svg

    # Step 1: PDF → SVG
    svg_string = pdf_bytes_to_svg(pdf_bytes)

    # Step 2: Build reverse-value map from real XML data
    value_map = build_value_map(item_data)

    if not value_map:
        # No data to match against — return raw SVG with empty field map
        return svg_string, {}

    # Step 3: Match and replace
    variablized_svg, field_map = map_svg_to_variables(svg_string, value_map)

    return variablized_svg, field_map
