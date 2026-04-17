"""
TOK100 Label Builder — generates a single label PDF for one OVS KIDS price tag variant.

Matches the design language of the actual XMPie reference output (TOK100_B0854559_1.pdf):
  - Dark navy front panel   (OVS logo + kids brand + punch hole)
  - White data back panel   (size grid, price, barcode, refs, country)

All dimensions in PDF points (1 pt = 1/72 inch).
Physical tag: 45 mm × 100 mm  →  127.56 × 283.46 pt
We render at 2.2× scale for screen clarity:  ~280 × 624 pt per panel.
"""
import io
import re
import fitz  # PyMuPDF

# ── Scale factor ─────────────────────────────────────────────────────────────
SCALE = 2.2          # render at 2.2× physical size for screen quality
PHYSICAL_W_PT = 127.56   # 45 mm
PHYSICAL_H_PT = 283.46   # 100 mm

TAG_W = PHYSICAL_W_PT * SCALE   # ~280 pt
TAG_H = PHYSICAL_H_PT * SCALE   # ~624 pt

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY     = (0.057, 0.094, 0.165)   # dark navy blue
GOLD     = (0.922, 0.714, 0.180)   # OVS gold/yellow
MAGENTA  = (0.878, 0.129, 0.392)   # pink/magenta accent strip
WHITE    = (1.0, 1.0, 1.0)
BLACK    = (0.0, 0.0, 0.0)
DARK     = (0.1, 0.1, 0.1)
GREY     = (0.55, 0.55, 0.55)
HIGHLIGHT_BG = (0.95, 0.95, 0.95)   # light grey for highlighted size row
BORDER   = (0.3, 0.3, 0.3)

# PyMuPDF base-14 font aliases
FB = "hebo"    # Helvetica-Bold
FR = "helv"    # Helvetica

# ── Sizes known for TOK100 KIDS 3-15 range (label shows all, one highlighted)
TOK100_SIZE_RANGE = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]


def _draw_front_panel(page: fitz.Page, x: float, y: float) -> None:
    """Draw the navy blue front tag face with OVS + kids branding."""
    w, h = TAG_W, TAG_H

    # --- Background
    r = fitz.Rect(x, y, x + w, y + h)
    page.draw_rect(r, color=NAVY, fill=NAVY, width=0)

    # --- Punch hole at top-centre
    cx = x + w / 2
    hole_y = y + 18 * SCALE
    page.draw_circle(fitz.Point(cx, hole_y), 5 * SCALE,
                     color=WHITE, fill=WHITE)

    # --- Thin magenta strip near top (under punch hole)
    strip_y = y + 30 * SCALE
    page.draw_line(fitz.Point(x, strip_y), fitz.Point(x + w, strip_y),
                   color=MAGENTA, width=1.5 * SCALE)

    # --- OVS text (gold, large, centred)
    ovs_fs = 18 * SCALE
    ovs_y = y + h * 0.43
    tw = fitz.get_text_length("OVS", fontname=FB, fontsize=ovs_fs)
    page.insert_text(fitz.Point(cx - tw / 2, ovs_y),
                     "OVS", fontname=FB, fontsize=ovs_fs, color=GOLD)

    # --- "kids" below (gold, smaller, italic-like via regular)
    kids_fs = 10 * SCALE
    kids_y = ovs_y + ovs_fs * 0.85
    tw2 = fitz.get_text_length("kids", fontname=FR, fontsize=kids_fs)
    page.insert_text(fitz.Point(cx - tw2 / 2, kids_y),
                     "kids", fontname=FR, fontsize=kids_fs, color=GOLD)

    # --- Thin magenta strip near bottom
    bot_strip_y = y + h - 10 * SCALE
    page.draw_line(fitz.Point(x, bot_strip_y), fitz.Point(x + w, bot_strip_y),
                   color=MAGENTA, width=1.5 * SCALE)


def _draw_back_panel(page: fitz.Page, item_data: dict,
                     x: float, y: float) -> None:
    """
    Draw the white back panel with all variable data fields.

    item_data expected keys:
      sizes           : dict  e.g. {'YEARS':'4-5','CM':'110','IT':'4-5','MEX':'4-5 A'}
      selling_price   : str   e.g. '169,00'
      currency_symbol : str   e.g. '€'  (may be garbled — we normalise)
      barcode_number  : str   e.g. '8051553298798'
      sku_code        : str
      commercial_ref  : str   e.g. 'PR711 AI08'
      supplier_style  : str   e.g. '262SWT301LT-230'
      color           : str   e.g. 'EGGNOG'
      country_of_origin: str  e.g. 'MADE IN MIDDLE EAST'
      quantity        : int
    """
    w, h = TAG_W, TAG_H
    pad_x = 5 * SCALE
    pad_y = 4 * SCALE

    # --- White background
    r = fitz.Rect(x, y, x + w, y + h)
    page.draw_rect(r, color=BORDER, fill=WHITE, width=0.5)

    cursor_y = y + pad_y + 6 * SCALE

    # ── Brand name "K I D S" spaced letters ─────────────────────────────────
    brand_fs = 5 * SCALE
    brand_txt = "K I D S"
    tw = fitz.get_text_length(brand_txt, fontname=FB, fontsize=brand_fs)
    page.insert_text(fitz.Point(x + (w - tw) / 2, cursor_y),
                     brand_txt, fontname=FB, fontsize=brand_fs, color=DARK)
    cursor_y += brand_fs + 2 * SCALE

    # Thin navy underline below brand
    page.draw_line(fitz.Point(x + pad_x, cursor_y),
                   fitz.Point(x + w - pad_x, cursor_y),
                   color=NAVY, width=0.8)
    cursor_y += 3 * SCALE

    # ── SIZE GRID ─────────────────────────────────────────────────────────────
    sizes = item_data.get("sizes") or {}
    current_years = sizes.get("YEARS", "")
    current_cm    = sizes.get("CM", "")
    current_it    = sizes.get("IT", "")
    current_mex   = sizes.get("MEX", current_it or "")

    # Header row: YEARS | CM
    hdr_fs = 3.8 * SCALE
    col_years_x = x + pad_x
    col_cm_x    = x + w * 0.63
    page.insert_text(fitz.Point(col_years_x, cursor_y),
                     "YEARS", fontname=FB, fontsize=hdr_fs, color=GREY)
    page.insert_text(fitz.Point(col_cm_x, cursor_y),
                     "CM", fontname=FB, fontsize=hdr_fs, color=GREY)
    cursor_y += hdr_fs + 1.5 * SCALE

    # Size range rows — highlight current item
    size_fs = 4.2 * SCALE
    row_h   = size_fs + 2.5 * SCALE
    for size_label in TOK100_SIZE_RANGE:
        is_current = (size_label == current_years)
        cm_val = current_cm if is_current else ""

        # Highlight box for current
        if is_current:
            hi_rect = fitz.Rect(x + pad_x - 1, cursor_y - size_fs + 1,
                                x + w - pad_x + 1, cursor_y + 2)
            page.draw_rect(hi_rect, color=NAVY, fill=NAVY, width=0)
            txt_color = WHITE
        else:
            txt_color = DARK

        page.insert_text(fitz.Point(col_years_x, cursor_y),
                         size_label, fontname=FB if is_current else FR,
                         fontsize=size_fs, color=txt_color)
        if cm_val:
            page.insert_text(fitz.Point(col_cm_x, cursor_y),
                             cm_val, fontname=FB,
                             fontsize=size_fs, color=txt_color)
        cursor_y += row_h

    # IT/MEX row (shown below size grid)
    cursor_y += 1 * SCALE
    page.draw_line(fitz.Point(x + pad_x, cursor_y),
                   fitz.Point(x + w - pad_x, cursor_y),
                   color=(0.8, 0.8, 0.8), width=0.4)
    cursor_y += 2.5 * SCALE
    itm_fs = 3.5 * SCALE
    it_row = f"IT {current_it}   MEX {current_mex}"
    page.insert_text(fitz.Point(x + pad_x, cursor_y),
                     it_row, fontname=FR, fontsize=itm_fs, color=GREY)
    cursor_y += itm_fs + 3 * SCALE

    # ── PRICE ─────────────────────────────────────────────────────────────────
    # Normalise currency symbol (may be garbled from XML encoding)
    raw_sym = item_data.get("currency_symbol", "") or ""
    # Strip non-ASCII control chars, keep printable
    currency = "".join(c for c in raw_sym if c.isprintable() and ord(c) < 0x200)
    if not currency or len(currency) > 2:
        currency = "€"

    raw_price = item_data.get("selling_price", "0,00") or "0,00"
    # Split at comma or dot for large/small display
    if "," in raw_price:
        major, minor = raw_price.split(",", 1)
        minor = "," + minor
    elif "." in raw_price:
        major, minor = raw_price.split(".", 1)
        minor = "." + minor
    else:
        major, minor = raw_price, ""

    page.draw_line(fitz.Point(x + pad_x, cursor_y),
                   fitz.Point(x + w - pad_x, cursor_y),
                   color=NAVY, width=0.8)
    cursor_y += 3 * SCALE

    price_large_fs = 14 * SCALE
    price_small_fs = 8 * SCALE
    sym_fs = 7 * SCALE

    # Currency symbol
    page.insert_text(fitz.Point(x + pad_x, cursor_y + price_large_fs * 0.5),
                     currency, fontname=FR, fontsize=sym_fs, color=DARK)

    # Major price part
    sym_w = fitz.get_text_length(currency, fontname=FR, fontsize=sym_fs) + 2 * SCALE
    page.insert_text(fitz.Point(x + pad_x + sym_w, cursor_y + price_large_fs * 0.85),
                     major, fontname=FB, fontsize=price_large_fs, color=DARK)

    # Minor price part (smaller, aligned top-right of major)
    maj_w = fitz.get_text_length(major, fontname=FB, fontsize=price_large_fs)
    page.insert_text(fitz.Point(x + pad_x + sym_w + maj_w + 1,
                                cursor_y + price_small_fs * 0.9),
                     minor, fontname=FR, fontsize=price_small_fs, color=DARK)

    cursor_y += price_large_fs + 3 * SCALE

    page.draw_line(fitz.Point(x + pad_x, cursor_y),
                   fitz.Point(x + w - pad_x, cursor_y),
                   color=NAVY, width=0.8)
    cursor_y += 4 * SCALE

    # ── REFS (SKU, commercial ref) ────────────────────────────────────────────
    ref_fs = 3.5 * SCALE
    sku  = item_data.get("sku_code", "") or ""
    cref = item_data.get("commercial_ref", "") or ""

    page.insert_text(fitz.Point(x + pad_x, cursor_y),
                     sku, fontname=FR, fontsize=ref_fs, color=GREY)
    cursor_y += ref_fs + 1.5 * SCALE
    page.insert_text(fitz.Point(x + pad_x, cursor_y),
                     cref, fontname=FR, fontsize=ref_fs, color=GREY)
    cursor_y += ref_fs + 3 * SCALE

    # ── BARCODE SECTION ───────────────────────────────────────────────────────
    barcode = item_data.get("barcode_number", "") or ""
    if barcode:
        # Visual barcode simulation: alternating thin/thick vertical lines
        bc_x     = x + pad_x
        bc_y     = cursor_y
        bc_w     = w - 2 * pad_x
        bc_h     = 18 * SCALE
        line_w   = bc_w / max(len(barcode) * 2, 1)

        for i, digit in enumerate(barcode):
            thick = (int(digit) % 3 == 0)
            lx = bc_x + i * (line_w * 2)
            lw = line_w * (2 if thick else 1) if lx + line_w < x + w - pad_x else 0.5
            page.draw_line(fitz.Point(lx, bc_y),
                           fitz.Point(lx, bc_y + bc_h),
                           color=BLACK, width=lw)

        # Barcode number below
        bc_num_fs = 3.2 * SCALE
        tw = fitz.get_text_length(barcode, fontname=FR, fontsize=bc_num_fs)
        page.insert_text(fitz.Point(x + (w - tw) / 2, cursor_y + bc_h + bc_num_fs),
                         barcode, fontname=FR, fontsize=bc_num_fs, color=DARK)

        cursor_y += bc_h + bc_num_fs + 4 * SCALE

    # ── COUNTRY OF ORIGIN ─────────────────────────────────────────────────────
    country_raw = item_data.get("country_of_origin", "") or ""
    # Normalise: strip "MADE IN " prefix if already present
    country_clean = re.sub(r"^MADE\s+IN\s+", "", country_raw.upper()).strip()
    country_txt = f"MADE IN {country_clean}" if country_clean else ""

    cty_fs = 3.5 * SCALE
    page.draw_line(fitz.Point(x + pad_x, cursor_y),
                   fitz.Point(x + w - pad_x, cursor_y),
                   color=(0.8, 0.8, 0.8), width=0.4)
    cursor_y += 3 * SCALE

    if country_txt:
        tw = fitz.get_text_length(country_txt, fontname=FR, fontsize=cty_fs)
        page.insert_text(fitz.Point(x + (w - tw) / 2, cursor_y),
                         country_txt, fontname=FR, fontsize=cty_fs, color=GREY)

    # ── OVS contact (very small) ──────────────────────────────────────────────
    contact_fs = 2.2 * SCALE
    contact = "OVS - Via Terraglio 17, 30174 Venezia ITALIA"
    cursor_y = y + h - 7 * SCALE
    page.insert_text(fitz.Point(x + pad_x, cursor_y),
                     contact, fontname=FR, fontsize=contact_fs, color=(0.75, 0.75, 0.75))


def build_label_pdf(item_data: dict) -> bytes:
    """
    Generate a single TOK100 label as a standalone PDF.

    The label shows:
      LEFT  : Front navy panel (OVS + kids branding)
      RIGHT : Back data panel (size grid, price, barcode, refs, country)

    Returns PDF bytes.
    """
    page_w = TAG_W * 2 + 6   # front + small gap + back
    page_h = TAG_H

    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)

    _draw_front_panel(page, 0, 0)
    _draw_back_panel(page, item_data, TAG_W + 6, 0)

    out = io.BytesIO()
    doc.save(out, garbage=4, deflate=True)
    doc.close()
    return out.getvalue()


def build_label_png(item_data: dict, dpi: int = 150) -> bytes:
    """Render label PDF → PNG bytes for approval sheet embedding."""
    pdf_bytes = build_label_pdf(item_data)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = doc[0].get_pixmap(matrix=mat, alpha=False)
    doc.close()
    return pix.tobytes("png")


def build_label_thumbnail(item_data: dict, dpi: int = 60) -> bytes:
    """Very small thumbnail for list views."""
    return build_label_png(item_data, dpi=dpi)
