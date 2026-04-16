"""
Approval PDF Service — generates a TOK100-style landscape A3 approval sheet.

Layout per page (one page per country_of_origin group):
  ┌──────────────────────────────────────────────────────────────────┐
  │  Sainmarks®  │ BUYER / CUSTOMER / DESIGN CODE / PRODUCT / DATE  │ ARTWORK FOR APPROVAL │
  ├──────────────────────────────────────────────────────────────────┤
  │         {supplier_style} - {country} - {color} - {order_id}     │  (red bold)
  │                       45mm x 100mm                               │
  │  Front  │  Back                                                  │
  │  [navy] │  [tag1] [tag2] [tag3] [tag4] [tag5] [tag6]           │
  │  OVS    │  Qty-21 Qty-21 ...                                     │
  └──────────────────────────────────────────────────────────────────┘

Uses PyMuPDF (fitz). No font files needed — uses built-in PDF base fonts.
"""
import io
from typing import Optional
import fitz  # PyMuPDF


# ── Page geometry (A3 landscape in points: 1pt = 1/72 inch) ───────────────────
PAGE_W = 1191.0   # A3 landscape width  (~420mm)
PAGE_H = 842.0    # A3 landscape height (~297mm)

# Margins
MARGIN_X = 40.0
MARGIN_Y = 30.0

# Header box dimensions
HDR_TOP    = MARGIN_Y
HDR_H      = 120.0
HDR_BOTTOM = HDR_TOP + HDR_H

# Logo cell width, info cell width, approval cell width
LOGO_W     = 200.0
INFO_W     = 400.0
APPROVAL_W = 160.0

HDR_LEFT   = MARGIN_X
HDR_RIGHT  = HDR_LEFT + LOGO_W + INFO_W + APPROVAL_W

# Title zone
TITLE_TOP  = HDR_BOTTOM + 20.0

# Label area
LABEL_TOP  = TITLE_TOP + 70.0
LABEL_BOT  = PAGE_H - MARGIN_Y - 60.0  # leave room for qty text

# Front column width
FRONT_W    = 130.0

# Back tags start x
BACK_START = HDR_LEFT + FRONT_W + 20.0


# ── Font helpers (built-in PDF base14, no file needed) ────────────────────────
F_REGULAR = "helvetica"
F_BOLD    = "helvetica-bold"


def _draw_header(page: fitz.Page, order_data: dict) -> None:
    """Draw the Sainmarks header box with three columns."""
    # Outer border
    border = fitz.Rect(HDR_LEFT, HDR_TOP, HDR_RIGHT, HDR_BOTTOM)
    page.draw_rect(border, color=(0.6, 0.6, 0.6), width=0.7)

    # Vertical dividers
    x1 = HDR_LEFT + LOGO_W
    x2 = x1 + INFO_W
    page.draw_line(fitz.Point(x1, HDR_TOP), fitz.Point(x1, HDR_BOTTOM),
                   color=(0.6, 0.6, 0.6), width=0.7)
    page.draw_line(fitz.Point(x2, HDR_TOP), fitz.Point(x2, HDR_BOTTOM),
                   color=(0.6, 0.6, 0.6), width=0.7)

    # ── Cell 1: Sainmarks logo (text approximation) ──────────────────────────
    logo_cx = HDR_LEFT + LOGO_W / 2
    page.insert_text(fitz.Point(logo_cx - 30, HDR_TOP + 55),
                     "Sainmarks\u00ae",
                     fontname=F_BOLD, fontsize=18,
                     color=(0.15, 0.55, 0.25))

    # ── Cell 2: Info rows ────────────────────────────────────────────────────
    rows = [
        ("BUYER",          order_data.get("buyer", "")),
        ("CUSTOMER",       order_data.get("customer_name", "")),
        ("DESIGN CODE",    order_data.get("design_code", "")),
        ("PRODUCT CODE",   order_data.get("product_code", "")),
        ("SUBMITTED DATE", order_data.get("submitted_date", "")),
    ]
    row_h = HDR_H / len(rows)
    for i, (label, value) in enumerate(rows):
        y = HDR_TOP + i * row_h + row_h * 0.65
        # Horizontal divider (except first)
        if i > 0:
            page.draw_line(fitz.Point(x1, HDR_TOP + i * row_h),
                           fitz.Point(x2, HDR_TOP + i * row_h),
                           color=(0.7, 0.7, 0.7), width=0.4)
        page.insert_text(fitz.Point(x1 + 6, y),
                         f"{label} : {value}",
                         fontname=F_REGULAR, fontsize=9,
                         color=(0.2, 0.2, 0.2))

    # ── Cell 3: ARTWORK FOR APPROVAL ─────────────────────────────────────────
    text_lines = ["ARTWORK", "FOR", "APPROVAL"]
    for i, line in enumerate(text_lines):
        y = HDR_TOP + 30 + i * 20
        tw = fitz.get_text_length(line, fontname=F_BOLD, fontsize=11)
        cx = x2 + APPROVAL_W / 2 - tw / 2
        page.insert_text(fitz.Point(cx, y),
                         line,
                         fontname=F_BOLD, fontsize=11,
                         color=(0.15, 0.15, 0.15))


def _draw_titles(page: fitz.Page, red_title: str, label_size: str) -> None:
    """Draw the red product title and dimension subtitle."""
    # Red bold title — centered
    tw = fitz.get_text_length(red_title, fontname=F_BOLD, fontsize=14)
    cx = PAGE_W / 2 - tw / 2
    page.insert_text(fitz.Point(cx, TITLE_TOP + 20),
                     red_title,
                     fontname=F_BOLD, fontsize=14,
                     color=(0.82, 0.08, 0.08))

    # Label size subtitle
    tw2 = fitz.get_text_length(label_size, fontname=F_BOLD, fontsize=11)
    cx2 = PAGE_W / 2 - tw2 / 2
    page.insert_text(fitz.Point(cx2, TITLE_TOP + 40),
                     label_size,
                     fontname=F_BOLD, fontsize=11,
                     color=(0.1, 0.1, 0.1))


def _draw_front_back_labels(page: fitz.Page) -> None:
    """Draw 'Front' and 'Back' section labels."""
    page.insert_text(fitz.Point(HDR_LEFT, LABEL_TOP - 10),
                     "Front",
                     fontname=F_BOLD, fontsize=12,
                     color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(BACK_START, LABEL_TOP - 10),
                     "Back",
                     fontname=F_BOLD, fontsize=12,
                     color=(0.1, 0.1, 0.1))


def _draw_front_tag(page: fitz.Page) -> None:
    """
    Draw the OVS kids navy blue front hang tag.
    Purely CSS/vector — no image file needed.
    """
    tag_w = FRONT_W - 10
    tag_h = LABEL_BOT - LABEL_TOP
    r = fitz.Rect(HDR_LEFT, LABEL_TOP, HDR_LEFT + tag_w, LABEL_BOT)

    # Navy background
    page.draw_rect(r, color=(0.06, 0.09, 0.16), fill=(0.06, 0.09, 0.16), width=0)

    cx = HDR_LEFT + tag_w / 2
    # White punch hole dot
    page.draw_circle(fitz.Point(cx, LABEL_TOP + 18), 5,
                     color=(1, 1, 1), fill=(1, 1, 1))

    # OVS text in gold/yellow
    ovs_y = LABEL_TOP + tag_h * 0.42
    tw = fitz.get_text_length("OVS", fontname=F_BOLD, fontsize=32)
    page.insert_text(fitz.Point(cx - tw / 2, ovs_y),
                     "OVS",
                     fontname=F_BOLD, fontsize=32,
                     color=(0.92, 0.71, 0.18))

    # kids text in gold below
    tw2 = fitz.get_text_length("kids", fontname=F_BOLD, fontsize=18)
    page.insert_text(fitz.Point(cx - tw2 / 2, ovs_y + 28),
                     "kids",
                     fontname=F_BOLD, fontsize=18,
                     color=(0.92, 0.71, 0.18))

    # Thin magenta/pink horizontal line near bottom
    line_y = LABEL_BOT - 25
    page.draw_line(fitz.Point(HDR_LEFT, line_y),
                   fitz.Point(HDR_LEFT + tag_w, line_y),
                   color=(0.88, 0.13, 0.39), width=1)


def _draw_back_tags(page: fitz.Page, variants: list[dict], png_streams: dict) -> None:
    """
    Draw each back label tag image + Qty text.
    variants: list of {artwork_id, quantity, sizes, barcode_number, selling_price, currency_symbol}
    png_streams: {artwork_id: bytes}
    """
    max_tags = 6
    visible = variants[:max_tags]
    if not visible:
        return

    total_back_w = PAGE_W - BACK_START - MARGIN_X
    tag_w = min(115.0, total_back_w / max(len(visible), 1) - 8)
    tag_h = LABEL_BOT - LABEL_TOP
    gap   = (total_back_w - tag_w * len(visible)) / max(len(visible) - 1, 1) if len(visible) > 1 else 0
    gap   = max(gap, 8)

    for i, v in enumerate(visible):
        x = BACK_START + i * (tag_w + gap)
        tag_rect = fitz.Rect(x, LABEL_TOP, x + tag_w, LABEL_BOT)

        art_id = v.get("artwork_id")
        png_bytes = png_streams.get(art_id) if art_id else None

        if png_bytes:
            # Drop shadow / border
            page.draw_rect(tag_rect, color=(0.85, 0.06, 0.4), width=0.8)
            page.insert_image(tag_rect, stream=png_bytes, keep_proportion=True)
        else:
            # Placeholder box
            page.draw_rect(tag_rect, color=(0.8, 0.8, 0.8), width=0.5)
            page.insert_text(fitz.Point(x + 10, LABEL_TOP + tag_h / 2),
                             "No Artwork",
                             fontname=F_REGULAR, fontsize=7,
                             color=(0.5, 0.5, 0.5))

        # Qty label below
        qty = v.get("quantity", 0)
        qty_txt = f"Qty - {qty}"
        tw = fitz.get_text_length(qty_txt, fontname=F_BOLD, fontsize=10)
        page.insert_text(fitz.Point(x + tag_w / 2 - tw / 2, LABEL_BOT + 22),
                         qty_txt,
                         fontname=F_BOLD, fontsize=10,
                         color=(0.1, 0.1, 0.1))


def _draw_page_number(page: fitz.Page, num: int) -> None:
    txt = str(num)
    tw = fitz.get_text_length(txt, fontname=F_REGULAR, fontsize=9)
    page.insert_text(fitz.Point(PAGE_W / 2 - tw / 2, PAGE_H - 12),
                     txt, fontname=F_REGULAR, fontsize=9,
                     color=(0.5, 0.5, 0.5))


# ── Public entry point ────────────────────────────────────────────────────────

def create_approval_sheet_pdf(
    order_data: dict,
    variant_groups: list[dict],
    png_streams: dict,
) -> bytes:
    """
    Build the full TOK100-style approval PDF.

    Args:
        order_data: {buyer, customer_name, design_code, product_code, submitted_date, bgp_order_id}
        variant_groups: list of {
            'country': str,
            'title': str,            # red bold line e.g. "262SWT301LT-230 - WARM - EGGNOG - B0854559"
            'label_size': str,       # e.g. "45mm x 100mm"
            'variants': [
                {artwork_id, quantity, sizes, barcode_number, selling_price, currency_symbol}
            ]
        }
        png_streams: {artwork_id: bytes}  — artwork PNG binary keyed by artwork UUID

    Returns:
        PDF bytes
    """
    doc = fitz.open()

    for page_num, group in enumerate(variant_groups, start=1):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)

        _draw_header(page, order_data)
        _draw_titles(page, group.get("title", ""), group.get("label_size", "45mm x 100mm"))
        _draw_front_back_labels(page)
        _draw_front_tag(page)
        _draw_back_tags(page, group.get("variants", []), png_streams)
        _draw_page_number(page, page_num)

    if not doc.page_count:
        doc.new_page(width=PAGE_W, height=PAGE_H)

    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out
