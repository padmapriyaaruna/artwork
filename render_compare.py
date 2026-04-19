import fitz

def render_page(pdf_path, page_idx=0, dpi=200, out_path=None):
    doc = fitz.open(pdf_path)
    pg = doc[page_idx]
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = pg.get_pixmap(matrix=mat, alpha=False)
    if out_path:
        pix.save(out_path)
    doc.close()
    return pix

# Render actual reference PDF page 0
render_page("TOK100_B0854559_1.pdf", 0, dpi=150, out_path="cmp_actual_ref_p0.png")
print("Rendered actual PDF page 0 -> cmp_actual_ref_p0.png")

# Render generated approval sheet page 0
render_page("approval_sheet_B0854559 (10).pdf", 0, dpi=150, out_path="cmp_gen_p0.png")
print("Rendered generated PDF page 0 -> cmp_gen_p0.png")

# Also render page 1 of the actual (might have TOK100 size chart)
render_page("TOK100_B0854559_1.pdf", 1, dpi=150, out_path="cmp_actual_ref_p1.png")
print("Rendered actual PDF page 1 -> cmp_actual_ref_p1.png")
render_page("approval_sheet_B0854559 (10).pdf", 1, dpi=150, out_path="cmp_gen_p1.png")
print("Rendered generated PDF page 1 -> cmp_gen_p1.png")

# Also check actual PDF page 2
render_page("TOK100_B0854559_1.pdf", 2, dpi=150, out_path="cmp_actual_ref_p2.png")
print("Rendered actual PDF page 2 -> cmp_actual_ref_p2.png")
render_page("approval_sheet_B0854559 (10).pdf", 2, dpi=150, out_path="cmp_gen_p2.png")
print("Rendered generated PDF page 2 -> cmp_gen_p2.png")
