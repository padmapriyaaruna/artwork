"""Test v5 label builder — generate all 6 sizes and approval sheet."""
import sys, os, fitz
sys.path.insert(0, r"C:\AntiGravity_Projects\Art_Work")
from backend.engine.xml_normalizer import parse_bgp_xml_file
from backend.engine.tok100_label_builder import (
    build_label_pdf, build_label_png, FRONT_PANEL_TEMPLATE, BACK_PANEL_TEMPLATE
)
from backend.services.approval_pdf_service import create_approval_sheet_pdf
from collections import defaultdict

print(f"Front template exists: {os.path.exists(FRONT_PANEL_TEMPLATE)}")
print(f"Back  template exists: {os.path.exists(BACK_PANEL_TEMPLATE)}")

order = parse_bgp_xml_file(r"B0854559 TAG007061 1299052.xml")
items = order.items

# Single label test (all 6 sizes)
for i, item in enumerate(items[:6]):
    d = item.to_dict()
    sz = d.get("sizes",{}).get("YEARS","?")
    bc = d.get("barcode_number","?")[:8]
    print(f"  [{i}] YEARS={sz} barcode={bc}... country={d.get('country_of_origin','?')}")
    pdf = build_label_pdf(d)
    png = build_label_png(d, dpi=200)
    with open(f"test_v5_{i}_{sz.replace('-','_')}.pdf","wb") as f: f.write(pdf)
    with open(f"test_v5_{i}_{sz.replace('-','_')}.png","wb") as f: f.write(png)

print(f"\n6 labels generated OK")

# Approval sheet test
by_country = defaultdict(list)
for item in order.items:
    by_country[item.country_of_origin or "UNKNOWN"].append(item)

groups = []
for c, sibs in by_country.items():
    groups.append({
        "country": c,
        "title": f"{sibs[0].supplier_style} - {c} - {sibs[0].color} - {order.bgp_order_id}",
        "label_size": "45mm x 100mm",
        "variants": [s.to_dict() for s in sibs]
    })

order_data = {
    "buyer": "OVS",
    "customer_name": order.customer_name,
    "design_code": "TOK100",
    "product_code": "TAG007061",
    "submitted_date": "18/04/2026",
    "bgp_order_id": order.bgp_order_id
}

pdf = create_approval_sheet_pdf(order_data, groups, {})
with open("test_v5_approval.pdf","wb") as f: f.write(pdf)
doc = fitz.open(stream=pdf, filetype="pdf")
print(f"\nApproval: {len(pdf):,} bytes, {doc.page_count} pages")
for i in range(doc.page_count):
    pix = doc[i].get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
    pix.save(f"test_v5_approval_pg{i+1}.png")
    print(f"  page {i+1}: {doc[i].rect.width:.0f}x{doc[i].rect.height:.0f}")
doc.close()
os.startfile("test_v5_approval.pdf")
print("Done — PDF opened for review")
