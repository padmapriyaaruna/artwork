"""
Compare all 3 PDFs and dump full XML for country fields.
"""
import fitz, sys, os, lxml.etree as ET

# ── Render comparison pages ───────────────────────────────────────────────────
PDFS = {
    "master":   ("_OVS KIDS 2023.pdf",               [3, 4]),   # pages 4 & 5 (0-indexed)
    "actual":   ("TOK100_B0854559_1.pdf",             [0]),
    "generated":("approval_sheet_B0854559 (6).pdf",   [0]),
}

for label, (path, pages) in PDFS.items():
    if not os.path.exists(path):
        print(f"MISSING: {path}")
        continue
    doc = fitz.open(path)
    mat = fitz.Matrix(200/72, 200/72)
    for pi in pages:
        if pi < doc.page_count:
            pix = doc[pi].get_pixmap(matrix=mat, alpha=False)
            out = f"cmp_{label}_pg{pi+1}.png"
            pix.save(out)
            print(f"Saved {out}  ({pix.width}x{pix.height}px)")
    doc.close()

# ── Render FRONT panel from actual at 400 DPI ─────────────────────────────────
doc = fitz.open("TOK100_B0854559_1.pdf")
page = doc[0]
mat = fitz.Matrix(400/72, 400/72)
# Front panel: (416.8, 372.0, 567.1, 677.5)
pix = page.get_pixmap(matrix=mat,
                      clip=fitz.Rect(416.8, 372.0, 567.1, 677.5), alpha=False)
pix.save("cmp_front_panel_400dpi.png")
print(f"Saved cmp_front_panel_400dpi.png  ({pix.width}x{pix.height}px)")

# Back label zone B (logos area): y_rel 183-260 of panel 1
pix2 = page.get_pixmap(matrix=mat,
                       clip=fitz.Rect(586.4, 372.8+183, 736.7, 372.8+260), alpha=False)
pix2.save("cmp_back_zoneB_400dpi.png")
print(f"Saved cmp_back_zoneB_400dpi.png  ({pix2.width}x{pix2.height}px)")

# The "KIDS to size" transition area: y_rel 57-155
pix3 = page.get_pixmap(matrix=mat,
                       clip=fitz.Rect(586.4, 372.8+57, 736.7, 372.8+155), alpha=False)
pix3.save("cmp_back_kids_to_size_400dpi.png")
print(f"Saved cmp_back_kids_to_size_400dpi.png  ({pix3.width}x{pix3.height}px)")
doc.close()

# ── Measure exact front panel elements ───────────────────────────────────────
print("\n=== FRONT PANEL EXACT PATHS ===")
doc = fitz.open("TOK100_B0854559_1.pdf")
page = doc[0]
paths = page.get_drawings()
FX0, FY0, FX1, FY1 = 416.8, 372.0, 567.1, 677.5
front_paths = [p for p in paths
               if p["rect"] and
               p["rect"].x0 >= FX0-5 and p["rect"].x1 <= FX1+5 and
               p["rect"].y0 >= FY0-5 and p["rect"].y1 <= FY1+5]
print(f"Front panel paths: {len(front_paths)}")
for p in sorted(front_paths, key=lambda x: (x["rect"].height * x["rect"].width), reverse=True)[:15]:
    r = p["rect"]
    fill = p.get("fill")
    col  = p.get("color")
    lw   = p.get("width",0)
    print(f"  ({r.x0-FX0:.1f},{r.y0-FY0:.1f})->({r.x1-FX0:.1f},{r.y1-FY0:.1f})"
          f" {r.width:.1f}x{r.height:.1f}"
          f" fill={[round(x,3) for x in fill] if fill else None}"
          f" stroke={[round(x,3) for x in col] if col else None}"
          f" lw={lw}")

# Front panel text
print("\n=== FRONT PANEL TEXT ===")
for b in page.get_text("dict")["blocks"]:
    if b["type"] == 0:
        for ln in b["lines"]:
            for sp in ln["spans"]:
                r = sp["bbox"]
                if FX0 <= r[0] <= FX1 and FY0 <= r[1] <= FY1:
                    print(f"  y={r[1]-FY0:.1f} x={r[0]-FX0:.1f} [{sp['size']:.1f}pt] {repr(sp['text'])}")
doc.close()

# ── Dump ALL country fields across all XML items ──────────────────────────────
print("\n=== XML COUNTRY FIELDS (all items) ===")
tree = ET.parse("B0854559 TAG007061 1299052.xml")
root = tree.getroot()
items = root.findall(".//OrderItem/Item")
print(f"Total items: {len(items)}")
for idx, item in enumerate(items):
    vars_el = item.find("Variables")
    if vars_el is None:
        continue
    country_val = None
    made_in_val = None
    for v in vars_el.findall("Variable"):
        q  = v.get("Question","")
        lt = v.get("LookupListType","")
        q_lower = q.lower()
        if "country" in q_lower or "made" in q_lower or "origin" in q_lower:
            a = v.find("Answer")
            if a is not None:
                for av in a.findall("AnswerValues/AnswerValue"):
                    print(f"  item[{idx:02d}] Q={q!r} Name={av.get('Name')!r} val={av.text!r}")
            else:
                print(f"  item[{idx:02d}] Q={q!r} (no answer)")
