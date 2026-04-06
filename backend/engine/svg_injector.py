"""
SVG Injector — dynamically injects NormalizedItem data into any SVG template.

Strategy A: Replace {{placeholder}} tokens in text content
Strategy B: Find elements by id attribute and set their text

Both strategies run together. No field names are hardcoded.
Field mapping is provided as a dict: {svg_id: "dot.path.in.item"}
"""
import copy
import re
from typing import Any

import lxml.etree as ET

SVG_NS   = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XHTML_NS = "http://www.w3.org/1999/xhtml"


# ── Path resolver ──────────────────────────────────────────────────────────────

def _resolve_path(data: dict, path: str) -> str:
    """
    Resolve a dotted field path against a data dict.
    e.g. "sizes.EUR" → data["sizes"]["EUR"]
         "country_of_origin" → data["country_of_origin"]
    """
    parts = path.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return ""
        if current is None:
            return ""
    return str(current) if current is not None else ""


# ── Variant selector ───────────────────────────────────────────────────────────

def select_variant(root: ET._Element, target_group: str) -> None:
    """
    Show only the target layout variant group; hide all others.
    Groups are <g> elements whose id starts with one of the known
    variant prefixes — fully dynamic.

    Convention: variant group ids contain "logo_with_size",
    "logo_without_size", "without_logo_with_size",
    "without_logo_without_size" etc.
    """
    # Collect all <g> elements that have a data-name or id suggesting they
    # are a variant group — we detect them by checking if their id is one of
    # the recognised variant ids in the field_map's variant_rules.
    # Simple approach: any <g> whose id matches a "variant-like" pattern.
    variant_pattern = re.compile(
        r"(logo_with_size|logo_without_size|without_logo_with_size|without_logo_without_size)",
        re.IGNORECASE,
    )

    for g in root.iter(f"{{{SVG_NS}}}g", "g"):
        g_id = g.get("id", "")
        if variant_pattern.search(g_id):
            if g_id == target_group:
                g.set("display", "inline")
            else:
                g.set("display", "none")


# ── foreignObject handler ──────────────────────────────────────────────────────

def _replace_foreign_object(root: ET._Element, field_id: str, value: str) -> bool:
    """
    Handle the <foreignObject> → <div> → <text id="..."> pattern
    produced by InDesign exports (used for 'made_in' field).

    Replaces the entire <foreignObject> block with a clean <text> element.
    Returns True if handled.
    """
    # Find all foreignObject elements
    for fo in root.iter(f"{{{SVG_NS}}}foreignObject"):
        # Look for our target id inside
        target_text = fo.find(f".//{{{XHTML_NS}}}text[@id='{field_id}']")
        if target_text is None:
            # Try without namespace
            target_text = fo.find(f".//text[@id='{field_id}']")
        if target_text is None:
            continue

        # Get position attributes from the foreignObject
        x = fo.get("x", "5")
        y_fo = fo.get("y", "0")
        w = fo.get("width", "89")

        # Parse style from the hidden text element to carry over font info
        style = target_text.get("style", "")

        # Build a clean SVG <text> element to replace the foreignObject
        parent = fo.getparent()
        if parent is None:
            continue

        idx = list(parent).index(fo)
        parent.remove(fo)

        new_text = ET.Element(f"{{{SVG_NS}}}text")
        new_text.set("id", field_id)
        new_text.set("x", x)
        # Position y slightly below the foreignObject's top
        try:
            new_y = float(y_fo) + 5
        except ValueError:
            new_y = float(y_fo) if y_fo.replace(".", "").isdigit() else 0.0
            new_y += 5
        new_text.set("y", f"{new_y:.2f}")
        new_text.set("style", style or
            "font-family: HMAmpersand-Regular, 'HM Ampersand'; font-size: 4.8px;")
        new_text.text = value

        parent.insert(idx, new_text)
        return True

    return False


# ── Main injector ──────────────────────────────────────────────────────────────

def inject_data(
    svg_content: str,
    item_data: dict,
    field_map: dict[str, str],
    layout_variant: str = "logo_with_size",
) -> ET._Element:
    """
    Inject NormalizedItem data into an SVG template.

    Args:
        svg_content:    Raw SVG string
        item_data:      NormalizedItem.to_dict() result
        field_map:      {"svg_element_id": "dot.path.in.item_data"}
        layout_variant: Which variant group to make visible

    Returns:
        Modified lxml Element tree root
    """
    root = ET.fromstring(svg_content.encode("utf-8"))

    # ── Step 1: Select layout variant ─────────────────────────────────────
    select_variant(root, layout_variant)

    # ── Step 2: Strategy A — replace {{placeholder}} tokens ───────────────
    for element in root.iter():
        if element.text and "{{" in element.text:
            for svg_id, path in field_map.items():
                value = _resolve_path(item_data, path)
                element.text = element.text.replace(f"{{{{{svg_id}}}}}", value)
        if element.tail and "{{" in element.tail:
            for svg_id, path in field_map.items():
                value = _resolve_path(item_data, path)
                element.tail = element.tail.replace(f"{{{{{svg_id}}}}}", value)

    # ── Step 3: Strategy B — inject by element id ──────────────────────────
    for svg_id, path in field_map.items():
        value = _resolve_path(item_data, path)

        # Try foreignObject first (handles InDesign 'made_in' field)
        if _replace_foreign_object(root, svg_id, value):
            continue

        # Standard id-based injection
        el = root.find(f'.//*[@id="{svg_id}"]')
        if el is None:
            continue

        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag  # strip namespace

        if tag in ("text", "tspan"):
            # Clear existing children (tspan nesting) and set text directly
            el.text = value
            for child in list(el):
                el.remove(child)

        elif tag == "image":
            el.set(f"{{{XLINK_NS}}}href", value)
            el.set("href", value)

        # For any other supported element, set data attribute
        else:
            el.set("data-value", value)

    # ── Step 4: Handle tspan children for compound fields ─────────────────
    # e.g. Product_number contains a <tspan id="season_code">
    for svg_id, path in field_map.items():
        value = _resolve_path(item_data, path)
        for tspan in root.iter(f"{{{SVG_NS}}}tspan"):
            if tspan.get("id") == svg_id:
                tspan.text = value

    return root


def svg_to_string(root: ET._Element) -> bytes:
    """Serialise lxml element tree to UTF-8 encoded SVG bytes."""
    return ET.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=False,
    )


# ── Dynamic field discovery ────────────────────────────────────────────────────

def discover_injectable_fields(svg_content: str) -> dict:
    """
    Introspect an SVG and return all elements that have id attributes.
    Used when registering a new template to suggest the field_map.

    Returns:
        {
          "text_fields": [{"id": "EUR", "tag": "text", "sample_text": "EUR"}],
          "group_variants": ["logo_with_size", "logo_without_size", ...],
          "image_fields": [{"id": "product_image", "tag": "image"}],
        }
    """
    root = ET.fromstring(svg_content.encode("utf-8"))

    text_fields    = []
    group_variants = []
    image_fields   = []

    variant_pattern = re.compile(
        r"(logo_with_size|logo_without_size|without_logo_with_size|without_logo_without_size)",
        re.IGNORECASE,
    )

    for el in root.iter():
        el_id = el.get("id")
        if not el_id:
            continue

        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag

        if tag == "g" and variant_pattern.search(el_id):
            group_variants.append(el_id)
        elif tag in ("text", "tspan"):
            text_fields.append({
                "id": el_id,
                "tag": tag,
                "sample_text": (el.text or "").strip(),
            })
        elif tag == "image":
            image_fields.append({"id": el_id, "tag": tag})

    return {
        "text_fields":    text_fields,
        "group_variants": list(dict.fromkeys(group_variants)),  # deduplicate
        "image_fields":   image_fields,
    }
