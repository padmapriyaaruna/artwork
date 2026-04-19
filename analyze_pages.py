import fitz
import json

def extract_text_items(pdf_path, page_idx=0):
    doc = fitz.open(pdf_path)
    pg = doc[page_idx]
    print(f"Page {page_idx}: {pg.rect.width:.1f} x {pg.rect.height:.1f} pts")
    blocks = pg.get_text('dict')['blocks']
    items = []
    for b in blocks:
        if b.get('type') == 0:
            for line in b.get('lines', []):
                for span in line.get('spans', []):
                    t = span['text'].strip()
                    if t:
                        items.append({
                            'text': t,
                            'x': round(span['origin'][0], 1),
                            'y': round(span['origin'][1], 1),
                            'size': round(span['size'], 2),
                            'font': span['font']
                        })
    doc.close()
    return items

print("=== ACTUAL: TOK100_B0854559_1.pdf Page 0 ===")
items = extract_text_items("TOK100_B0854559_1.pdf", 0)
for it in items:
    print(f"  '{it['text']}' @ ({it['x']},{it['y']}) sz={it['size']} font={it['font']}")

print()
print("=== GENERATED: approval_sheet_B0854559 (10).pdf Page 0 ===")
items2 = extract_text_items("approval_sheet_B0854559 (10).pdf", 0)
for it in items2:
    print(f"  '{it['text']}' @ ({it['x']},{it['y']}) sz={it['size']} font={it['font']}")
