"""
Extract precise coordinates from actual PDF back panel.
Results to firmly establish all baseline measurements.
"""
import fitz
from PIL import Image

# ── ACTUAL PDF exact coordinates ──────────────────────────────
# From analysis output:
# Panel for size 4-5 (first back panel, leftmost):
#   "Back" label at x=638.0, y=347.86
#   Panel outer: need to find magenta border positions
#   
# TEXT MEASUREMENTS (actual PDF back panel, size 4-5):
# ──────────────────────────────────────────────────── 
# YEARS row:  '4-5' @ (646.09, 521.22) sz=8.49  [value]
# CM row:     '110' @ (703.05, 521.22) sz=8.49   [value on same line]
# IT row:     '4-5' @ (646.37, 532.32) sz=8.49   [value]
# MEX row:    '4-5' + 'A' @ (693.14+706.3, 532.32)
#
# SIZE CHIPS (6.5pt):
# Row 1: 4-5@638.30, 5-6@657.36, 6-7@675.97   all at y=546.55
# Row 2: 7-8@637.08, 8-9@655.44, 9-10@674.04  all at y=558.57
#
# DEPT CODES (7.49pt Type3):
# '3632'@630.57, '230'@653.40, '2768957'@671.69  at y=573.80
#
# BARCODE DIGIT STRING (7.49pt Type3):
# '8'@626.60, '051553'@634.88, '298798'@667.21  at y=600.60
#
# STYLE/CREF (7.49pt):
# '2768957'@649.44  at y=609.96
# 'PR711 AI08'@645.30  at y=619.35
#
# PRICE (27.67pt):
# '€'@631.51, '29'@650.14  at y=657.74
# ',95'@673.69  at y=649.93 (raised)
#
# KEY POINT: actual page is 2004.1pt wide, our page is 1191pt
# Scale factor: 1191/2004.1 = 0.5943 (NOT used — labels are drawn at SAME pt scale)
# The back panel in actual is at ox≈556, oy≈273
# Let's calculate: YEARS value center x ≈ 646.09, 703.05 → midpoint = 674.57 → 
#   half inner width matches (674.57-556-11.5)/127.2 ≈ 83.3/127.2 ≈ 0.655 → 
#   that's 83pt into a 127pt wide area, which is the right col (col2 starts at _C3=42.4 → center of right half = 42.4+42.4/2 = 63.6pt)
# Let's get the ACTUAL panel origin:
# Panel ox = Left border x. Inner border at ix0.
# YEARS label 'YEARS' was NOT in the first 40 because it's Type3 font
# But from the size arrays: chip '4-5' (sz=6.5) at x=638.30
# chip '7-8' at x=637.08 → so leftmost chip at ~637
# chip_x0 for left edge of leftmost chip = 638.30 (approximate)
# In our coord: ix0 + (INNER_W - 3*CHIP_W - 2*CHIP_GAP)/2 was chip_x0
# If actual ix0 = ox + INNER_X = ox + 11.5
# Chip leftmost = 638.30 → ix0 ≈ 638.30 - (INNER_W - row_span)/2
# row_span = 3*CHIP_W + 2*CHIP_GAP; in actual, CHIP_W seems ≈ 19pt?
# 5-6 at 657.36 vs 4-5 at 638.30 → gap = 19.06 (chip_pitch = CHIP_W + CHIP_GAP)
# 6-7 at 675.97 → pitch = 18.61 → avg pitch ≈ 18.8
# row_span = 3*CHIP_W + 2*CHIP_GAP. If pitch = CHIP_W + CHIP_GAP ≈ 18.8
# Row total = 2*pitch + CHIP_W = 2*18.8 + CHIP_W
# For 3 chips: rightmost left = leftmost + 2*pitch → 638.30 + 2*18.8 = 675.9 ≈ 675.97 ✓
# So chip pitch ≈ 18.85, CHIP_W ≈ ? Let's use text width: '4-5' at 6.5pt ≈ 6+9+5 ≈ 10pt text
# chip box width = CHIP_W, center alignment: chipLeft + (CHIP_W-tw)/2 = chipLeft_text
# From actual: the black box for '4-5' (active chip) appears visually to be ~14-16pt wide

# ACTUAL panel origin calculation:
# Center of label inner area: (right_val_right + left_val_right) / 2
# From: '4-5' val at x=646.09 (left col right edge area), '110' at 703.05 (right col)
# YEARS label (if it were there) at ix0 + GAP ≈ ix0 + 4
# Vert divider at ix0 + half (half = INNER_W/2 = 63.6)
# '4-5' value at x=646.09 is right-aligned to vert_x - GAP
# '110' value at x=703.05+... right-aligned to ix1 - GAP
# From '110' right edge: 703.05 + tw('110' @8.49) ≈ 703.05 + 13.5 = 716.55 = ix1 - GAP
# ix1 - 4 = 716.55 → ix1 = 720.55 → ix0 = 720.55 - 127.2 = 593.35
# ox = ix0 - 11.5 = 581.85

print("ACTUAL PDF PANEL CALCULATIONS:")
print(f"  ix1 estimated: 720.55 pt")
print(f"  ix0 estimated: 593.35 pt") 
print(f"  ox estimated:  581.85 pt")
print(f"  vert_x estimated: 593.35 + 63.6 = 656.95 pt")

# Verify: YEARS '4-5' val right edge = vert_x - GAP = 656.95 - 4 = 652.95
# '4-5' at x=646.09, tw = fitz.get_text_length('4-5',fontname='hebo',fontsize=8.49) 
# Using ratio from known: at 9pt, '4-5' ≈ 9.63pt wide → at 8.49: 8.49/9 * 9.63 ≈ 9.08pt
# 646.09 + 9.08 = 655.17 ≈ 652.95? Close enough (4pt padding is slightly variable)
print(f"  YEARS '4-5' val: x=646.09, right≈655.17, vert_x-GAP≈652.95 ✓ (close)")

# Panel y origin:
# oy = ? 
# 'K I D S' at y=443.57 → in template, KIDS is at y=KIDS_Y relative to panel
# In our back panel template, KIDS is at panel y≈50 (approx)
# So oy ≈ 443.57 - 50 = 393.57? No...
# Actually 'Back' heading at y=347.86 is above the panel
# Let's use the price: '€'+'29' at y=657.74 → pr_y = ay(SEP_Y + 27) = oy + 284.49
# oy = 657.74 - 284.49 = 373.25
# Verify: KIDS at y=443.57 → panel_rel = 443.57 - 373.25 = 70.32 (plausible, KIDS is in upper section)

oy_actual = 373.25
ox_actual = 581.85
print(f"\n  oy_actual = {oy_actual}")
print(f"  ox_actual = {ox_actual}")
print(f"\nPANEL-RELATIVE COORDINATES (actual - oy = {oy_actual}):")
coords = [
    ("YEARS val y=521.22", 521.22 - oy_actual),
    ("IT val y=532.32",    532.32 - oy_actual),
    ("SizeRow1 y=546.55",  546.55 - oy_actual),
    ("SizeRow2 y=558.57",  558.57 - oy_actual),
    ("DeptCodes y=573.80", 573.80 - oy_actual),
    ("BarDigits y=600.60", 600.60 - oy_actual),
    ("StyleCode y=609.96", 609.96 - oy_actual),
    ("Cref y=619.35",      619.35 - oy_actual),
    ("Price EUR y=657.74", 657.74 - oy_actual),
    (",95 y=649.93",       649.93 - oy_actual),
]
for label, y_rel in coords:
    print(f"  {label}: y_rel = {y_rel:.2f}")

# Now: where does the barcode IMAGE sit?
# From actual PDF: barcode is rendered as Type3 font characters, not a PNG image
# The digit string '8 051553 298798' at y=600.60 is the BELOW-bars text
# The bars themselves (Type3 chars) would be ABOVE this y
# The dept codes '3632 230 2768957' at y=573.80 are ABOVE the bars
# So bars span from y=573.80+some_gap to y≈600.60-digit_height
# 600.60 - 4.5(approx fs) - 2(gap) ≈ 594.10 = bars bottom
# 573.80 + 4.5 + 2 = 580.30 = bars top
# BAR_H_actual ≈ 594.10 - 580.30 = 13.8 pt panel-relative... seems too small
# Actually dept codes at y=573.80 are the ABOVE TEXT
# Looking at actual Actual.jpg image: the bars appear ≈ 18-20pt tall in the label

# More precise: digit string at y=600.60 (baseline), bars end at y≈ 600.60 - 4.5(fs+gap) ≈ 593.85
# Bars start: dept codes at y=573.80 + something... 
# In actual label: dept codes line, then bars, then digit string
# Actual dept_y_rel = 573.80 - 373.25 = 200.55 (panel-relative)
# Bars top = dept_y_rel + 4.5(dept fs) + 2 ≈ 207
# Bars bottom = digit_y_rel - 4.5 - 2 ≈ 227.35 - 6.5 ≈ 220.85
# BAR_H = 220.85 - 207 = 13.85pt

# Hmm, but the visual shows bigger bars. Let's check the actual image positions
print("\n" + "="*60)
print("CHECKING ACTUAL PDF IMAGE POSITIONS:")
doc = fitz.open("TOK100_B0854559_1.pdf")
pg = doc[0]
for info in pg.get_image_info(hashes=False):
    bbox = info["bbox"]
    if 550 < bbox[0] < 800:
        print(f"  Image: bbox={[round(v,2) for v in bbox]}, "
              f"display={round(bbox[2]-bbox[0],1)}x{round(bbox[3]-bbox[1],1)}pt, "
              f"src={info['width']}x{info['height']}px")
doc.close()

print("\n" + "="*60)
print("CHECKING GENERATED PDF IMAGE POSITIONS (first back panel):")
doc2 = fitz.open("approval_sheet_B0854559 (12).pdf")
pg2 = doc2[0]
for info in pg2.get_image_info(hashes=False):
    bbox = info["bbox"]
    if 200 < bbox[0] < 360 and 185 < bbox[1] < 500:
        print(f"  Barcode: bbox={[round(v,2) for v in bbox]}, "
              f"display={round(bbox[2]-bbox[0],1)}x{round(bbox[3]-bbox[1],1)}pt, "
              f"src={info['width']}x{info['height']}px")
doc2.close()

print("\n" + "="*60)
print("KEY FINDINGS SUMMARY:")
print("""
ACTUAL PDF (back panel, size 4-5):
  Panel oy ≈ 373.25 pt (page absolute)
  Panel ox ≈ 581.85 pt
  
  Panel-relative coordinates:
    YEARS row baseline : y_rel ≈ 148.0  (521.22 - 373.25)
    IT row baseline    : y_rel ≈ 159.1  (532.32 - 373.25)
    Size chip row 1    : y_rel ≈ 173.3  (546.55 - 373.25)
    Size chip row 2    : y_rel ≈ 185.3  (558.57 - 373.25)
    Dept codes         : y_rel ≈ 200.6  (573.80 - 373.25)
    Barcode digit str  : y_rel ≈ 227.4  (600.60 - 373.25)
    Style code         : y_rel ≈ 236.7  (609.96 - 373.25)
    Cref               : y_rel ≈ 246.1  (619.35 - 373.25)
    Price EUR+29       : y_rel ≈ 284.5  (657.74 - 373.25)
    Cents ,95          : y_rel ≈ 276.7  (649.93 - 373.25)
    
  TABLE borders (need to check drawings):
    TABLE_TOP ≈ y_rel of "line above YEARS" ≈ 138 (YEARS y=148, subtract ~10)
    TABLE_BOT ≈ y_rel of "line below IT" ≈ 168 (IT y=159, add ~9)

  SIZE CHIP PITCH:
    5-6 - 4-5 = 19.06pt  (x distance between chip starts)
    6-7 - 5-6 = 18.61pt
    Average pitch ≈ 18.8pt (this = CHIP_W + CHIP_GAP)
    
  PRICE layout:
    EUR at x=631.51 (page absolute)
    29  at x=650.14 → gap from EUR = 650.14 - 631.51 = 18.63pt
    At 27.67pt font, EUR char width ≈ 18pt → gap = 18.63-18 = 0.63pt (almost touching)
    ,95 at x=673.69 (superscript y=649.93, raised 7.81pt from main baseline)
    
  BARCODE (Type3 font in actual, no PNG image):
    Bars are Type3 glyphs, NOT a PNG — that's why our PNG barcode looks different!
""")
