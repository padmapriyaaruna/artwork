"""
Template Registry — manages SVG templates and their field mappings.
Templates are stored in the DB. On first run, the HM30105 template
is seeded automatically from the templates/ folder.
"""
import json
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import TEMPLATES_DIR
from backend.models import Template


# ── Default field map for HM30105 ─────────────────────────────────────────────
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

# ── Variant rules for HM30105 ─────────────────────────────────────────────────
# Each rule: {condition: {has_logo, has_size}, group: "svg_group_id"}
# "has_logo" and "has_size" are resolved from item_data flags
HM30105_VARIANT_RULES = [
    {"condition": {"has_logo": True,  "has_size": True},  "group": "logo_with_size"},
    {"condition": {"has_logo": True,  "has_size": False}, "group": "logo_without_size"},
    {"condition": {"has_logo": False, "has_size": False}, "group": "without_logo_without_size"},
    {"condition": {"has_logo": False, "has_size": True},  "group": "without_logo_with_size"},
]


def resolve_variant(item_data: dict, variant_rules: list[dict]) -> str:
    """
    Determine which SVG layout variant group to show.
    Uses flags in item_data or sensible defaults.

    The variant is chosen from variant_rules stored per-template in DB.
    """
    has_logo = item_data.get("has_logo", True)   # default True
    has_size = bool(item_data.get("sizes"))       # True if any size values exist

    for rule in variant_rules:
        cond = rule.get("condition", {})
        if (
            cond.get("has_logo", True) == has_logo
            and cond.get("has_size", True) == has_size
        ):
            return rule["group"]

    # Fallback
    return variant_rules[0]["group"] if variant_rules else "logo_with_size"


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


async def seed_default_templates(db: AsyncSession) -> None:
    """
    On startup, ensure the HM30105 template exists in the DB.
    Safe to call multiple times — skips if already present.
    """
    svg_path = TEMPLATES_DIR / "HM30105_HM30105_1_FRONT.svg"
    if not svg_path.exists():
        return  # Template file not found yet — skip seeding

    # Check if already seeded
    existing = await get_template(db, "HM30105")
    if existing:
        return

    svg_content = svg_path.read_text(encoding="utf-8")

    template = Template(
        design_code   = "HM30105",
        name          = "HM30105 Care Label 35mm",
        description   = "H&M 35mm wash care label — front panel. "
                        "Supports logo/no-logo and size/no-size variants.",
        svg_content   = svg_content,
        field_map     = HM30105_FIELD_MAP,
        variant_rules = HM30105_VARIANT_RULES,
        is_active     = True,
    )
    db.add(template)
    await db.commit()
    print(f"[TemplateRegistry] Seeded template: HM30105")


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
    Called from the admin API when uploading a new SVG.
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
