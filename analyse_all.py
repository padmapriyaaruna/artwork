"""
Deep analysis of all three PDFs:
1. _OVS KIDS 2023.pdf   — master design template
2. TOK100_B0854559_1.pdf — actual approved output
3. approval_sheet_B0854559 (12).pdf — our generated output

Extract:
- High-res page renders (300 DPI)
- Back panel crops for each label
- Text positions with font sizes
- Image (barcode) bounding boxes
- Line path coordinates
"""
import fitz
from PIL import Image
import json, os

PDFs = {
    "master":  "_OVS KIDS 2023.pdf",
    "actual":  "TOK100_B0854559_1.pdf",
    "gen":     "approval_sheet_B0854559 (12).pdf",
}

DPI = 200   # render DPI

results = {}

for tag, fname in PDFs.items():
    if not os.path.exists(fname):
        print(f"MISSING: {fname}")
        continue

    doc = fitz.open(fname)
    pg  = doc[0]
    pw, ph = pg.rect.width, pg.rect.height

    print(f"\n{'='*60}")
    print(f"[{tag}] {fname}")
    print(f"  Page size: {pw:.1f} x {ph:.1f} pt")
    print(f"  Pages: {len(doc)}")

    # Render page 0 at DPI
    mat = fitz.Matrix(DPI/72, DPI/72)
    pix = pg.get_pixmap(matrix=mat, alpha=False)
    out_img = f"analysis_{tag}_p0.png"
    pix.save(out_img)
    print(f"  Rendered: {out_img} ({pix.width}x{pix.height}px)")

    # Extract all text with positions
    blocks = pg.get_text("dict")["blocks"]
    texts = []
    for b in blocks:
        if b.get("type") == 0:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if t:
                        texts.append({
                            "text": t,
                            "x": round(span["origin"][0], 2),
                            "y": round(span["origin"][1], 2),
                            "size": round(span["size"], 2),
                            "font": span["font"],
                            "color": span.get("color", 0),
                        })

    # Extract image bounding boxes
    images = []
    for info in pg.get_image_info(hashes=False):
        bbox = info["bbox"]
        images.append({
            "x0": round(bbox[0], 2), "y0": round(bbox[1], 2),
            "x1": round(bbox[2], 2), "y1": round(bbox[3], 2),
            "w_pt": round(bbox[2]-bbox[0], 2),
            "h_pt": round(bbox[3]-bbox[1], 2),
            "w_px": info["width"], "h_px": info["height"],
        })

    # Extract paths (lines)
    paths = pg.get_drawings()
    lines = []
    for p in paths:
        if p.get("type") == "l":  # line
            lines.append({
                "x0": round(p["rect"].x0, 2), "y0": round(p["rect"].y0, 2),
                "x1": round(p["rect"].x1, 2), "y1": round(p["rect"].y1, 2),
                "color": str(p.get("color")), "width": round(p.get("width", 0), 2),
            })

    results[tag] = {"texts": texts, "images": images, "lines": len(lines)}

    # Print key items for inspection
    print(f"\n  KEY TEXTS (first 40):")
    for t in texts[:40]:
        print(f"    '{t['text']}' @ ({t['x']},{t['y']}) sz={t['size']} font={t['font'][:20]}")

    print(f"\n  IMAGES ({len(images)}):")
    for img in images[:10]:
        print(f"    bbox=({img['x0']},{img['y0']},{img['x1']},{img['y1']}) "
              f"display={img['w_pt']}x{img['h_pt']}pt  src={img['w_px']}x{img['h_px']}px")

    print(f"\n  PATHS (line count): {len(lines)}")
    doc.close()

print("\n\nDone analysing all PDFs.")
