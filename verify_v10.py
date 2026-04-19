# v10 fix analysis — numerical verification
import fitz

print("=== v10 Numerical Verification ===\n")

doc = fitz.open("test_v10_approval.pdf")
pg = doc[0]

# Check barcode image dimensions
img_infos = pg.get_image_info(hashes=False)
print("Barcode images in v10:")
for info in img_infos:
    if info["width"] == 200 or (info["width"] > 150 and info["width"] < 250):
        bbox = info["bbox"]
        h = bbox[3] - bbox[1]
        w = bbox[2] - bbox[0]
        print(f"  bbox={[round(v,1) for v in bbox]}, display={round(w,1)}x{round(h,1)}pt")

print()

# Check currency symbol  
blocks = pg.get_text("dict")["blocks"]
for b in blocks:
    if b.get("type") == 0:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                # Currency symbol is chr(128) in WinAnsi
                if t and ord(t[0]) == 128:
                    print(f"Currency symbol size: {round(span['size'],2)}pt (was 7.5pt, target ~20pt)")

# Check size chip positions
for b in blocks:
    if b.get("type") == 0:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t in ("4-5", "5-6", "6-7", "7-8", "8-9", "9-10") and span["size"] > 7.0 and span["font"] and "Helvetica" in span["font"]:
                    print(f"  Size chip '{t}' @ y={round(span['origin'][1],1)} sz={round(span['size'],2)} font={span['font']}")

doc.close()

# Also check actual ref for comparison
print("\n=== ACTUAL PDF Reference ===")
doc2 = fitz.open("TOK100_B0854559_1.pdf")
pg2 = doc2[0]
blocks2 = pg2.get_text("dict")["blocks"]
for b in blocks2:
    if b.get("type") == 0:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t and ord(t[0]) == 128:
                    print(f"Currency symbol size in ACTUAL: {round(span['size'],2)}pt")
                    break
doc2.close()
