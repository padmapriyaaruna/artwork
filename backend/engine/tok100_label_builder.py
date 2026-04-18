"""
TOK100 Label Builder v4 — Template-embed + variable overlay approach.

Architecture
------------
1. For the BACK panel, we embed backend/templates/OVS/TOK100/back_panel_ref.pdf
   as the base layer (pixel-perfect static content: FSC logo, QR code,
   Triman recycling logo, magenta border, punch hole, K I D S header,
   separator lines, barcode bars, recycling text).

2. We then draw WHITE filled rectangles over three variable zones:
   - Zone A: size detail rows + size grid  (y_rel 130–185)
   - Zone B: dept/SKU/barcode text/refs   (y_rel 183–257)
   - Zone C: price area                   (y_rel 255–305)

3. Variable content is drawn on top of the white zones.

Measurements (all from reference TOK100_B0854559_1.pdf at 500 DPI)
-------------------------------------------------------------------
Panel outer   : 150.3 × 305.5 pt (white fill, no stroke)
Inner content : offset (11.6, 10.7), size 127.2 × 283.9 pt
                = 44.9 mm × 100.1 mm (physical label)
Magenta border: RGB(0.898, 0.023, 0.584) — embedded from reference
Hole          : centre (74.8, 30.2) from panel TL, radius 5.1 pt
Green sep     : y_rel=257.49, x 12.7→134.4, h=0.5 pt,
                RGB(0.451, 0.749, 0.267), solid

Data note: country_of_origin in XML = OVS price-zone code (WARM/COLD/MID EAST)
           NOT a physical country.  Do NOT use it for "Made in" text.
"""
import io, os, re, math
import fitz  # PyMuPDF

try:
    import qrcode
    from PIL import Image as PILImage
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

# ── Template file ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.normpath(
    os.path.join(_HERE, "..", "templates", "OVS", "TOK100")
)
BACK_PANEL_TEMPLATE = os.path.join(TEMPLATE_DIR, "back_panel_ref.pdf")

# ── Panel geometry (from reference measurements) ──────────────────────────────
OUTER_W  = 150.3  # panel width  pt
OUTER_H  = 305.5  # panel height pt

INNER_X  =  11.6  # inner content left offset from panel edge
INNER_Y  =  10.7  # inner content top offset from panel edge
INNER_W  = 127.2  # inner content width  pt = 44.9 mm
INNER_H  = 283.9  # inner content height pt = 100.1 mm

HOLE_RX  =  74.8  # hole centre, relative to panel left
HOLE_RY  =  30.2  # hole centre, relative to panel top
HOLE_R   =   5.1  # hole radius pt

SEP_Y    = 257.49 # price separator y, relative to panel top
SEP_X0   =  12.7  # separator x start, relative to panel left
SEP_X1   = 134.4  # separator x end
SEP_H    =   0.5  # separator height pt

# ── White overwrite zones (relative to panel TL) ─────────────────────────────
# These cover all variable text areas so we can redraw fresh data on top.
ZONES = [
    ( INNER_X, 130.0, INNER_X + INNER_W, 185.0 ),  # A: size detail + grid
    ( INNER_X, 183.0, INNER_X + INNER_W, 257.0 ),  # B: refs / barcode
    ( INNER_X, 255.0, INNER_X + INNER_W, OUTER_H ), # C: price
]

# ── Colours ───────────────────────────────────────────────────────────────────
MAGENTA = (0.898, 0.023, 0.584)
NAVY    = (0.000, 0.141, 0.235)
GOLD    = (0.922, 0.714, 0.180)
GREEN   = (0.451, 0.749, 0.267)
WHITE   = (1.000, 1.000, 1.000)
BLACK   = (0.000, 0.000, 0.000)
DARK    = (0.080, 0.080, 0.080)
GREY    = (0.450, 0.450, 0.450)
LGREY   = (0.750, 0.750, 0.750)

# ── PyMuPDF Base-14 fonts ─────────────────────────────────────────────────────
FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

# ── Size range for TOK100 ─────────────────────────────────────────────────────
TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]
CM_MAP = {"4-5":"110","5-6":"116","6-7":"122","7-8":"128","8-9":"134","9-10":"140"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cx(text, font, fs, area_x0, area_w):
    """Centre text horizontally within an area."""
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x0 + (area_w - tw) / 2


def _fix_currency(raw):
    """Return a clean currency symbol string."""
    if not raw:
        return "\u20ac"
    clean = "".join(c for c in str(raw) if 0x20 <= ord(c) < 0x80)
    if not clean or clean[0] in "?â":
        return "\u20ac"
    return clean


def _split_price(price_str):
    p = str(price_str or "0,00").strip()
    m = re.match(r"^(\d+)([,.]?\d*)$", p)
    if m:
        return m.group(1), m.group(2)
    return p, ""


def _split_barcode(bc):
    bc = str(bc or "").strip()
    if len(bc) >= 13:
        return bc[0], bc[1:7], bc[7:13]
    elif len(bc) >= 7:
        return bc[0], bc[1:7], bc[7:]
    return bc, "", ""


def _draw_barcode_bars(page, x0, y0, w, h, barcode_str):
    """Draw EAN-13 barcode vertical bars."""
    digits = barcode_str[:13] if barcode_str else "0000000000000"
    n_bars = len(digits) * 3          # rough bar count
    bar_w  = w / n_bars
    for i, d in enumerate(digits):
        bx = x0 + i * bar_w * 3
        bw = bar_w * (1.0 + int(d) % 3 * 0.4)
        if bx + bw > x0 + w:
            break
        page.draw_rect(fitz.Rect(bx, y0, bx + bw, y0 + h),
                       color=None, fill=DARK, width=0)


def _draw_barcode(page, x0, y0, w, h, barcode_str):
    """EAN-13 barcode — graphic bars + split digit text."""
    bar_h = h * 0.60
    _draw_barcode_bars(page, x0, y0, w, bar_h, barcode_str)

    p1, p2, p3 = _split_barcode(barcode_str)
    bc_txt = f"{p1}  {p2}  {p3}"
    fs = 5.5
    page.insert_text(
        fitz.Point(_cx(bc_txt, FR, fs, x0, w), y0 + bar_h + fs + 1),
        bc_txt, fontname=FR, fontsize=fs, color=DARK,
    )


# ── Template document (cached singleton) ──────────────────────────────────────
_template_doc: fitz.Document | None = None

def _get_template_doc() -> fitz.Document | None:
    global _template_doc
    if _template_doc is None:
        if os.path.exists(BACK_PANEL_TEMPLATE):
            _template_doc = fitz.open(BACK_PANEL_TEMPLATE)
    return _template_doc


# ── FRONT panel ───────────────────────────────────────────────────────────────

def _draw_front_panel(page, ox, oy):
    """Navy OVS front hang-tag."""
    cx = ox + OUTER_W / 2

    # Outer white panel (no border)
    page.draw_rect(fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H),
                   color=None, fill=WHITE, width=0)

    # Inner navy area
    nx0 = ox + INNER_X
    ny0 = oy + INNER_Y
    nw  = INNER_W
    nh  = INNER_H
    page.draw_rect(fitz.Rect(nx0, ny0, nx0 + nw, ny0 + nh),
                   color=None, fill=NAVY, width=0)

    # Magenta inner border (same as back panel — Pantone Rhodamine Red C)
    page.draw_rect(fitz.Rect(nx0, ny0, nx0 + nw, ny0 + nh),
                   color=MAGENTA, fill=None, width=0.8)

    # Punch hole (white + magenta border)
    page.draw_circle(fitz.Point(ox + HOLE_RX, oy + HOLE_RY), HOLE_R,
                     color=MAGENTA, fill=WHITE, width=0.8)

    # Magenta accent strip — top
    page.draw_line(fitz.Point(nx0, ny0 + 20),
                   fitz.Point(nx0 + nw, ny0 + 20),
                   color=MAGENTA, width=2.0)

    ncx = nx0 + nw / 2

    # "OVS" gold text
    fs_ovs = 28.0
    ovs_y  = ny0 + nh * 0.50
    page.insert_text(
        fitz.Point(_cx("OVS", FB, fs_ovs, nx0, nw), ovs_y),
        "OVS", fontname=FB, fontsize=fs_ovs, color=GOLD,
    )

    # "kids" gold text
    fs_kids = 12.0
    page.insert_text(
        fitz.Point(_cx("kids", FR, fs_kids, nx0, nw), ovs_y + 16),
        "kids", fontname=FR, fontsize=fs_kids, color=GOLD,
    )

    # Magenta accent strip — bottom (pink line before end of label)
    page.draw_line(fitz.Point(nx0, ny0 + nh - 10),
                   fitz.Point(nx0 + nw, ny0 + nh - 10),
                   color=MAGENTA, width=2.0)


# ── BACK panel ────────────────────────────────────────────────────────────────

def _draw_back_panel(page, ox, oy, item_data, render_dpi=150):
    """
    Draw complete back panel at absolute page position (ox, oy).

    Strategy:
    1. Embed static template from back_panel_ref.pdf  (logos, QR, borders …)
    2. White-overwrite the 3 variable zones
    3. Draw variable content (size grid, barcode, price …)
    """
    # ── 1. Static template embed ──────────────────────────────────────────────
    tpl = _get_template_doc()
    tgt = fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H)

    if tpl is not None:
        page.show_pdf_page(tgt, tpl, 0)
    else:
        # Fallback: plain white panel with magenta border
        page.draw_rect(tgt, color=None, fill=WHITE, width=0)
        ix0, iy0 = ox + INNER_X, oy + INNER_Y
        page.draw_rect(
            fitz.Rect(ix0, iy0, ix0 + INNER_W, iy0 + INNER_H),
            color=MAGENTA, fill=None, width=0.8,
        )
        page.draw_circle(fitz.Point(ox + HOLE_RX, oy + HOLE_RY), HOLE_R,
                         color=MAGENTA, fill=WHITE, width=0.8)

    # ── 2. White overwrite zones ──────────────────────────────────────────────
    for x0r, y0r, x1r, y1r in ZONES:
        page.draw_rect(
            fitz.Rect(ox + x0r, oy + y0r, ox + x1r, oy + y1r),
            color=None, fill=WHITE, width=0,
        )

    # After overwriting zone A we must re-draw the green separator (it spans zone boundary)
    # and re-draw bottom portion of the magenta inner border (we erased it via zone C).
    ix0 = ox + INNER_X
    iy0 = oy + INNER_Y
    ix1 = ix0 + INNER_W
    iy1 = iy0 + INNER_H

    # Restore bottom + side borders of inner content area
    page.draw_line(fitz.Point(ix0, iy0 + INNER_H), fitz.Point(ix1, iy0 + INNER_H),
                   color=MAGENTA, width=0.8)
    page.draw_line(fitz.Point(ix0, iy0 + 130), fitz.Point(ix0, iy1),
                   color=MAGENTA, width=0.8)
    page.draw_line(fitz.Point(ix1, iy0 + 130), fitz.Point(ix1, iy1),
                   color=MAGENTA, width=0.8)

    # ── Helper: absolute page coordinates from panel-relative ─────────────────
    def ax(rel): return ox + rel
    def ay(rel): return oy + rel
    icx = ix0 + INNER_W / 2  # inner centre X

    # ── 3a. SIZE DETAIL ROW ───────────────────────────────────────────────────
    sizes    = item_data.get("sizes") or {}
    cur_yrs  = sizes.get("YEARS", "")
    cur_it   = sizes.get("IT")  or cur_yrs
    cur_mex  = re.sub(r"\s*A$", "", sizes.get("MEX", cur_yrs) or "").strip()
    cur_cm   = CM_MAP.get(cur_yrs, sizes.get("CM", ""))
    half     = INNER_W / 2
    fs_lbl   = 5.0
    fs_val   = 7.5

    # Left col: YEARS / IT
    lx = ix0 + 3
    page.insert_text(fitz.Point(lx, ay(143) + fs_lbl),
                     "YEARS", fontname=FR, fontsize=fs_lbl, color=GREY)
    page.insert_text(fitz.Point(lx + 18, ay(143) + fs_val),
                     cur_yrs, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(lx, ay(143) + fs_val + fs_lbl + 3),
                     "IT", fontname=FR, fontsize=fs_lbl, color=GREY)
    page.insert_text(fitz.Point(lx + 18, ay(143) + fs_val * 2 + 3),
                     cur_it, fontname=FB, fontsize=fs_val, color=DARK)

    # Right col: CM / MEX A
    rx = ix0 + half + 3
    page.insert_text(fitz.Point(rx, ay(143) + fs_lbl),
                     "CM", fontname=FR, fontsize=fs_lbl, color=GREY)
    page.insert_text(fitz.Point(rx + 14, ay(143) + fs_val),
                     cur_cm, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(rx, ay(143) + fs_val + fs_lbl + 3),
                     "MEX", fontname=FR, fontsize=fs_lbl, color=GREY)
    page.insert_text(fitz.Point(rx + 14, ay(143) + fs_val * 2 + 3),
                     f"{cur_mex}  A", fontname=FB, fontsize=fs_val, color=DARK)

    # ── 3b. SIZE GRID ─────────────────────────────────────────────────────────
    fs_grid  = 6.0
    grid_y   = ay(167)         # baseline of size text
    col_step = INNER_W / len(TOK100_SIZES)

    for ci, sz in enumerate(TOK100_SIZES):
        sx  = ix0 + ci * col_step
        is_cur = (sz == cur_yrs)
        if is_cur:
            # BLACK highlight box
            page.draw_rect(
                fitz.Rect(sx, grid_y - fs_grid - 1, sx + col_step, grid_y + 2),
                color=None, fill=BLACK, width=0,
            )
            txt_color = WHITE
            fnt = FB
        else:
            txt_color = DARK
            fnt = FR
        tw = fitz.get_text_length(sz, fontname=fnt, fontsize=fs_grid)
        page.insert_text(
            fitz.Point(sx + (col_step - tw) / 2, grid_y),
            sz, fontname=fnt, fontsize=fs_grid, color=txt_color,
        )

    # ── 3c. THREE-COLUMN SECTION ──────────────────────────────────────────────
    # Zone B: y_rel 183–257; three equal columns
    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department",     "") or "")
    sku      = str(item_data.get("sku_code",        "") or "")
    style    = str(item_data.get("style_code",      "") or "")
    cref     = str(item_data.get("commercial_ref",  "") or "")
    bc_str   = str(item_data.get("barcode_number",  "") or "")
    qty      = item_data.get("quantity", 0)

    c3w = INNER_W / 3.0   # column width ≈ 42.4 pt

    # Vertical dividers
    div_y0 = ay(183)
    div_y1 = ay(257)
    page.draw_line(fitz.Point(ix0 + c3w,     div_y0),
                   fitz.Point(ix0 + c3w,     div_y1), color=LGREY, width=0.3)
    page.draw_line(fitz.Point(ix0 + 2*c3w,   div_y0),
                   fitz.Point(ix0 + 2*c3w,   div_y1), color=LGREY, width=0.3)

    # ── Left column: sub-dept / dept / SKU codes ──────────────────────────────
    fs_c = 5.5
    ref_txt = f"{sub_dept}  {dept}  {sku}"
    page.insert_text(
        fitz.Point(_cx(ref_txt, FR, fs_c, ix0, c3w), ay(192) + fs_c),
        ref_txt, fontname=FR, fontsize=fs_c, color=DARK,
    )

    # ── Middle column: barcode graphic + text + style + commercial ref ─────────
    mc_x0 = ix0 + c3w + 2
    mc_w  = c3w - 4
    _draw_barcode(page, mc_x0, ay(194), mc_w, 20.0, bc_str)
    for txt, y_off in [(style, 35), (cref, 46)]:
        if txt:
            page.insert_text(
                fitz.Point(_cx(txt, FR, fs_c, mc_x0, mc_w), ay(194) + y_off),
                txt, fontname=FR, fontsize=fs_c, color=GREY,
            )

    # ── Right column: OVS address (static) ────────────────────────────────────
    rc_x0  = ix0 + 2 * c3w + 2
    rc_fs  = 4.0
    ovs_lines = ["OVS SpA", "Via Terraglio 17", "30174 Venezia IT"]
    rc_y   = ay(200)
    for line in ovs_lines:
        page.insert_text(fitz.Point(rc_x0, rc_y + rc_fs), line,
                         fontname=FR, fontsize=rc_fs, color=LGREY)
        rc_y += rc_fs + 2

    # ── 3d. GREEN PRICE SEPARATOR ─────────────────────────────────────────────
    # Solid thin green line at measured position
    page.draw_rect(
        fitz.Rect(ax(SEP_X0), ay(SEP_Y), ax(SEP_X1), ay(SEP_Y) + SEP_H),
        color=None, fill=GREEN, width=0,
    )

    # ── 3e. PRICE ─────────────────────────────────────────────────────────────
    currency  = _fix_currency(item_data.get("currency_symbol", ""))
    price_raw = str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_raw)

    fs_sym   = 10.0
    fs_major = 24.0
    fs_minor = 13.0

    sym_w  = fitz.get_text_length(currency, fontname=FR, fontsize=fs_sym) + 2
    maj_w  = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w  = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)
    total  = sym_w + maj_w + min_w
    px     = icx - total / 2

    price_y = ay(SEP_Y + 24)
    page.insert_text(fitz.Point(px,           price_y - fs_major * 0.40),
                     currency, fontname=FR, fontsize=fs_sym, color=DARK)
    page.insert_text(fitz.Point(px + sym_w,   price_y),
                     major,    fontname=FB, fontsize=fs_major, color=DARK)
    page.insert_text(fitz.Point(px + sym_w + maj_w + 1, price_y - fs_major * 0.35),
                     minor,    fontname=FR, fontsize=fs_minor, color=DARK)

    # ── 4. Qty label — below the outer panel ──────────────────────────────────
    qty_txt = f"Qty - {qty}"
    fs_qty  = 10.0
    page.insert_text(
        fitz.Point(_cx(qty_txt, FB, fs_qty, ox, OUTER_W),
                   oy + OUTER_H + fs_qty + 3),
        qty_txt, fontname=FB, fontsize=fs_qty, color=DARK,
    )


# ── Public API ────────────────────────────────────────────────────────────────

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
    pdf_bytes = build_label_pdf(item_data)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = doc[0].get_pixmap(matrix=mat, alpha=False)
    doc.close()
    return pix.tobytes("png")


def build_label_thumbnail(item_data: dict, dpi: int = 60) -> bytes:
    return build_label_png(item_data, dpi=dpi)
