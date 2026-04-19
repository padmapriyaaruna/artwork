"""
Extract the ACTUAL back-of-label template page from the master PDF.
Page 2 (index 1) shows Code:TOK100.
We need to extract the back of the label (right panel) as a standalone design.

Also does a detailed text dump of the master page 2 back-label area
to understand the exact coordinates and font structure.
"""
import fitz
import os

os.makedirs('compare_output', exist_ok=True)

doc = fitz.open("_OVS KIDS 2023.pdf")

# ── Page 2 (index 1) — TOK100 template page ─────────────────────────────────
page = doc[1]
print("Page 2 size:", page.rect)

# Full text extraction
blocks = page.get_text('dict')
print()
print("=== ALL TEXT SPANS (page 2) ===")
for b in blocks['blocks']:
    if b['type'] == 0:
        for line in b['lines']:
            for span in line['spans']:
                txt = span['text'].strip()
                if txt:
                    print("  [%5.1fpt %-30s] %r  @ bbox=%s" % (
                        span['size'], span['font'][:30], txt[:60],
                        '[%.0f,%.0f,%.0f,%.0f]' % tuple(span['bbox'])
                    ))

print()
print("=== IMAGES on page 2 ===")
for b in blocks['blocks']:
    if b['type'] == 1:
        print("  image bbox:", b['bbox'])

# Render page 2 at high DPI for visual inspection
mat = fitz.Matrix(3, 3)
pix = page.get_pixmap(matrix=mat)
pix.save('compare_output/master_p2_3x.png')
print()
print("Rendered page 2 at 3x zoom -> compare_output/master_p2_3x.png")

# Crop just the BACK label area (right portion of page 2)
# From visual inspection the back label is roughly right half
# Page is 1190x841, back label roughly at x=580.. 920, y=90..490
clip = fitz.Rect(580, 90, 920, 500)
pix2 = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=clip)
pix2.save('compare_output/master_p2_back_label.png')
print("Cropped BACK label area -> compare_output/master_p2_back_label.png")

doc.close()
