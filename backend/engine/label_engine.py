# -*- coding: utf-8 -*-
"""
Generic Label Engine Dispatcher.

Routes label-build requests to the correct customer-specific renderer
based on (customer_code, label_type).

Resolution order
----------------
1. Try to import the customer-specific renderer:
       backend/engine/customers/{cust}/{type}_renderer.py
   If it exists → use it directly (highest priority, no overhead).

2. If no specific renderer → check the template registry for a zone_map.json:
       backend/templates/{CUST}/{TYPE}/zone_map.json
   If found → wrap generic_pdf_renderer with the zone_map.
   This is the "no-code" path for new customers onboarded via zip_intake.

3. If neither exists → raise ValueError with clear instructions.

Usage
-----
    # Dispatch automatically (recommended)
    from backend.engine.label_engine import build_labels

    results = build_labels({
        "customer_code": "OVS",
        "label_type":    "TOK100",
        "records":       [item_data, ...]
    })

    # Or get a renderer directly
    from backend.engine.label_engine import get_renderer
    renderer = get_renderer("OVS", "TOK100")
    pdf_bytes = renderer.build_label_pdf(item_data)

    # Generic-renderer customers also work via the same interface:
    renderer = get_renderer("ZARA", "WVN50")
    pdf_bytes = renderer.build_label_pdf(item_data)

Adding a new customer
---------------------
Option A (no code):
  Upload BRAT zip with template PDF → auto-onboarded via /intake/upload-brat-zip
  Fill backend/templates/{CUST}/{TYPE}/zone_map.json variable_zones
  Generic renderer handles the rest automatically.

Option B (custom renderer):
  Create backend/engine/customers/{cust}/{type}_renderer.py
  Expose build_label_pdf / build_label_png / build_label_thumbnail
  Dispatcher picks it up automatically — no changes needed here.
"""
import importlib
from pathlib import Path

# Base package for customer-specific renderers
_RENDERER_BASE = "backend.engine.customers"


# ── Generic renderer proxy ────────────────────────────────────────────────────

class _GenericRendererProxy:
    """
    Wraps generic_pdf_renderer with a pre-loaded zone_map so it satisfies
    the standard renderer contract:
        build_label_pdf(item_data) → bytes
        build_label_png(item_data, dpi) → bytes
        build_label_thumbnail(item_data, dpi) → bytes
    """

    def __init__(self, customer_code: str, label_type: str, zone_map: dict):
        self._customer_code = customer_code
        self._label_type    = label_type
        self._zone_map      = zone_map
        # Import lazily to avoid circular imports
        import backend.engine.generic_pdf_renderer as _gr
        self._gr = _gr

    def build_label_pdf(self, item_data: dict) -> bytes:
        return self._gr.build_label_pdf(item_data, self._zone_map)

    def build_label_png(self, item_data: dict, dpi: int = 150) -> bytes:
        return self._gr.build_label_png(item_data, self._zone_map, dpi=dpi)

    def build_label_thumbnail(self, item_data: dict, dpi: int = 60) -> bytes:
        return self._gr.build_label_thumbnail(item_data, self._zone_map, dpi=dpi)

    def __repr__(self):
        return (
            f"<GenericRenderer customer={self._customer_code!r} "
            f"label_type={self._label_type!r}>"
        )


# ── Dispatcher ────────────────────────────────────────────────────────────────

def get_renderer(customer_code: str, label_type: str):
    """
    Return the appropriate renderer for a customer + label type.

    Resolution order:
      1. Customer-specific renderer module (customers/{cust}/{type}_renderer.py)
      2. Generic renderer backed by zone_map.json
      3. ValueError if neither exists

    Args:
        customer_code: e.g. "OVS", "ZARA"
        label_type:    e.g. "TOK100", "WVN50"

    Returns:
        An object exposing build_label_pdf / build_label_png / build_label_thumbnail.

    Raises:
        ValueError: if no renderer or zone_map exists for the combination.
    """
    # ── Resolution step 1: specific renderer ──────────────────────────────────
    module_path = (
        f"{_RENDERER_BASE}"
        f".{customer_code.lower()}"
        f".{label_type.lower()}_renderer"
    )
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError:
        pass   # Fall through to step 2

    # ── Resolution step 2: generic renderer via zone_map ─────────────────────
    try:
        from backend.intake.registry import lookup_template
        zone_map = lookup_template(customer_code, label_type)
        return _GenericRendererProxy(customer_code, label_type, zone_map)
    except FileNotFoundError:
        pass   # Fall through to step 3

    # ── Resolution step 3: nothing found ─────────────────────────────────────
    specific_path  = module_path.replace(".", "/") + ".py"
    zone_map_path  = (
        f"backend/templates/{customer_code.upper()}"
        f"/{label_type.upper()}/zone_map.json"
    )
    raise ValueError(
        f"No renderer found for customer='{customer_code}', "
        f"label_type='{label_type}'.\n\n"
        f"Option A (no code — fill zone_map):\n"
        f"  1. Upload a BRAT zip with template PDF via POST /api/intake/upload-brat-zip\n"
        f"  2. Fill variable_zones in: {zone_map_path}\n\n"
        f"Option B (custom renderer):\n"
        f"  Create: {specific_path}\n"
        f"  Expose: build_label_pdf / build_label_png / build_label_thumbnail"
    )


def build_labels(job_data: dict) -> list[dict]:
    """
    Render all records in a job through the appropriate renderer.

    Args:
        job_data: {
            "customer_code": str,
            "label_type":    str,
            "records":       list[dict]
        }

    Returns:
        list of {
            "sku":   str,
            "pdf":   bytes,
            "png":   bytes,
            "thumb": bytes
        }
    """
    renderer = get_renderer(
        job_data["customer_code"],
        job_data["label_type"],
    )
    results = []
    for record in job_data["records"]:
        results.append({
            "sku":   record.get("sku_code", "unknown"),
            "pdf":   renderer.build_label_pdf(record),
            "png":   renderer.build_label_png(record, dpi=150),
            "thumb": renderer.build_label_thumbnail(record, dpi=60),
        })
    return results
