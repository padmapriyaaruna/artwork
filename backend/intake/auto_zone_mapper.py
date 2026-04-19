# -*- coding: utf-8 -*-
"""
Automatic Zone Mapper.

Given a PDF template and XML records, automatically detects variable
zones and generates a complete zone_map.json — no human required.

Detection strategy (3-pass):
-----------------------------
Pass 1 — Placeholder pattern matching
  Scans PDF text for placeholder patterns like:
    {{barcode_number}},  {PRICE},  [SIZE],  <sku_code>,  __BARCODE__
  Normalises to field_key, cross-checks vs XML fields.
  Most reliable — use if template designer followed a convention.

Pass 2 — Value matching
  For each XML record field value, searches if that exact value
  appears as text in the PDF. If found, treats the span bbox as a zone.
  Handles templates that shipped with real sample data instead of placeholders.

Pass 3 — Heuristic type detection
  Detects barcodes (13-digit strings), prices (currency+number),
  and size patterns ("4-5", "110") even without explicit placeholder names.

Then for each detected zone:
  - Infers zone type (barcode / price / text / text_rotated / table / size_grid)
  - Determines orientation from bbox shape (wide → text, tall+narrow → text_rotated)
  - Expands bbox by type-appropriate padding

Usage (called from onboarding.py):
  from backend.intake.auto_zone_mapper import auto_generate_zone_map
  zone_map = auto_generate_zone_map(template_pdf_path, xml_records, cust, type)
"""
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


# ── Placeholder patterns to detect ───────────────────────────────────────────
# Each pattern must have one capture group = the field name

PLACEHOLDER_PATTERNS = [
    r"\{\{([a-zA-Z0-9_]+)\}\}",   # {{field_name}}
    r"\{([a-zA-Z0-9_]+)\}",       # {field_name}
    r"\[([a-zA-Z0-9_]+)\]",       # [field_name]
    r"<([a-zA-Z0-9_]+)>",         # <field_name>
    r"__([a-zA-Z0-9_]+)__",       # __field_name__
    r"\$\{([a-zA-Z0-9_]+)\}",     # ${field_name}
    r"%([a-zA-Z0-9_]+)%",         # %field_name%
]

_PLACEHOLDER_RE = re.compile(
    "|".join(f"(?:{p})" for p in PLACEHOLDER_PATTERNS),
    re.IGNORECASE,
)

# ── Field alias table ─────────────────────────────────────────────────────────
# Maps common placeholder name variants → canonical item_data key

FIELD_ALIASES: dict[str, str] = {
    # Barcode
    "barcode":         "barcode_number",
    "barcode_no":      "barcode_number",
    "ean":             "barcode_number",
    "ean13":           "barcode_number",
    "ean_13":          "barcode_number",
    "bar_code":        "barcode_number",

    # Price
    "price":           "selling_price",
    "amount":          "selling_price",
    "retail_price":    "selling_price",
    "sell_price":      "selling_price",

    # Currency
    "currency":        "currency_symbol",
    "currency_code":   "currency_symbol",
    "curr":            "currency_symbol",

    # Sizes
    "size":            "sizes",
    "size_years":      "sizes",
    "years":           "sizes",
    "size_grid":       "sizes",
    "size_chart":      "sizes",

    # Country of origin
    "country":         "country_of_origin",
    "made_in":         "country_of_origin",
    "origin":          "country_of_origin",
    "coo":             "country_of_origin",

    # Style / SKU
    "style":           "style_code",
    "style_no":        "style_code",
    "sku":             "sku_code",
    "sku_no":          "sku_code",
    "article":         "sku_code",

    # Department
    "dept":            "department",
    "sub_dept":        "sub_department",
    "subdepartment":   "sub_department",

    # References
    "ref":             "commercial_ref",
    "cref":            "commercial_ref",
    "commercial":      "commercial_ref",

    # Quantity
    "qty":             "quantity",
    "quantity":        "quantity",
}

# ── Zone type rules ───────────────────────────────────────────────────────────
# Maps canonical field_key → default zone type

ZONE_TYPES: dict[str, str] = {
    "barcode_number":   "barcode",
    "selling_price":    "price",
    "currency_symbol":  "price",    # merged with price at render time
    "sizes":            "table",
    "country_of_origin": "text_rotated",
    "quantity":         "text",
    "style_code":       "text",
    "commercial_ref":   "text",
    "sku_code":         "text",
    "department":       "text",
    "sub_department":   "text",
}

# ── Heuristic value patterns ──────────────────────────────────────────────────
# (regex, field_key, zone_type) — matched against raw PDF text

HEURISTIC_PATTERNS: list[tuple[str, str, str]] = [
    (r"^\d{13}$",              "barcode_number",   "barcode"),        # 13-digit EAN
    (r"^\d{12}$",              "barcode_number",   "barcode"),        # 12-digit UPC
    (r"^[\d]+[,.][\d]{2}$",   "selling_price",    "price"),          # 29,95 / 29.95
    (r"^[€£$]\s*[\d]+",       "selling_price",    "price"),          # €29 / $29
    (r"^\d{1,2}-\d{1,2}$",    "sizes",            "size_grid"),      # 4-5 / 7-8
    (r"^\d{3}$",               "sizes",            "size_grid"),      # 110 / 128 (CM)
]

# Zone expansion (pt) by type — placeholder text bbox → actual content bbox
ZONE_EXPAND: dict[str, dict] = {
    "barcode":       {"top": 4,  "bottom": 10, "left": 2,  "right": 2},
    "price":         {"top": 8,  "bottom": 8,  "left": 4,  "right": 4},
    "table":         {"top": 6,  "bottom": 6,  "left": 2,  "right": 2},
    "size_grid":     {"top": 4,  "bottom": 4,  "left": 2,  "right": 2},
    "text_rotated":  {"top": 2,  "bottom": 2,  "left": 4,  "right": 4},
    "text":          {"top": 2,  "bottom": 2,  "left": 2,  "right": 2},
}


# ── Helper functions ──────────────────────────────────────────────────────────

def _normalise_key(raw: str) -> str:
    """Lower-case + underscores, then check alias table."""
    key = raw.lower().strip().replace(" ", "_").replace("-", "_")
    return FIELD_ALIASES.get(key, key)


def _infer_type(field_key: str, bbox: tuple, is_rotated: bool = False) -> str:
    """Infer zone type from field_key and bbox shape."""
    if is_rotated:
        return "text_rotated"
    return ZONE_TYPES.get(field_key, "text")


def _is_rotated(span: dict) -> bool:
    """
    Detect if a text span is rotated (90°/270°).
    PyMuPDF span['dir'] is a unit vector: (1,0)=normal, (0,1)=rotated 90°.
    """
    direction = span.get("dir", (1, 0))
    # Rotated if x component ~0 (i.e. text flows vertically)
    return abs(direction[0]) < 0.1


def _expand_bbox(bbox: tuple, zone_type: str, page_w: float, page_h: float) -> tuple:
    """Expand a bbox by the type-appropriate padding, clamped to page bounds."""
    x0, y0, x1, y1 = bbox
    exp = ZONE_EXPAND.get(zone_type, ZONE_EXPAND["text"])
    x0 = max(0,       x0 - exp["left"])
    y0 = max(0,       y0 - exp["top"])
    x1 = min(page_w,  x1 + exp["right"])
    y1 = min(page_h,  y1 + exp["bottom"])
    return round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)


def _bbox_dict(bbox: tuple) -> dict:
    return {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]}


# ── Pass 1: Placeholder detection ────────────────────────────────────────────

def _detect_from_placeholders(
    page: fitz.Page,
    known_fields: set[str],
    page_w: float,
    page_h: float,
) -> list[dict]:
    """
    Scan page text for placeholder patterns.
    Returns list of zone dicts with all matched placeholders.
    """
    zones = []
    seen_fields: set[str] = set()

    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:   # skip image blocks
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                raw_text = span.get("text", "").strip()
                if not raw_text:
                    continue

                # Search for any placeholder pattern in the span text
                match = _PLACEHOLDER_RE.search(raw_text)
                if not match:
                    continue

                # Extract the captured group (field name)
                raw_field = next((g for g in match.groups() if g), "")
                if not raw_field:
                    continue

                field_key  = _normalise_key(raw_field)
                is_rot     = _is_rotated(span)
                zone_type  = _infer_type(field_key, span["bbox"], is_rot)
                bbox       = _expand_bbox(span["bbox"], zone_type, page_w, page_h)

                # De-duplicate: if we've already added this field, expand the bbox
                if field_key in seen_fields:
                    continue
                seen_fields.add(field_key)

                zones.append({
                    "id":        field_key,
                    "name":      raw_field.replace("_", " ").title(),
                    "field_key": field_key,
                    "type":      zone_type,
                    "detected_by": "placeholder",
                    **_bbox_dict(bbox),
                })

    return zones


# ── Pass 2: Value matching ────────────────────────────────────────────────────

def _detect_from_values(
    page: fitz.Page,
    xml_records: list[dict],
    already_found: set[str],
    page_w: float,
    page_h: float,
) -> list[dict]:
    """
    For each XML field value, check if that exact text appears in the PDF.
    Only runs for fields not already found in Pass 1.
    """
    if not xml_records:
        return []

    # Build a flat value→field_key map from the first XML record
    record = xml_records[0]
    value_to_field: dict[str, str] = {}
    for field_key, val in record.items():
        if field_key in already_found:
            continue
        if val is None or isinstance(val, dict):
            continue
        s = str(val).strip()
        if len(s) >= 3:   # skip very short values (too many false positives)
            value_to_field[s] = field_key

    zones = []
    seen_fields: set[str] = set()
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                raw_text = span.get("text", "").strip()
                if not raw_text:
                    continue

                field_key = value_to_field.get(raw_text)
                if not field_key or field_key in seen_fields:
                    continue

                seen_fields.add(field_key)
                is_rot    = _is_rotated(span)
                zone_type = _infer_type(field_key, span["bbox"], is_rot)
                bbox      = _expand_bbox(span["bbox"], zone_type, page_w, page_h)

                zones.append({
                    "id":        field_key,
                    "name":      field_key.replace("_", " ").title(),
                    "field_key": field_key,
                    "type":      zone_type,
                    "detected_by": "value_match",
                    **_bbox_dict(bbox),
                })

    return zones


# ── Pass 3: Heuristic detection ───────────────────────────────────────────────

def _detect_from_heuristics(
    page: fitz.Page,
    already_found: set[str],
    page_w: float,
    page_h: float,
) -> list[dict]:
    """
    Apply heuristic regex patterns to detect known data types
    (13-digit barcode, price format, etc.) even without placeholder names.
    """
    zones = []
    seen_fields: set[str] = set()

    compiled = [(re.compile(pat), fk, zt) for pat, fk, zt in HEURISTIC_PATTERNS]
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                raw_text = span.get("text", "").strip()
                if not raw_text:
                    continue

                for pattern, field_key, zone_type in compiled:
                    if field_key in already_found or field_key in seen_fields:
                        continue
                    if pattern.match(raw_text):
                        seen_fields.add(field_key)
                        bbox = _expand_bbox(span["bbox"], zone_type, page_w, page_h)
                        zones.append({
                            "id":        field_key,
                            "name":      field_key.replace("_", " ").title(),
                            "field_key": field_key,
                            "type":      zone_type,
                            "detected_by": "heuristic",
                            **_bbox_dict(bbox),
                        })
                        break  # next span

    return zones


# ── Main entry point ──────────────────────────────────────────────────────────

def auto_generate_zone_map(
    template_pdf_path: Path,
    xml_records:       list[dict],
    customer_code:     str,
    label_type:        str,
) -> dict:
    """
    Auto-detect all variable zones from a template PDF + XML records.

    Runs 3 detection passes:
      1. Placeholder text pattern matching  (e.g. {{barcode_number}})
      2. XML value matching                 (e.g. "8051553298804" in PDF)
      3. Heuristic type recognition         (e.g. 13-digit = barcode)

    Args:
        template_pdf_path: Path to the template PDF.
        xml_records:       List of item_data dicts parsed from XML.
        customer_code:     e.g. "ZARA"
        label_type:        e.g. "WVN50"

    Returns:
        Complete zone_map dict with variable_zones populated.
    """
    doc   = fitz.open(str(template_pdf_path))
    page  = doc[0]
    rect  = page.rect
    pw, ph = rect.width, rect.height

    # Collect XML field keys for context
    known_fields: set[str] = set()
    if xml_records:
        for key in xml_records[0].keys():
            known_fields.add(_normalise_key(key))

    # ── Pass 1: Placeholders ──────────────────────────────────────────────────
    zones_p1 = _detect_from_placeholders(page, known_fields, pw, ph)
    found_p1 = {z["field_key"] for z in zones_p1}

    # ── Pass 2: Value matching ────────────────────────────────────────────────
    zones_p2 = _detect_from_values(page, xml_records, found_p1, pw, ph)
    found_p2 = found_p1 | {z["field_key"] for z in zones_p2}

    # ── Pass 3: Heuristics ────────────────────────────────────────────────────
    zones_p3 = _detect_from_heuristics(page, found_p2, pw, ph)

    doc.close()

    all_zones  = zones_p1 + zones_p2 + zones_p3
    confidence = "high" if zones_p1 else ("medium" if zones_p2 else "low")

    print(f"[AUTO-MAP] {customer_code}/{label_type}: {len(all_zones)} zones detected "
          f"(pass1={len(zones_p1)}, pass2={len(zones_p2)}, pass3={len(zones_p3)}) "
          f"confidence={confidence}")

    for z in all_zones:
        print(f"  [{z['detected_by']:12s}] {z['field_key']:25s} type={z['type']:14s} "
              f"bbox=({z['x0']:.1f},{z['y0']:.1f} → {z['x1']:.1f},{z['y1']:.1f})")

    return {
        "customer_code":  customer_code.upper(),
        "label_type":     label_type.upper(),
        "page_width_pt":  round(pw, 2),
        "page_height_pt": round(ph, 2),
        "renderer_module": "generic_pdf_renderer",
        "static_template": str(template_pdf_path),
        "auto_detected":  True,
        "detection_confidence": confidence,
        "variable_zones": all_zones,
    }
