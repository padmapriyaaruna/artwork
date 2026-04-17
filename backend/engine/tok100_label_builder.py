"""
TOK100 Label Builder v2 — generates a single OVS KIDS price tag PDF.

Design precisely matches TOK100_B0854559_1.pdf reference output from XMPie.

Label back panel field order (top→bottom):
  1. "K I D S"                  (brand, spaced, bold)
  2. YEARS  CM                  (current size highlighted — bold, larger)
  3. IT___  MEX___  A           (secondary sizing, same row)
  4. 4-5  5-6  6-7              (full size range row 1, small)
     7-8  8-9  9-10             (full size range row 2, small)
  5. 3632   230   2768957       (sub_dept | dept/colour | sku_code)
  6. 8  051553  298798          (barcode EAN-13 split 1+6+6)
  7. 2768957                    (style_code = parent style SKU)
  8. PR711 AI08                 (commercial_ref)
  9. € 29,95                    (selling_price, large)
 10. Qty - 128                  (quantity, shown below label boundary)

All measurements derived from the 2004×1417 reference page then
scaled to 300×680 pt standalone label page.
"""
import io
import re
import fitz  # PyMuPDF


# ── Page / tag geometry ────────────────────────────────────────────────────────
# Standalone label page (back panel only — front is drawn on approval sheet)
PAGE_W = 300.0   # pt
PAGE_H = 680.0   # pt

# Back panel region inside page
BX = 15.0        # panel left margin
BY = 10.0        # panel top margin
BW = PAGE_W - 2 * BX   # panel width
BH = PAGE_H - 30.0      # panel height (leave room for Qty at bottom)

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY     = (0.057, 0.094, 0.165)
GOLD     = (0.922, 0.714, 0.180)
MAGENTA  = (0.878, 0.129, 0.392)
WHITE    = (1.0, 1.0, 1.0)
BLACK    = (0.0, 0.0, 0.0)
DARK     = (0.08, 0.08, 0.08)
BORDER   = (0.3, 0.3, 0.3)
GREY     = (0.50, 0.50, 0.50)
LGREY    = (0.72, 0.72, 0.72)

# Font aliases (PyMuPDF Base-14)
FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

# TOK100 size range (always shown in full)
TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fix_currency(raw: str) -> str:
    """Normalise garbled currency — map common encodings to € or AED."""
    if not raw:
        return "€"
    # Remove non-printable / high-byte garbage, keep ASCII
    clean = "".join(c for c in raw if 0x20 <= ord(c) < 0x80)
    if not clean or clean in ("?", "â", "¬", "â¬"):
        return "€"
    return clean[:2]


def _split_barcode(barcode: str) -> tuple[str, str, str]:
    """Split EAN-13 as prefix(1) + manufacturer(6) + product(6)."""
    bc = barcode.strip()
    if len(bc) >= 13:
        return bc[0], bc[1:7], bc[7:13]
    elif len(bc) >= 7:
        return bc[0], bc[1:7], bc[7:]
    else:
        return bc, "", ""


def _split_price(price_str: str) -> tuple[str, str]:
    """Split '29,95' → ('29', ',95')  or  '29.95' → ('29', '.95')."""
    p = price_str.strip()
    m = re.match(r"^(\d+)([,.]?\d*)$", p)
    if m:
        return m.group(1), m.group(2)
    return p, ""


def _centered_x(text: str, font: str, fs: float, cx: float) -> float:
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return cx - tw / 2


# ── Back panel renderer ────────────────────────────────────────────────────────

def _draw_back_panel(page: fitz.Page,
                     x0: float, y0: float,
                     w: float, h: float,
                     item_data: dict) -> None:
    """
    Draw the data back panel of the OVS KIDS label.
    (x0, y0) = top-left corner, (w, h) = panel size.
    """
    pad = 6.0
    cx = x0 + w / 2
    y = y0 + 4.0    # running cursor

    # Outer border
    page.draw_rect(fitz.Rect(x0, y0, x0 + w, y0 + h),
                   color=BORDER, width=0.6)

    # ── Top punch-hole area ─────────────────────────────────────────────────
    page.draw_circle(fitz.Point(cx, y + 6), 4.0, color=LGREY, fill=LGREY)
    y += 18.0

    # Thin navy line under punch hole
    page.draw_line(fitz.Point(x0 + pad, y), fitz.Point(x0 + w - pad, y),
                   color=NAVY, width=0.6)
    y += 6.0

    # ── 1. "K I D S" ────────────────────────────────────────────────────────
    fs_brand = 9.0
    page.insert_text(
        fitz.Point(_centered_x("K I D S", FB, fs_brand, cx), y + fs_brand),
        "K I D S", fontname=FB, fontsize=fs_brand, color=DARK
    )
    y += fs_brand + 4.0

    # Thin rule
    page.draw_line(fitz.Point(x0 + pad, y), fitz.Point(x0 + w - pad, y),
                   color=LGREY, width=0.4)
    y += 5.0

    # ── 2. Current YEARS + CM (highlighted row) ─────────────────────────────
    sizes      = item_data.get("sizes") or {}
    cur_years  = sizes.get("YEARS", "")
    cur_cm     = sizes.get("CM", "")
    cur_it     = sizes.get("IT", "")
    cur_mex_raw= sizes.get("MEX", cur_it)
    # Strip trailing ' A' — we print 'A' separately
    cur_mex    = re.sub(r"\s*A$", "", cur_mex_raw).strip()

    fs_cur = 9.5
    # Highlight background
    hi_h = fs_cur + 4.0
    page.draw_rect(fitz.Rect(x0 + pad, y, x0 + w - pad, y + hi_h),
                   color=NAVY, fill=NAVY, width=0)

    # YEARS label
    lbl_fs = 6.5
    page.insert_text(fitz.Point(x0 + pad + 2, y + lbl_fs + 1),
                     "YEARS", fontname=FB, fontsize=lbl_fs, color=WHITE)
    # YEARS value
    page.insert_text(fitz.Point(x0 + pad + 30, y + fs_cur + 1),
                     cur_years, fontname=FB, fontsize=fs_cur, color=WHITE)
    # CM label
    page.insert_text(fitz.Point(x0 + w * 0.62, y + lbl_fs + 1),
                     "CM", fontname=FB, fontsize=lbl_fs, color=WHITE)
    # CM value
    page.insert_text(fitz.Point(x0 + w * 0.62 + 16, y + fs_cur + 1),
                     cur_cm, fontname=FB, fontsize=fs_cur, color=WHITE)
    y += hi_h + 2.0

    # ── 3. IT + MEX + A (secondary sizing) ─────────────────────────────────
    fs_sec = 8.0
    # IT label + value
    lbl_fs2 = 6.0
    page.insert_text(fitz.Point(x0 + pad, y + lbl_fs2),
                     "IT", fontname=FR, fontsize=lbl_fs2, color=GREY)
    page.insert_text(fitz.Point(x0 + pad + 12, y + fs_sec),
                     cur_it, fontname=FB, fontsize=fs_sec, color=DARK)
    # MEX label + value
    mex_x = x0 + w * 0.40
    page.insert_text(fitz.Point(mex_x, y + lbl_fs2),
                     "MEX", fontname=FR, fontsize=lbl_fs2, color=GREY)
    page.insert_text(fitz.Point(mex_x + 18, y + fs_sec),
                     cur_mex, fontname=FB, fontsize=fs_sec, color=DARK)
    # A suffix
    a_x = mex_x + 18 + fitz.get_text_length(cur_mex, fontname=FB, fontsize=fs_sec) + 3
    page.insert_text(fitz.Point(a_x, y + fs_sec),
                     "A", fontname=FB, fontsize=fs_sec, color=DARK)
    y += fs_sec + 4.0

    # ── 4. Size range grid (all 6 sizes in 2 rows) ──────────────────────────
    fs_rng = 6.5
    row1 = TOK100_SIZES[:3]  # 4-5, 5-6, 6-7
    row2 = TOK100_SIZES[3:]  # 7-8, 8-9, 9-10
    col_step = (w - 2 * pad) / 3.0

    for ri, row in enumerate([row1, row2]):
        for ci, sz in enumerate(row):
            sx = x0 + pad + ci * col_step + col_step / 2
            sx -= fitz.get_text_length(sz, fontname=FR, fontsize=fs_rng) / 2
            # Underline current size in range
            color = NAVY if sz == cur_years else LGREY
            fw = FB if sz == cur_years else FR
            page.insert_text(fitz.Point(sx, y + fs_rng), sz,
                              fontname=fw, fontsize=fs_rng, color=color)
        y += fs_rng + 2.0
    y += 2.0

    # Thin rule
    page.draw_line(fitz.Point(x0 + pad, y), fitz.Point(x0 + w - pad, y),
                   color=LGREY, width=0.4)
    y += 5.0

    # ── 5. sub_dept | dept/colour | sku_code ────────────────────────────────
    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department", "") or "")
    sku      = str(item_data.get("sku_code", "") or "")
    fs_ref   = 7.0

    ref_row = f"{sub_dept}   {dept}   {sku}"
    page.insert_text(
        fitz.Point(_centered_x(ref_row, FR, fs_ref, cx), y + fs_ref),
        ref_row, fontname=FR, fontsize=fs_ref, color=DARK
    )
    y += fs_ref + 4.0

    # ── 6. Barcode number (EAN-13 split 1+6+6) ─────────────────────────────
    barcode  = str(item_data.get("barcode_number", "") or "")
    p1, p2, p3 = _split_barcode(barcode)
    bc_row = f"{p1}   {p2}   {p3}"

    # Mini barcode graphic — alternating vertical rules
    bc_y  = y
    bc_h  = 18.0
    bc_x0 = x0 + pad
    bc_x1 = x0 + w - pad
    if barcode:
        n   = len(barcode)
        bar_w = (bc_x1 - bc_x0) / (n * 1.8)
        for i, d in enumerate(barcode):
            lx = bc_x0 + i * (bar_w * 1.8)
            lw = bar_w * (1.6 if int(d) % 3 == 0 else 0.8)
            if lx < bc_x1:
                page.draw_line(fitz.Point(lx, bc_y),
                               fitz.Point(lx, bc_y + bc_h),
                               color=BLACK, width=lw)

    y += bc_h + 2.0

    # Barcode digits below bars
    fs_bc = 7.0
    page.insert_text(
        fitz.Point(_centered_x(bc_row, FR, fs_bc, cx), y + fs_bc),
        bc_row, fontname=FR, fontsize=fs_bc, color=DARK
    )
    y += fs_bc + 4.0

    # ── 7. style_code (parent style SKU) ───────────────────────────────────
    style = str(item_data.get("style_code", "") or "")
    if style:
        page.insert_text(
            fitz.Point(_centered_x(style, FR, fs_ref, cx), y + fs_ref),
            style, fontname=FR, fontsize=fs_ref, color=GREY
        )
        y += fs_ref + 3.0

    # ── 8. commercial_ref ───────────────────────────────────────────────────
    cref = str(item_data.get("commercial_ref", "") or "")
    if cref:
        page.insert_text(
            fitz.Point(_centered_x(cref, FR, fs_ref, cx), y + fs_ref),
            cref, fontname=FR, fontsize=fs_ref, color=GREY
        )
        y += fs_ref + 4.0

    # Thin navy rule before price
    page.draw_line(fitz.Point(x0 + pad, y), fitz.Point(x0 + w - pad, y),
                   color=NAVY, width=0.7)
    y += 6.0

    # ── 9. Currency symbol + price (large) ─────────────────────────────────
    currency = _fix_currency(item_data.get("currency_symbol", ""))
    price_str= str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_str)

    fs_sym   = 9.0
    fs_major = 28.0
    fs_minor = 15.0

    sym_w   = fitz.get_text_length(currency, fontname=FR, fontsize=fs_sym)
    maj_w   = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w   = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)
    total_w = sym_w + 4 + maj_w + 2 + min_w
    px = cx - total_w / 2

    page.insert_text(fitz.Point(px, y + fs_major * 0.55),
                     currency, fontname=FR, fontsize=fs_sym, color=DARK)
    page.insert_text(fitz.Point(px + sym_w + 4, y + fs_major),
                     major, fontname=FB, fontsize=fs_major, color=DARK)
    page.insert_text(fitz.Point(px + sym_w + 4 + maj_w + 2, y + fs_minor * 1.1),
                     minor, fontname=FR, fontsize=fs_minor, color=DARK)
    y += fs_major + 6.0

    # Thin navy rule after price
    page.draw_line(fitz.Point(x0 + pad, y), fitz.Point(x0 + w - pad, y),
                   color=NAVY, width=0.7)
    y += 5.0

    # ── Country of Origin (MADE IN ______) ─────────────────────────────────
    country_raw = str(item_data.get("country_of_origin", "") or "")
    country_clean = re.sub(r"^MADE\s+IN\s+", "", country_raw.upper()).strip()
    if country_clean:
        cty_txt = f"MADE IN {country_clean}"
        fs_cty  = 7.0
        page.insert_text(
            fitz.Point(_centered_x(cty_txt, FR, fs_cty, cx), y + fs_cty),
            cty_txt, fontname=FR, fontsize=fs_cty, color=GREY
        )
        y += fs_cty + 4.0

    # OVS address (very small)
    fs_addr = 5.5
    addr = "OVS - Via Terraglio 17, 30174 Venezia ITALIA"
    page.insert_text(
        fitz.Point(_centered_x(addr, FR, fs_addr, cx), y + fs_addr),
        addr, fontname=FR, fontsize=fs_addr, color=LGREY
    )

    # ── 10. Qty (below panel) ───────────────────────────────────────────────
    qty     = item_data.get("quantity", 0)
    qty_txt = f"Qty - {qty}"
    fs_qty  = 11.0
    qty_y   = y0 + h + fs_qty + 4
    page.insert_text(
        fitz.Point(_centered_x(qty_txt, FB, fs_qty, cx), qty_y),
        qty_txt, fontname=FB, fontsize=fs_qty, color=DARK
    )


# ── Front panel renderer ──────────────────────────────────────────────────────

def _draw_front_panel(page: fitz.Page,
                      x0: float, y0: float,
                      w: float, h: float) -> None:
    """Navy blue front hang-tag with OVS branding."""
    cx = x0 + w / 2

    # Navy body
    page.draw_rect(fitz.Rect(x0, y0, x0 + w, y0 + h),
                   color=NAVY, fill=NAVY, width=0)

    # Punch hole
    page.draw_circle(fitz.Point(cx, y0 + 14), 5.5, color=WHITE, fill=WHITE)

    # Top magenta strip
    page.draw_line(fitz.Point(x0, y0 + 26), fitz.Point(x0 + w, y0 + 26),
                   color=MAGENTA, width=2.0)

    # OVS (gold, large)
    fs_ovs = 38.0
    ovs_y  = y0 + h * 0.45
    page.insert_text(
        fitz.Point(_centered_x("OVS", FB, fs_ovs, cx), ovs_y),
        "OVS", fontname=FB, fontsize=fs_ovs, color=GOLD
    )

    # "kids" (gold, smaller)
    fs_kids = 16.0
    page.insert_text(
        fitz.Point(_centered_x("kids", FR, fs_kids, cx), ovs_y + fs_kids * 1.1),
        "kids", fontname=FR, fontsize=fs_kids, color=GOLD
    )

    # Bottom magenta strip
    page.draw_line(fitz.Point(x0, y0 + h - 14), fitz.Point(x0 + w, y0 + h - 14),
                   color=MAGENTA, width=2.0)


# ── Public API ────────────────────────────────────────────────────────────────

def build_label_pdf(item_data: dict) -> bytes:
    """
    Single-item label PDF: front panel LEFT, back panel RIGHT.
    Used as the per-item artwork stored in DB.
    """
    gap      = 8.0
    front_w  = BW * 0.38        # front is narrower (just OVS logo)
    back_w   = BW - front_w - gap

    full_w   = BX + front_w + gap + back_w + BX
    full_h   = PAGE_H

    doc  = fitz.open()
    page = doc.new_page(width=full_w, height=full_h)

    # Draw white background
    page.draw_rect(fitz.Rect(0, 0, full_w, full_h), color=WHITE, fill=WHITE, width=0)

    _draw_front_panel(page, BX, BY, front_w, BH)
    _draw_back_panel(page, BX + front_w + gap, BY, back_w, BH, item_data)

    out = io.BytesIO()
    doc.save(out, garbage=4, deflate=True)
    doc.close()
    return out.getvalue()


def build_label_png(item_data: dict, dpi: int = 150) -> bytes:
    """Render label PDF → PNG bytes."""
    pdf_bytes = build_label_pdf(item_data)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = doc[0].get_pixmap(matrix=mat, alpha=False)
    doc.close()
    return pix.tobytes("png")


def build_label_thumbnail(item_data: dict, dpi: int = 60) -> bytes:
    """Very small thumbnail for list views."""
    return build_label_png(item_data, dpi=dpi)


def build_back_panel_png(item_data: dict, dpi: int = 150) -> bytes:
    """
    Render ONLY the back panel (data side) as a PNG.
    Used by the approval sheet to embed individual label backs.
    """
    doc  = fitz.open()
    page = doc.new_page(width=BW, height=BH + 30)
    page.draw_rect(fitz.Rect(0, 0, BW, BH + 30), color=WHITE, fill=WHITE, width=0)
    _draw_back_panel(page, 0, 0, BW, BH, item_data)

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = doc[0].get_pixmap(matrix=mat, alpha=False)
    doc.close()
    return pix.tobytes("png")
