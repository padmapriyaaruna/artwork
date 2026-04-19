"""
Precision analysis of actual PDF back panel and generated PDF back panel.
Focus on:
1. Exact line/border positions
2. YEARS/IT table exact coordinates
3. Size chip exact positions
4. Barcode image positions  
5. Price positions
"""
import fitz
from PIL import Image

# ─────────────────────────────────────────────────────────────
# ACTUAL PDF analysis (TOK100_B0854559_1.pdf)
# Page size: 2004.1 x 1417.3 pt
# From previous extraction, FIRST back-panel label (size 4-5):
#   YEARS at y=?, barcode at 573.8, price EUR at 657.74
# ─────────────────────────────────────────────────────────────
print("="*60)
print("ACTUAL PDF — Complete back-panel text dump")
doc = fitz.open("TOK100_B0854559_1.pdf")
pg = doc[0]
pw, ph = pg.rect.width, pg.rect.height
print(f"  Page: {pw:.1f} x {ph:.1f} pt")

# Get ALL text
blocks = pg.get_text("dict")["blocks"]
all_texts = []
for b in blocks:
    if b.get("type") == 0:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t:
                    all_texts.append({
                        "text": t,
                        "x": round(span["origin"][0], 2),
                        "y": round(span["origin"][1], 2),
                        "size": round(span["size"], 2),
                        "font": span["font"][:30],
                    })

# Sort by y then x
all_texts.sort(key=lambda t: (round(t["y"]/2)*2, t["x"]))

# Focus on the first back panel (x approximately 560-790, y 250-700)
# From analysis: "Back" label is at x=638.0, y=347.86
# Panel starts at ~x=558, y=273 (panel outer left top)
print("\n  Texts in first back-panel region (x=550-800, y=270-700):")
panel_texts = [t for t in all_texts if 550 <= t["x"] <= 800 and 270 <= t["y"] <= 700]
for t in panel_texts:
    print(f"    '{t['text']}' @ ({t['x']}, {t['y']}) sz={t['size']} [{t['font']}]")

# Get drawings/paths in the page — specifically horizontal lines
print("\n  Drawings in back-panel zone (x=550-800, y=270-700):")
drawings = pg.get_drawings()
panel_drawings = []
for d in drawings:
    rect = d.get("rect")
    if rect and 550 <= rect.x0 <= 800 and 270 <= rect.y0 <= 700:
        panel_drawings.append(d)

for d in panel_drawings[:30]:
    print(f"    type={d.get('type')} rect={[round(v,2) for v in d.get('rect', [0,0,0,0])]} "
          f"color={d.get('color')} width={d.get('width',0):.2f}")

# Image info
print("\n  Images in back-panel zone:")
for info in pg.get_image_info(hashes=False):
    bbox = info["bbox"]
    if 550 <= bbox[0] <= 800 and 270 <= bbox[1] <= 700:
        print(f"    bbox={[round(v,2) for v in bbox]} "
              f"display={round(bbox[2]-bbox[0],2)}x{round(bbox[3]-bbox[1],2)}pt "
              f"src={info['width']}x{info['height']}px")

doc.close()

# ─────────────────────────────────────────────────────────────
# GENERATED PDF analysis
# Page size: 1191 x 842 pt
# First back panel at ox≈203.75, oy=190
# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("GENERATED PDF — Complete back-panel text dump")
doc2 = fitz.open("approval_sheet_B0854559 (12).pdf")
pg2 = doc2[0]
pw2, ph2 = pg2.rect.width, pg2.rect.height
print(f"  Page: {pw2:.1f} x {ph2:.1f} pt")

# First back panel spans ox=203.75 to ox+150.3=354.05, oy=190 to oy+305.5=495.5
blocks2 = pg2.get_text("dict")["blocks"]
all_texts2 = []
for b in blocks2:
    if b.get("type") == 0:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t:
                    all_texts2.append({
                        "text": t,
                        "x": round(span["origin"][0], 2),
                        "y": round(span["origin"][1], 2),
                        "size": round(span["size"], 2),
                        "font": span["font"][:30],
                    })

all_texts2.sort(key=lambda t: (round(t["y"]/2)*2, t["x"]))
print("\n  Texts in first back-panel region (x=203-354, y=188-496):")
panel_texts2 = [t for t in all_texts2 if 200 <= t["x"] <= 360 and 185 <= t["y"] <= 500]
for t in panel_texts2:
    print(f"    '{t['text']}' @ ({t['x']}, {t['y']}) sz={t['size']} [{t['font']}]")

print("\n  Drawings in first back-panel zone:")
drawings2 = pg2.get_drawings()
panel_drawings2 = [d for d in drawings2 if d.get("rect") and
                   200 <= d["rect"].x0 <= 360 and 185 <= d["rect"].y0 <= 500]
for d in panel_drawings2[:20]:
    print(f"    type={d.get('type')} rect={[round(v,2) for v in d.get('rect',[0,0,0,0])]} "
          f"color={d.get('color')} width={d.get('width',0):.2f}")

print("\n  Images in first back-panel zone:")
for info in pg2.get_image_info(hashes=False):
    bbox = info["bbox"]
    if 200 <= bbox[0] <= 360 and 185 <= bbox[1] <= 500:
        print(f"    bbox={[round(v,2) for v in bbox]} "
              f"display={round(bbox[2]-bbox[0],2)}x{round(bbox[3]-bbox[1],2)}pt "
              f"src={info['width']}x{info['height']}px")

doc2.close()
