# -*- coding: utf-8 -*-
"""
Generic Label Engine Dispatcher.

Routes label-build requests to the correct customer-specific renderer
based on (customer_code, label_type).

Usage:
    from backend.engine.label_engine import build_labels, get_renderer

    # Direct renderer access (for single-item use)
    renderer = get_renderer("OVS", "TOK100")
    pdf_bytes = renderer.build_label_pdf(item_data)

    # Batch job use
    results = build_labels({
        "customer_code": "OVS",
        "label_type":    "TOK100",
        "records":       [item_data, ...]
    })

Renderer contract
-----------------
Each renderer module at:
    backend/engine/customers/{customer_code}/{label_type}_renderer.py

MUST expose the following three public functions:

    build_label_pdf(item_data: dict) -> bytes
        Full front+back PDF for a single label.

    build_label_png(item_data: dict, dpi: int = 150) -> bytes
        Rasterised PNG of the label PDF.

    build_label_thumbnail(item_data: dict, dpi: int = 60) -> bytes
        Small thumbnail PNG suitable for approval sheets.

Adding a new customer
---------------------
1. Create folder: backend/engine/customers/{CUST_CODE}/
2. Add __init__.py (empty)
3. Add {label_type}_renderer.py exposing the three functions above
4. (Optional) Add template + zone_map.json to backend/templates/{CUST_CODE}/{LABEL_TYPE}/

No changes to this file are needed when adding new customers.
"""
import importlib

# Root package for all customer renderers
_RENDERER_BASE = "backend.engine.customers"


def get_renderer(customer_code: str, label_type: str):
    """
    Dynamically import and return the renderer module for the given
    customer_code + label_type combination.

    Args:
        customer_code: e.g. "OVS", "ZARA", "HM"
        label_type:    e.g. "TOK100", "WVN50"

    Returns:
        The imported renderer module.

    Raises:
        ValueError: if no renderer module exists for the combination.
    """
    module_path = (
        f"{_RENDERER_BASE}"
        f".{customer_code.lower()}"
        f".{label_type.lower()}_renderer"
    )
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError:
        raise ValueError(
            f"No renderer found for customer='{customer_code}', "
            f"label_type='{label_type}'. "
            f"Expected module at: {module_path.replace('.', '/')}.py\n"
            f"To add this customer, create that file exposing "
            f"build_label_pdf / build_label_png / build_label_thumbnail."
        )


def build_labels(job_data: dict) -> list[dict]:
    """
    Render all records in a job through the appropriate customer renderer.

    Args:
        job_data: {
            "customer_code": str,   e.g. "OVS"
            "label_type":    str,   e.g. "TOK100"
            "records":       list[dict]   each dict = one item's variable data
        }

    Returns:
        list of {
            "sku":   str,    # item identifier
            "pdf":   bytes,  # full PDF
            "png":   bytes,  # 150 DPI PNG
            "thumb": bytes   # 60 DPI thumbnail PNG
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
