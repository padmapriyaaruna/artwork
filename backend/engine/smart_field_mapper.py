"""
Smart Field Mapper — scans SVG text nodes and replaces sample text
with {{variable_name}} placeholders based on a vocabulary of known
BGP Connect / BRAT XML field patterns.

Design principle:
  - Works from REAL sample data in the PDF (not pre-tagged templates)
  - Unmatched text stays as static text (logo taglines, legal text, etc.)
  - Expandable vocabulary — add new patterns without changing core logic
"""
import re
from typing import Optional

import lxml.etree as ET


# ── Matching vocabulary ────────────────────────────────────────────────────────
# Each entry: (variable_name, list_of_patterns)
# Patterns are tried in order — first match wins for each text node.
# Patterns can be strings (substring match) or compiled regex objects.

FIELD_VOCABULARY = [
    # ── Barcode ───────────────────────────────────────────────────────────
    # Barcode placeholders in PDFs are often repeated mirrored chars like SSIIMMIILLEE
    # or actual EAN-13 digit strings
    ("barcode_number", [
        re.compile(r"^\d{8,14}$"),                 # EAN-8 / EAN-13 / UPC
        re.compile(r"SSIIMMIIL"),                   # mirrored placeholder char
        "BARCODE", "EAN", "GTIN",
    ]),

    # ── Price / Selling Price ─────────────────────────────────────────────
    ("selling_price", [
        re.compile(r"^\d{1,4}[,.]\d{2}$"),          # e.g. 169,00 or 29.99
        re.compile(r"^[€$£¥₹AED]+\s*\d"),           # currency-prefixed price
        re.compile(r"^0[,.]00$"),                    # PDF placeholder price
        "SELLING PRICE", "PRICE", "PREZZO",
    ]),

    # ── Currency symbol ───────────────────────────────────────────────────
    ("currency_symbol", [
        re.compile(r"^(AED|EUR|USD|GBP|INR|CHF|SEK|DKK|NOK|PLN|CZK|HUF|RON)$"),
        "CURRENCY", "SYMBOL",
    ]),

    # ── SKU / Stock Code ──────────────────────────────────────────────────
    ("sku_code", [
        re.compile(r"^\d{6,9}$"),                   # 6-9 digit SKU
        "SKU", "SKU CODE", "STOCK CODE", "ARTICLE",
    ]),

    # ── Commercial Ref / Style Reference ─────────────────────────────────
    ("commercial_ref", [
        re.compile(r"^[A-Z]{2,4}\d{3}\s[A-Z]{2}\d{2}$"),  # e.g. PR711 AI08
        re.compile(r"^RRFF$"),                      # mirrored FFRR placeholder
        "COMMERCIAL REF", "COMM REF", "REFERENCE", "COMMERCIAL",
    ]),

    # ── Color ─────────────────────────────────────────────────────────────
    ("color", [
        re.compile(r"^FFAACC$"),                    # mirrored color placeholder
        re.compile(r"^C[0-9A-F]{5,6}$"),            # hex color code placeholder
        re.compile(r"^[A-Z]{4,15}$"),               # color name (EGGNOG, BLACK, etc.)
        "COLOR", "COLOUR", "COLORE",
    ]),

    # ── Style Code ────────────────────────────────────────────────────────
    ("style_code", [
        re.compile(r"^\d{6,8}$"),                   # style code (numeric)
        "STYLE CODE", "STYLE",
    ]),

    # ── Supplier Style ────────────────────────────────────────────────────
    ("supplier_style", [
        re.compile(r"^[A-Z0-9]{3,6}[A-Z0-9-]{4,20}$"),  # e.g. 262SWT301LT-230
        "SUPPLIER", "SUPPLIER STYLE",
    ]),

    # ── Country of Origin ─────────────────────────────────────────────────
    ("country_of_origin", [
        "MADE IN", "COUNTRY OF ORIGIN", "ORIGIN", "COUNTRY",
        re.compile(r"MADE IN [A-Z]+"),
        re.compile(r"SPACE FOR MADE IN"),            # placeholder text in PDF
    ]),

    # ── Sizes — Children/Clothing tags (OVS style) ────────────────────────
    ("sizes.YEARS",  [re.compile(r"^\d{1,2}-\d{1,2}$"), "YEARS", "Y-0"]),
    ("sizes.CM",     [re.compile(r"^\d{2,3}$"), "CM", "SIZE CM"]),
    ("sizes.IT",     ["IT SIZE", "IT"]),
    ("sizes.MEX",    [re.compile(r"^\d{1,2}-\d{1,2}\s*A$"), "MEX", "MEXICO"]),
    ("sizes.MONTHS", [re.compile(r"^\d{1,2}-\d{1,2}M$"), "MONTHS", "MESI"]),
    ("sizes.KG",     [re.compile(r"^\d[,.]\d-\d+$"), "KG", "WEIGHT"]),

    # ── Standard garment sizes (H&M style) ───────────────────────────────
    ("sizes.EUR",    [re.compile(r"^\d{1,3}[A-Z]?$"), "EUR", "EUROPEAN"]),
    ("sizes.US",     ["US SIZE", "US"]),
    ("sizes.CA",     ["CA SIZE", "CA"]),
    ("sizes.UK",     ["UK SIZE", "UK"]),
    ("sizes.BR",     ["BR SIZE", "BR"]),
    ("sizes.CN",     ["CN SIZE", "CN"]),
    ("sizes.AUS",    ["AUS SIZE", "AUS"]),

    # ── Order / Product references ────────────────────────────────────────
    ("order_number",   [re.compile(r"^B\d{6,10}$"), "ORDER NO", "ORDER NUMBER"]),
    ("product_number", [re.compile(r"^[A-Z]{1,4}\d{4,8}$"), "PROD NO", "PRODUCT NUMBER"]),
    ("season_code",    [re.compile(r"^[A-Z]\d{2,4}$"), "SEASON", "SEASON CODE"]),

    # ── Care instructions ─────────────────────────────────────────────────
    ("care_symbols.wash",     ["MACHINE WASH", "HAND WASH", "DO NOT WASH",
                               "WASH COLD", "WASH HOT", re.compile(r"WASH \d+")]),
    ("care_symbols.bleach",   ["BLEACH", "DO NOT BLEACH", "NO BLEACH"]),
    ("care_symbols.iron",     ["IRON", "DO NOT IRON", "NO IRON"]),
    ("care_symbols.dry_clean",["DRY CLEAN", "DO NOT DRY CLEAN"]),
    ("care_symbols.tumble_dry",["TUMBLE DRY", "DO NOT TUMBLE"]),

    # ── Fibre content ─────────────────────────────────────────────────────
    ("fibre_content", [
        re.compile(r"\d+%\s*(COTTON|POLYESTER|WOOL|NYLON|VISCOSE|ELASTANE|SILK|"
                   r"LINEN|ACRYLIC|MODAL|BAMBOO|HEMP|LYOCELL|CASHMERE|TENCEL)"),
        "% COTTON", "% POLYESTER", "% WOOL", "% CASHMERE",
        "SHELL", "LINING", "TRIM",
    ]),
]

# SVG namespaces commonly produced by Illustrator/poppler
SVG_NAMESPACES = {
    "svg":  "http://www.w3.org/2000/svg",
    "xlink":"http://www.w3.org/1999/xlink",
}


# ── Core matcher ──────────────────────────────────────────────────────────────

def _match_text(text: str) -> Optional[str]:
    """
    Given a text string from an SVG node, return the matched variable name
    or None if no match found.

    Matching is case-insensitive, strip-aware.
    """
    if not text:
        return None

    upper = text.strip().upper()
    if len(upper) < 2:
        return None

    for variable_name, patterns in FIELD_VOCABULARY:
        for pattern in patterns:
            if isinstance(pattern, re.Pattern):
                if pattern.search(upper):
                    return variable_name
            else:
                if pattern.upper() in upper or upper in pattern.upper():
                    return variable_name

    return None


def map_svg_fields(svg_string: str) -> tuple[str, dict[str, str]]:
    """
    Parse an SVG string, detect text nodes that match known XML field names,
    and replace their content with {{variable_name}} placeholders.

    Args:
        svg_string: Raw SVG content (from pdftosvg or existing template)

    Returns:
        Tuple of:
          - Modified SVG string with {{placeholders}} inserted
          - field_map dict: {svg_element_id: variable_dot_path}
            e.g. {"text_42": "country_of_origin"}
    """
    # lxml needs bytes for fromstring to handle XML declarations
    root = ET.fromstring(svg_string.encode("utf-8"))

    field_map: dict[str, str] = {}
    counter = {"n": 0}  # mutable counter for closure

    def _ensure_id(el: ET._Element) -> str:
        """Give the element a stable ID if it doesn't have one."""
        el_id = el.get("id")
        if not el_id:
            counter["n"] += 1
            el_id = f"auto_field_{counter['n']}"
            el.set("id", el_id)
        return el_id

    # Walk every text-bearing element in the SVG
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag

        if tag not in ("text", "tspan", "flowPara", "flowRoot"):
            continue

        # Collect all text in this element + children
        full_text = "".join(el.itertext()).strip()
        if not full_text:
            continue

        matched_var = _match_text(full_text)
        if matched_var:
            el_id = _ensure_id(el)
            field_map[el_id] = matched_var

            # Clear child tspans and set placeholder directly on element
            for child in list(el):
                el.remove(child)
            el.text = f"{{{{{matched_var}}}}}"

    # Serialize back to string
    modified_svg = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return modified_svg, field_map


def build_field_map_summary(field_map: dict[str, str]) -> str:
    """Return a human-readable summary of what was auto-mapped."""
    if not field_map:
        return "No fields were automatically mapped."
    lines = [f"  • {svg_id!r:30s} → {var}" for svg_id, var in field_map.items()]
    return "Auto-mapped fields:\n" + "\n".join(lines)
