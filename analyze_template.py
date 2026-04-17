"""Analyze _OVS KIDS 2023.pdf master template - extract all structure, dimensions, text blocks, images."""
import fitz
import json
import os
import sys

# Force UTF-8 stdout on Windows
sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = "_OVS KIDS 2023.pdf"
OUT_DIR = "template_analysis"
os.makedirs(OUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)
print(f"Total pages: {doc.page_count}")
print()

all_info = {}
for page_idx in range(doc.page_count):
    page = doc[page_idx]
    w_pt = page.rect.width
    h_pt = page.rect.height
    w_mm = w_pt * 25.4 / 72
    h_mm = h_pt * 25.4 / 72

    print("=" * 70)
    print(f"PAGE {page_idx+1}: {w_pt:.1f} x {h_pt:.1f} pt  =  {w_mm:.1f} x {h_mm:.1f} mm")
    print("=" * 70)

    # Render high-res PNG
    mat = fitz.Matrix(3, 3)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_path = f"{OUT_DIR}/page_{page_idx+1:02d}.png"
    pix.save(png_path)
    print(f"  Saved: {png_path}")

    # Text blocks
    print(f"\n  TEXT BLOCKS:")
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    text_entries = []
    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                txt = span["text"].strip()
                if not txt:
                    continue
                bbox = span["bbox"]
                font = span.get("font", "")
                size = span.get("size", 0)
                color_raw = span.get("color", 0)
                r = (color_raw >> 16) & 0xFF
                g = (color_raw >> 8) & 0xFF
                bc = color_raw & 0xFF
                entry = {
                    "text": txt,
                    "x0_mm": round(bbox[0]*25.4/72, 1),
                    "y0_mm": round(bbox[1]*25.4/72, 1),
                    "x1_mm": round(bbox[2]*25.4/72, 1),
                    "y1_mm": round(bbox[3]*25.4/72, 1),
                    "font": font,
                    "size_pt": round(size, 1),
                    "color_rgb": [r, g, bc],
                }
                text_entries.append(entry)
                color_str = f"rgb({r},{g},{bc})"
                safe_txt = txt[:80].encode('ascii', errors='replace').decode('ascii')
                print(f"    [{bbox[0]:.0f},{bbox[1]:.0f}->{bbox[2]:.0f},{bbox[3]:.0f}]  "
                      f"pt={size:.1f}  col={color_str}  font={font[:25]}  \"{safe_txt}\"")

    # Images
    print(f"\n  IMAGES:")
    img_list = page.get_images(full=True)
    for img_info in img_list:
        xref = img_info[0]
        w_px, h_px = img_info[2], img_info[3]
        cs = img_info[5]
        name = img_info[7]
        rects = page.get_image_rects(xref)
        for r in rects:
            w_img_mm = (r.x1 - r.x0) * 25.4 / 72
            h_img_mm = (r.y1 - r.y0) * 25.4 / 72
            print(f"    xref={xref} px={w_px}x{h_px} cs={cs} name={name}")
            print(f"      pos: [{r.x0:.0f},{r.y0:.0f}->{r.x1:.0f},{r.y1:.0f}]  "
                  f"= {w_img_mm:.1f}x{h_img_mm:.1f}mm")

    # Drawings summary
    drawings = page.get_drawings()
    print(f"\n  DRAWINGS: {len(drawings)} paths")
    if drawings:
        xs = [d["rect"].x0 for d in drawings] + [d["rect"].x1 for d in drawings]
        ys = [d["rect"].y0 for d in drawings] + [d["rect"].y1 for d in drawings]
        print(f"    extent: x=[{min(xs):.0f},{max(xs):.0f}]  y=[{min(ys):.0f},{max(ys):.0f}]")
        for d in drawings[:6]:
            r = d["rect"]
            print(f"    [{r.x0:.0f},{r.y0:.0f}->{r.x1:.0f},{r.y1:.0f}]  "
                  f"fill={d.get('fill')}  stroke={d.get('color')}")

    all_info[f"page_{page_idx+1}"] = {
        "width_mm": round(w_mm,1),
        "height_mm": round(h_mm,1),
        "text_blocks": text_entries,
        "image_count": len(img_list),
        "drawing_count": len(drawings),
    }
    print()

doc.close()

with open(f"{OUT_DIR}/structure.json", "w", encoding="utf-8") as f:
    json.dump(all_info, f, indent=2, ensure_ascii=False)
print(f"Saved structure.json and {doc.page_count} PNGs to {OUT_DIR}/")
