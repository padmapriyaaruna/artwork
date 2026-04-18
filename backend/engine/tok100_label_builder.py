# -*- coding: utf-8 -*-
"""
TOK100 Label Builder v11  -  pixel-perfect match to Actual.jpg master template

v11 fixes (from Actual.jpg pixel analysis vs Sample.jpg defects):

  1. YEARS/CM TABLE  — now fully enclosed with DARK top + bottom borders.
     Vertical divider spans exactly between those two lines. Labels left-aligned
     with 4pt padding; values right-aligned with 4pt padding.

  2. SIZE CHART  — active chip box positioned 3pt below TABLE_BOT so it never
     overlaps the table bottom border. CHIP_W=30pt, CHIP_GAP=7.5pt giving
     natural spacing matching Actual.jpg. Both rows horizontally centered.

  3. BARCODE AREA  — dept/sub_dept/sku joined inline, centered over the FULL
     middle-column width (not just barcode-image width). Barcode bars at BAR_H=28pt.
     Style+cref centered below digit string.

  4. CURRENCY SYMBOL  — € uses SAME bold font AND SAME 24pt size as the main
     integer "29". EUR_raise=0 (identical baseline). Small 2pt kerning gap
     between € and 29.

  5. CENTS  — ,95 at 50% of major (12pt), raised by (fs_major - fs_minor)*0.72
     so its cap-top aligns with the cap-top of "29" (superscript style).
"""
import io, os, re
import fitz  # PyMuPDF

# ── Template file paths ────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_TMPL = os.path.normpath(os.path.join(_HERE, "..", "templates", "OVS", "TOK100"))

FRONT_PANEL_TEMPLATE = os.path.join(_TMPL, "front_panel_ref.pdf")
BACK_PANEL_TEMPLATE  = os.path.join(_TMPL, "back_panel_ref.pdf")

# ── Panel geometry (pt, measured from reference at 400 DPI) ───────────────────
OUTER_W = 150.3
OUTER_H = 305.5

INNER_X = 11.5
INNER_Y = 10.8
INNER_W = 127.2
INNER_H = 283.9

HOLE_RX = 74.8
HOLE_RY = 30.2
HOLE_R  = 5.1

SEP_Y  = 257.49   # dashed green price-separator y (panel-relative)
SEP_X0 = 12.7
SEP_X1 = 134.4

_C3 = INNER_W / 3.0   # ~42.4 pt per column

# White-overwrite zones (panel-relative)
# LEFT COL extra erase (y=188-215): prevents Triman icon bleeding into size grid row 2
ZONES = [
    (INNER_X,           120.0, INNER_X + INNER_W,   188.0),
    (INNER_X,           188.0, INNER_X + _C3,        215.0),   # left col top portion
    (INNER_X + _C3,     188.0, INNER_X + 2 * _C3,  258.0),
    (INNER_X + 2*_C3,   188.0, INNER_X + INNER_W,  258.0),
    (INNER_X,           256.0, INNER_X + INNER_W,  OUTER_H),
]

# ── Colours ───────────────────────────────────────────────────────────────────
MAGENTA = (0.898, 0.023, 0.584)
NAVY    = (0.000, 0.141, 0.235)
GOLD    = (0.992, 0.725, 0.153)
GREEN   = (0.451, 0.749, 0.267)
WHITE   = (1.000, 1.000, 1.000)
BLACK   = (0.000, 0.000, 0.000)
DARK    = (0.080, 0.080, 0.080)
GREY    = (0.450, 0.450, 0.450)
LGREY   = (0.680, 0.680, 0.680)
MID     = (0.280, 0.280, 0.280)

# ── Fonts ─────────────────────────────────────────────────────────────────────
FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

# ── Sizes ─────────────────────────────────────────────────────────────────────
TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]
SIZE_ROWS    = [TOK100_SIZES[:3], TOK100_SIZES[3:]]
CM_MAP = {"4-5":"110","5-6":"116","6-7":"122",
           "7-8":"128","8-9":"134","9-10":"140"}

COUNTRY_ZONE_MAP = {
    "WARM":        "INDIA",
    "COLD":        "INDIA",
    "MIDDLE EAST": "INDIA",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cx(text, font, fs, area_x0, area_w):
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x0 + (area_w - tw) / 2

def _rx(text, font, fs, area_x1):
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x1 - tw

def _fix_currency(raw):
    EUR = chr(128)          # euro in WinAnsiEncoding (cp1252 byte 0x80)
    if not raw:
        return EUR
    s = str(raw)
    # Catch Unicode euro U+20AC in any encoding form
    if "\u20ac" in s or "&#8364;" in s or "&euro;" in s:
        return EUR
    clean = "".join(c for c in s if 0x20 <= ord(c) < 0x80)
    if not clean or clean[0] in "?":
        return EUR
    return clean

def _split_price(s):
    s = str(s or "0,00").strip()
    m = re.match(r"^(\d+)([,.]?\d*)$", s)
    return (m.group(1), m.group(2)) if m else (s, "")

def _bc_chunks(bc):
    bc = str(bc or "").strip()
    if len(bc) >= 13:
        return bc[0], bc[1:7], bc[7:13]
    if len(bc) >= 7:
        return bc[0], bc[1:7], bc[7:]
    return bc, "", ""


# ── EAN-13 ────────────────────────────────────────────────────────────────────
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


def _draw_barcode(page, x0, y0, w, bar_h, bc_str, txt_x0=None, txt_w=None):
    """EAN-13 barcode as 300 DPI PNG + digit string centred below."""
    from PIL import Image, ImageDraw
    bits  = _ean13_bits(bc_str)
    w_px  = max(220, round(w     / 72 * 300))
    h_px  = max(90,  round(bar_h / 72 * 300))
    img   = Image.new("RGB", (w_px, h_px), (255, 255, 255))
    draw  = ImageDraw.Draw(img)
    mod   = w_px / len(bits)
    for i, b in enumerate(bits):
        if b == "1":
            lx = round(i * mod)
            rx = max(lx + 1, round((i + 1) * mod))
            draw.rectangle([lx, 0, rx, h_px - 1], fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(fitz.Rect(x0, y0, x0 + w, y0 + bar_h), stream=buf.getvalue())
    # Digit string "D XXXXXX XXXXXX" centred below bars
    p1, p2, p3 = _bc_chunks(bc_str)
    txt = p1 + " " + p2 + " " + p3
    fs  = 4.5
    cx0 = txt_x0 if txt_x0 is not None else x0
    cw  = txt_w  if txt_w  is not None else w
    page.insert_text(
        fitz.Point(_cx(txt, FR, fs, cx0, cw), y0 + bar_h + fs + 0.8),
        txt, fontname=FR, fontsize=fs, color=DARK,
    )


# ── Template cache ────────────────────────────────────────────────────────────
_TDOC = {}

def _tpl(path):
    if path not in _TDOC and os.path.exists(path):
        _TDOC[path] = fitz.open(path)
    return _TDOC.get(path)


# ── FRONT PANEL ───────────────────────────────────────────────────────────────
def _draw_front_panel(page, ox, oy):
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    tpl = _tpl(FRONT_PANEL_TEMPLATE)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
        return
    ix0, iy0 = ox + INNER_X, oy + INNER_Y
    page.draw_rect(tgt, color=None, fill=WHITE, width=0)
    page.draw_rect(fitz.Rect(ix0, iy0, ix0+INNER_W, iy0+INNER_H),
                   color=None, fill=NAVY, width=0)
    page.draw_rect(fitz.Rect(ix0, iy0, ix0+INNER_W, iy0+INNER_H),
                   color=MAGENTA, fill=None, width=0.5)
    page.draw_circle(fitz.Point(ox+HOLE_RX, oy+HOLE_RY), HOLE_R,
                     color=MAGENTA, fill=WHITE, width=0.5)
    fs_o = 28.0
    page.insert_text(fitz.Point(_cx("OVS", FB, fs_o, ix0, INNER_W),
                                 iy0 + INNER_H*0.50), "OVS",
                     fontname=FB, fontsize=fs_o, color=GOLD)
    page.insert_text(fitz.Point(_cx("kids", FR, 13, ix0, INNER_W),
                                 iy0 + INNER_H*0.50 + 16), "kids",
                     fontname=FR, fontsize=13, color=GOLD)
    page.draw_line(fitz.Point(ix0+INNER_W*0.25, iy0+INNER_H*0.50-4),
                   fitz.Point(ix0+INNER_W*0.75, iy0+INNER_H*0.50-4),
                   color=GOLD, width=1.5)
    page.draw_line(fitz.Point(ix0, iy0+257.8-INNER_Y),
                   fitz.Point(ix0+INNER_W, iy0+257.8-INNER_Y),
                   color=MAGENTA, width=0.5)


# ── BACK PANEL ────────────────────────────────────────────────────────────────
def _draw_back_panel(page, ox, oy, item_data, render_dpi=150):
    ix0 = ox + INNER_X
    iy0 = oy + INNER_Y
    ix1 = ix0 + INNER_W
    iy1 = iy0 + INNER_H
    half = INNER_W / 2.0

    ay = lambda r: oy + r   # panel-relative Y -> absolute page Y

    # ── 1. Static template ────────────────────────────────────────────────────
    tpl = _tpl(BACK_PANEL_TEMPLATE)
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
    else:
        page.draw_rect(tgt, color=None, fill=WHITE, width=0)

    # ── 2. White-overwrite variable zones ────────────────────────────────────
    for (rx0, ry0, rx1, ry1) in ZONES:
        page.draw_rect(
            fitz.Rect(ox + rx0, oy + ry0, ox + rx1, oy + ry1),
            color=None, fill=WHITE, width=0,
        )

    # ── 3. Restore magenta inner border edges ─────────────────────────────────
    page.draw_line(fitz.Point(ix0, ay(120)), fitz.Point(ix0, ay(188)),
                   color=MAGENTA, width=0.5)
    page.draw_line(fitz.Point(ix1, ay(120)), fitz.Point(ix1, iy1),
                   color=MAGENTA, width=0.5)
    page.draw_line(fitz.Point(ix0, iy1), fitz.Point(ix1, iy1),
                   color=MAGENTA, width=0.5)

    # ── 4. Item data ──────────────────────────────────────────────────────────
    sizes   = item_data.get("sizes") or {}
    cur_yrs = sizes.get("YEARS", "")
    cur_it  = sizes.get("IT") or cur_yrs
    cur_mex = re.sub(r"\s*A$", "", (sizes.get("MEX") or cur_yrs) or "").strip()
    cur_cm  = CM_MAP.get(cur_yrs, sizes.get("CM", ""))

    # ── 5. YEARS / CM TABLE ───────────────────────────────────────────────────
    # Actual.jpg: fully enclosed table with firm dark borders top & bottom.
    # Vertical divider right-border of left cell spans TABLE_TOP to TABLE_BOT.
    # Labels: Left-aligned with 4pt cell padding.
    # Values: Right-aligned with 4pt cell padding from divider.
    # TABLE_TOP=141, TABLE_BOT=157 (below IT baseline 151.2 + descender~6pt)

    fs_lbl    = 6.5
    fs_val    = 9.0
    CELL_PAD  = 4.0          # padding from cell border
    # Exact measurements from back_panel_ref.pdf template extraction:
    #   YEARS value baseline y=148.4, IT value baseline y=159.5
    #   Size chip row 1 baseline y=173.7, row 2 y=185.8
    # TABLE_TOP sits just above YEARS row, TABLE_BOT just below IT row.
    TABLE_TOP = 138.0        # panel-relative y: top border (above YEARS)
    TABLE_BOT = 168.0        # panel-relative y: bottom border (below IT bl=159.5)
    vert_x    = ix0 + half   # x of vertical cell divider

    # Top border
    page.draw_line(fitz.Point(ix0, ay(TABLE_TOP)),
                   fitz.Point(ix1, ay(TABLE_TOP)),
                   color=DARK, width=0.8)
    # Bottom border
    page.draw_line(fitz.Point(ix0, ay(TABLE_BOT)),
                   fitz.Point(ix1, ay(TABLE_BOT)),
                   color=DARK, width=0.8)
    # Vertical divider (right-border of left cell)
    page.draw_line(fitz.Point(vert_x, ay(TABLE_TOP)),
                   fitz.Point(vert_x, ay(TABLE_BOT)),
                   color=DARK, width=0.8)

    # Row 1: YEARS | value || CM | value
    # Template measurements: YEARS value y=148.4, labels slightly smaller
    bl1 = ay(148.4)
    page.insert_text(fitz.Point(ix0 + CELL_PAD, bl1),
                     "YEARS", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_yrs, FB, fs_val, vert_x - CELL_PAD), bl1),
                     cur_yrs, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + CELL_PAD, bl1),
                     "CM", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_cm, FB, fs_val, ix1 - CELL_PAD), bl1),
                     cur_cm, fontname=FB, fontsize=fs_val, color=DARK)

    # Row 2: IT | value || MEX | value
    # Template measurements: IT value y=159.5
    bl2 = ay(159.5)
    mex_txt = cur_mex + " A"
    page.insert_text(fitz.Point(ix0 + CELL_PAD, bl2),
                     "IT", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_it, FB, fs_val, vert_x - CELL_PAD), bl2),
                     cur_it, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + CELL_PAD, bl2),
                     "MEX", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(mex_txt, FB, fs_val, ix1 - CELL_PAD), bl2),
                     mex_txt, fontname=FB, fontsize=fs_val, color=DARK)

    # ── 6. SIZE CHART ─────────────────────────────────────────────────────────
    # 2 rows of 3 chips, centered in INNER_W.
    # Both rows MUST be inside Zone A whitewash area (panel y < 188) so the
    # left-column Triman template icons do not bleed through.
    # Reference measurements (back_panel_ref.pdf): row1 y=173.7, row2 y=185.8
    # CHIP_W=30pt, CHIP_GAP=7.5pt between chips for natural spacing.

    CHIP_W    = 30.0
    CHIP_GAP  = 7.5
    fs_gr     = 7.0
    CHIP_H    = fs_gr + 3.5   # visible chip box height

    row_span = 3 * CHIP_W + 2 * CHIP_GAP
    chip_x0  = ix0 + (INNER_W - row_span) / 2   # centred

    # Fixed baselines matching reference template measurements
    R1_BL = 173.7   # row-1 text baseline (panel-relative)
    R2_BL = 185.8   # row-2 text baseline (panel-relative)

    grid_baselines = [ay(R1_BL), ay(R2_BL)]

    for ri, (row, bl) in enumerate(zip(SIZE_ROWS, grid_baselines)):
        for ci, sz in enumerate(row):
            cx = chip_x0 + ci * (CHIP_W + CHIP_GAP)
            is_cur = (sz == cur_yrs)
            if is_cur:
                box_top = bl - fs_gr - 1.5
                box_bot = bl + 2.0
                page.draw_rect(
                    fitz.Rect(cx, box_top, cx + CHIP_W, box_bot),
                    color=None, fill=BLACK, width=0
                )
            fn = FB if is_cur else FR
            tc = WHITE if is_cur else DARK
            tw = fitz.get_text_length(sz, fontname=fn, fontsize=fs_gr)
            page.insert_text(
                fitz.Point(cx + (CHIP_W - tw) / 2, bl),
                sz, fontname=fn, fontsize=fs_gr, color=tc,
            )

    # ── 7. BARCODE + CODES (middle column, Zone B2) ───────────────────────────
    # Layout (top -> bottom in middle col):
    #   "3632  230  2768957"   — dept codes CENTERED in full mc_w
    #   [EAN-13 bars]          — fills bc_w with 2pt inset
    #   "8 051553 298798"      — digit string centered in mc_w
    #   "2768957"              — style code centered in mc_w (grey)
    #   "PR711 AI08"           — cref centered in mc_w (grey)

    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department",     "") or "")
    sku      = str(item_data.get("sku_code",        "") or "")
    bc_str   = str(item_data.get("barcode_number",  "") or "")
    style    = str(item_data.get("style_code",      "") or "")
    cref     = str(item_data.get("commercial_ref",  "") or "")

    # Middle column boundaries
    mc_x0 = ix0 + _C3
    mc_x1 = ix0 + 2 * _C3
    mc_w  = mc_x1 - mc_x0   # ~42.4 pt

    # Barcode image: 2pt inset inside middle col
    bc_x0 = mc_x0 + 2.0
    bc_w  = mc_w  - 4.0

    # Dept codes row: centred across full mc_w
    fs_dept  = 4.5
    dept_str = "  ".join(p for p in [sub_dept, dept, sku] if p)
    DEPT_Y   = 202.0   # panel-relative y for dept codes baseline

    if dept_str:
        page.insert_text(
            fitz.Point(_cx(dept_str, FR, fs_dept, mc_x0, mc_w), ay(DEPT_Y)),
            dept_str, fontname=FR, fontsize=fs_dept, color=DARK,
        )

    # Barcode bars (start 5pt below dept codes)
    BC_Y  = DEPT_Y + 6.0
    BAR_H = 28.0

    _draw_barcode(page, bc_x0, ay(BC_Y), bc_w, BAR_H, bc_str,
                  txt_x0=mc_x0, txt_w=mc_w)

    # Style code + commercial ref below digit string
    fs_c    = 5.0
    style_y = BC_Y + BAR_H + 4.5 + 2.0 + fs_c + 2.0
    cref_y  = style_y + fs_c + 2.5

    if style:
        page.insert_text(
            fitz.Point(_cx(style, FR, fs_c, mc_x0, mc_w), ay(style_y)),
            style, fontname=FR, fontsize=fs_c, color=GREY,
        )
    if cref:
        page.insert_text(
            fitz.Point(_cx(cref, FR, fs_c, mc_x0, mc_w), ay(cref_y)),
            cref, fontname=FR, fontsize=fs_c, color=GREY,
        )

    # ── 8. RIGHT COLUMN — vertical text ──────────────────────────────────────
    country_zone = str(item_data.get("country_of_origin", "") or "").upper()
    phys_country = COUNTRY_ZONE_MAP.get(country_zone, "")

    rc_x0 = ix0 + 2 * _C3
    rc_x1 = ix1
    rc_fs = 3.5

    v_lines = []
    if phys_country:
        v_lines.append(("MADE IN " + phys_country, FB, DARK))
    v_lines.append(("OVS - Via Terraglio 17", FR, LGREY))
    v_lines.append(("30174 Venezia ITALIA - info@ovs.it", FR, LGREY))

    zone_y_mid   = oy + (BC_Y + (BC_Y + BAR_H)) / 2
    line_spacing = rc_fs + 2.0
    total_span   = (len(v_lines) - 1) * line_spacing
    x_start      = rc_x0 + (rc_x1 - rc_x0 - total_span) / 2

    for li, (vtxt, vfn, vcol) in enumerate(v_lines):
        vx = x_start + li * line_spacing + rc_fs
        tw = fitz.get_text_length(vtxt, fontname=vfn, fontsize=rc_fs)
        vy_start = zone_y_mid + tw / 2
        page.insert_text(fitz.Point(vx, vy_start),
                         vtxt, fontname=vfn, fontsize=rc_fs,
                         color=vcol, rotate=90)

    # ── 9. DASHED GREEN PRICE SEPARATOR ──────────────────────────────────────
    page.draw_line(
        fitz.Point(ox + SEP_X0, ay(SEP_Y)),
        fitz.Point(ox + SEP_X1, ay(SEP_Y)),
        color=GREEN, dashes="[3 3] 0", width=1.0,
    )

    # ── 10. PRICE  € 29,95  ───────────────────────────────────────────────────
    # Actual.jpg: € same bold weight AND same 24pt size as "29".
    # ,95 is 12pt (50%), raised to cap-top of "29" (superscript).
    # Entire price group horizontally centred in label inner area.

    currency  = _fix_currency(item_data.get("currency_symbol", ""))
    price_raw = str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_raw)

    CAP_H    = 0.72
    fs_major = 24.0          # "29"
    fs_sym   = 24.0          # "€" — same size as major (pixel-matched to Actual.jpg)
    fs_minor = 12.0          # ",95" — 50% of major
    MIN_raise = (fs_major - fs_minor) * CAP_H   # raise ,95 to cap-top

    icx = ix0 + INNER_W / 2   # horizontal centre of inner area

    sym_w   = fitz.get_text_length(currency, fontname=FB, fontsize=fs_sym)
    sym_gap = 2.0              # kerning gap between € and 29
    maj_w   = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w   = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)

    total_w = sym_w + sym_gap + maj_w + min_w
    px      = icx - total_w / 2
    pr_y    = ay(SEP_Y + 27)

    # € (same baseline as "29", no raise)
    page.insert_text(fitz.Point(px, pr_y),
                     currency, fontname=FB, fontsize=fs_sym, color=DARK)
    # 29
    page.insert_text(fitz.Point(px + sym_w + sym_gap, pr_y),
                     major, fontname=FB, fontsize=fs_major, color=DARK)
    # ,95  (superscript raised)
    page.insert_text(fitz.Point(px + sym_w + sym_gap + maj_w, pr_y - MIN_raise),
                     minor, fontname=FR, fontsize=fs_minor, color=DARK)

    # ── 11. QTY below outer panel ─────────────────────────────────────────────
    qty_txt = "Qty - " + str(item_data.get("quantity", 0))
    fs_qty  = 10.0
    page.insert_text(
        fitz.Point(_cx(qty_txt, FB, fs_qty, ox, OUTER_W),
                   oy + OUTER_H + fs_qty + 3),
        qty_txt, fontname=FB, fontsize=fs_qty, color=DARK,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def build_label_pdf(item_data):
    """Single-item PDF: front + back side by side."""
    pw = OUTER_W * 2 + 10
    ph = OUTER_H + 25
    doc  = fitz.open()
    page = doc.new_page(width=pw, height=ph)
    page.draw_rect(fitz.Rect(0, 0, pw, ph), color=None, fill=WHITE, width=0)
    _draw_front_panel(page, 0, 0)
    _draw_back_panel(page, OUTER_W + 10, 0, item_data)
    out = io.BytesIO()
    doc.save(out, garbage=4, deflate=True)
    doc.close()
    return out.getvalue()


def build_label_png(item_data, dpi=150):
    pdf = build_label_pdf(item_data)
    doc = fitz.open(stream=pdf, filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    doc.close()
    return pix.tobytes("png")


def build_label_thumbnail(item_data, dpi=60):
    return build_label_png(item_data, dpi=dpi)
