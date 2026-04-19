# -*- coding: utf-8 -*-
"""
Customer Template Onboarding.

Called when a BRAT zip contains both an XML file AND a PDF template
(mode == "xml_plus_template"). This is the first-time setup flow for
a new customer.

What it does:
  1. Creates the customer folder in backend/templates/{CUST_CODE}/{LABEL_TYPE}/
  2. Stores the uploaded PDF as template.pdf
  3. Creates a starter zone_map.json (operators fill in variable_zones)
  4. Registers the customer in the template registry

Usage:
    from backend.intake.onboarding import onboard_template
    result = onboard_template("ZARA", "WVN50", Path("/tmp/label_template.pdf"))
"""
import json
import shutil
from pathlib import Path

import fitz  # PyMuPDF

TEMPLATE_BASE = Path("backend/templates")


# ── Folder management ────────────────────────────────────────────────────────

def create_customer_folder(customer_code: str, label_type: str) -> Path:
    """
    Create (or ensure) the template folder for a customer + label type.

    Path: backend/templates/{CUSTOMER_CODE}/{LABEL_TYPE}/

    Args:
        customer_code: e.g. "OVS", "ZARA"
        label_type:    e.g. "TOK100", "WVN50"

    Returns:
        Path to the created folder.
    """
    folder = TEMPLATE_BASE / customer_code.upper() / label_type.upper()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ── PDF Template Ingestion ───────────────────────────────────────────────────

def ingest_pdf_template(
    customer_code: str,
    label_type:    str,
    pdf_path:      Path,
) -> dict:
    """
    Store a customer's PDF template and create a starter zone_map.json.

    The zone_map.json is created with an empty variable_zones list.
    An operator (or future AI step) must fill this in to define which
    rectangular areas on the label are variable data vs static artwork.

    Args:
        customer_code: e.g. "ZARA"
        label_type:    e.g. "WVN50"
        pdf_path:      Path to the uploaded template PDF.

    Returns:
        {
            "template_stored": str,  path to saved template.pdf
            "zone_map":        str,  path to created zone_map.json
            "dimensions":      {"width": float, "height": float}
        }
    """
    folder = create_customer_folder(customer_code, label_type)

    # Copy the uploaded PDF into the templates folder
    dest_pdf = folder / "template.pdf"
    shutil.copy2(str(pdf_path), str(dest_pdf))

    # Extract page dimensions for zone_map metadata
    doc   = fitz.open(str(dest_pdf))
    rect  = doc[0].rect
    doc.close()

    # Starter zone_map — operators complete variable_zones
    zone_map = {
        "customer_code":  customer_code.upper(),
        "label_type":     label_type.upper(),
        "page_width_pt":  rect.width,
        "page_height_pt": rect.height,
        "renderer_module": "generic_pdf_renderer",
        # variable_zones: list of dicts, each describing one variable area:
        # {
        #   "id":        "barcode",
        #   "name":      "EAN-13 Barcode",
        #   "field_key": "barcode_number",   # key in item_data
        #   "x0": 10.0, "y0": 150.0,
        #   "x1": 90.0, "y1": 170.0,
        #   "type": "barcode" | "text" | "image"
        # }
        "variable_zones": [],
        "static_template": str(dest_pdf),
    }

    zone_map_path = folder / "zone_map.json"
    with open(zone_map_path, "w", encoding="utf-8") as f:
        json.dump(zone_map, f, indent=2)

    return {
        "template_stored": str(dest_pdf),
        "zone_map":        str(zone_map_path),
        "dimensions":      {"width": rect.width, "height": rect.height},
    }


# ── Full onboarding pipeline ─────────────────────────────────────────────────

def onboard_template(
    customer_code: str,
    label_type:    str,
    pdf_path:      Path,
) -> dict:
    """
    Full first-time onboarding for a new customer template.

    Called from zip_intake when mode == "xml_plus_template".

    Args:
        customer_code: e.g. "ZARA"
        label_type:    e.g. "WVN50"
        pdf_path:      Path to the uploaded template PDF

    Returns:
        Result dict from ingest_pdf_template.

    Side effects:
        - Creates folder backend/templates/{CUST_CODE}/{LABEL_TYPE}/
        - Writes template.pdf and zone_map.json
        - Prints an operator action notice
    """
    result = ingest_pdf_template(customer_code, label_type, pdf_path)

    print(f"[ONBOARD] New customer template registered: {customer_code}/{label_type}")
    print(f"  Template : {result['template_stored']}")
    print(f"  Zone map : {result['zone_map']}")
    print(
        f"  ⚠ ACTION REQUIRED: Open zone_map.json and fill in "
        f"variable_zones to define which label areas contain variable data."
    )

    # TODO: register in PostgreSQL (customer_templates table)
    # from backend.database import get_db
    # await register_in_db(customer_code, label_type, result)

    return result
