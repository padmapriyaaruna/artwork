import fitz

# Check image placements structure
doc = fitz.open("approval_sheet_B0854559 (10).pdf")
pg = doc[0]

# Get image list with dimensions
imgs = pg.get_images(full=True)
print(f"Images in generated page 0: {len(imgs)}")
for img in imgs:
    xref = img[0] 
    w = img[2]
    h = img[3]
    print(f"  xref={xref}: {w}x{h} px")

# Try different API
print("\nImage info keys:", pg.get_image_info(hashes=False)[0].keys() if pg.get_image_info(hashes=False) else "none")

img_info = pg.get_image_info(hashes=False)
for info in img_info[:5]:
    print(f"  info: {info}")

doc.close()

# Also check actual PDF images
print("\n=== ACTUAL PDF images ===")
doc2 = fitz.open("TOK100_B0854559_1.pdf")
pg2 = doc2[0]
imgs2 = pg2.get_images(full=True)
print(f"Images in actual page 0: {len(imgs2)}")
for img in imgs2[:10]:
    xref = img[0]
    w = img[2]
    h = img[3]
    print(f"  xref={xref}: {w}x{h} px")
doc2.close()

# Now let's extract a barcode image from generated for visual inspection  
doc3 = fitz.open("approval_sheet_B0854559 (10).pdf")
pg3 = doc3[0]
imgs3 = pg3.get_images(full=True)

# Extract first small barcode image (190x67)
for img in imgs3:
    xref = img[0]
    w = img[2]
    h = img[3]
    if w == 190 and h == 67:
        pix = fitz.Pixmap(doc3, xref)
        pix.save("cmp_barcode_gen.png")
        print(f"\nSaved barcode image {w}x{h} -> cmp_barcode_gen.png")
        break
doc3.close()
