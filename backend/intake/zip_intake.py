# -*- coding: utf-8 -*-
"""
ZIP Intake Pipeline.

Handles BRAT zip uploads:
  1. Extract zip to a job-specific temp folder
  2. Classify contents (xml_only vs xml_plus_template)
  3. Parse BRAT XML → structured job data
  4. Route to the correct engine path

Usage:
    from backend.intake.zip_intake import extract_zip, classify_contents, parse_xml

    job_id, temp_dir = extract_zip("/path/to/upload.zip")
    contents = classify_contents(temp_dir)
    job_data = parse_xml(contents["xml_path"])
    # job_data = {"customer_code": "OVS", "label_type": "TOK100", "records": [...]}
"""
import zipfile
import uuid
import shutil
from pathlib import Path
from lxml import etree

# Base directory for per-job extraction folders
JOBS_BASE = Path("jobs")


# ── Extraction ───────────────────────────────────────────────────────────────

def extract_zip(zip_path: str) -> tuple[str, Path]:
    """
    Extract a BRAT zip to a unique job folder.

    Args:
        zip_path: Absolute or relative path to the uploaded .zip file.

    Returns:
        (job_id, temp_dir) where temp_dir is the extraction folder.
    """
    job_id = str(uuid.uuid4())[:8]
    temp_dir = JOBS_BASE / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(temp_dir)
    return job_id, temp_dir


# ── Classification ───────────────────────────────────────────────────────────

def classify_contents(temp_dir: Path) -> dict:
    """
    Inspect the extracted zip and classify its contents.

    Returns:
        {
            "mode": "xml_only" | "xml_plus_template",
            "xml_path": Path,
            "template_pdf_path": Path | None
        }

    Raises:
        ValueError: if no XML file is found (malformed upload).
    """
    all_files    = list(temp_dir.rglob("*"))
    xml_files    = [f for f in all_files if f.suffix.lower() == ".xml"]
    pdf_files    = [f for f in all_files if f.suffix.lower() == ".pdf"]

    if not xml_files:
        raise ValueError(
            "ZIP does not contain any XML file. "
            "A valid BRAT upload must include exactly one XML data file."
        )

    # BRAT always produces one XML; take the first if multiple exist
    xml_path     = xml_files[0]
    template_pdf = pdf_files[0] if pdf_files else None

    return {
        "mode":              "xml_plus_template" if template_pdf else "xml_only",
        "xml_path":          xml_path,
        "template_pdf_path": template_pdf,
    }


# ── XML Parsing ──────────────────────────────────────────────────────────────

def parse_xml(xml_path: Path) -> dict:
    """
    Parse the BRAT XML file and return structured job data.

    Expected XML structure (adapt tag names to actual BRAT schema):

        <order>
          <customer_code>OVS</customer_code>
          <label_type>TOK100</label_type>
          <order_ref>B0854559</order_ref>     <!-- optional -->
          <items>
            <item>
              <barcode_number>8051553298804</barcode_number>
              <sku_code>2768960</sku_code>
              <sub_department>3632</sub_department>
              <department>230</department>
              <style_code>2768957</style_code>
              <commercial_ref>PR711 AI08</commercial_ref>
              <country_of_origin>WARM</country_of_origin>
              <currency_symbol>EUR</currency_symbol>
              <selling_price>29,95</selling_price>
              <quantity>128</quantity>
              <sizes>
                <YEARS>4-5</YEARS>
                <IT>4-5</IT>
                <MEX>4-5</MEX>
                <CM>110</CM>
              </sizes>
            </item>
          </items>
        </order>

    Args:
        xml_path: Path to the XML file.

    Returns:
        {
            "customer_code": str,   e.g. "OVS"
            "label_type":    str,   e.g. "TOK100"
            "order_ref":     str,   e.g. "B0854559"  (may be empty)
            "records":       list[dict]
        }

    Raises:
        ValueError: if customer_code or label_type are missing.
    """
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    customer_code = root.findtext("customer_code", default="").strip().upper()
    label_type    = root.findtext("label_type",    default="").strip().upper()
    order_ref     = root.findtext("order_ref",     default="").strip()

    if not customer_code:
        raise ValueError(
            "XML is missing <customer_code>. "
            "This field is mandatory in the BRAT output."
        )
    if not label_type:
        raise ValueError(
            "XML is missing <label_type>. "
            "This field is mandatory in the BRAT output."
        )

    records = []
    for item in root.findall(".//item"):
        record: dict = {}
        for child in item:
            # Flatten simple fields
            if len(child) == 0:
                record[child.tag] = child.text or ""
            else:
                # Nested element (e.g. <sizes>) → dict
                record[child.tag] = {
                    sub.tag: sub.text or "" for sub in child
                }
        records.append(record)

    return {
        "customer_code": customer_code,
        "label_type":    label_type,
        "order_ref":     order_ref,
        "records":       records,
    }


# ── Cleanup ──────────────────────────────────────────────────────────────────

def cleanup_job(job_id: str) -> None:
    """
    Remove the temp extraction folder for a completed job.
    Call this after all label PDFs have been generated and saved.
    """
    job_dir = JOBS_BASE / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
