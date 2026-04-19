# -*- coding: utf-8 -*-
"""
Artwork Job Service — end-to-end label generation pipeline.

Orchestrates intake → render → save → approval sheet for a BRAT job.

Usage:
    from backend.services.artwork_job_service import run_artwork_job

    result = run_artwork_job(job_id, job_data, temp_dir)
    # result = {
    #     "job_id":       str,
    #     "labels_dir":   str,
    #     "approval_pdf": str,
    #     "label_count":  int
    # }
"""
from pathlib import Path

from backend.engine.label_engine import build_labels
from backend.services.approval_sheet import build_approval_sheet

OUTPUT_BASE = Path("output")


def run_artwork_job(job_id: str, job_data: dict, temp_dir: Path) -> dict:
    """
    Full end-to-end job pipeline.

    Steps:
      1. Render all label PDFs + thumbnails via the customer renderer
      2. Save individual label PDFs to output/{job_id}/labels/
      3. Build a standardised A4 approval sheet
      4. Return paths to all outputs

    Args:
        job_id:   Unique job identifier (from extract_zip).
        job_data: Parsed job data dict from parse_xml:
                  {"customer_code": str, "label_type": str,
                   "order_ref": str, "records": list[dict]}
        temp_dir: Path to the extracted zip folder (for cleanup reference).

    Returns:
        {
            "job_id":       str,
            "labels_dir":   str,
            "approval_pdf": str,
            "label_count":  int
        }

    Raises:
        ValueError: if no renderer is found for the customer + label type.
    """
    customer   = job_data["customer_code"]
    label_type = job_data["label_type"]
    order_ref  = job_data.get("order_ref", job_id)

    # Step 1: Render all label PDFs + thumbnails
    renders = build_labels(job_data)

    # Step 2: Save individual label PDFs
    labels_dir = OUTPUT_BASE / job_id / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    for r in renders:
        label_path = labels_dir / f"{r['sku']}.pdf"
        label_path.write_bytes(r["pdf"])

    # Step 3: Build standardised approval sheet
    approval_path = str(OUTPUT_BASE / job_id / "approval_sheet.pdf")
    build_approval_sheet(
        job_id=job_id,
        customer_code=customer,
        order_ref=order_ref,
        label_renders=renders,
        output_path=approval_path,
    )

    return {
        "job_id":       job_id,
        "labels_dir":   str(labels_dir),
        "approval_pdf": approval_path,
        "label_count":  len(renders),
    }
