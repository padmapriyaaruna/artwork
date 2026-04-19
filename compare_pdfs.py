"""Deep PDF comparison: master template vs TOK100 reference vs generated approval."""
import fitz
import os, json

os.makedirs('compare_output', exist_ok=True)

def extract_text_blocks(pdf_path, max_pages=3):
    doc = fitz.open(pdf_path)
    result = []
    for i in range(min(max_pages, doc.page_count)):
        page = doc[i]
        page_info = {
            "page": i+1,
            "size": list(page.rect),
            "text_spans": [],
            "images": [],
        }
        blocks = page.get_text('dict')
        for b in blocks['blocks']:
            if b['type'] == 0:  # text block
                for line in b['lines']:
                    for span in line['spans']:
                        txt = span['text'].strip()
                        if txt:
                            page_info["text_spans"].append({
                                "text": txt,
                                "font": span["font"],
                                "size": round(span["size"], 2),
                                "color": span["color"],
                                "bbox": [round(x, 2) for x in span["bbox"]],
                            })
            elif b['type'] == 1:  # image block
                page_info["images"].append({
                    "bbox": [round(x, 2) for x in b["bbox"]],
                    "width": b.get("width"),
                    "height": b.get("height"),
                })
        result.append(page_info)
    doc.close()
    return result


print("=== MASTER TEMPLATE (_OVS KIDS 2023.pdf) ===")
master = extract_text_blocks(r"_OVS KIDS 2023.pdf", max_pages=1)
for pg in master:
    print(f"Page {pg['page']} size: {pg['size']}")
    print(f"  Text spans ({len(pg['text_spans'])}):")
    for s in pg['text_spans']:
        print(f"    [{s['size']}pt {s['font']}] '{s['text']}' @ {s['bbox']}")
    print(f"  Images ({len(pg['images'])}):")
    for im in pg['images']:
        print(f"    bbox={im['bbox']}")

print()
print("=== TOK100 REFERENCE (TOK100_B0854559_1.pdf) ===")
tok100 = extract_text_blocks(r"TOK100_B0854559_1.pdf", max_pages=2)
for pg in tok100:
    print(f"Page {pg['page']} size: {pg['size']}")
    print(f"  Text spans ({len(pg['text_spans'])}):")
    for s in pg['text_spans']:
        print(f"    [{s['size']}pt {s['font']}] '{s['text']}' @ {s['bbox']}")
    print(f"  Images ({len(pg['images'])}):")
    for im in pg['images']:
        print(f"    bbox={im['bbox']}")

print()
print("=== XML DATA (B0854559) ===")
import lxml.etree as ET
tree = ET.parse(r"B0854559 TAG007061 1299052.xml")
root = tree.getroot()
# Print first item's key fields
items = root.findall('.//{*}item') or root.findall('.//item')
if not items:
    items = root.findall('.//{*}LabelItem') or root.findall('.//LabelItem')
print(f"Found {len(items)} item elements")
if items:
    first = items[0]
    for child in first:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        print(f"  {tag}: '{child.text}'")

print()
print("=== APPROVAL SHEET (generated) ===")
approval = extract_text_blocks(r"approval_sheet_B0854559.pdf", max_pages=1)
for pg in approval:
    print(f"Page {pg['page']} size: {pg['size']}")
    print(f"  Text spans ({len(pg['text_spans'])}):")
    for s in pg['text_spans']:
        print(f"    [{s['size']}pt {s['font']}] '{s['text']}' @ {s['bbox']}")

# Save full JSON for later inspection
with open('compare_output/analysis.json', 'w', encoding='utf-8') as f:
    json.dump({
        "master": master,
        "tok100": tok100,
        "approval": approval,
    }, f, indent=2, ensure_ascii=False)
print("\nFull analysis saved to compare_output/analysis.json")
