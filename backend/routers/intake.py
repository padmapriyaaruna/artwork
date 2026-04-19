# -*- coding: utf-8 -*-
"""
Intake Router — /upload-brat-zip endpoint.

Accepts a BRAT-generated zip file upload, extracts and routes it
through the intake pipeline, and triggers label generation.

Endpoints:
    POST /intake/upload-brat-zip   — upload a BRAT zip and start a job
    GET  /intake/customers         — list all registered customers
    GET  /intake/status/{job_id}   — check job status (placeholder)
"""
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from backend.intake.zip_intake import extract_zip, classify_contents, parse_xml, cleanup_job
from backend.intake.onboarding import onboard_template
from backend.intake.registry import list_registered_customers, is_registered

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/upload-brat-zip")
async def upload_brat_zip(file: UploadFile = File(...)) -> JSONResponse:
    """
    Accept a BRAT zip upload and start the label generation pipeline.

    The zip must contain:
      - Exactly one XML file with <customer_code> and <label_type> fields
      - Optionally one PDF (new customer template — triggers onboarding)

    Returns:
        {
            "job_id":       str,
            "customer":     str,
            "label_type":   str,
            "status":       "queued",
            "label_count":  int
        }
    """
    # Save upload to a temp file
    suffix = Path(file.filename).suffix if file.filename else ".zip"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(tmp_fd, "wb") as tmp_file:
            content = await file.read()
            tmp_file.write(content)

        # Step 1: Extract
        try:
            job_id, temp_dir = extract_zip(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"ZIP extraction failed: {e}")

        # Step 2: Classify
        try:
            contents = classify_contents(temp_dir)
        except ValueError as e:
            cleanup_job(job_id)
            raise HTTPException(status_code=422, detail=str(e))

        # Step 3: Parse XML
        try:
            job_data = parse_xml(contents["xml_path"])
        except ValueError as e:
            cleanup_job(job_id)
            raise HTTPException(status_code=422, detail=str(e))

        customer_code = job_data["customer_code"]
        label_type    = job_data["label_type"]

        # Step 4: Onboard new customer if template PDF was included
        if contents["mode"] == "xml_plus_template":
            try:
                onboard_template(
                    customer_code=customer_code,
                    label_type=label_type,
                    pdf_path=contents["template_pdf_path"],
                    xml_records=job_data.get("records", []),   # pass XML for value matching
                )
            except Exception as e:
                cleanup_job(job_id)
                raise HTTPException(
                    status_code=500,
                    detail=f"Template onboarding failed: {e}"
                )
        elif not is_registered(customer_code, label_type):
            # Known hard-coded renderers (OVS) don't need zone_map registration
            # but if a truly unknown customer arrives, warn clearly
            pass  # label_engine will raise if no renderer module exists

        # Step 5: Trigger generation (async background task in production)
        # For now, return queued status. Wire to artwork_job_service.py for full run.
        return JSONResponse({
            "job_id":      job_id,
            "customer":    customer_code,
            "label_type":  label_type,
            "order_ref":   job_data.get("order_ref", ""),
            "status":      "queued",
            "label_count": len(job_data["records"]),
            "mode":        contents["mode"],
        })

    finally:
        # Always clean up the temp upload file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/customers")
def list_customers() -> JSONResponse:
    """List all registered customers and their label types."""
    customers = list_registered_customers()
    return JSONResponse({"customers": customers, "count": len(customers)})


@router.get("/status/{job_id}")
def job_status(job_id: str) -> JSONResponse:
    """
    Check the status of a label generation job.
    Placeholder — wire to artwork_job_service for live status.
    """
    job_dir = Path("jobs") / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JSONResponse({"job_id": job_id, "status": "processing"})
