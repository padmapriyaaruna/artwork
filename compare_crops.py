"""
Create a side-by-side crop comparison of:
1. The currency symbol area  
2. The barcode area
3. The size chart area

From actual vs v10 generated.
"""
from PIL import Image
import fitz

# Scale: generated page is 1191x842pt, rendered at 200dpi = 3309x2339px
# Actual page is 2004x1417pt, rendered at 150dpi = 4175x2952px  
# Focus on first label (size 4-5 / leftmost back panel) in the generated

# For generated v10 (page0, 200DPI render = 3309x2339px)
# oy = 190, ox = front_x + OUTER_W + PANEL_GAP ~ 203.75  
# OUTER_W=150.3, OUTER_H=305.5, INNER_X=11.5, INNER_Y=10.8
# First back panel ox = front_x + OUTER_W + PANEL_GAP
# front_x = (1191 - total_w)/2 = (1191-1100.1)/2 = 45.45
# back1_x = 45.45 + 150.3 + 8 = 203.75
# Scale: 200_dpi/72pt = 2.78 px/pt

DPI = 200
SCALE = DPI / 72.0  # px per pt in rendered image

# Generated page0 at 200DPI
gen = Image.open("test_v10_page0.png")
print(f"Generated image: {gen.size} via {DPI}DPI")

oy = 190.0    # LABEL_T
ox_b1 = 203.75  # first back panel ox

# Currency area: panel y=SEP_Y+15 to SEP_Y+40 (~257 to 297), full inner width
# SEP_Y=257.49, price at SEP_Y+26=283.49
# Panel-absolute: oy+257 to oy+297 = 447 to 487
# Absolute in generated page: 447 to 487 pt -> px: 447*SCALE to 487*SCALE
# x range: ox_b1 + INNER_X to ox_b1 + INNER_X + INNER_W = 215 to 342 pt -> px

currency_crop_gen = gen.crop([
    int((ox_b1 + 11.5 - 5)  * SCALE),  # left
    int((oy + 257)           * SCALE),  # top
    int((ox_b1 + 139)        * SCALE),  # right
    int((oy + 300)           * SCALE),  # bottom
])
currency_crop_gen.save("crop_gen_currency.png")
print(f"Currency crop (gen): {currency_crop_gen.size}")

# Barcode area: panel y=196 to 255, middle col
# x: ox_b1 + _C3 + 11.5 to ox_b1 + 2*_C3 + 11.5 (approx ox_b1+53.9 to ox_b1+96.3)
barcode_crop_gen = gen.crop([
    int((ox_b1 + 50)   * SCALE),
    int((oy + 192)     * SCALE),
    int((ox_b1 + 100)  * SCALE),
    int((oy + 257)     * SCALE),
])
barcode_crop_gen.save("crop_gen_barcode.png")
print(f"Barcode crop (gen): {barcode_crop_gen.size}")

# Size chart area: panel y=173 to 195, full inner width
sizechart_crop_gen = gen.crop([
    int((ox_b1 + 11.5) * SCALE),
    int((oy + 170)     * SCALE),
    int((ox_b1 + 139)  * SCALE),
    int((oy + 197)     * SCALE),
])
sizechart_crop_gen.save("crop_gen_sizechart.png")
print(f"Size chart crop (gen): {sizechart_crop_gen.size}")

# Now for ACTUAL ref PDF (renders at 150DPI)
# In actual page (2004pt wide), first back panel is at different scale
# We need to find the right-most left back panel from actual
# From text analysis: 'YEARS' in actual at x=693.2 (for the 4th panel, size 4-5 from actual page 0)
# Let's use the actual rendered page at 150DPI = 2004*150/72 x 1417*150/72 = 4175x2952px
actual_dpi = 150
actual_scale = actual_dpi / 72.0

actual = Image.open("cmp_actual_ref_p0.png")
print(f"Actual image: {actual.size}")

# In actual page, panel for size 4-5 (leftmost back label): 
# from text: YEARS at x=693.2, INNER_X=11.5, GAP=3.0 -> ix0=693.2-3.0=690.2 -> ox_b1=690.2-11.5=678.7
# Panel oy in actual: from text 'YEARS' @ y=341.2, ay(151.2) = oy+151.2 -> oy=341.2-151.2=190.0
# Same! oy=190.0 and ox_b1=678.7 (first back panel in actual page 0)
ox_b1_actual = 678.7
oy_actual = 190.0

# Currency area in actual
currency_crop_actual = actual.crop([
    int((ox_b1_actual + 11.5 - 5)  * actual_scale),
    int((oy_actual + 257)           * actual_scale),
    int((ox_b1_actual + 139)        * actual_scale),
    int((oy_actual + 300)           * actual_scale),
])
currency_crop_actual.save("crop_actual_currency.png")
print(f"Currency crop (actual): {currency_crop_actual.size}")

# Barcode area in actual
barcode_crop_actual = actual.crop([
    int((ox_b1_actual + 50)  * actual_scale),
    int((oy_actual + 192)    * actual_scale),
    int((ox_b1_actual + 100) * actual_scale),
    int((oy_actual + 257)    * actual_scale),
])
barcode_crop_actual.save("crop_actual_barcode.png")
print(f"Barcode crop (actual): {barcode_crop_actual.size}")

# Size chart in actual
sizechart_crop_actual = actual.crop([
    int((ox_b1_actual + 11.5) * actual_scale),
    int((oy_actual + 170)     * actual_scale),
    int((ox_b1_actual + 139)  * actual_scale),
    int((oy_actual + 197)     * actual_scale),
])
sizechart_crop_actual.save("crop_actual_sizechart.png")
print(f"Size chart crop (actual): {sizechart_crop_actual.size}")

print("\nAll crops saved!")
