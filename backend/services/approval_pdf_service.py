"""
Approval PDF Service — generates OVS KIDS approval sheet matching TOK100_B0854559_1.pdf.

Layout per page (one page per country_of_origin group):
  ┌─────────────────────────────────────────────────────────────────┐
  │  Sainmarks®  │ BUYER/CUSTOMER/DESIGN/PRODUCT/DATE │ ARTWORK FOR │
  │              │                                     │  APPROVAL   │
  ├─────────────────────────────────────────────────────────────────┤
  │  {supplier_style} - {country} - {color} - {order_id}  RED BOLD │
  │                    45mm x 100mm                                  │
  │  Front         Back                                              │
  │  [navy front]  [back1] [back2] [back3] [back4] [back5] [back6]  │
  │                 Qty-128 Qty-128  ...                             │
  └─────────────────────────────────────────────────────────────────┘

Uses PyMuPDF. For OVS templates, draws directly — no PNG embedding.

Panel sizes come from tok100_label_builder constants:
  OUTER_W = 150.3 pt, OUTER_H = 305.5 pt (53mm x 108mm physical)
"""
import io
import re
from typing import Optional
from collections import defaultdict

import fitz  # PyMuPDF

from backend.engine.tok100_label_builder import (
    _draw_front_panel,
    _draw_back_panel,
    OUTER_W, OUTER_H,
    FB, FR, DARK, GREY, LGREY, NAVY, WHITE
)


# ── Page geometry ─────────────────────────────────────────────────────────────
# We use A3 landscape (1191 × 842) for compatibility.
# Panel dimensions come from tok100_label_builder (OUTER_W=150.3, OUTER_H=305.5).
PAGE_W = 1191.0
PAGE_H =  842.0

MAR_X  =  24.0
MAR_Y  =  18.0

# Header box
HDR_H  = 105.0
HDR_T  = MAR_Y
HDR_B  = HDR_T + HDR_H

# Three header columns
LOGO_W     = 170.0
INFO_W     = 380.0
APPROVAL_W = 140.0
HDR_L  = MAR_X
HDR_R  = HDR_L + LOGO_W + INFO_W + APPROVAL_W

# Title / dimension zone
TITLE_T = HDR_B + 12.0

# Label layout: OUTER_H from builder = 305.5 pt, fits in remaining height
LABEL_T = TITLE_T + 55.0          # top of label row
LABEL_B = PAGE_H - MAR_Y - 28.0   # leave space for Qty text

PANEL_GAP = 8.0   # gap between panels


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_header(page: fitz.Page, order_data: dict) -> None:
    # Outer border
    border = fitz.Rect(HDR_L, HDR_T, HDR_R, HDR_B)
    page.draw_rect(border, color=(0.6, 0.6, 0.6), width=0.7)

    x1 = HDR_L + LOGO_W
    x2 = x1 + INFO_W

    # Column dividers
    for xd in [x1, x2]:
        page.draw_line(fitz.Point(xd, HDR_T), fitz.Point(xd, HDR_B),
                       color=(0.6, 0.6, 0.6), width=0.7)

    # Cell 1: Sainmarks® logo (text)
    lo_cx = HDR_L + LOGO_W / 2
    fs_logo = 15.0
    tw = fitz.get_text_length("Sainmarks\u00ae", fontname=FB, fontsize=fs_logo)
    page.insert_text(fitz.Point(lo_cx - tw / 2, HDR_T + HDR_H / 2 + fs_logo / 2),
                     "Sainmarks\u00ae", fontname=FB, fontsize=fs_logo,
                     color=(0.15, 0.55, 0.25))

    # Cell 2: info rows
    rows = [
        ("BUYER",          order_data.get("buyer", "OVS")),
        ("CUSTOMER",       order_data.get("customer_name", "")),
        ("DESIGN CODE",    order_data.get("design_code", "")),
        ("PRODUCT CODE",   order_data.get("product_code", "")),
        ("SUBMITTED DATE", order_data.get("submitted_date", "")),
    ]
    row_h = HDR_H / len(rows)
    for i, (label, val) in enumerate(rows):
        y = HDR_T + i * row_h + row_h * 0.65
        if i > 0:
            page.draw_line(fitz.Point(x1, HDR_T + i * row_h),
                           fitz.Point(x2, HDR_T + i * row_h),
                           color=(0.7, 0.7, 0.7), width=0.4)
        page.insert_text(fitz.Point(x1 + 5, y),
                         f"{label} : {val}",
                         fontname=FR, fontsize=8.0, color=(0.2, 0.2, 0.2))

    # Cell 3: ARTWORK FOR APPROVAL
    for i, line in enumerate(["ARTWORK", "FOR", "APPROVAL"]):
        y = HDR_T + 24 + i * 18
        tw = fitz.get_text_length(line, fontname=FB, fontsize=10.0)
        page.insert_text(fitz.Point(x2 + APPROVAL_W / 2 - tw / 2, y),
                         line, fontname=FB, fontsize=10.0, color=(0.1, 0.1, 0.1))


def _draw_page_labels(page: fitz.Page,
                      country: str, title: str, label_size: str,
                      front_x: float) -> None:
    # Red bold title
    fs_title = 12.0
    tw = fitz.get_text_length(title, fontname=FB, fontsize=fs_title)
    cx = (HDR_L + HDR_R) / 2
    page.insert_text(fitz.Point(cx - tw / 2, TITLE_T + 14),
                     title, fontname=FB, fontsize=fs_title,
                     color=(0.82, 0.08, 0.08))

    # Dimension subtitle
    fs_dim = 10.0
    tw2 = fitz.get_text_length(label_size, fontname=FB, fontsize=fs_dim)
    page.insert_text(fitz.Point(cx - tw2 / 2, TITLE_T + 33),
                     label_size, fontname=FB, fontsize=fs_dim,
                     color=(0.1, 0.1, 0.1))

    # "Front" / "Back" labels — positions use OUTER_W (panel width) + PANEL_GAP
    page.insert_text(fitz.Point(front_x, LABEL_T - 8),
                     "Front", fontname=FB, fontsize=11.0, color=DARK)
    back_x = front_x + OUTER_W + PANEL_GAP
    page.insert_text(fitz.Point(back_x, LABEL_T - 8),
                     "Back", fontname=FB, fontsize=11.0, color=DARK)


def _page_number(page: fitz.Page, num: int) -> None:
    txt = str(num)
    tw = fitz.get_text_length(txt, fontname=FR, fontsize=8.0)
    page.insert_text(fitz.Point(PAGE_W / 2 - tw / 2, PAGE_H - 6),
                     txt, fontname=FR, fontsize=8.0, color=(0.5, 0.5, 0.5))


# ── Public API ────────────────────────────────────────────────────────────────

def create_approval_sheet_pdf(
    order_data: dict,
    variant_groups: list[dict],
    png_streams: Optional[dict] = None,          # kept for backward compat, unused
) -> bytes:
    """
    Build the full approval PDF.

    variant_groups: list of {
        'country'    : str,
        'title'      : str,   e.g. "262SWT301LT-230 - WARM - EGGNOG - B0854559"
        'label_size' : str,   e.g. "45mm x 100mm"
        'variants'   : list[{all item fields required by _draw_back_panel}]
    }
    """
    doc = fitz.open()

    for page_num, group in enumerate(variant_groups, start=1):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)

        # White background
        page.draw_rect(fitz.Rect(0, 0, PAGE_W, PAGE_H),
                       color=WHITE, fill=WHITE, width=0)

        # Header
        _draw_header(page, order_data)

        variants = group.get("variants", [])
        n_back   = min(len(variants), 6)
        if n_back == 0:
            _page_number(page, page_num)
            continue

        # Centre all panels (1 front + n_back backs) on the page
        total_panels = 1 + n_back
        total_w = total_panels * OUTER_W + (total_panels - 1) * PANEL_GAP
        front_x = (PAGE_W - total_w) / 2

        # Page titles
        _draw_page_labels(page,
                          group.get("country", ""),
                          group.get("title", ""),
                          group.get("label_size", "45mm x 100mm"),
                          front_x)

        # Front panel — uses OUTER_W x OUTER_H fixed dimensions
        _draw_front_panel(page, front_x, LABEL_T)

        # Back panels — one per size variant, same fixed dimensions
        back_start = front_x + OUTER_W + PANEL_GAP
        for i, v in enumerate(variants[:6]):
            bx = back_start + i * (OUTER_W + PANEL_GAP)
            _draw_back_panel(page, bx, LABEL_T, v)

        _page_number(page, page_num)

    if not doc.page_count:
        doc.new_page(width=PAGE_W, height=PAGE_H)

    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out
