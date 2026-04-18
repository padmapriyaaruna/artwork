# -*- coding: utf-8 -*-
"""
TOK100 Label Builder v10  -  pixel-fidelity using template embed + variable overlay

v10 fixes applied (per user review of TOK100_B0854559_1.pdf vs generated PDF):
  1. Barcode height increased (BAR_H=16->25) and width optimized; digit-text
     centred in wider mc_num area to avoid clipping.
  2. Size chart converted from flat 1x6 row back to proper 2x3 grid with
     CHIP_W=34pt, CHIP_GAP=2pt, row baselines at y=179.2 and y=188.0.
  3. Currency symbol size fixed: single-char (EUR) now 20pt vs major 24pt
     so it visually matches the reference (actual PDF shows symbol same height
     as major digits).  2-char -> 14pt, 3-char AED -> 9pt.

Reference measurements (TOK100_B0854559_1.pdf, 400 DPI):
  Panel outer : 150.3 x 305.5 pt
  Inner area  : offset (11.5, 10.8), 127.2 x 283.9 pt
  Hole        : centre (74.8, 30.2), r=5.1  - magenta stroke, white fill
  sep1 line   : y_rel=141 (above YEARS+IT block)
  SEP green   : y_rel=257.49, x 12.7->134.4, dashed green
  Text rows from abs->panel_rel:
    y_panel=151.2  YEARS/CM values
    y_panel=167.2  IT/MEX values
    y_panel=179.2  Grid row 1 (4-5 5-6 6-7)
    y_panel=188.0  Grid row 2 (7-8 8-9 9-10)
    y_panel=196    Sub-dept / Dept / SKU codes
    y_panel=200    Barcode bars start
"""
import io, os, re
import fitz  # PyMuPDF

# Template file paths
_HERE = os.path.dirname(os.path.abspath(__file__))
_TMPL = os.path.normpath(os.path.join(_HERE, "..", "templates", "OVS", "TOK100"))

FRONT_PANEL_TEMPLATE = os.path.join(_TMPL, "front_panel_ref.pdf")
BACK_PANEL_TEMPLATE  = os.path.join(_TMPL, "back_panel_ref.pdf")

# Panel geometry (all in pt, measured from reference at 400 DPI)
OUTER_W = 150.3
OUTER_H = 305.5

INNER_X = 11.5
INNER_Y = 10.8
INNER_W = 127.2
INNER_H = 283.9

HOLE_RX = 74.8
HOLE_RY = 30.2
HOLE_R  = 5.1

SEP_Y   = 257.49
SEP_X0  = 12.7
SEP_X1  = 134.4

_C3 = INNER_W / 3.0

ZONES = [
    (INNER_X,           120.0, INNER_X + INNER_W,   188.0),
    (INNER_X + _C3,     188.0, INNER_X + 2 * _C3,  258.0),
    (INNER_X + 2*_C3,   188.0, INNER_X + INNER_W,  258.0),
    (INNER_X,           256.0, INNER_X + INNER_W,  OUTER_H),
]

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

FB = "hebo"
FR = "helv"

TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]
SIZE_ROWS    = [TOK100_SIZES[:3], TOK100_SIZES[3:]]
CM_MAP = {"4-5":"110","5-6":"116","6-7":"122",
           "7-8":"128","8-9":"134","9-10":"140"}

COUNTRY_ZONE_MAP = {
    "WARM":        "INDIA",
    "COLD":        "INDIA",
    "MIDDLE EAST": "INDIA",
}


def _cx(text, font, fs, area_x0, area_w):
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x0 + (area_w - tw) / 2

def _rx(text, font, fs, area_x1):
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x1 - tw

def _fix_currency(raw):
    EUR = chr(128)
    if not raw:
        return EUR
    s = str(raw)
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
    from PIL import Image, ImageDraw
    bits  = _ean13_bits(bc_str)
    w_px  = max(200, round(w     / 72 * 300))
    h_px  = max(80,  round(bar_h / 72 * 300))
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
    p1, p2, p3 = _bc_chunks(bc_str)
    txt = p1 + " " + p2 + " " + p3
    fs  = 4.8
    cx0 = txt_x0 if txt_x0 is not None else x0
    cw  = txt_w  if txt_w  is not None else w
    page.insert_text(
        fitz.Point(_cx(txt, FR, fs, cx0, cw), y0 + bar_h + fs + 0.5),
        txt, fontname=FR, fontsize=fs, color=DARK,
    )


_TDOC = {}

def _tpl(path):
    if path not in _TDOC and os.path.exists(path):
        _TDOC[path] = fitz.open(path)
    return _TDOC.get(path)


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


def _draw_back_panel(page, ox, oy, item_data, render_dpi=150):
    ix0 = ox + INNER_X
    iy0 = oy + INNER_Y
    ix1 = ix0 + INNER_W
    iy1 = iy0 + INNER_H
    half = INNER_W / 2.0

    ay = lambda r: oy + r

    tpl = _tpl(BACK_PANEL_TEMPLATE)
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)
    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
    else:
        page.draw_rect(tgt, color=None, fill=WHITE, width=0)

    for (rx0, ry0, rx1, ry1) in ZONES:
        page.draw_rect(
            fitz.Rect(ox + rx0, oy + ry0, ox + rx1, oy + ry1),
            color=None, fill=WHITE, width=0,
        )

    SEP_INSET = 2.0
    page.draw_line(fitz.Point(ix0, ay(120)), fitz.Point(ix0, ay(188)),
                   color=MAGENTA, width=0.5)
    page.draw_line(fitz.Point(ix1, ay(120)), fitz.Point(ix1, iy1),
                   color=MAGENTA, width=0.5)
    page.draw_line(fitz.Point(ix0, iy1), fitz.Point(ix1, iy1),
                   color=MAGENTA, width=0.5)

    sizes   = item_data.get("sizes") or {}
    cur_yrs = sizes.get("YEARS", "")
    cur_it  = sizes.get("IT") or cur_yrs
    cur_mex = re.sub(r"\s*A$", "", (sizes.get("MEX") or cur_yrs) or "").strip()
    cur_cm  = CM_MAP.get(cur_yrs, sizes.get("CM", ""))

    fs_lbl = 6.5
    fs_val = 9.0
    GAP    = 3.0
    vert_x = ix0 + half

    sep1 = ay(141)
    page.draw_line(fitz.Point(ix0 + SEP_INSET, sep1),
                   fitz.Point(ix1 - SEP_INSET, sep1),
                   color=MID, width=0.6)
    page.draw_line(fitz.Point(vert_x, sep1),
                   fitz.Point(vert_x, ay(172)),
                   color=LGREY, width=0.3)

    bl1 = ay(151.2)
    page.insert_text(fitz.Point(ix0 + GAP, bl1),
                     "YEARS", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_yrs, FB, fs_val, vert_x - GAP), bl1),
                     cur_yrs, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(vert_x + GAP, bl1),
                     "CM", fontname=FB, fontsize=fs_lbl, color=DARK)
    page.insert_text(fitz.Point(_rx(cur_cm, FB, fs_val, ix1 - GAP), bl1),
                     cur_cm, fontname=FB, fontsize=fs_val, color=DARK)

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

    # SIZE GRID - FIX: proper 2x3 grid matching the reference layout
    CHIP_W   = 34.0
    CHIP_GAP = 2.0
    fs_gr    = 7.5
    chip_x0  = ix0 + (INNER_W - 3 * CHIP_W - 2 * CHIP_GAP) / 2
    grid_baselines = [ay(179.2), ay(188.0)]

    for ri, (row, bl) in enumerate(zip(SIZE_ROWS, grid_baselines)):
        for ci, sz in enumerate(row):
            cx = chip_x0 + ci * (CHIP_W + CHIP_GAP)
            is_cur = (sz == cur_yrs)
            if is_cur:
                page.draw_rect(
                    fitz.Rect(cx, bl - fs_gr + 1, cx + CHIP_W, bl + 1),
                    color=None, fill=BLACK, width=0
                )
            fn = FB if is_cur else FR
            tc = WHITE if is_cur else DARK
            tw = fitz.get_text_length(sz, fontname=fn, fontsize=fs_gr)
            page.insert_text(
                fitz.Point(cx + (CHIP_W - tw) / 2, bl),
                sz, fontname=fn, fontsize=fs_gr, color=tc,
            )

    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department",     "") or "")
    sku      = str(item_data.get("sku_code",        "") or "")
    fs_c     = 5.5
    fs_dept  = 4.5
    dept_y   = ay(196.0)
    mc_dept  = ix0 + _C3 + 2

    _dx = mc_dept
    for code in filter(None, [sub_dept, dept, sku]):
        page.insert_text(fitz.Point(_dx, dept_y),
                         code, fontname=FR, fontsize=fs_dept, color=DARK)
        _dx += fitz.get_text_length(code, fontname=FR, fontsize=fs_dept) + 3

    # BARCODE - FIX: increased BAR_H from 16 to 25pt; wider digit-text centering area
    bc_str    = str(item_data.get("barcode_number",  "") or "")
    style     = str(item_data.get("style_code",      "") or "")
    cref      = str(item_data.get("commercial_ref",  "") or "")
    mc_x0     = ix0 + _C3 + 2
    mc_w      = _C3 - 4
    mc_num_x0 = ix0 + _C3 + 2
    mc_num_w  = _C3 - 4
    BC_Y      = 200.0
    BAR_H     = 25.0
    _draw_barcode(page, mc_x0, ay(BC_Y), mc_w, BAR_H, bc_str,
                  txt_x0=mc_num_x0, txt_w=mc_num_w)
    for txt, y_off in [(style, 34), (cref, 44)]:
        if txt:
            page.insert_text(
                fitz.Point(_cx(txt, FR, fs_c, mc_x0, mc_w), ay(BC_Y + y_off)),
                txt, fontname=FR, fontsize=fs_c, color=GREY,
            )

    country_zone = str(item_data.get("country_of_origin", "") or "").upper()
    phys_country  = COUNTRY_ZONE_MAP.get(country_zone, "")

    rc_x0 = ix0 + 2 * _C3
    rc_x1 = ix1
    rc_fs = 3.5

    v_lines = []
    if phys_country:
        v_lines.append(("MADE IN " + phys_country, FB, DARK))
    v_lines.append(("OVS - Via Terraglio 17", FR, LGREY))
    v_lines.append(("30174 Venezia ITALIA - info@ovs.it", FR, LGREY))

    zone_y_mid   = oy + (200 + 258) / 2
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

    page.draw_line(
        fitz.Point(ox + SEP_X0, ay(SEP_Y)),
        fitz.Point(ox + SEP_X1, ay(SEP_Y)),
        color=GREEN, dashes="[3 3] 0", width=1.0,
    )

    # CURRENCY SYMBOL - FIX: single-char EUR/GBP 20pt (was 9pt) to match reference
    currency  = _fix_currency(item_data.get("currency_symbol", ""))
    price_raw = str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_raw)

    CAP_H    = 0.72
    fs_major = 24.0
    fs_minor = 12.0
    _sym_sz  = {1: 20.0, 2: 14.0, 3: 9.0}
    fs_sym   = _sym_sz.get(len(currency), 7.0)
    EUR_raise = (fs_major - fs_sym)   * CAP_H
    MIN_raise = (fs_major - fs_minor) * CAP_H
    icx = ix0 + INNER_W / 2

    sym_w = fitz.get_text_length(currency, fontname=FR, fontsize=fs_sym) + 1
    maj_w = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)
    px    = icx - (sym_w + maj_w + min_w) / 2
    pr_y  = ay(SEP_Y + 26)

    page.insert_text(fitz.Point(px,               pr_y - EUR_raise),
                     currency, fontname=FR, fontsize=fs_sym, color=DARK)
    page.insert_text(fitz.Point(px + sym_w,       pr_y),
                     major,    fontname=FB, fontsize=fs_major, color=DARK)
    page.insert_text(fitz.Point(px+sym_w+maj_w+1, pr_y - MIN_raise),
                     minor,    fontname=FR, fontsize=fs_minor, color=DARK)

    qty_txt = "Qty - " + str(item_data.get("quantity", 0))
    fs_qty  = 10.0
    page.insert_text(
        fitz.Point(_cx(qty_txt, FB, fs_qty, ox, OUTER_W),
                   oy + OUTER_H + fs_qty + 3),
        qty_txt, fontname=FB, fontsize=fs_qty, color=DARK,
    )


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
