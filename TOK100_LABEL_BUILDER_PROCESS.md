# OVS TOK100 Artwork Label Builder — Complete Development Process

> **Project:** OVS x Cotton Blossom — Automated Kids Clothing Label Generation  
> **Repository:** `https://github.com/padmapriyaaruna/artwork`  
> **Engine file:** `backend/engine/tok100_label_builder.py`  
> **Current stable version:** `v14` · Git commit `0e8e4f8` · Tag `v1.0` @ `402043c`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Reference Files](#3-reference-files)
4. [Panel Geometry & Coordinate System](#4-panel-geometry--coordinate-system)
5. [White-Overwrite Zone Strategy](#5-white-overwrite-zone-strategy)
6. [Version-by-Version Changelog](#6-version-by-version-changelog)
7. [Final Layout Specification (v14)](#7-final-layout-specification-v14)
8. [Key Technical Measurements](#8-key-technical-measurements)
9. [Currency & Price Logic](#9-currency--price-logic)
10. [EAN-13 Barcode Generation](#10-ean-13-barcode-generation)
11. [Git History & Tags](#11-git-history--tags)
12. [How to Run & Test](#12-how-to-run--test)
13. [Known Remaining Items](#13-known-remaining-items)
14. [Engine Code Structure](#14-engine-code-structure)

---

## 1. Project Overview

The OVS Artwork Engine is a web application that **automatically generates clothing label PDFs** for OVS Kids garments. Instead of manually creating each label, artwork coordinators upload an XML data file and the system generates a pixel-perfect approval PDF matching the OVS master design template.

**Label type handled:** `TOK100` — OVS Kids hang tag  
**Physical size:** 45 mm × 100 mm  
**PDF size:** 150.3 × 305.5 pt

**What the back label contains:**
- FSC certification logo (static)
- Hole circle indicator (top centre)
- QR code + "DIFFERENZIA I RIFIUTI / SEPARATE THE WASTE" (static)
- **KIDS** heading with top/bottom separator lines
- Multilingual size table: YEARS / CM / IT / MEX
- Size chart selection grid (2 rows × 3 columns, active size highlighted)
- Triman recycling logos (static, left column)
- EAN-13 barcode + department/SKU codes + style/commercial ref
- Vertical address text: MADE IN INDIA / OVS address
- Green dashed tear-off separator
- Price: currency symbol + main integer + superscript cents

---

## 2. System Architecture

```
Art_Work/
├── backend/
│   ├── engine/
│   │   └── tok100_label_builder.py      ← CORE ENGINE
│   ├── templates/
│   │   └── OVS/TOK100/
│   │       ├── front_panel_ref.pdf      ← static front panel
│   │       └── back_panel_ref.pdf       ← static back panel (logos, KIDS, QR)
│   ├── services/
│   │   └── approval_pdf_service.py      ← calls engine per size variant
│   └── routers/
│       └── approval.py                  ← FastAPI endpoints
├── frontend/
│   └── src/pages/
│       ├── ApprovalPreview.jsx          ← server-rendered PNG viewer
│       └── ApprovalPortal.jsx           ← management interface
├── test_v10.py                          ← test: generates all 6 size labels
├── analyse_all.py                       ← deep PDF coordinate extractor
├── precision_analysis.py                ← actual vs generated comparison
└── check_positions.py                   ← chip & barcode position verifier
```

**Technology stack:**
| Component | Technology |
|-----------|-----------|
| PDF manipulation | PyMuPDF (`fitz`) |
| Barcode image generation | Pillow (`PIL`) |
| Backend API | FastAPI + Python 3.11 |
| Frontend | React + Vite |
| Database | PostgreSQL (asyncpg) |
| Hosting | Render.com |

---

## 3. Reference Files

| File | Role |
|------|------|
| `_OVS KIDS 2023.pdf` | Master design template (57 pages, one per style) |
| `TOK100_B0854559_1.pdf` | **Ground truth** — actual approved label output |
| `approval_sheet_B0854559 (12).pdf` | Latest generated output for comparison |
| `back_panel_ref.pdf` | Single-page static back panel template |
| `front_panel_ref.pdf` | Single-page static front panel template |

> **IMPORTANT:** `TOK100_B0854559_1.pdf` is the **single source of truth** for all
> coordinate measurements. All Y positions, font sizes, chip positions, and barcode
> locations were extracted programmatically from this file using PyMuPDF — not estimated visually.

**Actual PDF metadata:**
- Page size: `2004.1 × 1417.3 pt`
- Back panel 1 (size 4-5): `ox ≈ 581.85, oy ≈ 373.25`
- Inner content box: `ix0 = 593.35, ix1 = 720.55` (INNER_W = 127.2 pt)

---

## 4. Panel Geometry & Coordinate System

All measurements are in **PDF points (pt)** — 1 pt = 1/72 inch.

```python
OUTER_W = 150.3     # Full panel width
OUTER_H = 305.5     # Full panel height
INNER_X = 11.5      # Left inset to inner border
INNER_Y = 10.8      # Top inset to inner border
INNER_W = 127.2     # Inner content area width
INNER_H = 283.9     # Inner content area height
_C3     = 42.4      # One column width (INNER_W / 3)

# Derived positions (per panel instance)
# ix0 = ox + INNER_X        left edge of content area
# ix1 = ix0 + INNER_W       right edge of content area
# vert_x = ix0 + 63.6       vertical table divider
```

**Y coordinate convention:**
- Y values in code are **panel-relative** (distance from panel top edge)
- Helper `ay = lambda r: oy + r` converts panel-relative → absolute page Y
- PDF/fitz: Y increases **downward**

**Column structure (barcode zone, y = 188–258):**
```
ix0 ──────── _C3 ──────── _C3 ──────── _C3 ─── ix1
│  Left col  │  Middle col │  Right col  │
│  Logos     │  Barcode    │  Address    │
│  (static)  │  (variable) │  (variable) │
```

---

## 5. White-Overwrite Zone Strategy

The `back_panel_ref.pdf` template contains **static artwork** (logos, KIDS text, QR code) plus **placeholder variable data** (template barcode, placeholder price etc.).

**Strategy:** Embed the full template → white-overwrite variable zones → draw all actual variable data on top.

### Final Zone Structure (v14)

```python
ZONES = [
    # Zone A: Full-width — YEARS table + size chart area
    (INNER_X,              120.0,  INNER_X + INNER_W,    188.0),

    # Zone B2: Middle column barcode zone
    # Extended 15pt LEFT beyond mc_x0 to erase the template's own
    # EAN-13 guard digit that bleeds at the left/middle column seam
    (INNER_X + _C3 - 15,   188.0,  INNER_X + 2*_C3,      258.0),

    # Zone B3: Right column — address vertical text zone
    (INNER_X + 2*_C3,      188.0,  INNER_X + INNER_W,    258.0),

    # Zone C: Price section
    (INNER_X,              256.0,  INNER_X + INNER_W,    OUTER_H),
]
```

**Why the left column is NOT erased:**  
The Triman recycling logos (recycling person, FR label, price-tag icon, recycle bin) exist in the left column as **static template artwork**. They must show through unchanged. Only the 15pt extension of Zone B2 clips a narrow strip at the column boundary to clean up the template's own barcode bleed.

---

## 6. Version-by-Version Changelog

### Initial Versions (v1–v5): Foundation

**v1–v3 (commits `9891561`–`41b2257`):**
- Basic PyMuPDF PDF generation with hand-coded approximate layout
- Hard-coded coordinates based on visual estimates
- Basic Helvetica text for all fields
- No template embedding — entire label drawn from scratch

**v4 (commit `4e07f47`):**
- Introduced `page.show_pdf_page()` to embed `back_panel_ref.pdf` static template
- White-overwrite zones first introduced as concept
- Customer/template multi-label architecture established
- `approval_pdf_service.py` calling engine per size variant

**v5 (embedded in v4 work):**
- All 6 size variants (4-5, 5-6, 6-7, 7-8, 8-9, 9-10) generated in one approval sheet
- Labels placed in a 3-column × 2-row grid per page

---

### v6 (commit `08b5a11`): Pixel-Fidelity Overhaul

- Thorough visual comparison against `_OVS KIDS 2023.pdf` master
- Font standardisation to `hebo` (Helvetica-Bold) and `helv` (Helvetica)
- Improved zone boundary estimates
- MAGENTA colour `(0.898, 0.023, 0.584)` matched from master

---

### v7 (commit `f076f05`): EAN-13 + Green Separator

- Implemented proper **EAN-13 bit pattern encoding** from scratch
  - L-code, G-code, R-code lookup tables
  - Parity table driven by first digit
  - 95-bit output: `101 + 6L/G + 01010 + 6R + 101`
- Dashed green separator line at `SEP_Y = 257.49`
- Full Triman icon reference added

---

### v8 (commit `5ca55fd`): Acrobat Compatibility

- Fixed PDF error visible when opening in Adobe Acrobat (`garbage=4, deflate=True`)
- Barcode right-alignment corrected
- Tighter active size chip highlight
- Price styling: bold integer, lighter cents

---

### v9 (commit `e17bd6d`): PNG Barcode + Compact Chips

- **Switched from font-based to Pillow PNG EAN-13 barcode** generation
  - Renders at 400 DPI for crisp bars
  - `insert_image()` places PNG into PDF at precise coordinates
- Size chips switched from plain text to compact boxes
- Cap-height-aligned price (EUR symbol raised)

---

### v10 (commit `126c0bb`): Barcode Height + 2×3 Grid

- Increased `BAR_H` for better visual weight matching master
- **Restored 2×3 size chart grid** (was incorrectly rendered as 1×6 elongated list)
- Currency symbol sizing improved
- Cell padding and right-align logic for YEARS/IT values added

---

### v11 (commit `dda4c01`): Pixel-Precise from Reference Image

- First attempt to match exact coordinates from visual measurement of `Actual.jpg`
- YEARS/CM table fully enclosed with top + bottom borders
- Size chip active highlight no longer overlapping table border
- EUR symbol matched to same bold weight as price integer

---

### v12 (commit `6d0c96f`): Scientific Coordinate Extraction ⭐ Major Milestone

All coordinates **programmatically extracted** from `TOK100_B0854559_1.pdf` using PyMuPDF text extraction — zero guesswork.

**5 major issues fixed simultaneously:**

| Issue | Root Cause | Fix Applied |
|-------|-----------|-------------|
| Table borders touching magenta border | Lines overshot `ix1` | Borders now span `ix0 → ix1` exactly (127.2pt), same as KIDS separator lines |
| Size chip elongated + misaligned | `chip_x0` and `CHIP_W` estimated incorrectly | `CHIP_W=13.5pt`, `CHIP_PITCH=19.06pt` from actual; `chip_x0 = ix0+40.4` |
| Pink border breaks at corners | White zones clipped partial magenta edges | Explicit `draw_rect(ix0, iy0, ix1, iy1, MAGENTA)` redraws all 4 sides |
| Triman icons erased | Left-col zone was too wide | Left col y>188 preserved (no whitewash) |
| Barcode wrong height | `BAR_H` overestimated | `BAR_H = 16pt` from actual PDF measurement |
| Currency appears as text "AED" | No symbol normalisation | `_fix_currency()` always returns a symbol char |
| EUR and digits no gap | No explicit gap code | `sym_gap = 2.5pt` added between symbol and integer |

---

### v13 (commit `402043c`) — Tag: `v1.0` ⭐ Stable Release

Two critical issues from v12 fixed:

**Issue 1: Triman logos erased**
- v12 had a left-column whitewash zone from `y=188 to y=258`
- This erased all three Triman/recycling logos
- Fix: Removed that zone entirely. Left col below y=188 passes through template as-is

**Issue 2: Active chip `[4-5]` touching TABLE_BOT border**
- `TABLE_BOT = 168.0` but `chip box_top = R1_BL - fs_gr - 1.0 = 173.3 - 6.5 - 1.0 = 165.8`
- Since `165.8 < 168.0`, box top was **above** the border line (overlap!)
- Fix: `TABLE_BOT = 163.5` → clearance = `165.8 - 163.5 = 2.3pt` ✅

---

### v14 (commit `0e8e4f8`): Barcode & Logo Overlap Resolved ⭐ Current Stable

**Problem:**  
After restoring Triman logos (v13), the barcode PNG appeared to overlap/bleed into the logo area at the left column / middle column boundary.

**Root cause discovered:**  
`back_panel_ref.pdf` has its **own EAN-13 barcode** drawn in Type3 vector font (from the original template). The guard digit `8` sits at the `_C3` column boundary — partially outside Zone B2's white erase area. This digit and the first few chars were bleeding through into the visible area.

**Three-part fix:**

| Fix | Change |
|-----|--------|
| Zone B2 left boundary extended | `INNER_X + _C3 - 15` (was `INNER_X + _C3`) — erases template's own barcode digits at the seam |
| Barcode PNG inset increased | `BC_INSET = 8.0` → `bc_x0 = mc_x0 + 8pt` — bars start cleanly past logo right edge |
| All barcode text re-anchored | Dept codes, digit string, style, cref all use `bc_x0/bc_w` (not `mc_x0/mc_w`) |

---

## 7. Final Layout Specification (v14)

### Rendering Order

```
1.  show_pdf_page(back_panel_ref.pdf)          embed static template
2.  White-overwrite Zones A / B2 / B3 / C      clear variable areas
3.  draw_rect(inner border, MAGENTA, 0.75pt)   restore full pink border
4.  TABLE_TOP line  ix0 → ix1, 0.8pt dark
5.  TABLE_BOT line  ix0 → ix1, 0.8pt dark
6.  Vertical divider  vert_x, 0.8pt dark
7.  YEARS row text (label + value, bold)
8.  IT/MEX row text  (label + value, bold)
9.  Size chart: 2×3 chips — white boxes with dark text, active = black box + white text
10. Dept codes text   centred in bc_x0..bc_x0+bc_w
11. EAN-13 PNG bars   at bc_x0, height 16pt
12. Digit string      centred below bars
13. Style code        centred, grey
14. Commercial ref    centred, grey
15. Right col vertical text   rotated 90°
16. Green dashed separator    y=257.49
17. Price: EUR symbol + gap + integer + raised cents
18. Qty label below panel
```

### Layout Constants

```python
# ── GEOMETRY ───────────────────────────────────────────
OUTER_W, OUTER_H = 150.3, 305.5
INNER_X, INNER_Y = 11.5, 10.8
INNER_W = 127.2
_C3 = 42.4    # column width

# ── TABLE (YEARS / CM) ─────────────────────────────────
TABLE_TOP = 138.0   # top border (panel-relative y)
TABLE_BOT = 163.5   # bottom border  (must be <= chip_box_top - 2pt)
fs_lbl    = 6.5     # "YEARS" / "IT" / "CM" / "MEX" labels
fs_val    = 9.0     # "4-5" / "110" / "4-5 A" values
CELL_PAD  = 4.0     # text padding from cell edge
# Row baselines:
#   YEARS/CM  bl = oy + 148.0
#   IT/MEX    bl = oy + 159.1

# ── SIZE CHART ─────────────────────────────────────────
CHIP_PITCH = 19.06  # chip-to-chip distance (measured from actual PDF)
CHIP_W     = 13.5   # chip box width
fs_gr      = 6.5    # chip text font size
chip_x0    = ix0 + 40.4   # x of leftmost chip
R1_BL      = 173.3  # row 1 baseline (panel-relative)
R2_BL      = 185.3  # row 2 baseline (panel-relative)
# Active chip geometry:
#   box_top = bl - fs_gr - 1.0   (= 165.8 for row 1)
#   box_bot = bl + 1.5
#   Clearance from TABLE_BOT: 165.8 - 163.5 = 2.3pt ✓

# ── BARCODE ────────────────────────────────────────────
BC_INSET = 8.0      # left inset from mc_x0 into middle col
bc_x0    = mc_x0 + BC_INSET
bc_w     = mc_w - BC_INSET - 0.5   # ≈ 33.9 pt
DEPT_Y   = 200.6    # dept codes baseline (panel-relative)
BC_Y     = 207.0    # bar top y (panel-relative)
BAR_H    = 16.0     # bar height in pt
# style code: y = 236.7, cref: y = 246.1

# ── PRICE ──────────────────────────────────────────────
fs_major  = 24.0    # EUR symbol + main integer  (actual PDF: 27.67pt Type3)
fs_minor  = 13.0    # cents ",95"                (actual PDF: 15.1pt Type3)
sym_gap   = 2.5     # gap between symbol and integer
CAP_H     = 0.72    # cap-height ratio for superscript raise
pr_y_rel  = 284.5   # price baseline (panel-relative)
# MIN_raise = (24 - 13) × 0.72 = 7.92pt  (cents raised above baseline)

# ── SEPARATOR ──────────────────────────────────────────
SEP_Y  = 257.49     # green dashed line y (panel-relative)
SEP_X0 = 12.7
SEP_X1 = 134.4
# dash="[3 3] 0", width=1.0, color=GREEN=(0.451,0.749,0.267)
```

---

## 8. Key Technical Measurements

All values extracted programmatically from `TOK100_B0854559_1.pdf`.

### Panel Origin
```
Page size : 2004.1 × 1417.3 pt
Panel oy  : 373.25 pt
Panel ox  : 581.85 pt
ix0       : 593.35 pt  (ox + INNER_X)
ix1       : 720.55 pt  (ix0 + INNER_W)
```

### Text Y Coordinates
| Element | Absolute Page Y | Panel-relative Y |
|---------|----------------|-----------------|
| YEARS value `4-5` | 521.22 | **148.0** |
| IT value `4-5` | 532.32 | **159.1** |
| Size chip row 1 | 546.55 | **173.3** |
| Size chip row 2 | 558.57 | **185.3** |
| Dept codes | 573.80 | **200.6** |
| Barcode digit string | 600.60 | **227.4** |
| Style code | 609.96 | **236.7** |
| Commercial ref | 619.35 | **246.1** |
| Price EUR+29 | 657.74 | **284.5** |
| Cents `,95` | 649.93 | **276.7** |

### Size Chip X Coordinates (page-absolute)
| Chip | Page X | Gap to next |
|------|--------|------------|
| `4-5` row 1 | 638.30 | — |
| `5-6` row 1 | 657.36 | **19.06 pt** |
| `6-7` row 1 | 675.97 | 18.61 pt |
| `7-8` row 2 | 637.08 | — |
| `8-9` row 2 | 655.44 | 18.36 pt |
| `9-10` row 2 | 674.04 | 18.60 pt |

→ `CHIP_PITCH = 19.06 pt`

### Font Size Mapping (Type3 actual → Helv equivalent)
| Element | Actual (Type3) | Used in engine |
|---------|---------------|---------------|
| YEARS/IT label | ~6.5 pt | **6.5pt FB** |
| YEARS/IT value | ~8.49 pt | **9.0pt FB** |
| Size chip | 6.5 pt | **6.5pt FR/FB** |
| Barcode digits | 7.49 pt | 5.0pt FR |
| EUR + 29 | 27.67 pt | **24.0pt FB** |
| Cents `,95` | 15.1 pt | **13.0pt FR** |
| KIDS heading | ~9.99 pt | (static template) |

---

## 9. Currency & Price Logic

### Currency normalisation

```python
def _fix_currency(raw):
    """
    Converts any currency input to a single renderable PDF WinAnsi symbol.
    Never returns raw text like "AED" in the display (except for AED itself
    which renders at 65% font size as 3-char text).
    """
    # EUR / Euro / €  →  chr(128)   = € in cp1252/WinAnsi
    # GBP / Sterling  →  chr(163)   = £
    # USD / $         →  "$"
    # AED             →  "AED"     (rendered at fs_major × 0.65)
    # Empty / default →  chr(128)  = € (default)
```

### Price rendering pipeline

```
Input:  currency="EUR",  selling_price="29,95"

Step 1: _fix_currency("EUR") → chr(128)  [= €]
Step 2: _split_price("29,95") → major="29",  minor=",95"
Step 3: Compute widths
          sym_w  = text_length("€", FB, 24)
          maj_w  = text_length("29", FB, 24)
          min_w  = text_length(",95", FR, 13)
Step 4: total_w = sym_w + 2.5 + maj_w + min_w
Step 5: px = panel_centre_x - total_w / 2
Step 6: Draw:
          €   at (px,         pr_y)               — 24pt bold
          29  at (px+sym_w+2.5, pr_y)             — 24pt bold
          ,95 at (px+sym_w+2.5+maj_w, pr_y-7.92) — 13pt, raised 7.92pt
```

---

## 10. EAN-13 Barcode Generation

### Encoding tables (verified correct)

```python
_EAN_L = ["0001101","0011001","0010011","0111101","0100011",
           "0110001","0101111","0111011","0110111","0001011"]
_EAN_G = ["0100111","0110011","0011011","0100001","0011101",
           "0111001","0000101","0010001","0001001","0010111"]
_EAN_R = ["1110010","1100110","1101100","1000010","1011100",
           "1001110","1010000","1000100","1001000","1110100"]
_EAN_PARITY = ["LLLLLL","LLGLGG","LLGGLG","LLGGGL","LGLLGG",
               "LGGLLG","LGGGLL","LGLGLG","LGLGGL","LGGLGL"]
```

### Bit generation

```
95-bit structure:
[101]  start guard (3 bits)
[7×L/G × 6 digits]  left half using parity pattern from digit[0]
[01010]  centre guard (5 bits)
[7×R × 6 digits]  right half
[101]  end guard (3 bits)
```

### PNG rendering

```python
def _draw_barcode(page, x0, y0, w, bar_h, bc_str, txt_x0, txt_w):
    bits  = _ean13_bits(bc_str)          # 95-char bit string
    w_px  = max(280, round(w / 72 * 400))  # 400 DPI
    h_px  = max(100, round(bar_h / 72 * 400))
    img   = Image.new("RGB", (w_px, h_px), (255,255,255))
    draw  = ImageDraw.Draw(img)
    mod   = w_px / len(bits)            # module width
    for i, b in enumerate(bits):
        if b == "1":
            draw.rectangle([round(i*mod), 0, max(round(i*mod)+1, round((i+1)*mod)), h_px-1], fill=(0,0,0))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    page.insert_image(fitz.Rect(x0, y0, x0+w, y0+bar_h), stream=buf.getvalue())
    # Digit string below bars
    p1, p2, p3 = _bc_chunks(bc_str)   # "8", "051553", "298804"
    txt = f"{p1} {p2} {p3}"
    page.insert_text(fitz.Point(_cx(txt, FR, 5.0, txt_x0, txt_w), y0+bar_h+1.5+5.0), ...)
```

**Current barcode dimensions:**
- Display width: `bc_w ≈ 33.9 pt` (`mc_w - 8.5`)
- Display height: `BAR_H = 16 pt`
- Internal render: `400 DPI`

---

## 11. Git History & Tags

| Commit | Tag | Description |
|--------|-----|-------------|
| `3e1a12b` | — | Initialize Artwork Engine standalone repository |
| `c69034a` | — | OVS KIDS TOK100 full support — XML normalizer, SVG template, smart mapper |
| `47175f5` | — | Fully autonomous PDF creation — dynamic XML field matching |
| `9891561` | — | New TOK100 label builder (PyMuPDF) — v1 prototype |
| `41b2257` | — | TOK100 label v3 — pixel-precise attempt #1 |
| `4e07f47` | — | v4 template-embed label builder + architecture |
| `08b5a11` | — | v6 pixel-fidelity overhaul |
| `f076f05` | — | v7 proper EAN-13 + green dashed separator |
| `5ca55fd` | — | v8 Acrobat fix + tighter highlight + price style |
| `e17bd6d` | — | v9 Pillow PNG barcode + compact size chips |
| `126c0bb` | — | v10 barcode height + 2×3 size grid |
| `dda4c01` | — | v11 pixel-precise from Actual.jpg reference |
| `6d0c96f` | — | **v12** scientific coordinate extraction — 5 issues fixed |
| `402043c` | **`v1.0`** | **v13** Triman logos restored + chip border clearance |
| `0e8e4f8` | — | **v14** barcode overlap with logos resolved ← _CURRENT_ |

---

## 12. How to Run & Test

### Prerequisites

```powershell
cd c:\AntiGravity_Projects\Art_Work
pip install pymupdf pillow
```

### Generate full approval sheet

```powershell
python test_v10.py
# Generates:
#   test_v10_approval.pdf    (3-page PDF, all 6 size variants × 6 labels)
#   test_v10_page0.png       (200 DPI render of page 1 for quick review)
```

### Inspect a specific back panel at high resolution

```python
import fitz
from PIL import Image

SCALE = 300 / 72.0
oy, ox_b1 = 190.0, 203.75   # First back panel position in test approval sheet

doc = fitz.open('test_v10_approval.pdf')
pix = doc[0].get_pixmap(matrix=fitz.Matrix(SCALE, SCALE), alpha=False)
img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
doc.close()

panel = img.crop([
    int(ox_b1 * SCALE),
    int((oy - 5) * SCALE),
    int((ox_b1 + 150.3) * SCALE),
    int((oy + 305.5 + 5) * SCALE)
])
panel.save('back_panel_inspect.png')
```

### Run coordinate analysis tools

```powershell
python analyse_all.py          # Full comparison: actual vs generated
python precision_analysis.py   # Extract all text/image positions from actual PDF
python check_positions.py      # Chip x-positions + barcode bbox in generated PDF
```

### Check git state

```powershell
git log --oneline -10
git tag -l
git show v1.0                  # Show v1.0 tag details
git diff HEAD~1 backend/engine/tok100_label_builder.py
```

---

## 13. Known Remaining Items

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 1 | Barcode width narrower than actual | Low | `bc_w ≈ 33.9pt` vs actual full middle-col. Can reduce `BC_INSET` if logo bleed is confirmed gone on all sizes |
| 2 | Dept codes spacing | Low | Current: joined with 2 spaces. Actual uses non-uniform spacing between the 3 fields |
| 3 | AED currency rendering | Medium | Shows as `AED` text at 65% size. Confirm acceptable for Middle East label variant |
| 4 | All 6 sizes visual verification | Medium | Visually confirmed only for size `4-5`. Run full sheet review |
| 5 | Price symbol gap | Low | `sym_gap=2.5pt` — fine-tune if print output differs from screen preview |
| 6 | Backend integration test | High | Confirm `approval_pdf_service.py` passes all required fields correctly to engine |

---

## 14. Engine Code Structure

```python
# ── Module header ───────────────────────────────────────────
# tok100_label_builder.py
# Docstring with all measured coordinates from actual PDF

# ── Template paths ──────────────────────────────────────────
FRONT_PANEL_TEMPLATE = ".../front_panel_ref.pdf"
BACK_PANEL_TEMPLATE  = ".../back_panel_ref.pdf"

# ── Panel geometry constants ────────────────────────────────
OUTER_W, OUTER_H, INNER_X, INNER_Y, INNER_W, INNER_H
_C3 = INNER_W / 3.0

# ── White-overwrite zones ───────────────────────────────────
ZONES = [...]   # 4 rect tuples (rx0, ry0, rx1, ry1) panel-relative

# ── Colour constants (0.0–1.0 RGB tuples) ──────────────────
MAGENTA, NAVY, GOLD, GREEN, WHITE, BLACK, DARK, GREY, LGREY

# ── Font aliases ────────────────────────────────────────────
FB = "hebo"   # Helvetica-Bold
FR = "helv"   # Helvetica

# ── Size reference data ─────────────────────────────────────
TOK100_SIZES = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]
SIZE_ROWS    = [sizes[:3], sizes[3:]]
CM_MAP       = {"4-5": "110", ...}
COUNTRY_ZONE_MAP = {...}
CURRENCY_SYMBOL_MAP = {...}

# ── Helper functions ────────────────────────────────────────
def _cx(text, font, fs, x0, w)    # Centre-align: returns insert x
def _rx(text, font, fs, x1)       # Right-align: returns insert x
def _fix_currency(raw)             # Normalise currency → symbol char
def _split_price(s)               # "29,95" → ("29", ",95")
def _bc_chunks(bc)                # "8051..." → ("8","051553","298804")

# ── EAN-13 barcode engine ───────────────────────────────────
_EAN_L, _EAN_G, _EAN_R = [...]   # Encoding lookup tables
_EAN_PARITY = [...]               # Parity pattern table
def _ean13_bits(bc)               # Returns 95-char "0"/"1" bit string
def _draw_barcode(page, x0, y0, w, bar_h, bc_str, txt_x0, txt_w)

# ── Template cache ──────────────────────────────────────────
_TDOC = {}
def _tpl(path)                    # Returns cached fitz.Document

# ── Panel renderers ─────────────────────────────────────────
def _draw_front_panel(page, ox, oy)
def _draw_back_panel(page, ox, oy, item_data, render_dpi=150)
    # 11 rendering steps — see Section 7

# ── Public API ──────────────────────────────────────────────
def build_label_pdf(item_data)           # → bytes  (front+back PDF)
def build_label_png(item_data, dpi=150) # → bytes  (PNG image)
def build_label_thumbnail(item_data, dpi=60) # → bytes (small PNG)
```

### `item_data` dictionary keys

| Key | Type | Example |
|-----|------|---------|
| `sizes` | dict | `{"YEARS": "4-5", "IT": "4-5", "MEX": "4-5", "CM": "110"}` |
| `sub_department` | str | `"3632"` |
| `department` | str | `"230"` |
| `sku_code` | str | `"2768960"` |
| `barcode_number` | str | `"8051553298804"` |
| `style_code` | str | `"2768957"` |
| `commercial_ref` | str | `"PR711 AI08"` |
| `country_of_origin` | str | `"WARM"` / `"COLD"` / `"MIDDLE EAST"` |
| `currency_symbol` | str | `"EUR"` / `"GBP"` / `"AED"` |
| `selling_price` | str | `"29,95"` |
| `quantity` | int | `128` |

---

*Generated: 2026-04-19 | Repo: padmapriyaaruna/artwork | Stable: `v1.0` @ `402043c` | Current: `v14` @ `0e8e4f8`*
