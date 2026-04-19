# -*- coding: utf-8 -*-
"""
Generic PDF Renderer.

A universal label renderer that reads a zone_map.json and renders
variable data into the correct positions on any customer's PDF template.

This renderer is used automatically when:
  - No customer-specific renderer exists at
    backend/engine/customers/{cust}/{type}_renderer.py
  - But a zone_map.json IS registered at
    backend/templates/{CUST}/{TYPE}/zone_map.json

How it works
------------
1. Embeds the static template PDF (template.pdf from zone_map)
2. White-overwrites each variable_zone rectangle
3. For each zone, calls the appropriate field renderer based on zone["type"]

Supported zone types
--------------------
  text          → plain text, auto-sized to fit zone width
  text_rotated  → text rotated 90° (e.g. address column)
  barcode       → EAN-13 PNG barcode + digit string below bars
  price         → currency symbol + integer + superscript cents
  table         → 2-column key/value rows (e.g. YEARS / CM / IT / MEX)
  size_grid     → 2×N grid of size chips, active size highlighted

Public API (matches renderer contract)
--------------------------------------
  build_label_pdf(item_data, zone_map)       → bytes
  build_label_png(item_data, zone_map, dpi)  → bytes
  build_label_thumbnail(item_data, zone_map, dpi) → bytes

These are called via GenericRendererProxy in label_engine.py —
do not import this module directly in application code.
Use label_engine.get_renderer() instead.
"""
import io
import os
import re
from pathlib import Path

import fitz  # PyMuPDF

# ── Shared rendering helpers (mirrors OVS renderer) ───────────────────────────

FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

WHITE   = (1.0, 1.0, 1.0)
BLACK   = (0.0, 0.0, 0.0)
DARK    = (0.08, 0.08, 0.08)
GREY    = (0.45, 0.45, 0.45)
LGREY   = (0.68, 0.68, 0.68)


def _cx(text, font, fs, x0, w):
    """Return x for horizontally centred text."""
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return x0 + (w - tw) / 2


def _fit_fontsize(text, font, max_w, max_fs=11.0, min_fs=5.0):
    """Find the largest font size where text fits within max_w."""
    fs = max_fs
    while fs >= min_fs:
        if fitz.get_text_length(text, fontname=font, fontsize=fs) <= max_w:
            return fs
        fs -= 0.5
    return min_fs


def _fix_currency(raw):
    """Normalise any currency input to a single printable symbol."""
    if not raw:
        return chr(128)
    s = str(raw).strip()
    if "\u20ac" in s or s in ("EUR", "Euro", "euro"):
        return chr(128)
    if "\u00a3" in s or s in ("GBP", "Sterling"):
        return chr(163)
    if s in ("USD", "$"):
        return "$"
    if s == "AED":
        return "AED"
    clean = "".join(c for c in s if 0x20 <= ord(c) < 0x80)
    if clean:
        return clean[0] if len(clean) == 1 else clean[:3]
    return chr(128)


def _split_price(s):
    s = str(s or "0,00").strip()
    m = re.match(r"^(\d+)([,.]?\d*)$", s)
    return (m.group(1), m.group(2)) if m else (s, "")


# ── EAN-13 barcode (same verified tables as OVS renderer) ────────────────────

_EAN_L = ["0001101","0011001","0010011","0111101","0100011",
          "0110001","0101111","0111011","0110111","0001011"]
_EAN_G = ["0100111","0110011","0011011","0100001","0011101",
          "0111001","0000101","0010001","0001001","0010111"]
_EAN_R = ["1110010","1100110","1101100","1000010","1011100",
          "1001110","1010000","1000100","1001000","1110100"]
_EAN_PARITY = ["LLLLLL","LLGLGG","LLGGLG","LLGGGL","LGLLGG",
               "LGGLLG","LGGGLL","LGLGLG","LGLGGL","LGGLGL"]


def _ean13_bits(bc):
    raw    = (str(bc) if bc else "").strip()
    digits = (raw + "0" * 13)[:13]
    try:
        digs = [int(c) for c in digits]
    except ValueError:
        digs = [0] * 13
    parity = _EAN_PARITY[digs[0]]
    bits   = "101"
    for i, p in enumerate(parity):
        d = digs[i + 1]
        bits += _EAN_L[d] if p == "L" else _EAN_G[d]
    bits += "01010"
    for i in range(6):
        bits += _EAN_R[digs[i + 7]]
    bits += "101"
    return bits


# ── Template cache ────────────────────────────────────────────────────────────

_TDOC: dict = {}

def _tpl(path: str):
    if path not in _TDOC and os.path.exists(path):
        _TDOC[path] = fitz.open(path)
    return _TDOC.get(path)


# ── Zone-type field renderers ─────────────────────────────────────────────────

def _render_text(page, zone, value, ox, oy):
    """
    Render plain text into a zone.
    Auto-sizes font to fit zone width. Vertically centres in zone.
    """
    x0 = ox + zone["x0"]
    y0 = oy + zone["y0"]
    x1 = ox + zone["x1"]
    y1 = oy + zone["y1"]
    w  = x1 - x0
    h  = y1 - y0

    text = str(value) if value is not None else ""
    if not text:
        return

    fs   = _fit_fontsize(text, FB, w - 4, max_fs=10.0)
    bl_y = y0 + h / 2 + fs * 0.35   # vertically centred baseline

    page.insert_text(
        fitz.Point(_cx(text, FB, fs, x0, w), bl_y),
        text, fontname=FB, fontsize=fs, color=DARK,
    )


def _render_text_rotated(page, zone, value, ox, oy):
    """
    Render text rotated 90° into a zone (e.g. address column).
    Multiple lines separated by '|' are spaced vertically.
    """
    x0   = ox + zone["x0"]
    y0   = oy + zone["y0"]
    x1   = ox + zone["x1"]
    y1   = oy + zone["y1"]
    w    = x1 - x0
    h    = y1 - y0

    text  = str(value) if value is not None else ""
    lines = [l.strip() for l in text.split("|") if l.strip()]
    if not lines:
        return

    fs           = _fit_fontsize(max(lines, key=len), FR, h - 4, max_fs=4.0)
    line_spacing = fs + 2.0
    total_span   = (len(lines) - 1) * line_spacing
    x_start      = x0 + (w - total_span) / 2

    zone_y_mid = (y0 + y1) / 2

    for li, line in enumerate(lines):
        lx = x_start + li * line_spacing + fs
        tw = fitz.get_text_length(line, fontname=FR, fontsize=fs)
        ly = zone_y_mid + tw / 2
        page.insert_text(
            fitz.Point(lx, ly),
            line, fontname=FR, fontsize=fs, color=LGREY, rotate=90,
        )


def _render_barcode(page, zone, value, ox, oy):
    """
    Render EAN-13 barcode image + digit string below bars.
    """
    from PIL import Image, ImageDraw

    x0 = ox + zone["x0"]
    y0 = oy + zone["y0"]
    x1 = ox + zone["x1"]
    y1 = oy + zone["y1"]
    w  = x1 - x0
    h  = y1 - y0

    bc_str = str(value) if value else ""

    # Render barcode PNG at 400 DPI
    bits  = _ean13_bits(bc_str)
    w_px  = max(280, round(w  / 72 * 400))
    h_px  = max(80,  round((h * 0.7) / 72 * 400))  # bars = 70% of zone height
    img   = Image.new("RGB", (w_px, h_px), (255, 255, 255))
    draw  = ImageDraw.Draw(img)
    mod   = w_px / len(bits)
    for i, b in enumerate(bits):
        if b == "1":
            lx = round(i * mod)
            rx = max(lx + 1, round((i + 1) * mod))
            draw.rectangle([lx, 0, rx, h_px - 1], fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    bar_h = h * 0.7
    page.insert_image(fitz.Rect(x0, y0, x0 + w, y0 + bar_h), stream=buf.getvalue())

    # Digit string
    if len(bc_str) >= 13:
        p1, p2, p3 = bc_str[0], bc_str[1:7], bc_str[7:13]
    elif len(bc_str) >= 7:
        p1, p2, p3 = bc_str[0], bc_str[1:7], bc_str[7:]
    else:
        p1, p2, p3 = bc_str, "", ""
    digit_str = f"{p1} {p2} {p3}".strip()
    fs_d = 5.0
    page.insert_text(
        fitz.Point(_cx(digit_str, FR, fs_d, x0, w), y0 + bar_h + 1.5 + fs_d),
        digit_str, fontname=FR, fontsize=fs_d, color=DARK,
    )


def _render_price(page, zone, value, ox, oy, item_data):
    """
    Render price: [currency symbol] [main integer] [superscript cents].
    """
    x0 = ox + zone["x0"]
    y0 = oy + zone["y0"]
    x1 = ox + zone["x1"]
    y1 = oy + zone["y1"]
    w  = x1 - x0
    h  = y1 - y0

    currency  = _fix_currency(item_data.get("currency_symbol", ""))
    price_raw = str(value or item_data.get("selling_price", "0,00"))
    major, minor = _split_price(price_raw)

    fs_major = _fit_fontsize(major, FB, w * 0.45, max_fs=24.0, min_fs=12.0)
    fs_minor = fs_major * 0.55
    fs_sym   = fs_major * 0.65 if len(currency) > 1 else fs_major
    sym_gap  = 2.5
    cap_raise = (fs_major - fs_minor) * 0.72

    icx = x0 + w / 2
    sym_w = fitz.get_text_length(currency, fontname=FB, fontsize=fs_sym)
    maj_w = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)

    total_w = sym_w + sym_gap + maj_w + min_w
    px      = icx - total_w / 2
    pr_y    = y0 + h * 0.75   # 75% down the zone

    page.insert_text(fitz.Point(px, pr_y),
                     currency, fontname=FB, fontsize=fs_sym, color=DARK)
    page.insert_text(fitz.Point(px + sym_w + sym_gap, pr_y),
                     major, fontname=FB, fontsize=fs_major, color=DARK)
    if minor:
        page.insert_text(fitz.Point(px + sym_w + sym_gap + maj_w, pr_y - cap_raise),
                         minor, fontname=FR, fontsize=fs_minor, color=DARK)


def _render_table(page, zone, value, ox, oy):
    """
    Render a 2-column key/value table.

    value must be a dict, e.g.:
        {"YEARS": "4-5", "IT": "4-5", "MEX": "4-5 A", "CM": "110"}

    Rows are drawn evenly spaced, with a vertical centre divider.
    Top and bottom horizontal rules are drawn.
    """
    x0 = ox + zone["x0"]
    y0 = oy + zone["y0"]
    x1 = ox + zone["x1"]
    y1 = oy + zone["y1"]
    w  = x1 - x0
    h  = y1 - y0

    if not isinstance(value, dict) or not value:
        return

    rows      = list(value.items())   # [("YEARS", "4-5"), ...]
    n         = len(rows)
    row_h     = h / n
    mid_x     = x0 + w / 2
    cell_pad  = 3.0
    fs_lbl    = _fit_fontsize("YEARS",  FB, w / 2 - cell_pad * 2, max_fs=7.0)
    fs_val    = _fit_fontsize("9-10 A", FB, w / 2 - cell_pad * 2, max_fs=9.0)

    # Top and bottom rules
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y0), color=DARK, width=0.8)
    page.draw_line(fitz.Point(x0, y1), fitz.Point(x1, y1), color=DARK, width=0.8)
    # Vertical centre divider
    page.draw_line(fitz.Point(mid_x, y0), fitz.Point(mid_x, y1), color=DARK, width=0.8)

    for i, (label, val) in enumerate(rows):
        row_y = y0 + i * row_h
        bl    = row_y + row_h * 0.72

        # Row divider (skip first)
        if i > 0:
            page.draw_line(fitz.Point(x0, row_y), fitz.Point(x1, row_y),
                           color=LGREY, width=0.4)

        # Label (left-aligned, left cell)
        page.insert_text(fitz.Point(x0 + cell_pad, bl),
                         str(label), fontname=FB, fontsize=fs_lbl, color=DARK)
        # Value (right-aligned, left cell)
        val_str = str(val)
        val_w   = fitz.get_text_length(val_str, fontname=FB, fontsize=fs_val)
        page.insert_text(fitz.Point(mid_x - cell_pad - val_w, bl),
                         val_str, fontname=FB, fontsize=fs_val, color=DARK)


def _render_size_grid(page, zone, value, ox, oy, all_sizes=None, active_size=None):
    """
    Render a 2×N size chip grid.

    value: the active size string (e.g. "4-5")
    all_sizes: list of all sizes to display (e.g. ["4-5","5-6","6-7","7-8","8-9","9-10"])
    active_size: which chip to highlight (filled black box, white text)
    """
    x0 = ox + zone["x0"]
    y0 = oy + zone["y0"]
    x1 = ox + zone["x1"]
    y1 = oy + zone["y1"]
    w  = x1 - x0
    h  = y1 - y0

    sizes      = all_sizes or []
    active     = active_size or str(value or "")
    if not sizes:
        return

    cols    = 3
    n_rows  = (len(sizes) + cols - 1) // cols
    rows    = [sizes[i*cols:(i+1)*cols] for i in range(n_rows)]
    chip_w  = (w - 2) / cols
    chip_h  = (h - 2) / max(n_rows, 1)
    fs      = _fit_fontsize("9-10", FB, chip_w - 2, max_fs=7.0, min_fs=4.5)

    for ri, row in enumerate(rows):
        for ci, sz in enumerate(row):
            cx      = x0 + ci * chip_w
            cy      = y0 + ri * chip_h
            is_cur  = (sz == active)

            if is_cur:
                page.draw_rect(
                    fitz.Rect(cx, cy, cx + chip_w, cy + chip_h),
                    fill=BLACK, color=None, width=0,
                )

            fn    = FB if is_cur else FR
            tc    = WHITE if is_cur else DARK
            tw    = fitz.get_text_length(sz, fontname=fn, fontsize=fs)
            bl_y  = cy + chip_h * 0.75
            page.insert_text(
                fitz.Point(cx + (chip_w - tw) / 2, bl_y),
                sz, fontname=fn, fontsize=fs, color=tc,
            )


# ── Main render function ──────────────────────────────────────────────────────

def render_label_on_page(
    page:      fitz.Page,
    ox:        float,
    oy:        float,
    item_data: dict,
    zone_map:  dict,
) -> None:
    """
    Render a complete label onto an existing PDF page at position (ox, oy).

    Steps:
      1. Embed the static template PDF
      2. White-overwrite all variable zones
      3. For each zone, call the appropriate field renderer

    Args:
        page:      The fitz.Page to draw on.
        ox:        X origin of the label panel on the page.
        oy:        Y origin of the label panel on the page.
        item_data: Variable data dict (one item from XML records).
        zone_map:  Loaded zone_map.json dict for this customer/label_type.
    """
    template_path = zone_map.get("static_template", "")
    pw = zone_map.get("page_width_pt",  150.3)
    ph = zone_map.get("page_height_pt", 305.5)

    # 1. Embed static template
    tpl = _tpl(template_path)
    tgt = fitz.Rect(ox, oy, ox + pw, oy + ph)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
    else:
        page.draw_rect(tgt, fill=WHITE, color=None, width=0)

    # 2. White-overwrite all variable zones
    for z in zone_map.get("variable_zones", []):
        page.draw_rect(
            fitz.Rect(ox + z["x0"], oy + z["y0"],
                      ox + z["x1"], oy + z["y1"]),
            fill=WHITE, color=None, width=0,
        )

    # 3. Render each zone by type
    for z in zone_map.get("variable_zones", []):
        field_key = z.get("field_key", "")
        value     = item_data.get(field_key)
        ztype     = z.get("type", "text")

        if ztype == "text":
            _render_text(page, z, value, ox, oy)

        elif ztype == "text_rotated":
            _render_text_rotated(page, z, value, ox, oy)

        elif ztype == "barcode":
            _render_barcode(page, z, value, ox, oy)

        elif ztype == "price":
            _render_price(page, z, value, ox, oy, item_data)

        elif ztype == "table":
            # value should be a dict, e.g. sizes dict
            _render_table(page, z, value, ox, oy)

        elif ztype == "size_grid":
            # Derive active size and full size list from item_data
            sizes_dict  = item_data.get("sizes", {})
            active_size = sizes_dict.get("YEARS", "") if isinstance(sizes_dict, dict) else str(value or "")
            all_sizes   = z.get("all_sizes")   # optional override in zone_map
            if not all_sizes and isinstance(sizes_dict, dict):
                # Fall back: item_data won't have the full grid, so use zone_map hint
                all_sizes = z.get("all_sizes", [])
            _render_size_grid(page, z, active_size, ox, oy,
                              all_sizes=all_sizes, active_size=active_size)

        # Unknown types are silently skipped


# ── Public API ────────────────────────────────────────────────────────────────

def build_label_pdf(item_data: dict, zone_map: dict) -> bytes:
    """
    Build a single-item PDF (front panel space + back panel with variable data).

    If zone_map does not specify a front panel template, only the back panel
    (the main variable data side) is rendered.

    Returns:
        PDF bytes.
    """
    pw = zone_map.get("page_width_pt",  150.3)
    ph = zone_map.get("page_height_pt", 305.5)

    # Simple layout: single label panel
    doc  = fitz.open()
    page = doc.new_page(width=pw, height=ph)
    page.draw_rect(fitz.Rect(0, 0, pw, ph), fill=WHITE, color=None, width=0)
    render_label_on_page(page, 0, 0, item_data, zone_map)

    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True)
    doc.close()
    return buf.getvalue()


def build_label_png(item_data: dict, zone_map: dict, dpi: int = 150) -> bytes:
    """Rasterise a label PDF to PNG bytes."""
    pdf = build_label_pdf(item_data, zone_map)
    doc = fitz.open(stream=pdf, filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    doc.close()
    return pix.tobytes("png")


def build_label_thumbnail(item_data: dict, zone_map: dict, dpi: int = 60) -> bytes:
    """Render a small thumbnail PNG."""
    return build_label_png(item_data, zone_map, dpi=dpi)
