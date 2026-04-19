# -*- coding: utf-8 -*-
"""
Template Registry.

Looks up registered customer templates by (customer_code, label_type).
A customer is registered when they have a zone_map.json in:
    backend/templates/{CUSTOMER_CODE}/{LABEL_TYPE}/zone_map.json

Usage:
    from backend.intake.registry import lookup_template, list_registered_customers

    zone_map = lookup_template("OVS", "TOK100")
    # zone_map["renderer_module"] tells the engine which renderer to use
    # zone_map["variable_zones"]  lists all variable areas (for generic renderer)
"""
import json
from pathlib import Path

TEMPLATE_BASE = Path("backend/templates")


def lookup_template(customer_code: str, label_type: str) -> dict:
    """
    Return the zone_map dict for a registered customer + label type.

    Args:
        customer_code: e.g. "OVS"
        label_type:    e.g. "TOK100"

    Returns:
        Parsed zone_map.json dict.

    Raises:
        FileNotFoundError: if the customer/label_type is not registered.
    """
    zone_map_path = (
        TEMPLATE_BASE
        / customer_code.upper()
        / label_type.upper()
        / "zone_map.json"
    )

    if not zone_map_path.exists():
        raise FileNotFoundError(
            f"No template registered for customer='{customer_code}', "
            f"label_type='{label_type}'. "
            f"Expected: {zone_map_path}\n"
            f"This customer must upload a template PDF first "
            f"(BRAT zip with xml_plus_template mode)."
        )

    with open(zone_map_path, encoding="utf-8") as f:
        return json.load(f)


def list_registered_customers() -> list[dict]:
    """
    Return all registered customer + label type combinations.

    Returns:
        list of {
            "customer_code": str,
            "label_type":    str,
            "template":      str,   path to template.pdf
            "renderer":      str,   renderer_module name
        }
    """
    results = []
    for zone_map_file in sorted(TEMPLATE_BASE.rglob("zone_map.json")):
        try:
            with open(zone_map_file, encoding="utf-8") as f:
                data = json.load(f)
            results.append({
                "customer_code": data.get("customer_code", ""),
                "label_type":    data.get("label_type", ""),
                "template":      data.get("static_template", ""),
                "renderer":      data.get("renderer_module", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue  # Skip malformed zone_maps
    return results


def is_registered(customer_code: str, label_type: str) -> bool:
    """
    Quick check: does a zone_map.json exist for this customer + label_type?

    Args:
        customer_code: e.g. "OVS"
        label_type:    e.g. "TOK100"

    Returns:
        True if registered, False otherwise.
    """
    zone_map_path = (
        TEMPLATE_BASE
        / customer_code.upper()
        / label_type.upper()
        / "zone_map.json"
    )
    return zone_map_path.exists()
