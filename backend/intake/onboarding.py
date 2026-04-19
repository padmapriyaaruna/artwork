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

from backend.intake.auto_zone_mapper import auto_generate_zone_map

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
    xml_records:   list[dict] | None = None,
) -> dict:
    """
    Store a customer's PDF template and auto-generate the zone_map.json.

    Uses auto_zone_mapper to detect variable zones automatically via:
      - Pass 1: Placeholder text patterns ({{field_name}}, {FIELD}, etc.)
      - Pass 2: XML value matching (find actual values from XML in the PDF)
      - Pass 3: Heuristic recognition (13-digit = barcode, price formats, etc.)

    If xml_records is supplied, Passes 2 and 3 are also active, giving the
    highest detection accuracy. Without xml_records, only Pass 1 + 3 run.

    Args:
        customer_code: e.g. "ZARA"
        label_type:    e.g. "WVN50"
        pdf_path:      Path to the uploaded template PDF.
        xml_records:   Optional list of parsed item_data dicts from the XML
                       (pass these for best detection accuracy).

    Returns:
        {
            "template_stored": str,  path to saved template.pdf
            "zone_map":        str,  path to created zone_map.json
            "dimensions":      {"width": float, "height": float},
            "zones_detected":  int,
            "confidence":      str   ("high" / "medium" / "low")
        }
    """
    folder = create_customer_folder(customer_code, label_type)

    # Copy the uploaded PDF into the templates folder
    dest_pdf = folder / "template.pdf"
    shutil.copy2(str(pdf_path), str(dest_pdf))

    # Auto-detect variable zones from the template + XML records
    zone_map = auto_generate_zone_map(
        template_pdf_path=dest_pdf,
        xml_records=xml_records or [],
        customer_code=customer_code,
        label_type=label_type,
    )

    # Persist zone_map.json
    zone_map_path = folder / "zone_map.json"
    with open(zone_map_path, "w", encoding="utf-8") as f:
        json.dump(zone_map, f, indent=2)

    dims = {
        "width":  zone_map["page_width_pt"],
        "height": zone_map["page_height_pt"],
    }
    n_zones = len(zone_map["variable_zones"])

    return {
        "template_stored": str(dest_pdf),
        "zone_map":        str(zone_map_path),
        "dimensions":      dims,
        "zones_detected":  n_zones,
        "confidence":      zone_map.get("detection_confidence", "low"),
    }


# ── Full onboarding pipeline ─────────────────────────────────────────────────

def onboard_template(
    customer_code: str,
    label_type:    str,
    pdf_path:      Path,
    xml_records:   list[dict] | None = None,
) -> dict:
    """
    Full first-time onboarding for a new customer template.

    Called from zip_intake when mode == "xml_plus_template".
    Automatically detects variable zones from the template PDF + XML records.

    Args:
        customer_code: e.g. "ZARA"
        label_type:    e.g. "WVN50"
        pdf_path:      Path to the uploaded template PDF
        xml_records:   Parsed item_data dicts from the XML (for best accuracy)

    Returns:
        Result dict from ingest_pdf_template.
    """
    result = ingest_pdf_template(customer_code, label_type, pdf_path, xml_records)

    confidence = result.get("confidence", "low")
    n_zones    = result.get("zones_detected", 0)

    print(f"[ONBOARD] Customer registered: {customer_code}/{label_type}")
    print(f"  Template   : {result['template_stored']}")
    print(f"  Zone map   : {result['zone_map']}")
    print(f"  Zones found: {n_zones} (confidence: {confidence})")

    if confidence == "low" or n_zones == 0:
        print(
            f"  ⚠ Low detection confidence — consider adding placeholder text\n"
            f"    to the template PDF (e.g. {{{{barcode_number}}}}, {{{{selling_price}}}})\n"
            f"    then re-upload. Or manually review: {result['zone_map']}"
        )
    else:
        print(f"  ✅ Auto-detection complete — labels ready to generate.")

    # TODO: register in PostgreSQL (customer_templates table)
    # from backend.database import get_db
    # await register_in_db(customer_code, label_type, result)

    return result
