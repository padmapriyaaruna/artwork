"""Quick test: generate a test approval PDF with the fixed builder."""
import sys, os
sys.path.insert(0, ".")

from backend.engine.customers.ovs.tok100_renderer import build_label_pdf, build_label_png
from backend.services.approval_pdf_service import create_approval_sheet_pdf

# Test data from B0854559
test_sizes = [
    {"4-5": "110"},
    {"5-6": "116"},
    {"6-7": "122"},
    {"7-8": "128"},
    {"8-9": "134"},
    {"9-10": "140"},
]

barcode_map = {
    "4-5":  "8051553298804",
    "5-6":  "8051553298811",
    "6-7":  "8051553298818",
    "7-8":  "8051553298825",
    "8-9":  "8051553298832",
    "9-10": "8051553298849",
}

size_labels = ["4-5", "5-6", "6-7", "7-8", "8-9", "9-10"]

variants = []
for sz in size_labels:
    variants.append({
        "sizes": {"YEARS": sz, "IT": sz, "MEX": sz, "CM": ["110","116","122","128","134","140"][size_labels.index(sz)]},
        "barcode_number": barcode_map[sz],
        "style_code": "2768957",
        "commercial_ref": "PR711 AI08",
        "sub_department": "3632",
        "department": "230",
        "sku_code": str(2768960 + size_labels.index(sz)),
        "country_of_origin": "WARM",
        "currency_symbol": "\u20ac",
        "selling_price": "29,95",
        "quantity": 128,
    })

order_data = {
    "buyer": "OVS",
    "customer_name": "OVS SPA",
    "design_code": "262SWT301LT",
    "product_code": "B0854559",
    "submitted_date": "2024-01-15",
}

variant_groups = [{
    "country": "WARM",
    "title": "262SWT301LT-230 - WARM - EGGNOG - B0854559",
    "label_size": "45mm x 100mm",
    "variants": variants,
}]

print("Generating test approval PDF...")
pdf_bytes = create_approval_sheet_pdf(order_data, variant_groups)
with open("test_v10_approval.pdf", "wb") as f:
    f.write(pdf_bytes)
print(f"Written test_v10_approval.pdf ({len(pdf_bytes)//1024} KB)")

# Also render as PNG for visual check
import fitz
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
for i, pg in enumerate(doc):
    pix = pg.get_pixmap(matrix=fitz.Matrix(200/72, 200/72), alpha=False)
    pix.save(f"test_v10_page{i}.png")
    print(f"  Saved test_v10_page{i}.png ({pix.width}x{pix.height}px)")
doc.close()

# Verify currency symbol size
doc2 = fitz.open("test_v10_approval.pdf")
pg2 = doc2[0]
blocks = pg2.get_text("dict")["blocks"]
for b in blocks:
    if b.get("type") == 0:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t and (t[0] == chr(128) or "29" in t or "YEARS" in t or "4-5" in t):
                    print(f"  Text '{t}' sz={round(span['size'],2)} @ ({round(span['origin'][0],1)},{round(span['origin'][1],1)})")
doc2.close()
print("Done!")
