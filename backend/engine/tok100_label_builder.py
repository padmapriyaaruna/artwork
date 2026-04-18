"""
TOK100 Label Builder v3 — pixel-precise match of TOK100_B0854559_1.pdf reference.

Reference panel measurements (from actual PDF at 400 DPI):
  Outer panel : 150.3 × 305.5 pt = 53.0 × 107.8 mm
  Inner label  : 127.2 × 283.9 pt ≈ 45mm × 100mm
  Label spacing: 169.6 pt (centre-to-centre between K I D S positions)

Exact layout zones (relative to inner panel top, in pts):
  ┌─────────────────────────────────────────────┐  ← y=0
  │  FSC logo │ Hole │ QR code  │               │  ← y=0-60
  │           │      │ + recycle text            │
  ├─────────────────────────────────────────────┤  ← y=60  separator line
  │                K I D S                       │  ← y=63
  ├─────────────────────────────────────────────┤  ← y=68  separator line
  │              (blank space)                   │  ← y=68-140
  │  YEARS 4-5 │         CM 110                 │  ← y=140 (size highlight row)
  │  IT    4-5 │        MEX 4-5 A               │  ← y=151
  ├─────────────────────────────────────────────┤
  │  [4-5] 5-6  6-7  7-8  8-9  9-10            │  ← y=165 (full grid, [] = black bg)
  │  3632  230  2768957                          │  ← y=185 (dept | colour | SKU)
  ├───────────┬────────────────┬─────────────────┤  ← y=195
  │ Triman/  │ ████████████  │ MADE IN         │
  │ Recycle  │ 8 051553 2987│ INDIA           │  ← y=195-260 (3-column)
  │  logos   │ 2768957       │ OVS address     │
  │          │ PR711 AI08    │                 │
  ├─────────────────────────────────────────────┤  ← y=260 separator
  │              € 29,95                         │  ← y=260-305
  └─────────────────────────────────────────────┘  ← y=305
  Qty - 128   (below label)
"""
import io, re, math
import fitz  # PyMuPDF

try:
    import qrcode
    from PIL import Image as PILImage
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


# ── Exact reference panel dimensions ─────────────────────────────────────────
# We work at 1:1 scale of the reference (1pt = 1pt)
# Then render to PNG at chosen DPI for screen/approval

OUTER_W = 150.3          # full panel width including border
OUTER_H = 305.5          # full panel height including border
INNER_X = 11.0           # inner content starts from left of outer
INNER_Y = 10.0           # inner content starts from top of outer
INNER_W = OUTER_W - 2 * INNER_X     # ≈ 128 pt = ~45mm
INNER_H = OUTER_H - 2 * INNER_Y     # ≈ 285 pt = ~100mm

# ── Colours ───────────────────────────────────────────────────────────────────
NAVY   = (0.000, 0.141, 0.235)   # exact from reference fill
GOLD   = (0.922, 0.714, 0.180)
MAGENTA= (0.878, 0.129, 0.392)
WHITE  = (1.0, 1.0, 1.0)
BLACK  = (0.0, 0.0, 0.0)
DARK   = (0.08, 0.08, 0.08)
GREY   = (0.45, 0.45, 0.45)
LGREY  = (0.75, 0.75, 0.75)
DGREEN = (0.0,  0.45, 0.15)
BORDER = (0.2,  0.2,  0.2)

# PyMuPDF Base-14 fonts
FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

# TOK100 size range
TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]


# ── Reference zone Y positions (relative to INNER content top) ───────────────
Z_LOGO_TOP   = 0.0      # logo / QR / hole zone start
Z_LOGO_BOT   = 57.0     # logo / QR / hole zone end
Z_SEP1       = 57.0     # first K I D S separator
Z_KIDS       = 64.0     # K I D S text baseline
Z_SEP2       = 67.0     # second K I D S separator
Z_SIZE_TOP   = 135.0    # size detail rows start
Z_GRID_TOP   = 157.0    # all-sizes grid start
Z_GRID_BOT   = 180.0    # all-sizes grid end
Z_REFS_TOP   = 182.0    # dept / SKU row
Z_3COL_TOP   = 192.0    # 3-column section start
Z_3COL_BOT   = 257.0    # 3-column section end (price separator)
Z_PRICE_TOP  = 260.0    # price area start
Z_BOTTOM     = INNER_H  # inner bottom


# ── Helper: centred X ─────────────────────────────────────────────────────────
def _cx(text, font, fs, area_x0, area_w):
    tw = fitz.get_text_length(text, fontname=font, fontsize=fs)
    return area_x0 + (area_w - tw) / 2


def _fix_currency(raw):
    if not raw:
        return "\u20ac"
    clean = "".join(c for c in raw if 0x20 <= ord(c) < 0x80)
    if not clean or len(clean) < 1 or clean[0] in "?â":
        return "\u20ac"
    return clean[:2]


def _split_price(price_str):
    p = (price_str or "0,00").strip()
    m = re.match(r"^(\d+)([,.]?\d*)$", p)
    if m:
        return m.group(1), m.group(2)
    return p, ""


def _split_barcode(bc):
    bc = (bc or "").strip()
    if len(bc) >= 13:
        return bc[0], bc[1:7], bc[7:13]
    elif len(bc) >= 7:
        return bc[0], bc[1:7], bc[7:]
    return bc, "", ""


# ── QR Code generator ─────────────────────────────────────────────────────────
def _make_qr_png(data: str, size_pt: float, dpi: int) -> bytes | None:
    """Generate QR code as PNG bytes at the correct target size."""
    if not HAS_QRCODE:
        return None
    px = int(size_pt * dpi / 72)
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=max(2, px // 25),
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((px, px), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


# ── FSC logo (simplified geometric representation) ───────────────────────────
def _draw_fsc(page, x0, y0, w, h):
    """Draw a simplified FSC "MIX Board" logo placeholder."""
    # Green border box
    page.draw_rect(fitz.Rect(x0, y0, x0 + w, y0 + h),
                   color=DGREEN, width=0.5)
    # Circle (FSC tree symbol placeholder)
    cx, cy = x0 + w/2, y0 + h*0.38
    page.draw_circle(fitz.Point(cx, cy), w*0.22,
                     color=DGREEN, fill=DGREEN, width=0)
    # "FSC" text
    fs_fsc = max(3.5, w * 0.22)
    tw = fitz.get_text_length("FSC", fontname=FB, fontsize=fs_fsc)
    page.insert_text(fitz.Point(cx - tw/2, y0 + h*0.70 + fs_fsc),
                     "FSC", fontname=FB, fontsize=fs_fsc, color=DGREEN)
    # "MIX Board" text
    fs_mix = max(2.5, w * 0.14)
    tw2 = fitz.get_text_length("MIX Board", fontname=FR, fontsize=fs_mix)
    page.insert_text(fitz.Point(cx - tw2/2, y0 + h*0.88 + fs_mix),
                     "MIX Board", fontname=FR, fontsize=fs_mix, color=DGREEN)


# ── Triman recycling logo (simplified) ───────────────────────────────────────
def _draw_triman(page, x0, y0, w, h):
    """Draw a simplified Triman/recycling logo (triangle of arrows)."""
    cx, cy = x0 + w/2, y0 + h/2
    r = min(w, h) * 0.38
    # Draw 3 arrowhead triangles in a circle formation
    for i in range(3):
        angle = math.radians(90 + i * 120)
        ax = cx + r * math.cos(angle)
        ay = cy + r * math.sin(angle)
        bx = cx + r * math.cos(angle + math.radians(90))
        by = cy + r * math.sin(angle + math.radians(90))
        page.draw_line(fitz.Point(ax, ay), fitz.Point(bx, by),
                       color=DARK, width=1.0)
    # Center label
    fs_t = max(3.0, w * 0.18)
    tw = fitz.get_text_length("01", fontname=FB, fontsize=fs_t)
    page.insert_text(fitz.Point(cx - tw/2, cy + fs_t/2),
                     "01", fontname=FB, fontsize=fs_t, color=DARK)


# ── Barcode graphic ────────────────────────────────────────────────────────────
def _draw_barcode(page, x0, y0, w, h, barcode_str):
    """Draw EAN-13 barcode vertical lines."""
    n = max(len(barcode_str), 13)
    bar_unit = w / (n * 1.8)
    for i, d in enumerate(barcode_str):
        lx = x0 + i * bar_unit * 1.8
        lw = bar_unit * (1.6 if int(d) % 3 == 0 else 0.8)
        if lx < x0 + w:
            page.draw_line(fitz.Point(lx, y0),
                           fitz.Point(lx, y0 + h),
                           color=BLACK, width=lw)


# ── Main back panel renderer ──────────────────────────────────────────────────
def _draw_back_panel(page, ox, oy, item_data, render_dpi=150):
    """
    Draw complete back panel at (ox, oy) = top-left of outer panel rect.
    ox, oy are absolute page coordinates.
    """
    # ── Outer border ────────────────────────────────────────────────────────
    page.draw_rect(fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H),
                   color=BORDER, fill=WHITE, width=0.5)

    # Helper: convert zone-Y to absolute page Y
    iX = ox + INNER_X       # inner content left edge (abs)
    iY = oy + INNER_Y       # inner content top edge (abs)
    cX = iX + INNER_W / 2   # inner centre X
    iW = INNER_W

    def ay(zone_y): return iY + zone_y

    # ── Section 1: LOGO / HOLE / QR ─────────────────────────────────────────
    logo_h  = Z_LOGO_BOT - Z_LOGO_TOP   # ~57 pt
    col_w   = iW / 3.0

    # Left: FSC logo
    _draw_fsc(page, iX, ay(Z_LOGO_TOP), col_w - 2, logo_h - 4)

    # Centre: Punch hole
    hole_cx = iX + iW / 2
    hole_cy = ay(Z_LOGO_TOP + logo_h / 2)
    page.draw_circle(fitz.Point(hole_cx, hole_cy), 4.5,
                     color=LGREY, fill=WHITE, width=0.7)

    # Right: QR code
    qr_x0  = iX + col_w * 2 + 2
    qr_y0  = ay(Z_LOGO_TOP + 6)
    qr_size= col_w - 4   # square QR
    barcode = str(item_data.get("barcode_number", "") or "0000000000000")

    qr_png = _make_qr_png(barcode, qr_size, render_dpi)
    if qr_png:
        page.insert_image(
            fitz.Rect(qr_x0, qr_y0, qr_x0 + qr_size, qr_y0 + qr_size - 6),
            stream=qr_png, keep_proportion=True
        )
    else:
        # Fallback: placeholder grid
        page.draw_rect(fitz.Rect(qr_x0, qr_y0, qr_x0 + qr_size, qr_y0 + qr_size - 6),
                       color=DARK, width=0.5)
        qr_fs = 4.5
        page.insert_text(fitz.Point(qr_x0 + 2, qr_y0 + qr_size / 2),
                         "QR", fontname=FB, fontsize=qr_fs, color=DARK)

    # Recycling text flanking the QR (very small)
    recycle_fs = 3.5
    page.insert_text(fitz.Point(qr_x0, ay(Z_LOGO_TOP + 1)),
                     "SEPARATE THE WASTE",
                     fontname=FR, fontsize=recycle_fs, color=GREY)
    page.insert_text(fitz.Point(qr_x0, ay(Z_LOGO_BOT - 5)),
                     "DIFFERENZIA I RIFIUTI",
                     fontname=FR, fontsize=recycle_fs, color=GREY)

    # ── Section 2: Separator lines + K I D S ────────────────────────────────
    page.draw_line(fitz.Point(iX, ay(Z_SEP1)),
                   fitz.Point(iX + iW, ay(Z_SEP1)),
                   color=DARK, width=1.0)

    kids_fs = 8.5
    page.insert_text(
        fitz.Point(_cx("K I D S", FB, kids_fs, iX, iW), ay(Z_KIDS)),
        "K I D S", fontname=FB, fontsize=kids_fs, color=DARK
    )

    page.draw_line(fitz.Point(iX, ay(Z_SEP2 + kids_fs * 0.3)),
                   fitz.Point(iX + iW, ay(Z_SEP2 + kids_fs * 0.3)),
                   color=DARK, width=1.0)

    # ── Section 3: SIZE DETAILS ROW ─────────────────────────────────────────
    sizes    = item_data.get("sizes") or {}
    cur_yrs  = sizes.get("YEARS", "")
    cur_cm   = sizes.get("CM", "")
    cur_it   = sizes.get("IT", "")
    cur_mex  = re.sub(r"\s*A$", "", sizes.get("MEX", cur_it) or "").strip()

    fs_lbl = 5.5    # label font size
    fs_val = 8.5    # value font size

    half = iW / 2

    # Left col: YEARS / IT
    lx = iX + 2
    page.insert_text(fitz.Point(lx, ay(Z_SIZE_TOP + fs_lbl)),
                     "YEARS", fontname=FR, fontsize=fs_lbl, color=GREY)
    page.insert_text(fitz.Point(lx + 18, ay(Z_SIZE_TOP + fs_val)),
                     cur_yrs, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(lx, ay(Z_SIZE_TOP + fs_val + fs_lbl + 1)),
                     "IT", fontname=FR, fontsize=fs_lbl, color=GREY)
    page.insert_text(fitz.Point(lx + 18, ay(Z_SIZE_TOP + fs_val * 2 + 1)),
                     cur_it, fontname=FB, fontsize=fs_val, color=DARK)

    # Right col: CM / MEX A
    rx = iX + half + 2
    page.insert_text(fitz.Point(rx, ay(Z_SIZE_TOP + fs_lbl)),
                     "CM", fontname=FR, fontsize=fs_lbl, color=GREY)
    page.insert_text(fitz.Point(rx + 14, ay(Z_SIZE_TOP + fs_val)),
                     cur_cm, fontname=FB, fontsize=fs_val, color=DARK)
    page.insert_text(fitz.Point(rx, ay(Z_SIZE_TOP + fs_val + fs_lbl + 1)),
                     "MEX", fontname=FR, fontsize=fs_lbl, color=GREY)
    mex_str = f"{cur_mex}  A"
    page.insert_text(fitz.Point(rx + 14, ay(Z_SIZE_TOP + fs_val * 2 + 1)),
                     mex_str, fontname=FB, fontsize=fs_val, color=DARK)

    # ── Section 4: SIZE RANGE GRID ──────────────────────────────────────────
    fs_grid = 6.5
    grid_y  = ay(Z_GRID_TOP)
    col_step = iW / len(TOK100_SIZES)
    for ci, sz in enumerate(TOK100_SIZES):
        sx = iX + ci * col_step
        is_cur = (sz == cur_yrs)
        if is_cur:
            # Black background highlight
            hi_x0 = sx - 0.5
            hi_x1 = sx + col_step - 0.5
            page.draw_rect(fitz.Rect(hi_x0, grid_y - fs_grid,
                                     hi_x1, grid_y + 2.5),
                           color=BLACK, fill=BLACK, width=0)
            txt_color = WHITE
        else:
            txt_color = DARK
        tw = fitz.get_text_length(sz, fontname=FB if is_cur else FR,
                                  fontsize=fs_grid)
        page.insert_text(
            fitz.Point(sx + (col_step - tw) / 2, grid_y),
            sz,
            fontname=FB if is_cur else FR,
            fontsize=fs_grid,
            color=txt_color
        )

    # ── Section 5: DEPT / COLOUR / SKU ROW ──────────────────────────────────
    sub_dept = str(item_data.get("sub_department", "") or "")
    dept     = str(item_data.get("department", "") or "")
    sku      = str(item_data.get("sku_code", "") or "")
    fs_ref   = 6.5
    ref_txt  = f"{sub_dept}   {dept}   {sku}"
    page.insert_text(
        fitz.Point(_cx(ref_txt, FR, fs_ref, iX, iW), ay(Z_REFS_TOP + fs_ref)),
        ref_txt, fontname=FR, fontsize=fs_ref, color=DARK
    )

    # ── Section 6: THREE-COLUMN ROW ──────────────────────────────────────────
    c3_y0 = ay(Z_3COL_TOP)
    c3_y1 = ay(Z_3COL_BOT)
    c3_h  = c3_y1 - c3_y0
    c3_w  = iW / 3.0

    # Vertical dividers
    page.draw_line(fitz.Point(iX + c3_w,     c3_y0),
                   fitz.Point(iX + c3_w,     c3_y1), color=LGREY, width=0.3)
    page.draw_line(fitz.Point(iX + 2 * c3_w, c3_y0),
                   fitz.Point(iX + 2 * c3_w, c3_y1), color=LGREY, width=0.3)

    # Left: Triman recycling logo
    tri_pad = 3.0
    _draw_triman(page,
                 iX + tri_pad, c3_y0 + tri_pad,
                 c3_w - 2 * tri_pad, c3_h - 2 * tri_pad)

    # Middle: barcode + refs
    bx0    = iX + c3_w + 2
    bx1    = iX + 2 * c3_w - 2
    bw     = bx1 - bx0
    bc_str = str(item_data.get("barcode_number", "") or "")
    p1, p2, p3 = _split_barcode(bc_str)

    bc_bar_h = 14.0
    bc_y0    = c3_y0 + 2
    _draw_barcode(page, bx0, bc_y0, bw, bc_bar_h, bc_str)

    fs_bc    = 6.0
    bc_txt   = f"{p1}  {p2}  {p3}"
    page.insert_text(
        fitz.Point(_cx(bc_txt, FR, fs_bc, bx0, bw), bc_y0 + bc_bar_h + fs_bc),
        bc_txt, fontname=FR, fontsize=fs_bc, color=DARK
    )

    style = str(item_data.get("style_code", "") or "")
    cref  = str(item_data.get("commercial_ref", "") or "")
    cur_y = bc_y0 + bc_bar_h + fs_bc + 4
    for txt in [style, cref]:
        if txt:
            page.insert_text(
                fitz.Point(_cx(txt, FR, fs_bc, bx0, bw), cur_y + fs_bc),
                txt, fontname=FR, fontsize=fs_bc, color=GREY
            )
            cur_y += fs_bc + 2.5

    # Right: MADE IN + address
    rx0 = iX + 2 * c3_w + 2
    country_raw = str(item_data.get("country_of_origin", "") or "")
    country     = re.sub(r"^MADE\s+IN\s+", "", country_raw.upper()).strip()
    cty_fs      = 6.5

    if country:
        made_y = c3_y0 + cty_fs * 2 + 4
        page.insert_text(fitz.Point(rx0, made_y),
                         "MADE IN", fontname=FR, fontsize=5.5, color=GREY)
        page.insert_text(fitz.Point(rx0, made_y + cty_fs + 2),
                         country, fontname=FB, fontsize=cty_fs, color=DARK)

    # OVS address (tiny)
    addr_fs = 4.0
    ovs_addr= "OVS SpA"
    ovs_via = "Via Terraglio 17"
    ovs_loc = "30174 Venezia IT"
    addr_y  = c3_y1 - addr_fs * 5
    for aline in [ovs_addr, ovs_via, ovs_loc]:
        page.insert_text(fitz.Point(rx0, addr_y + addr_fs),
                         aline, fontname=FR, fontsize=addr_fs, color=LGREY)
        addr_y += addr_fs + 1.5

    # ── Section 7: PRICE ─────────────────────────────────────────────────────
    # Separator line
    page.draw_line(fitz.Point(iX, ay(Z_PRICE_TOP)),
                   fitz.Point(iX + iW, ay(Z_PRICE_TOP)),
                   color=DGREEN, width=0.7)

    currency = _fix_currency(item_data.get("currency_symbol", ""))
    price_str = str(item_data.get("selling_price", "0,00") or "0,00")
    major, minor = _split_price(price_str)

    fs_sym   = 10.0
    fs_major = 26.0
    fs_minor = 14.0

    sym_w  = fitz.get_text_length(currency, fontname=FR, fontsize=fs_sym) + 3
    maj_w  = fitz.get_text_length(major,    fontname=FB, fontsize=fs_major)
    min_w  = fitz.get_text_length(minor,    fontname=FR, fontsize=fs_minor)
    total  = sym_w + maj_w + min_w
    px     = cX - total / 2

    price_y = ay(Z_PRICE_TOP + 26)
    page.insert_text(fitz.Point(px, price_y - fs_major * 0.45),
                     currency, fontname=FR, fontsize=fs_sym, color=DARK)
    page.insert_text(fitz.Point(px + sym_w, price_y),
                     major, fontname=FB, fontsize=fs_major, color=DARK)
    page.insert_text(fitz.Point(px + sym_w + maj_w + 1, price_y - fs_major * 0.35),
                     minor, fontname=FR, fontsize=fs_minor, color=DARK)

    # ── Qty below panel ──────────────────────────────────────────────────────
    qty     = item_data.get("quantity", 0)
    qty_txt = f"Qty - {qty}"
    fs_qty  = 10.0
    page.insert_text(
        fitz.Point(_cx(qty_txt, FB, fs_qty, ox, OUTER_W), oy + OUTER_H + fs_qty + 3),
        qty_txt, fontname=FB, fontsize=fs_qty, color=DARK
    )


# ── Front panel ───────────────────────────────────────────────────────────────
def _draw_front_panel(page, ox, oy):
    """Navy blue front hang-tag — same geometry as back panel outer bounds."""
    cx = ox + OUTER_W / 2

    # Outer white border rect
    page.draw_rect(fitz.Rect(ox, oy, ox + OUTER_W, oy + OUTER_H),
                   color=BORDER, fill=WHITE, width=0.5)

    # Inner navy area
    nx0 = ox + INNER_X
    ny0 = oy + INNER_Y
    nw  = INNER_W
    nh  = INNER_H
    page.draw_rect(fitz.Rect(nx0, ny0, nx0 + nw, ny0 + nh),
                   color=NAVY, fill=NAVY, width=0)

    ncx = nx0 + nw / 2

    # Punch hole
    page.draw_circle(fitz.Point(ncx, ny0 + 14), 5.0,
                     color=WHITE, fill=WHITE, width=0)

    # Magenta accent strip (top)
    page.draw_line(fitz.Point(nx0, ny0 + 26),
                   fitz.Point(nx0 + nw, ny0 + 26),
                   color=MAGENTA, width=2.5)

    # "OVS" (bold gold, large centred)
    fs_ovs = 30.0
    ovs_y  = ny0 + nh * 0.50
    page.insert_text(
        fitz.Point(_cx("OVS", FB, fs_ovs, nx0, nw), ovs_y),
        "OVS", fontname=FB, fontsize=fs_ovs, color=GOLD
    )

    # "kids" (gold, smaller)
    fs_kids = 12.0
    page.insert_text(
        fitz.Point(_cx("kids", FR, fs_kids, nx0, nw), ovs_y + 14),
        "kids", fontname=FR, fontsize=fs_kids, color=GOLD
    )

    # Magenta accent strip (bottom)
    page.draw_line(fitz.Point(nx0, ny0 + nh - 12),
                   fitz.Point(nx0 + nw, ny0 + nh - 12),
                   color=MAGENTA, width=2.5)


# ── Public API ────────────────────────────────────────────────────────────────

def build_label_pdf(item_data: dict) -> bytes:
    """
    Single-item label PDF (front + back side by side).
    Page size: (OUTER_W * 2 + 10) x (OUTER_H + 20) pt.
    """
    pw = OUTER_W * 2 + 10
    ph = OUTER_H + 25
    doc  = fitz.open()
    page = doc.new_page(width=pw, height=ph)
    page.draw_rect(fitz.Rect(0, 0, pw, ph), color=WHITE, fill=WHITE, width=0)

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
