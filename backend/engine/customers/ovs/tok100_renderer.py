# -*- coding: utf-8 -*-
"""
TOK100 Renderer — OVS customer, TOK100 label type.

This is the customer-specific renderer for OVS/TOK100.
It is the authoritative v14 engine, moved here from
backend/engine/tok100_label_builder.py as part of the
multi-customer architecture refactor.

See backend/engine/label_engine.py for the generic dispatcher
that routes to this module based on customer_code='OVS' and
label_type='TOK100'.

All rendering logic, coordinates, and constants are identical
to the original tok100_label_builder.py v14 (commit 0e8e4f8).
Do NOT modify this file for structural reasons — only for
OVS/TOK100-specific rendering fixes.
"""


import io, os, re
import fitz  # PyMuPDF

# ── Template paths ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
# Path from customers/ovs/ → up 3 levels → backend/templates/OVS/TOK100
_TMPL = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "templates", "OVS", "TOK100"))

FRONT_PANEL_TEMPLATE = os.path.join(_TMPL, "front_panel_ref.pdf")
BACK_PANEL_TEMPLATE  = os.path.join(_TMPL, "back_panel_ref.pdf")

# ── Panel geometry (pt) ────────────────────────────────────────────────────────
OUTER_W = 150.3
OUTER_H = 305.5
INNER_X = 11.5
INNER_Y = 10.8
INNER_W = 127.2
INNER_H = 283.9
HOLE_RX = 74.8
HOLE_RY = 30.2
HOLE_R  = 5.1
SEP_Y   = 257.49   # dashed green line (panel-relative)
SEP_X0  = 12.7
SEP_X1  = 134.4
_C3     = INNER_W / 3.0   # ~42.4 pt per column

# White-overwrite zones.
# NOTE: Left column (x=INNER_X..INNER_X+_C3) for y>188 is NOT erased so the
# Triman/FR recycling logos from the static template show through correctly.
# Zone B2 left boundary is extended 10pt into left col to erase the template's
# own barcode '8' guard digit and leading digits that bleed at the column edge.
# The Triman logos sit higher in the left col (y~192-230) and are untouched
# because we only extend the LEFT PART of zone B2 (middle col white erase).
ZONES = [
    (INNER_X,              120.0, INNER_X + INNER_W,       188.0),   # Zone A: full width
    (INNER_X + _C3 - 15,   188.0, INNER_X + 2*_C3,          258.0),  # Zone B2: mid col + 15pt left
    (INNER_X + 2*_C3,      188.0, INNER_X + INNER_W,        258.0),  # Zone B3: right col
    (INNER_X,              256.0, INNER_X + INNER_W,        OUTER_H), # Zone C: price area
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

# ── Fonts ─────────────────────────────────────────────────────────────────────
FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

# ── Size reference ────────────────────────────────────────────────────────────
TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]
SIZE_ROWS    = [TOK100_SIZES[:3], TOK100_SIZES[3:]]
CM_MAP = {"4-5":"110","5-6":"116","6-7":"122",
           "7-8":"128","8-9":"134","9-10":"140"}

# Currency symbol mapping by ISO country code / OVS zone -> symbol
# Returns the correct PDF-renderable single character
COUNTRY_ZONE_MAP = {
    "WARM":        "INDIA",
    "COLD":        "INDIA",
    "MIDDLE EAST": "INDIA",
}

# Currency display mapping: OVS price-zone -> printable symbol
# We NEVER display raw currency text like "AED" — always a symbol
CURRENCY_SYMBOL_MAP = {
    "EUR": chr(128),   # € in cp1252/WinAnsi
    "GBP": chr(163),   # £
    "USD": "$",
    "AED": "AED",      # kept as 3-char (handled with smaller font)
    "":    chr(128),   # default euro
}


def _cx(text, font, fs, x0, w):
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return x0 + (w - tw) / 2

def _rx(text, font, fs, x1):
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return x1 - tw

def _fix_currency(raw):
    """Convert any currency input to a renderable PDF WinAnsi symbol."""
    if not raw:
        return chr(128)   # default euro
    s = str(raw).strip()
    # Unicode euro
    if "\u20ac" in s or s in ("EUR", "Euro", "euro"):
        return chr(128)
    # Sterling
    if "\u00a3" in s or s in ("GBP", "Sterling"):
        return chr(163)
    # Dollar
    if s in ("USD", "$"):
        return "$"
    # AED — keep as-is (handled with smaller font in price section)
    if s == "AED":
        return "AED"
    # cp1252 single byte symbols
    clean = "".join(c for c in s if 0x20 <= ord(c) < 0x80)
    if clean:
        return clean[0] if len(clean) == 1 else clean[:3]
    return chr(128)

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
    """
    EAN-13 PNG barcode + digit string.
    In the actual PDF the barcode is rendered via Type3 font with the left
    guard digit printed separately outside the main bars. We replicate this
    visual style: the full digit string "D XXXXXX XXXXXX" is centred below.
    """
    from PIL import Image, ImageDraw
    bits  = _ean13_bits(bc_str)
    # High resolution for clean bars
    w_px  = max(280, round(w     / 72 * 400))
    h_px  = max(100, round(bar_h / 72 * 400))
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
    page.insert_image(fitz.Rect(x0, y0, x0 + w, y0 + bar_h), stream=buf.getvalue())
    # Digit string centred below bars
    p1, p2, p3 = _bc_chunks(bc_str)
    txt = p1 + " " + p2 + " " + p3
    fs  = 5.0
    cx0 = txt_x0 if txt_x0 is not None else x0
    cw  = txt_w  if txt_w  is not None else w
    page.insert_text(
        fitz.Point(_cx(txt, FR, fs, cx0, cw), y0 + bar_h + 1.5 + fs),
        txt, fontname=FR, fontsize=fs, color=DARK,
    )


# ── Template cache ────────────────────────────────────────────────────────────
_TDOC = {}

def _tpl(path):
    if path not in _TDOC and os.path.exists(path):
        _TDOC[path] = fitz.open(path)
    return _TDOC.get(path)


# ──────────────────────────────────────────────────────────────────────────────
# FRONT PANEL
# ──────────────────────────────────────────────────────────────────────────────
def _draw_front_panel(page, ox, oy):
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    tpl = _tpl(FRONT_PANEL_TEMPLATE)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
        return
    # Fallback
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


# ──────────────────────────────────────────────────────────────────────────────
# BACK PANEL
# ──────────────────────────────────────────────────────────────────────────────
def _draw_back_panel(page, ox, oy, item_data, render_dpi=150):
    ix0 = ox + INNER_X
    iy0 = oy + INNER_Y
    ix1 = ix0 + INNER_W
    iy1 = iy0 + INNER_H
    half = INNER_W / 2.0

    ay = lambda r: oy + r   # panel-relative Y -> absolute page Y

    # ── 1. Embed static template ───────────────────────────────────────────────
    tpl = _tpl(BACK_PANEL_TEMPLATE)
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
    else:
        page.draw_rect(tgt, color=None, fill=WHITE, width=0)

    # ── 2. White-overwrite variable zones ─────────────────────────────────────
    for (rx0, ry0, rx1, ry1) in ZONES:
        page.draw_rect(
            fitz.Rect(ox + rx0, oy + ry0, ox + rx1, oy + ry1),
            color=None, fill=WHITE, width=0,
        )

    # ── 3. Restore FULL magenta inner border ───────────────────────────────────
    # Draw all 4 sides of the inner rectangle explicitly so no gaps appear.
    # White zones may clip partial edges from the template.
    page.draw_rect(fitz.Rect(ix0, iy0, ix1, iy1),
                   color=MAGENTA, fill=None, width=0.75)

    # ── 4. Item data ──────────────────────────────────────────────────────────
    sizes   = item_data.get("sizes") or {}
    cur_yrs = sizes.get("YEARS", "")
    cur_it  = sizes.get("IT")  or cur_yrs
    cur_mex = re.sub(r"\s*A$", "", (sizes.get("MEX") or cur_yrs) or "").strip()
    cur_cm  = CM_MAP.get(cur_yrs, sizes.get("CM", ""))

    # ── 5. YEARS / CM TABLE ───────────────────────────────────────────────────
    # From actual PDF:
    #   TABLE_TOP = 138 (line above YEARS, same width as KIDS separator = ix0..ix1)
    #   TABLE_BOT = 168 (line below IT, same width = ix0..ix1, no inset)
    #   Vertical divider at vert_x = ix0 + half (spans TABLE_TOP .. TABLE_BOT)
    #   Cell padding: 4pt from inner border, values right-aligned
    #
    # CRITICAL: The horizontal lines do NOT touch the magenta border.
    # They are INNER lines spanning ix0 to ix1 only (no overshoot).

    fs_lbl   = 6.5
    fs_val   = 9.0
    CELL_PAD = 4.0
    TABLE_TOP = 138.0     # panel-relative y of top border
    TABLE_BOT = 163.5     # panel-relative y of bottom border
                          # Must be <= chip_box_top - 2pt clearance
                          # chip_box_top = R1_BL - fs_gr - 1.0 = 173.3-6.5-1.0 = 165.8
                          # TABLE_BOT=163.5 gives 2.3pt clearance gap to chip box
    vert_x = ix0 + half   # vertical divider x

    # Top horizontal line: ix0 -> ix1 (same span as KIDS lines above)
    page.draw_line(fitz.Point(ix0, ay(TABLE_TOP)), fitz.Point(ix1, ay(TABLE_TOP)),
                   color=DARK, width=0.8)
    # Bottom horizontal line
    page.draw_line(fitz.Point(ix0, ay(TABLE_BOT)), fitz.Point(ix1, ay(TABLE_BOT)),
                   color=DARK, width=0.8)
    # Vertical divider (right border of left cell)
    page.draw_line(fitz.Point(vert_x, ay(TABLE_TOP)), fitz.Point(vert_x, ay(TABLE_BOT)),
                   color=DARK, width=0.8)

    # Row 1 (YEARS / CM)  bl = 148.0 panel-relative
    bl1 = ay(148.0)
    page.insert_text(fitz.Point(ix0 + CELL_PAD, bl1),
                     "YEARS", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_yrs, FB, fs_val, vert_x - CELL_PAD), bl1),
                     cur_yrs, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + CELL_PAD, bl1),
                     "CM", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_cm, FB, fs_val, ix1 - CELL_PAD), bl1),
                     cur_cm, fontname=FB, fontsize=fs_val, color=DARK)

    # Row 2 (IT / MEX)  bl = 159.1 panel-relative
    bl2 = ay(159.1)
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
    # From actual PDF measurements:
    #   chip pitch = 19.06pt (CHIP_W + CHIP_GAP)
    #   chip_x0 (from ix0) = 44.95 → chip starts 44.95pt from ix0
    #   Row 1 baseline y_rel = 173.3  (panel relative)
    #   Row 2 baseline y_rel = 185.3
    #   Active chip: compact tight rectangle, NOT full-width
    #   CHIP_W ~ 13pt (visual estimate; pitch 19 - GAP 6 = 13)
    #   The chip box is ONLY as wide as needed for text + 3pt padding each side

    CHIP_PITCH  = 19.06   # measured: 5-6.x - 4-5.x = 274.71 - 255.65 = 19.06
    CHIP_W      = 13.5    # chip box width (pitch 19.06 - visual gap 5.5)
    fs_gr       = 6.5     # matches actual PDF chip font size exactly
    # chip_x0: measured from generated approval sheet template overlay:
    # template chip '4-5' text starts at x=255.65, ix0=215.25 -> rel=40.4
    chip_x0     = ix0 + 40.4   # measured from approval sheet template embed

    # Verify centring: leftmost chip at ix0+44.95, 3 chips at 19.06 pitch
    # Middle of 3 chips: ix0 + 44.95 + CHIP_W/2 + 19.06 = ix0 + 71.025 + 6.75 = ix0+77.8
    # INNER_W/2 = 63.6 → leftmost chip should be ix0+(INNER_W/2 - 19.06 - CHIP_W/2) = ix0+43.8
    # Close enough to measured 44.95; use measured value

    R1_BL = 173.3   # panel-relative row-1 baseline
    R2_BL = 185.3   # panel-relative row-2 baseline

    grid_baselines = [ay(R1_BL), ay(R2_BL)]

    for ri, (row, bl) in enumerate(zip(SIZE_ROWS, grid_baselines)):
        for ci, sz in enumerate(row):
            cx = chip_x0 + ci * CHIP_PITCH
            is_cur = (sz == cur_yrs)
            if is_cur:
                # Compact chip box. box_top must NOT touch TABLE_BOT line above.
                # TABLE_BOT=163.5, box_top=R1_BL-fs_gr-1.0=165.8 -> 2.3pt safe gap.
                box_top = bl - fs_gr - 1.0
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

    # ── 7. BARCODE ZONE (middle column, Zone B2) ──────────────────────────────
    # Layout from actual PDF (panel-relative):
    #   Dept codes : y_rel = 200.6  (3632  230  2768957)
    #   Bar top    : y_rel ≈ 207
    #   Bar bottom : y_rel ≈ 223   (BAR_H ≈ 16pt)
    #   Digit str  : y_rel = 227.4 (8 051553 298798)
    #   Style code : y_rel = 236.7
    #   Cref       : y_rel = 246.1
    #
    # Middle col: ix0+_C3 to ix0+2*_C3 (~42.4pt wide)
    # Barcode image fills the middle column with 1pt inset each side.

    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department",     "") or "")
    sku_code = str(item_data.get("sku_code",        "") or "")
    bc_str   = str(item_data.get("barcode_number",  "") or "")
    style    = str(item_data.get("style_code",      "") or "")
    cref     = str(item_data.get("commercial_ref",  "") or "")

    mc_x0 = ix0 + _C3         # left edge of middle column (~42.4pt from ix0)
    mc_x1 = ix0 + 2 * _C3     # right edge of middle column
    mc_w  = mc_x1 - mc_x0     # ~42.4 pt

    # Barcode image: inset 8pt from left to fully clear the logo bleed edge.
    # The price-tag/tag logo in the left col extends ~7pt past mc_x0.
    # bc_x0 = mc_x0 + 8.0 places bars cleanly to the right with no overlap.
    BC_INSET = 8.0
    bc_x0 = mc_x0 + BC_INSET
    bc_w  = mc_w  - BC_INSET - 0.5   # ~33.9 pt

    # Dept codes: centred in bc_x0..bc_x0+bc_w (aligns with bars, avoids logo)
    fs_dept  = 5.0
    dept_str = "  ".join(p for p in [sub_dept, dept, sku_code] if p)
    DEPT_Y   = 200.6   # panel-relative

    if dept_str:
        page.insert_text(
            fitz.Point(_cx(dept_str, FR, fs_dept, bc_x0, bc_w), ay(DEPT_Y)),
            dept_str, fontname=FR, fontsize=fs_dept, color=DARK,
        )

    # Barcode bars
    BC_Y  = 207.0   # panel-relative top of bars
    BAR_H = 16.0    # measured from actual PDF

    _draw_barcode(page, bc_x0, ay(BC_Y), bc_w, BAR_H, bc_str,
                  txt_x0=bc_x0, txt_w=bc_w)

    # Style code + cref centred in same bc_x0..bc_x0+bc_w region
    fs_c    = 5.0
    style_y = 236.7   # panel-relative
    cref_y  = 246.1   # panel-relative

    if style:
        page.insert_text(
            fitz.Point(_cx(style, FR, fs_c, bc_x0, bc_w), ay(style_y)),
            style, fontname=FR, fontsize=fs_c, color=GREY,
        )
    if cref:
        page.insert_text(
            fitz.Point(_cx(cref, FR, fs_c, bc_x0, bc_w), ay(cref_y)),
            cref, fontname=FR, fontsize=fs_c, color=GREY,
        )

    # ── 8. RIGHT COLUMN — vertical text ──────────────────────────────────────
    country_zone = str(item_data.get("country_of_origin", "") or "").upper()
    phys_country = COUNTRY_ZONE_MAP.get(country_zone, "")

    rc_x0 = ix0 + 2 * _C3
    rc_x1 = ix1
    rc_fs  = 3.5

    v_lines = []
    if phys_country:
        v_lines.append(("MADE IN " + phys_country, FB, DARK))
    v_lines.append(("OVS - Via Terraglio 17", FR, LGREY))
    v_lines.append(("30174 Venezia ITALIA - info@ovs.it", FR, LGREY))

    zone_y_mid   = oy + (BC_Y + BC_Y + BAR_H) / 2
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

    # ── 10. PRICE ─────────────────────────────────────────────────────────────
    # From actual PDF:
    #   EUR at x_rel=26.66 from ix0, baseline y_rel=284.5
    #   29  at x_rel=45.29, gap from EUR right edge = ~2pt
    #   ,95 at x_rel=68.84, y_rel=276.7 (raised 7.8pt from main baseline)
    #
    # Font sizes from actual:
    #   EUR + 29 : 27.67pt (Type3 font = heavy bold condensed)
    #   ,95      : 15.1pt
    # We map to: fs_major=24pt (FB bold), fs_minor=13pt (FR)
    # EUR symbol: same fs_major, same FB bold font
    # Gap between EUR and 29: 2pt
    # No "AED" text — currency symbol only (handled by _fix_currency)
    #
    # IMPORTANT: currency is ALWAYS a symbol char, never bare text like "AED".
    # For AED, use a smaller matching size.

    currency  = _fix_currency(item_data.get("currency_symbol", ""))
    price_raw = str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_raw)

    CAP_H    = 0.72
    fs_major = 24.0         # main integer "29"  (maps to actual 27.67pt Type3)
    fs_minor = 13.0         # cents ",95"         (maps to actual 15.1pt Type3)

    # Currency symbol size:
    # Single char (euro/pound/dollar): same as fs_major (like actual 27.67)
    # 3-char "AED": scaled down so it visually appears as superscript-height
    is_long_sym = len(currency) > 1
    fs_sym  = fs_major * 0.65 if is_long_sym else fs_major

    MIN_raise = (fs_major - fs_minor) * CAP_H   # raise cents to cap-top

    icx = ix0 + INNER_W / 2   # horizontal centre

    sym_w   = fitz.get_text_length(currency, fontname=FB, fontsize=fs_sym)
    sym_gap = 2.5              # gap between symbol and main integer (matches actual)
    maj_w   = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w   = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)

    total_w = sym_w + sym_gap + maj_w + min_w
    px      = icx - total_w / 2
    pr_y    = ay(284.5)      # main baseline (panel-relative 284.5)

    # EUR symbol (same baseline as 29, same bold font)
    page.insert_text(fitz.Point(px, pr_y),
                     currency, fontname=FB, fontsize=fs_sym, color=DARK)
    # Main integer
    page.insert_text(fitz.Point(px + sym_w + sym_gap, pr_y),
                     major, fontname=FB, fontsize=fs_major, color=DARK)
    # Cents (raised superscript)
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
