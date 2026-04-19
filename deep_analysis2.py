import fitz

# The key finding: barcode image in generated PDF
# bbox: (262.6, 391.8, 298.0, 404.2)
# Width = 298.0 - 262.6 = 35.4 pt
# Height = 404.2 - 391.8 = 12.5 pt

# The barcode image pixels = 190x67
# So aspect ratio in image = 190/67 = 2.835 wide/tall
# But displayed aspect = 35.4/12.5 = 2.83 wide/tall - actually OK proportionally!

# Wait - let me recalculate. The IMAGE is 190 wide x 67 tall
# But it's being shown at 35.4 wide x 12.5 tall 
# The image ASPECT RATIO = 190/67 = 2.84
# The DISPLAY ASPECT RATIO = 35.4/12.5 = 2.83 -- matches! So NO DISTORTION (proportional)

# HOWEVER: the barcode is only 12.5pt tall in display!
# vs the code setting BAR_H = 16pt

# Let me check what _draw_barcode is doing with the rectangle placement
# The code does: page.insert_image(fitz.Rect(x0, y0, x0+w, y0+bar_h), stream=...)
# mc_x0 = ix0 + _C3 + 5
# mc_w = _C3 - 7 = 42.4 - 7 = 35.4 pt  
# BC_Y = 200.0, BAR_H = 16.0
# So the Rect should be: (mc_x0, ay(200), mc_x0 + 35.4, ay(200) + 16)

# The image bbox y values: 391.8 to 404.2 
# Height = 12.5 -- but BAR_H = 16?? That means the coordinate transform is scaling
# Or the ay() function is doing panel-relative -> page scaling

# Let me check the approval_pdf_service to understand the page layout
doc = fitz.open("approval_sheet_B0854559 (10).pdf")
pg = doc[0]
img_infos = pg.get_image_info(hashes=False)
print("All image placements on generated page 0:")
for info in img_infos:
    bbox = info['bbox']
    w_display = bbox[2] - bbox[0]
    h_display = bbox[3] - bbox[1]
    img_w = info['width']
    img_h = info['height']
    if img_w == 190:  # barcode images
        print(f"  BARCODE: bbox={[round(v,1) for v in bbox]}")
        print(f"    Display: {w_display:.1f} x {h_display:.1f} pt")
        print(f"    Pixels: {img_w}x{img_h}")
        print(f"    Image AR: {img_w/img_h:.3f}")
        print(f"    Display AR: {w_display/h_display:.3f}")
        print(f"    Scale X: {img_w/w_display:.2f} px/pt")
        print(f"    Scale Y: {img_h/h_display:.2f} px/pt")
doc.close()

# Now let's understand the actual page scale
# In approval_sheet, page 0 is 1191x842 pt (A4 landscape)
# The labels are placed as cells in a grid

# Check the approval_pdf_service to understand layout
print("\n=== Checking approval PDF service ===")
import ast, sys
with open("backend/services/approval_pdf_service.py", 'r', encoding='utf-8') as f:
    content = f.read()
# Print relevant layout sections
lines = content.split('\n')
for i, line in enumerate(lines):
    if any(kw in line for kw in ['OUTER_W', 'OUTER_H', 'col', 'row', 'scale', 'matrix', 'dpi', 'zoom']):
        print(f"  L{i+1}: {line.rstrip()}")
