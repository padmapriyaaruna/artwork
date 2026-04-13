"""
Template Registry — manages SVG templates and their field mappings.
Templates are stored in the DB. On first run, default templates are
seeded automatically from the templates/ folder.
"""
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import TEMPLATES_DIR
from backend.models import Template


# ── Default field map for HM30105 (H&M Care Label) ───────────────────────────
# maps SVG element id → dot-path into NormalizedItem.to_dict()

HM30105_FIELD_MAP = {
    "EUR":            "sizes.EUR",
    "US":             "sizes.US",
    "CA":             "sizes.CA",
    "MX":             "sizes.MX",
    "CN":             "sizes.CN",
    "Order_number":   "order_number",
    "Product_number": "product_number",
    "season_code":    "season_code",
    "made_in":        "country_of_origin",
}

HM30105_VARIANT_RULES = [
    {"condition": {"has_logo": True,  "has_size": True},  "group": "logo_with_size"},
    {"condition": {"has_logo": True,  "has_size": False}, "group": "logo_without_size"},
    {"condition": {"has_logo": False, "has_size": False}, "group": "without_logo_without_size"},
    {"condition": {"has_logo": False, "has_size": True},  "group": "without_logo_with_size"},
]


# ── Default field map for TOK100 (OVS KIDS Main Clothing Tag) ─────────────────
# maps SVG element id → dot-path into NormalizedItem.to_dict()

TOK100_FIELD_MAP = {
    "barcode_field":          "barcode_number",
    "price_field":            "selling_price",
    "currency_field":         "currency_symbol",
    "sku_field":              "sku_code",
    "color_field":            "color",
    "commercial_ref_field":   "commercial_ref",
    "country_field":          "country_of_origin",
    "size_years_field":       "sizes.YEARS",
    "size_cm_field":          "sizes.CM",
    "size_it_field":          "sizes.IT",
    "size_mex_field":         "sizes.MEX",
    "style_code_field":       "style_code",
    "supplier_style_field":   "supplier_style",
}


# ── Variant resolution ────────────────────────────────────────────────────────

def resolve_variant(item_data: dict, variant_rules: list[dict]) -> str:
    """
    Determine which SVG layout variant group to show.
    Uses flags in item_data or sensible defaults.
    """
    has_logo = item_data.get("has_logo", True)
    has_size = bool(item_data.get("sizes"))

    for rule in variant_rules:
        cond = rule.get("condition", {})
        if (
            cond.get("has_logo", True) == has_logo
            and cond.get("has_size", True) == has_size
        ):
            return rule["group"]

    return variant_rules[0]["group"] if variant_rules else "logo_with_size"


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_template(
    db: AsyncSession,
    design_code: str,
) -> Optional[Template]:
    """Fetch a template record by design code."""
    result = await db.execute(
        select(Template).where(
            Template.design_code == design_code,
            Template.is_active == True,
        )
    )
    return result.scalar_one_or_none()


# ── Seeding ───────────────────────────────────────────────────────────────────

async def _seed_one(
    db: AsyncSession,
    design_code: str,
    name: str,
    description: str,
    svg_filename: str,
    field_map: dict,
    variant_rules: list,
) -> None:
    """Seed a single template if not already present. Safe to call repeatedly."""
    svg_path = TEMPLATES_DIR / svg_filename
    if not svg_path.exists():
        print(f"[TemplateRegistry] SVG not found, skipping: {svg_filename}")
        return
    existing = await get_template(db, design_code)
    if existing:
        return
    svg_content = svg_path.read_text(encoding="utf-8")
    template = Template(
        design_code   = design_code,
        name          = name,
        description   = description,
        svg_content   = svg_content,
        field_map     = field_map,
        variant_rules = variant_rules,
        is_active     = True,
    )
    db.add(template)
    await db.commit()
    print(f"[TemplateRegistry] Seeded template: {design_code}")


async def seed_default_templates(db: AsyncSession) -> None:
    """
    On startup, ensure all known bundled templates exist in the DB.
    Safe to call multiple times — skips already-seeded templates.
    """
    # H&M 35mm Care Label
    await _seed_one(
        db,
        design_code   = "HM30105",
        name          = "HM30105 Care Label 35mm",
        description   = "H&M 35mm wash care label — front panel. "
                        "Supports logo/no-logo and size/no-size variants.",
        svg_filename  = "HM30105_HM30105_1_FRONT.svg",
        field_map     = HM30105_FIELD_MAP,
        variant_rules = HM30105_VARIANT_RULES,
    )

    # OVS KIDS Main Clothing Tag
    await _seed_one(
        db,
        design_code   = "TOK100",
        name          = "TOK100 OVS KIDS Main Tag 45mm",
        description   = "OVS KIDS 45mm x 220mm swing ticket — front panel. "
                        "Includes barcode, price, SKU, color, size grid, country of origin.",
        svg_filename  = "TOK100_TAG007061_FRONT.svg",
        field_map     = TOK100_FIELD_MAP,
        variant_rules = [],   # Single layout — no variant rules
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def register_template_from_svg(
    db: AsyncSession,
    design_code: str,
    name: str,
    svg_content: str,
    field_map: dict,
    variant_rules: list,
    description: str = "",
) -> Template:
    """
    Register a new template or update an existing one.
    Called from the orders API when a new PDF template is auto-detected in a ZIP.
    """
    existing = await get_template(db, design_code)
    if existing:
        existing.svg_content   = svg_content
        existing.field_map     = field_map
        existing.variant_rules = variant_rules
        existing.name          = name
        existing.description   = description
        await db.commit()
        return existing

    template = Template(
        design_code   = design_code,
        name          = name,
        description   = description,
        svg_content   = svg_content,
        field_map     = field_map,
        variant_rules = variant_rules,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template
