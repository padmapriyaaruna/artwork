"""
Dynamic Template Builder — the fully autonomous PDF→variablized SVG pipeline.

When a ZIP with XML + PDF is uploaded for the FIRST TIME:
  1. Parse the XML to extract all real field values from the first item
  2. Convert PDF → SVG (via poppler pdftosvg)
  3. Walk every SVG text node; for those whose FULL text EXACTLY matches
     a known XML field value → replace just that text with {{field_name}}
  4. All other elements (symbols, icons, logos, decorative paths, static text,
     care icons, recycling logos, FSC logos, etc.) are left COMPLETELY UNTOUCHED.
  5. Save the variablized SVG to the template registry.

Key safety rules to avoid destroying symbols:
  - EXACT match only for short values (< 8 chars) — never "contains" match
  - Skip any text element whose characters are predominantly non-Latin unicode
    (these are embedded font glyphs for icons/symbols, not data text)
  - currency_symbol, department, sub_department are excluded from matching
    (too short or too ambiguous — they'd corrupt structured data in symbols)
  - Size values (YEARS, CM, IT, MEX) are matched exactly only
  - "MADE IN X" composite match is the only allowed "contains" match
"""
import re
from typing import Optional

import lxml.etree as ET


# ── Safe fields to variablize ──────────────────────────────────────────────────
#
# Only these fields are injected into the SVG as {{placeholders}}.
# Short / ambiguous / symbol-like fields are deliberately excluded.
#
# EXCLUDED from SVG matching (too short or too risky for false positives):
#   - currency_symbol  (€, AED — 1-3 chars; also embedded in price display)
#   - department       (3-digit number like "230" — matches too many things)
#   - sub_department   (4-digit number like "3632" — too generic)
#   - tape_color       (H&M-specific; OVS doesn't use this)
#   - translation_code (OVS-specific lookup; not rendered as plain text)
#
SAFE_SCALAR_FIELDS = [
    "barcode_number",    # 13-digit barcode — long, very safe
    "selling_price",     # e.g. "29,95" or "169,00"
    "sku_code",          # 7-digit SKU
    "commercial_ref",    # e.g. "PR711 AI08"
    "color",             # e.g. "EGGNOG"
    "style_code",        # e.g. "2768957"
    "supplier_style",    # e.g. "262SWT301LT-230"
    "country_of_origin", # e.g. "WARM", "COLD", "MIDDLE EAST"
    # H&M care label fields (only present for H&M templates)
    "order_number",
    "product_number",
    "season_code",
]

# Minimum character length before a value is allowed to match
# (short values cause too many false-positive matches in symbol glyphs)
MIN_EXACT_LEN  = 4   # exact matches: must be ≥ 4 chars
MIN_FUZZY_LEN  = 10  # "contains" matches: only allowed for very long values


# ── Unicode symbol detector ────────────────────────────────────────────────────

def _is_symbol_glyph(text: str) -> bool:
    """
    Return True if this text is likely a symbol/icon glyph rather than real data.

    poppler renders PDF symbol fonts (FSC, recycling, care icons) as <text>
    elements with unicode points in private-use or specialist ranges. These
    must NEVER be touched.

    Ranges we treat as "symbol":
      U+0300-U+036F   Combining Diacritical Marks  (sometimes mis-used by PDF fonts)
      U+0600-U+06FF   Arabic (if not intended as Arabic data)
      U+2000-U+27FF   General Punctuation, Arrows, Technical, Geometric, Misc
      U+2800-U+28FF   Braille (care symbol encoding in some PDFs)
      U+E000-U+F8FF   BMP Private Use Area
      U+F000-U+FFFF   Specialised / PUA
    """
    SYMBOL_RANGES = [
        (0x0300, 0x036F),
        (0x2000, 0x27FF),
        (0x2800, 0x28FF),
        (0xE000, 0xF8FF),
        (0xF000, 0xFFFF),
    ]
    symbol_count = 0
    for ch in text:
        cp = ord(ch)
        for lo, hi in SYMBOL_RANGES:
            if lo <= cp <= hi:
                symbol_count += 1
                break
    # If more than 30% of characters are in symbol ranges → treat as icon glyph
    return symbol_count > 0 and (symbol_count / max(len(text), 1)) > 0.30


# ── Value extractor ────────────────────────────────────────────────────────────

def build_value_map(item_data: dict) -> dict[str, str]:
    """
    Build a reverse map: {sample_value → variable_path}
    from a NormalizedItem.to_dict() result.

    Only includes values that are SAFE to match in the SVG — i.e., long enough
    and unambiguous enough that they won't accidentally replace symbol glyphs
    or structural SVG text.

    Returns:
        {UPPER_CASE_TEXT_IN_PDF: "field.path"}
    """
    value_map: dict[str, str] = {}

    for field in SAFE_SCALAR_FIELDS:
        val = (item_data.get(field) or "").strip()
        if val and len(val) >= MIN_EXACT_LEN:
            value_map[val.upper()] = field

    # ── Sizes: exact match only, and only if long enough ──────────────────────
    for size_name, size_val in (item_data.get("sizes") or {}).items():
        val = (size_val or "").strip()
        # e.g. "5-6", "116", "5-6 A" — only match if >= 3 chars
        # Use a slightly lower bar for sizes because they often appear as 3 chars
        if val and len(val) >= 3:
            value_map[val.upper()] = f"sizes.{size_name}"

    # ── Country of origin: also match the composite "MADE IN X" ──────────────
    country = (item_data.get("country_of_origin") or "").strip()
    if country and len(country) >= MIN_EXACT_LEN:
        # Individual country name already added above; also add composite
        composite = f"MADE IN {country.upper()}"
        value_map[composite] = "country_of_origin"

    # ── Fibre content (H&M templates) ─────────────────────────────────────────
    for fibre in (item_data.get("fibre_content") or []):
        wording = (fibre.get("wording") or "").strip()
        pct     = fibre.get("percentage", 0)
        if wording and len(wording) >= MIN_EXACT_LEN:
            composite = f"{pct}% {wording}".upper()
            value_map[composite] = "fibre_content"
            value_map[wording.upper()] = "fibre_content"

    # ── Extra variables ────────────────────────────────────────────────────────
    for question, val in (item_data.get("extra_variables") or {}).items():
        val = (val or "").strip()
        if val and len(val) >= MIN_EXACT_LEN:
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
) -> tuple[str, dict[str, str]]:
    """
    Scan every text-bearing SVG element.

    Rules (ordered by priority):
      1. If the element's full text is a symbol glyph → SKIP (leave untouched).
      2. EXACT match against value_map → replace with {{field_path}}.
      3. "Contains" match ONLY for long composites (≥ MIN_FUZZY_LEN chars)
         like "MADE IN WARM" — marks the whole element as that field.
      4. Everything else → leave completely untouched.

    This ensures that recycling logos, FSC logos, care symbols, and any other
    graphical text encoded via embedded PDF fonts are NEVER modified.
    """
    try:
        root = ET.fromstring(svg_string.encode("utf-8"))
    except ET.XMLSyntaxError:
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
        local_tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if local_tag not in TEXT_TAGS:
            continue

        # Collect full visible text
        full_text = _collect_text(el).strip()
        if not full_text:
            continue

        # ── Rule 1: Skip symbol glyphs entirely ───────────────────────────────
        if _is_symbol_glyph(full_text):
            continue

        full_upper = full_text.upper()

        # ── Rule 2: Exact match (primary strategy) ────────────────────────────
        if full_upper in value_map:
            var_path = value_map[full_upper]
            el_id = _ensure_id(el)
            field_map[el_id] = var_path
            _clear_text_children(el)
            el.text = f"{{{{{var_path}}}}}"
            continue

        # ── Rule 3: Conservative fuzzy match (long composites only) ──────────
        # Only attempt if no exact match found and the matched value is long
        # enough to be unambiguous (avoids false positives on short values)
        matched_var  = None
        matched_val  = None
        for sample_val, var_path in value_map.items():
            if len(sample_val) < MIN_FUZZY_LEN:
                continue   # too short to safely use as a "contains" match
            if sample_val in full_upper:
                if matched_val is None or len(sample_val) > len(matched_val):
                    matched_var = var_path
                    matched_val = sample_val

        if matched_var:
            el_id = _ensure_id(el)
            field_map[el_id] = matched_var
            _clear_text_children(el)
            el.text = f"{{{{{matched_var}}}}}"

        # ── Anything else: leave completely untouched ─────────────────────────

    modified_svg = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return modified_svg, field_map


# ── Public entry point ─────────────────────────────────────────────────────────

def build_variablized_svg(
    pdf_bytes: bytes,
    item_data: dict,
) -> tuple[str, dict[str, str]]:
    """
    Full pipeline: PDF bytes + XML item data → variablized SVG + field_map.

    Only the specific data-value text nodes are replaced with {{placeholders}}.
    All graphical elements (symbols, logos, decorative text, care icons,
    recycling marks, FSC logos, size chart headers, etc.) are preserved verbatim
    from the original PDF conversion.

    Args:
        pdf_bytes: Raw PDF bytes from the ZIP (single-page back-of-label design)
        item_data: dict from NormalizedItem.to_dict() — first item used (all
                   items share the same template layout; only values differ)

    Returns:
        (variablized_svg_string, field_map)

    Raises:
        RuntimeError if PDF conversion fails (poppler not available or bad PDF)
    """
    from backend.engine.pdf_to_svg import pdf_bytes_to_svg

    # Step 1: PDF → SVG (all original artwork preserved)
    svg_string = pdf_bytes_to_svg(pdf_bytes)

    # Step 2: Build conservative reverse-value map from real XML data
    value_map = build_value_map(item_data)

    if not value_map:
        # No data to match against — return raw SVG unchanged
        return svg_string, {}

    # Step 3: Match ONLY data fields; leave everything else untouched
    variablized_svg, field_map = map_svg_to_variables(svg_string, value_map)

    return variablized_svg, field_map
