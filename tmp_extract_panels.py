"""Extract both front and back panel templates from reference PDF."""
import fitz, os

SRC = r"TOK100_B0854559_1.pdf"
OUT = r"backend/templates/OVS/TOK100"
os.makedirs(OUT, exist_ok=True)

doc = fitz.open(SRC)
page = doc[0]
mat = fitz.Matrix(300/72, 300/72)

panels = {
    "front_panel_ref": fitz.Rect(416.8, 372.0, 567.1, 677.5),
    "back_panel_ref":  fitz.Rect(586.4, 372.8, 736.7, 678.2),
}

for name, src_rect in panels.items():
    W, H = src_rect.width, src_rect.height
    ndoc = fitz.open()
    pg = ndoc.new_page(width=W, height=H)
    pg.show_pdf_page(fitz.Rect(0, 0, W, H), doc, 0, clip=src_rect)
    path = os.path.join(OUT, f"{name}.pdf")
    ndoc.save(path, garbage=4, deflate=True)
    ndoc.close()
    print(f"Saved {path}  ({os.path.getsize(path):,} bytes  {W:.1f}x{H:.1f}pt)")
    # Preview PNG
    vdoc = fitz.open(path)
    pix = vdoc[0].get_pixmap(matrix=fitz.Matrix(300/72, 300/72), alpha=False)
    pix.save(os.path.join(OUT, f"{name}_preview.png"))
    vdoc.close()
    print(f"  preview PNG saved")

doc.close()
print("Done.")
