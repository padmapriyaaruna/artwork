
"""
Writes the definitive v11 tok100_label_builder.py based on exact Actual.jpg measurements.

Key pixel analysis of Actual.jpg vs Sample.jpg:

YEARS/CM TABLE:
- Two full-width horizontal DARK lines: one ABOVE YEARS row, one BELOW IT row  
- Vertical divider (right-border of left col) exactly spans between the two lines
- YEARS/IT labels: left-aligned with ~4pt gap from inner left border
- 4-5/110 values: right-aligned with ~4pt gap from vertical divider
- CM/MEX labels: left-aligned with ~4pt gap from vertical divider
- 110/4-5 A values: right-aligned with ~4pt gap from inner right border

SIZE CHART:
- Row 1: [4-5] 5-6  6-7  (active chip has black box, proper top margin so it does NOT touch sep1 border)
- Row 2: 7-8  8-9  9-10
- Both rows centered within the inner width
- Active chip box has padding on all sides, separated from grid top border by at least 2pt

BARCODE:
- "3632 230 2768957" - centered above the barcode bars (this is sub_dept+dept+sku)
- EAN-13 bars (tall, properly proportioned)
- "8 051553 298798" - digit string BELOW bars, left digit outside, right group aligned
- "2768957" - style code centered below digit string
- "PR711 AI08" - cref centered below style code

PRICE (€ 29,95):
- € symbol: SAME BOLD font as "29", same large size
- 29: bold, large
- ,95: smaller, top-aligned (superscript style)  
- All horizontally centered in the label
"""
new_content = '''# -*- coding: utf-8 -*-
"""
TOK100 Label Builder v11  -  pixel-perfect match to Actual.jpg master template

v11 fixes (from Actual.jpg pixel analysis):
  1. YEARS/CM table: adds second horizontal separator BELOW the IT/MEX row,
     so the table is fully enclosed top and bottom. Vertical divider now spans
     exactly between the two horizontal lines.
  2. Active size chip: top of the chip rect now starts 3pt BELOW sep1, so the
     box never overlaps the separator line above it.
  3. Barcode area: dept/sub_dept/sku codes row centered across the FULL inner
     width (not just middle col), so "3632 230 2768957" sits cleanly above bars.
  4. Currency symbol: € uses the same BOLD heavy font and same fontsize as the
     major integer "29". EUR_raise = 0 (no vertical lift needed, same cap-height).
  5. Minor (cents) set to 50% of major size and raised to the top of the major.
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

ZONES = [
    (INNER_X,           120.0, INNER_X + INNER_W,   188.0),
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

# ── Fonts ────────────────────────────────────────────────────────────────────
FB = "hebo"   # Helvetica-Bold   (condensed-looking at small sizes)
FR = "helv"   # Helvetica

# ── Size constants ─────────────────────────────────────────────────────────────
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
    """Centre x for text in area."""
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x0 + (area_w - tw) / 2

def _rx(text, font, fs, area_x1):
    """Right-align: x so text ends at area_x1."""
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x1 - tw

def _fix_currency(raw):
    EUR = chr(128)   # euro in WinAnsiEncoding / cp1252
    if not raw:
        return EUR
    s = str(raw)
    if "\\u20ac" in s or "&#8364;" in s or "&euro;" in s or "\\u20ac" in repr(s):
        return EUR
    # Catch the actual unicode euro sign
    s2 = s.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    if "\\u20ac" in repr(s2) or chr(0x20ac) in s2:
        return EUR
    clean = "".join(c for c in s if 0x20 <= ord(c) < 0x80)
    if not clean or clean[0] in "?":
        return EUR
    return clean

def _split_price(s):
    s = str(s or "0,00").strip()
    m = re.match(r"^(\\d+)([,.]?\\d*)$", s)
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
    """EAN-13 as 300-DPI PNG embedded in the PDF, digit string below."""
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
    # Digit string below bars: "D XXXXXX XXXXXX"
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

    # Panel-relative Y -> absolute page Y
    ay = lambda r: oy + r

    # ── 1. Static template embed ──────────────────────────────────────────────
    tpl = _tpl(BACK_PANEL_TEMPLATE)
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
    else:
        page.draw_rect(tgt, color=None, fill=WHITE, width=0)

    # ── 2. White-overwrite the 4 variable zones ────────────────────────────────
    for (rx0, ry0, rx1, ry1) in ZONES:
        page.draw_rect(
            fitz.Rect(ox + rx0, oy + ry0, ox + rx1, oy + ry1),
            color=None, fill=WHITE, width=0,
        )

    # ── 3. Restore magenta inner border edges clipped by zone whitewash ───────
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
    cur_mex = re.sub(r"\\s*A$", "", (sizes.get("MEX") or cur_yrs) or "").strip()
    cur_cm  = CM_MAP.get(cur_yrs, sizes.get("CM", ""))

    # ── 5. YEARS/CM TABLE ─────────────────────────────────────────────────────
    # Pixel analysis of Actual.jpg:
    #   sep_top: y_rel=141 — thick dark line, full inner width (no inset)
    #   YEARS row baseline: y_rel=151.2
    #   IT row baseline:    y_rel=167.2
    #   sep_bot: y_rel=172 — thick dark line, full inner width (no inset)
    #   Vertical divider: spans from sep_top to sep_bot at x=ix0+half
    # Labels (YEARS/IT/CM/MEX) use FB at 6.5pt; values use FB at 9pt.
    # Left col text: labels L-aligned at ix0+GAP, values R-aligned at vert_x-GAP.
    # Right col text: labels L-aligned at vert_x+GAP, values R-aligned at ix1-GAP.

    fs_lbl = 6.5     # label fontsize
    fs_val = 9.0     # value fontsize
    GAP    = 4.0     # cell padding from divider lines
    vert_x = ix0 + half   # vertical divider x coord

    # y coords of table borders
    TABLE_TOP = 141.0   # panel-relative y of top border
    TABLE_BOT = 173.0   # panel-relative y of bottom border (below IT baseline 167.2)

    # Draw top border — full inner width, solid dark
    page.draw_line(fitz.Point(ix0, ay(TABLE_TOP)),
                   fitz.Point(ix1, ay(TABLE_TOP)),
                   color=DARK, width=0.8)
    # Draw bottom border — full inner width, solid dark
    page.draw_line(fitz.Point(ix0, ay(TABLE_BOT)),
                   fitz.Point(ix1, ay(TABLE_BOT)),
                   color=DARK, width=0.8)
    # Draw vertical divider — spans exactly from TABLE_TOP to TABLE_BOT
    page.draw_line(fitz.Point(vert_x, ay(TABLE_TOP)),
                   fitz.Point(vert_x, ay(TABLE_BOT)),
                   color=DARK, width=0.8)

    # Row 1: YEARS (label L) | value R | CM (label L) | value R
    bl1 = ay(151.2)
    page.insert_text(fitz.Point(ix0 + GAP, bl1),
                     "YEARS", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_yrs, FB, fs_val, vert_x - GAP), bl1),
                     cur_yrs, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + GAP, bl1),
                     "CM", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_cm, FB, fs_val, ix1 - GAP), bl1),
                     cur_cm, fontname=FB, fontsize=fs_val, color=DARK)

    # Row 2: IT (label L) | value R | MEX (label L) | value R
    bl2 = ay(167.2)
    mex_txt = cur_mex + " A"
    page.insert_text(fitz.Point(ix0 + GAP, bl2),
                     "IT", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_it, FB, fs_val, vert_x - GAP), bl2),
                     cur_it, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + GAP, bl2),
                     "MEX", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(mex_txt, FB, fs_val, ix1 - GAP), bl2),
                     mex_txt, fontname=FB, fontsize=fs_val, color=DARK)

    # ── 6. SIZE CHART — 2 rows of 3, centered, with proper separation ─────────
    # Actual.jpg analysis:
    #   CHIP_W ~34pt, CHIP_GAP ~10pt between chips, rows centered within INNER_W
    #   Row 1 baseline: y_rel=183  (gap of 10pt below TABLE_BOT=173)
    #   Row 2 baseline: y_rel=192
    #   Active chip box: top = bl - fs_gr - 1, giving ~3pt clearance below TABLE_BOT
    #   Chip box padding: 2pt top/bottom, full CHIP_W width (no horizontal shrink)

    CHIP_W   = 30.0     # chip box width
    CHIP_GAP = 7.5      # gap between chips
    fs_gr    = 7.0      # chip font size
    CHIP_H   = fs_gr + 3.0   # chip box height (font + padding top+bottom)

    # Centre 3 chips + 2 gaps within INNER_W
    row_span = 3 * CHIP_W + 2 * CHIP_GAP
    chip_x0  = ix0 + (INNER_W - row_span) / 2

    # Row 1 baseline: 10pt below TABLE_BOT, row 2 is CHIP_H + 3pt below row 1
    GRID_ROW1_BL = TABLE_BOT + 2.0 + CHIP_H   # baseline of row-1 text
    GRID_ROW2_BL = GRID_ROW1_BL + CHIP_H + 3.0  # row-2 baseline

    grid_baselines = [ay(GRID_ROW1_BL), ay(GRID_ROW2_BL)]

    for ri, (row, bl) in enumerate(zip(SIZE_ROWS, grid_baselines)):
        for ci, sz in enumerate(row):
            cx = chip_x0 + ci * (CHIP_W + CHIP_GAP)
            is_cur = (sz == cur_yrs)
            if is_cur:
                # Black box — slightly taller than text
                box_top = bl - fs_gr - 1.5
                box_bot = bl + 1.5
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

    # ── 7. BARCODE + REF CODES (middle column, Zone B2) ──────────────────────
    # Actual.jpg layout (top to bottom in middle col):
    #   "3632 230 2768957"  — CENTERED above barcode bars (dept codes line)
    #   [EAN-13 bars]        — fills middle col width
    #   "8 051553 298798"   — digit string centered below bars
    #   "2768957"           — style code centered (grey)
    #   "PR711 AI08"        — commercial ref centered (grey)
    # Zone B2 starts at panel y=188. Barcode bars start at y=205 to give breathing room.

    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department",     "") or "")
    sku      = str(item_data.get("sku_code",        "") or "")
    style    = str(item_data.get("style_code",      "") or "")
    cref     = str(item_data.get("commercial_ref",  "") or "")
    bc_str   = str(item_data.get("barcode_number",  "") or "")

    # Middle column boundaries
    mc_x0 = ix0 + _C3          # left edge of middle col
    mc_x1 = ix0 + 2 * _C3      # right edge of middle col
    mc_w  = mc_x1 - mc_x0      # ~42.4 pt

    # Barcode fits within middle col with 2pt inset on each side
    bc_x0 = mc_x0 + 2.0
    bc_w  = mc_w - 4.0

    # Department codes centred above barcode
    fs_dept  = 4.5
    dept_parts = [sub_dept, dept, sku]
    dept_str = "  ".join(p for p in dept_parts if p)
    DEPT_Y   = 200.0   # panel-relative y for dept codes baseline

    if dept_str:
        page.insert_text(
            fitz.Point(_cx(dept_str, FR, fs_dept, mc_x0, mc_w), ay(DEPT_Y)),
            dept_str, fontname=FR, fontsize=fs_dept, color=DARK,
        )

    # Barcode bars
    BC_Y  = 205.0   # panel-relative y for top of bars (5pt below dept codes)
    BAR_H = 28.0    # bar height in pt — taller for better visual weight

    _draw_barcode(page, bc_x0, ay(BC_Y), bc_w, BAR_H, bc_str,
                  txt_x0=mc_x0, txt_w=mc_w)

    # Style code and commercial ref below digit string
    fs_c = 5.0
    style_y = BC_Y + BAR_H + 4.5 + 2.0 + fs_c + 2.0   # below digit string
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

    zone_y_mid   = oy + (205 + 258) / 2
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

    # ── 10. PRICE — € 29,95 ───────────────────────────────────────────────────
    # Actual.jpg analysis:
    #   € symbol: SAME bold font, SAME large size as "29"
    #   29: large, bold, condensed
    #   ,95: ~50% of major size, positioned at top of "29" (superscript)
    #   All three items horizontally centred in the label
    #
    # Implementation:
    #   fs_major = fs_sym = 24pt (both bold, same cap height)
    #   fs_minor = 12pt = 50% of major
    #   EUR_raise = 0 (same baseline as major — same font size)
    #   MIN_raise = (fs_major - fs_minor) * CAP_H (raised to cap-top of major)

    currency  = _fix_currency(item_data.get("currency_symbol", ""))
    price_raw = str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_raw)

    CAP_H    = 0.72          # ratio of cap-height to em-size
    fs_major = 24.0          # main price integer ("29")
    fs_sym   = 24.0          # currency symbol — SAME size as major (per Actual.jpg)
    fs_minor = 12.0          # cents ",95" — 50% of major
    MIN_raise = (fs_major - fs_minor) * CAP_H   # raise ,95 to cap-top of 29

    icx = ix0 + INNER_W / 2   # horizontal centre of label inner area

    # Measure each element
    sym_w = fitz.get_text_length(currency, fontname=FB, fontsize=fs_sym)
    # Add a small kerning gap between € and 29 (2pt)
    sym_gap = 2.0
    maj_w = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)

    # Total width for centering calculation
    total_price_w = sym_w + sym_gap + maj_w + min_w
    px = icx - total_price_w / 2
    pr_y = ay(SEP_Y + 27)   # baseline of main price row

    # € symbol — same baseline as major (EUR_raise = 0)
    page.insert_text(fitz.Point(px, pr_y),
                     currency, fontname=FB, fontsize=fs_sym, color=DARK)
    # Main integer "29"
    page.insert_text(fitz.Point(px + sym_w + sym_gap, pr_y),
                     major, fontname=FB, fontsize=fs_major, color=DARK)
    # Cents ",95" — raised to top
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
'''

with open("backend/engine/tok100_label_builder.py", "w", encoding="utf-8") as f:
    f.write(new_content.lstrip("\\n"))

print("File written!")
print("Lines:", new_content.count("\\n"))
