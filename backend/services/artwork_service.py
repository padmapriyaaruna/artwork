"""
Artwork generation service — ties the engine together.
Fetches template, injects data, renders, and stores binary in DB.

For OVS-family templates (design_code starts with TOK or similar OVS tags):
  → uses tok100_label_builder (PyMuPDF direct render — pixel-perfect)

For H&M care-label templates:
  → uses SVG inject + cairosvg (original pipeline)
"""
import io
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import RENDER_DPI
from backend.engine.svg_injector import inject_data, svg_to_string
from backend.engine.renderer import render_all
from backend.engine.template_registry import get_template, resolve_variant
from backend.engine.tok100_label_builder import (
    build_label_pdf,
    build_label_png,
    build_label_thumbnail,
)
from backend.models import Artwork, OrderItem


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_ovs_template(design_code: str) -> bool:
    """Return True for OVS price-tag templates (TOK*, TSPK*, etc.)."""
    code = (design_code or "").upper()
    return code.startswith("TOK") or code.startswith("TSPK") or code.startswith("OVS")


def _build_item_data_dict(item: "OrderItem") -> dict:
    """Build the unified data dict used by both pipelines."""
    return {
        # Common
        "bgp_item_id":      item.bgp_item_id,
        "variant_name":     item.variant_name,
        "quantity":         item.quantity,
        "sizes":            item.sizes or {},
        "order_number":     item.order_number or "",
        "product_number":   item.product_number or "",
        "season_code":      item.season_code or "",
        "country_of_origin": item.country_of_origin or "",
        "tape_color":       item.tape_color or "",
        "supplier_style":   item.supplier_style or "",
        "fibre_content":    item.fibre_content or [],
        "care_symbols":     item.care_symbols or {},
        "additional_care":  item.additional_care or [],
        "has_logo":         True,
        "has_size":         bool(item.sizes),
        # OVS price-tag specific
        "barcode_number":   item.barcode_number or "",
        "selling_price":    item.selling_price or "0,00",
        "currency_symbol":  item.currency_symbol or "\u20ac",
        "sku_code":         item.sku_code or "",
        "commercial_ref":   item.commercial_ref or "",
        "color":            item.color or "",
        "style_code":       item.style_code or "",
        "department":       item.department or "",
        "sub_department":   item.sub_department or "",
    }


async def generate_artwork_for_item(
    db: AsyncSession,
    item: OrderItem,
) -> Artwork:
    """
    Full pipeline for one OrderItem:
      OVS templates  → tok100_label_builder (PyMuPDF)
      H&M templates  → SVG inject + cairosvg
    """
    design_code = item.order.design_code
    item_data   = _build_item_data_dict(item)

    if _is_ovs_template(design_code):
        # ── OVS path ──────────────────────────────────────────────────────────
        pdf_bytes = build_label_pdf(item_data)
        png_bytes = build_label_png(item_data, dpi=RENDER_DPI)
        thumb     = build_label_thumbnail(item_data, dpi=60)
        rendered  = {"pdf": pdf_bytes, "png": png_bytes, "thumbnail": thumb}

    else:
        # ── H&M / SVG path ────────────────────────────────────────────────────
        template = await get_template(db, design_code)
        if template is None:
            raise ValueError(
                f"No active template found for design code '{design_code}'. "
                "Please register the template first."
            )

        layout_variant = resolve_variant(item_data, template.variant_rules)
        item.layout_variant = layout_variant

        svg_root  = inject_data(
            svg_content    = template.svg_content,
            item_data      = item_data,
            field_map      = template.field_map,
            layout_variant = layout_variant,
        )
        svg_bytes = svg_to_string(svg_root)
        rendered  = render_all(svg_bytes, dpi=RENDER_DPI)

    # ── Store / update Artwork record ─────────────────────────────────────────
    existing = await db.execute(
        select(Artwork).where(Artwork.item_id == item.id)
    )
    artwork_record = existing.scalar_one_or_none()

    if artwork_record:
        artwork_record.pdf_data      = rendered["pdf"]
        artwork_record.png_data      = rendered["png"]
        artwork_record.png_thumbnail = rendered["thumbnail"]
        artwork_record.version      += 1
        artwork_record.status        = "pending"
    else:
        artwork_record = Artwork(
            item_id       = item.id,
            pdf_data      = rendered["pdf"],
            png_data      = rendered["png"],
            png_thumbnail = rendered["thumbnail"],
            version       = 1,
            status        = "pending",
        )
        db.add(artwork_record)

    item.status = "ready"
    await db.commit()
    await db.refresh(artwork_record)
    return artwork_record


async def get_artwork_png_bytes(
    db: AsyncSession, artwork_id: str
) -> Optional[bytes]:
    result = await db.execute(
        select(Artwork).where(Artwork.id == artwork_id)
    )
    art = result.scalar_one_or_none()
    return art.png_data if art else None


async def get_artwork_pdf_bytes(
    db: AsyncSession, artwork_id: str
) -> Optional[bytes]:
    result = await db.execute(
        select(Artwork).where(Artwork.id == artwork_id)
    )
    art = result.scalar_one_or_none()
    return art.pdf_data if art else None


async def get_artwork_thumbnail_bytes(
    db: AsyncSession, artwork_id: str
) -> Optional[bytes]:
    result = await db.execute(
        select(Artwork).where(Artwork.id == artwork_id)
    )
    art = result.scalar_one_or_none()
    return art.png_thumbnail if art else None
