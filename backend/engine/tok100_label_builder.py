"""
TOK100 Label Builder v7  –  pixel-fidelity using template embed + variable overlay

v7 fixes applied (per user review of TOK100_B0854559_1.pdf vs _OVS KIDS 2023.pdf):
  1. Zone A starts at y=120 (was 130) — erases any template stray line near y=130
     so only ONE separator appears above the YEARS+IT block.
  2. Zone structure split: full-width y=120-192, then middle+right cols only y=192-258.
     Left column below y=192 is NOT erased → Triman logo fully preserved.
  3. Only ONE separator line (sep1 at y=141, inset 2 pt from border).
     Sep2 between YEARS and IT removed — reference shows no line there.
  4. Separator lines have SEP_INSET=2 pt margin from inner border
     so inner spacing is uniform top-to-bottom.
  5. Proper EAN-13 barcode using ISO/IEC 15420 bit patterns (no pseudo-random bars).
  6. Barcode bars 16 pt tall (was 8 pt); barcode number text at correct y.
  7. Green price-separator dashes "[3 3]" (3 pt on, 3 pt off) for visible gaps.
  8. Border-restore lines start at y=120 to match new zone top.

Reference measurements (TOK100_B0854559_1.pdf, 400 DPI):
  Panel outer : 150.3 × 305.5 pt
  Inner area  : offset (11.5, 10.8), 127.2 × 283.9 pt
  Hole        : centre (74.8, 30.2), r=5.1  — magenta stroke, white fill
  sep1 line   : y_rel=141 (above YEARS+IT block)
  SEP green   : y_rel=257.49, x 12.7→134.4, dashed green
  Text rows from abs→panel_rel:
    y_panel=151.2  YEARS/CM values
    y_panel=167.2  IT/MEX values
    y_panel=179.2  Grid row 1 (4-5 5-6 6-7)
    y_panel=188    Grid row 2 (7-8 8-9 9-10)
    y_panel=196    Sub-dept / Dept / SKU codes
"""
import io, os, re
import fitz  # PyMuPDF

# ── Template file paths ───────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_TMPL = os.path.normpath(os.path.join(_HERE, "..", "templates", "OVS", "TOK100"))

FRONT_PANEL_TEMPLATE = os.path.join(_TMPL, "front_panel_ref.pdf")
BACK_PANEL_TEMPLATE  = os.path.join(_TMPL, "back_panel_ref.pdf")

# ── Panel geometry (all in pt, measured from reference at 400 DPI) ────────────
OUTER_W = 150.3
OUTER_H = 305.5

INNER_X = 11.5      # inner-content left offset from panel edge
INNER_Y = 10.8      # inner-content top  offset from panel edge
INNER_W = 127.2
INNER_H = 283.9

HOLE_RX = 74.8      # hole centre, relative to panel left
HOLE_RY = 30.2      # hole centre, relative to panel top
HOLE_R  = 5.1

SEP_Y   = 257.49    # dashed green price-separator y
SEP_X0  = 12.7
SEP_X1  = 134.4

# Column widths in the 3-column logo/barcode zone
_C3 = INNER_W / 3.0   # ≈ 42.4 pt

# ── White-overwrite zones (panel-relative, x0/y0/x1/y1) ──────────────────────
# Strategy:
#  A-full : y=120-192, full inner width.
#           y=120 start erases any template separator that leaked near y=130.
#           y=192 stop preserves the Triman logo in the left col (starts ~y=201).
#  B2     : y=192-258, middle col only — dept+barcode+style+cref.
#  B3     : y=192-258, right col only  — MADE IN / address vertical text.
#  C      : y=256-OUTER_H, full width  — price section.
# The LEFT COL (x 11.5→53.9) between y=192 and y=201 is blank white space in
# the template, so sub_dept text can be drawn there without erasing Triman.
ZONES = [
    (INNER_X,           120.0, INNER_X + INNER_W,   192.0),  # A-full
    (INNER_X + _C3,     192.0, INNER_X + 2 * _C3,  258.0),  # B2 middle
    (INNER_X + 2*_C3,   192.0, INNER_X + INNER_W,  258.0),  # B3 right
    (INNER_X,           256.0, INNER_X + INNER_W,  OUTER_H), # C price
]

# ── Colours ───────────────────────────────────────────────────────────────────
MAGENTA = (0.898, 0.023, 0.584)   # Pantone Rhodamine Red C
NAVY    = (0.000, 0.141, 0.235)
GOLD    = (0.992, 0.725, 0.153)   # exact from reference paths
GREEN   = (0.451, 0.749, 0.267)   # price-separator green
WHITE   = (1.000, 1.000, 1.000)
BLACK   = (0.000, 0.000, 0.000)
DARK    = (0.080, 0.080, 0.080)
GREY    = (0.450, 0.450, 0.450)
LGREY   = (0.680, 0.680, 0.680)
MID     = (0.280, 0.280, 0.280)

# ── Fonts (PDF Base-14) ───────────────────────────────────────────────────────
FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

# ── Size constants ────────────────────────────────────────────────────────────
TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]
SIZE_ROWS    = [TOK100_SIZES[:3], TOK100_SIZES[3:]]   # 2 rows of 3
CM_MAP = {"4-5":"110","5-6":"116","6-7":"122",
           "7-8":"128","8-9":"134","9-10":"140"}

# OVS XML country_of_origin → physical country mapping
# (WARM/COLD/MIDDLE EAST are OVS price-zone codes, NOT physical countries)
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
    """Right-align: return x so text ends at area_x1."""
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x1 - tw

def _fix_currency(raw):
    """
    Return the euro-sign character that renders correctly in PDF Base-14 fonts
    using WinAnsiEncoding (cp1252).  In WinAnsi, the euro glyph is at byte
    0x80 (chr(128)), not at the Unicode code-point U+20AC.
    """
    EUR = chr(128)   # € in WinAnsiEncoding / cp1252
    if not raw:
        return EUR
    s = str(raw)
    # Detect any form of €: Unicode U+20AC, UTF-8 mis-decoded, or XML entity
    if "\u20ac" in s or "â\x82¬" in s or "&#8364;" in s or "&euro;" in s:
        return EUR
    clean = "".join(c for c in s if 0x20 <= ord(c) < 0x80)
    if not clean or clean[0] in "?â":
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


# ── EAN-13 encoding tables (ISO/IEC 15420) ───────────────────────────────────
_EAN_L = ["0001101","0011001","0010011","0111101","0100011",
          "0110001","0101111","0111011","0110111","0001011"]
_EAN_G = ["0100111","0110011","0011011","0100001","0011101",
          "0111001","0000101","0010001","0001001","0010111"]
_EAN_R = ["1110010","1100110","1101100","1000010","1011100",
          "1001110","1010000","1000100","1001000","1110100"]
# Left-half parity pattern indexed by first (system) digit
_EAN_PARITY = ["LLLLLL","LLGLGG","LLGGLG","LLGGGL","LGLLGG",
               "LGGLLG","LGGGLL","LGLGLG","LGLGGL","LGGLGL"]

def _draw_ean13(page, x0, y0, w, h, bc):
    """Render a proper EAN-13 barcode using standard ISO/IEC 15420 bit patterns."""
    raw = (str(bc) if bc else "").strip()
    digits = (raw + "0" * 13)[:13]
    try:
        digs = [int(c) for c in digits]
    except ValueError:
        digs = [0] * 13
    parity = _EAN_PARITY[digs[0]]
    # Build 95-module bit string: start(3) + left-6×7 + centre(5) + right-6×7 + end(3)
    bits = "101"
    for i, p in enumerate(parity):
        d = digs[i + 1]
        bits += _EAN_L[d] if p == "L" else _EAN_G[d]
    bits += "01010"
    for i in range(6):
        bits += _EAN_R[digs[i + 7]]
    bits += "101"
    mod_w = w / 95.0
    for idx, bit in enumerate(bits):
        if bit == "1":
            rx = x0 + idx * mod_w
            page.draw_rect(fitz.Rect(rx, y0, min(rx + mod_w, x0 + w), y0 + h),
                           color=None, fill=DARK, width=0)

def _draw_barcode(page, x0, y0, w, bar_h, bc_str):
    """Draw EAN-13 bars (bar_h pt tall) then human-readable digits below."""
    _draw_ean13(page, x0, y0, w, bar_h, bc_str)
    p1, p2, p3 = _bc_chunks(bc_str)
    txt = f"{p1}  {p2}  {p3}"
    fs  = 5.0
    page.insert_text(
        fitz.Point(_cx(txt, FR, fs, x0, w), y0 + bar_h + fs + 0.5),
        txt, fontname=FR, fontsize=fs, color=DARK,
    )


# ── Template document cache ───────────────────────────────────────────────────
_TDOC: dict = {}

def _tpl(path):
    if path not in _TDOC and os.path.exists(path):
        _TDOC[path] = fitz.open(path)
    return _TDOC.get(path)


# ─────────────────────────────────────────────────────────────────────────────
# FRONT PANEL
# ─────────────────────────────────────────────────────────────────────────────
def _draw_front_panel(page, ox, oy):
    """
    Embed front_panel_ref.pdf — pixel-perfect OVS/kids gold vector shapes,
    navy fill, magenta border, punch hole, gold rule, PREMIUM text.
    Falls back to a drawn approximation if the template file is missing.
    """
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    tpl = _tpl(FRONT_PANEL_TEMPLATE)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
        return

    # ── Fallback drawing ──────────────────────────────────────────────────────
    ix0, iy0 = ox + INNER_X, oy + INNER_Y
    page.draw_rect(tgt,                color=None, fill=WHITE, width=0)
    page.draw_rect(fitz.Rect(ix0, iy0, ix0+INNER_W, iy0+INNER_H),
                   color=None, fill=NAVY,  width=0)
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


# ─────────────────────────────────────────────────────────────────────────────
# BACK PANEL
# ─────────────────────────────────────────────────────────────────────────────
def _draw_back_panel(page, ox, oy, item_data, render_dpi=150):
    """
    1. Embed static template (top zone: FSC / hole / QR / KIDS / separators
       + Triman recycling logo in left column of barcode zone).
    2. White-overwrite 4 variable zones.
    3. Restore partially-erased magenta inner border edges.
    4. Redraw all variable content with master-template-accurate positions.
    """
    ix0 = ox + INNER_X
    iy0 = oy + INNER_Y
    ix1 = ix0 + INNER_W
    iy1 = iy0 + INNER_H
    half = INNER_W / 2.0       # vertical centre divider x offset from ix0

    # ── 1. Static template embed ──────────────────────────────────────────────
    tpl = _tpl(BACK_PANEL_TEMPLATE)
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
    else:
        page.draw_rect(tgt, color=None, fill=WHITE, width=0)
        page.draw_rect(fitz.Rect(ix0, iy0, ix1, iy1),
                       color=MAGENTA, fill=None, width=0.5)
        page.draw_circle(fitz.Point(ox+HOLE_RX, oy+HOLE_RY), HOLE_R,
                         color=MAGENTA, fill=WHITE, width=0.5)

    # ── 2. White-overwrite variable zones ─────────────────────────────────────
    for x0r, y0r, x1r, y1r in ZONES:
        page.draw_rect(
            fitz.Rect(ox+x0r, oy+y0r, ox+x1r, oy+y1r),
            color=None, fill=WHITE, width=0,
        )

    # ── 3. Restore magenta inner-border edges erased by overwrite ─────────────
    # Zone A now starts at y=120 so restore from y=120 down.
    page.draw_line(fitz.Point(ix0, iy1), fitz.Point(ix1, iy1),
                   color=MAGENTA, width=0.5)                              # bottom
    page.draw_line(fitz.Point(ix0, oy+120), fitz.Point(ix0, iy1),
                   color=MAGENTA, width=0.5)                              # left
    page.draw_line(fitz.Point(ix1, oy+120), fitz.Point(ix1, iy1),
                   color=MAGENTA, width=0.5)                              # right

    # ── Convenience helpers ───────────────────────────────────────────────────
    def ay(r): return oy + r    # panel-relative → page absolute y

    # ── 4. SIZE DETAIL SECTION ────────────────────────────────────────────────
    sizes   = item_data.get("sizes") or {}
    cur_yrs = sizes.get("YEARS", "")
    cur_it  = sizes.get("IT")  or cur_yrs
    cur_mex = re.sub(r"\s*A$", "", (sizes.get("MEX") or cur_yrs) or "").strip()
    cur_cm  = CM_MAP.get(cur_yrs, sizes.get("CM", ""))

    # Font sizes (matched to visual reference)
    fs_lbl = 6.5    # "YEARS", "IT", "CM", "MEX" labels
    fs_val = 9.0    # "4-5", "110" values
    GAP    = 3.0    # left margin inside each half

    SEP_INSET = 2.0    # pt inset from inner border — keeps lines from touching magenta
    vert_x = ix0 + half   # x of vertical divider between left/right halves

    # ── ONE separator ABOVE the YEARS+IT block (y_rel=141) ───────────────────
    # Reference has only one separator here; no line between YEARS and IT rows.
    sep1 = ay(141)
    page.draw_line(fitz.Point(ix0 + SEP_INSET, sep1),
                   fitz.Point(ix1 - SEP_INSET, sep1),
                   color=MID, width=0.6)
    # Vertical centre divider — spans the full YEARS+IT block height
    page.draw_line(fitz.Point(vert_x, sep1),
                   fitz.Point(vert_x, ay(172)),
                   color=LGREY, width=0.3)

    # ── Row 1: YEARS [val right-aligned] | CM [val right-aligned] ─────────────
    bl1 = ay(151.2)   # reference-measured baseline
    page.insert_text(fitz.Point(ix0 + GAP, bl1),
                     "YEARS", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_yrs, FB, fs_val, vert_x - GAP), bl1),
                     cur_yrs, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + GAP, bl1),
                     "CM", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_cm, FB, fs_val, ix1 - GAP), bl1),
                     cur_cm, fontname=FB, fontsize=fs_val, color=DARK)

    # ── Row 2: IT [val] | MEX [val A]  (no separator between YEARS and IT) ────
    bl2 = ay(167.2)   # reference-measured baseline
    mex_txt = f"{cur_mex} A"
    page.insert_text(fitz.Point(ix0 + GAP, bl2),
                     "IT", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_it, FB, fs_val, vert_x - GAP), bl2),
                     cur_it, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + GAP, bl2),
                     "MEX", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(mex_txt, FB, fs_val, ix1 - GAP), bl2),
                     mex_txt, fontname=FB, fontsize=fs_val, color=DARK)

    # ── 5. SIZE GRID: 2 rows of 3 ─────────────────────────────────────────────
    # Cell width = INNER_W / 3  (since 3 sizes per row)
    c3w    = INNER_W / 3.0
    fs_gr  = 7.5
    cell_h = 12.0

    # Row 1 → 4-5, 5-6, 6-7   baseline y_rel=179.2 (reference text extraction)
    # Row 2 → 7-8, 8-9, 9-10  baseline y_rel=188   (image pixel measurement: 730px/3.879px/pt)
    grid_baselines = [ay(179.2), ay(188.0)]

    for ri, (row, bl) in enumerate(zip(SIZE_ROWS, grid_baselines)):
        for ci, sz in enumerate(row):
            cx0 = ix0 + ci * c3w
            cx1 = cx0 + c3w
            is_cur = (sz == cur_yrs)
            if is_cur:
                page.draw_rect(fitz.Rect(cx0, bl - fs_gr - 2, cx1, bl + 2),
                               color=None, fill=BLACK, width=0)
            fn = FB if is_cur else FR
            tc = WHITE if is_cur else DARK
            tw = fitz.get_text_length(sz, fontname=fn, fontsize=fs_gr)
            page.insert_text(
                fitz.Point(cx0 + (c3w - tw) / 2, bl),
                sz, fontname=fn, fontsize=fs_gr, color=tc,
            )

    # ── 6. DEPT / SKU CODES ROW (y_rel=193.2, reference-measured) ──────────────
    # These codes appear above the barcode block in the middle column,
    # and sub_dept in the left column at the same y baseline.
    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department",     "") or "")
    sku      = str(item_data.get("sku_code",        "") or "")
    fs_c     = 5.5
    dept_y   = ay(196.0)   # measured: 760px/3.879px/pt=196pt (bottom image estimation)

    # Sub-dept in left col, dept and SKU in middle col
    page.insert_text(fitz.Point(ix0 + GAP, dept_y),
                     sub_dept, fontname=FR, fontsize=fs_c, color=DARK)
    page.insert_text(fitz.Point(ix0 + _C3 + GAP, dept_y),
                     dept, fontname=FR, fontsize=fs_c, color=DARK)
    page.insert_text(fitz.Point(ix0 + _C3 + 22,  dept_y),
                     sku,  fontname=FR, fontsize=fs_c, color=DARK)

    # ── 7. BARCODE + REFS (middle column, Zone B2) ───────────────────────────
    # Reference text positions (abs→panel_rel):
    #   barcode NUMBER text : y_rel=220.2 (y=593 abs)
    #   style code          : y_rel=229.2 (y=602 abs)
    #   commercial ref      : y_rel=239.2 (y=612 abs)
    # Bars start at y_rel=197, height=17pt so bars end at y_rel=214;
    # barcode number text at y_rel=214+5.5+0.5=220.  ✓
    bc_str = str(item_data.get("barcode_number",  "") or "")
    style  = str(item_data.get("style_code",      "") or "")
    cref   = str(item_data.get("commercial_ref",  "") or "")
    mc_x0  = ix0 + _C3 + 2
    mc_w   = _C3 - 4
    BC_Y   = 200.0   # barcode bars top (pt below dept codes descenders)
    BAR_H  = 16.0    # bar height in pt; number text at BC_Y+16+5.5=221.5 ≈ ref 220.2
    _draw_barcode(page, mc_x0, ay(BC_Y), mc_w, BAR_H, bc_str)
    # style → y=200+29=229 ≈ ref 229.2;  cref → y=200+39=239 ≈ ref 239.2
    for txt, y_off in [(style, 29), (cref, 39)]:
        if txt:
            page.insert_text(
                fitz.Point(_cx(txt, FR, fs_c, mc_x0, mc_w), ay(BC_Y + y_off)),
                txt, fontname=FR, fontsize=fs_c, color=GREY,
            )

    # ── 8. RIGHT COLUMN — vertical text (rotate=90, bottom→top) ─────────────
    country_zone = str(item_data.get("country_of_origin", "") or "").upper()
    phys_country  = COUNTRY_ZONE_MAP.get(country_zone, "")

    rc_x0 = ix0 + 2 * _C3   # right col left edge
    rc_x1 = ix1              # right col right edge
    rc_fs = 3.5              # font size for vertical text

    # Three vertical text lines, spaced side-by-side in the right column
    v_lines = []
    if phys_country:
        v_lines.append((f"MADE IN {phys_country}", FB, DARK))
    v_lines.append(("OVS - Via Terraglio 17", FR, LGREY))
    v_lines.append(("30174 Venezia ITALIA - info@ovs.it", FR, LGREY))

    # Zone spans y=200→258. Center each vertical line in the zone.
    zone_y_mid = oy + (200 + 258) / 2
    line_spacing = rc_fs + 2.0
    total_span = (len(v_lines) - 1) * line_spacing
    # x positions: stack lines from left of right col
    x_start = rc_x0 + (rc_x1 - rc_x0 - total_span) / 2

    for li, (vtxt, vfn, vcol) in enumerate(v_lines):
        vx = x_start + li * line_spacing + rc_fs
        tw = fitz.get_text_length(vtxt, fontname=vfn, fontsize=rc_fs)
        # Start y so text is centred in zone height
        vy_start = zone_y_mid + tw / 2
        page.insert_text(fitz.Point(vx, vy_start),
                         vtxt, fontname=vfn, fontsize=rc_fs,
                         color=vcol, rotate=90)

    # ── 9. DASHED GREEN PRICE SEPARATOR ──────────────────────────────────────
    # Reference: y_rel=257.49, x 12.7→134.4. "[3 3]" = 3pt dash / 3pt gap.
    page.draw_line(
        fitz.Point(ox + SEP_X0, ay(SEP_Y)),
        fitz.Point(ox + SEP_X1, ay(SEP_Y)),
        color=GREEN, dashes="[3 3]", width=1.0,
    )

    # ── 10. PRICE ─────────────────────────────────────────────────────────────
    currency  = _fix_currency(item_data.get("currency_symbol", ""))
    price_raw = str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_raw)

    fs_sym   = 10.0
    fs_major = 24.0
    fs_minor = 13.0
    icx = ix0 + INNER_W / 2

    sym_w = fitz.get_text_length(currency, fontname=FR, fontsize=fs_sym) + 2
    maj_w = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)
    px    = icx - (sym_w + maj_w + min_w) / 2
    pr_y  = ay(SEP_Y + 26)

    page.insert_text(fitz.Point(px,             pr_y - fs_major*0.38),
                     currency, fontname=FR, fontsize=fs_sym,   color=DARK)
    page.insert_text(fitz.Point(px + sym_w,     pr_y),
                     major,    fontname=FB, fontsize=fs_major,  color=DARK)
    page.insert_text(fitz.Point(px+sym_w+maj_w+1, pr_y - fs_major*0.35),
                     minor,    fontname=FR, fontsize=fs_minor,  color=DARK)

    # ── 11. QTY below outer panel ─────────────────────────────────────────────
    qty_txt = f"Qty - {item_data.get('quantity', 0)}"
    fs_qty  = 10.0
    page.insert_text(
        fitz.Point(_cx(qty_txt, FB, fs_qty, ox, OUTER_W),
                   oy + OUTER_H + fs_qty + 3),
        qty_txt, fontname=FB, fontsize=fs_qty, color=DARK,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_label_pdf(item_data: dict) -> bytes:
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


def build_label_png(item_data: dict, dpi: int = 150) -> bytes:
    pdf = build_label_pdf(item_data)
    doc = fitz.open(stream=pdf, filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False)
    doc.close()
    return pix.tobytes("png")


def build_label_thumbnail(item_data: dict, dpi: int = 60) -> bytes:
    return build_label_png(item_data, dpi=dpi)
