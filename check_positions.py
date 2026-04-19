import fitz

doc = fitz.open('test_v10_approval.pdf')
pg = doc[0]
blocks = pg.get_text('dict')['blocks']
for b in blocks:
    if b.get('type') == 0:
        for line in b.get('lines', []):
            for span in line.get('spans', []):
                t = span['text'].strip()
                if t in ('4-5','5-6','6-7','7-8','8-9','9-10') and span['size'] < 8:
                    ox = span['origin'][0]
                    oy = span['origin'][1]
                    print(f"chip {t!r} @ x={round(ox,2)} y={round(oy,2)} sz={round(span['size'],2)}")
doc.close()

# Also check barcode image positions
print("\nBarcode images:")
doc2 = fitz.open('test_v10_approval.pdf')
pg2 = doc2[0]
for info in pg2.get_image_info(hashes=False):
    bbox = info['bbox']
    if 200 < bbox[0] < 360 and 380 < bbox[1] < 450:
        print(f"  barcode: bbox=({round(bbox[0],1)},{round(bbox[1],1)},{round(bbox[2],1)},{round(bbox[3],1)}) "
              f"display={round(bbox[2]-bbox[0],1)}x{round(bbox[3]-bbox[1],1)}pt")
doc2.close()
