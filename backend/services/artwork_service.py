"""
Artwork generation service — ties the engine together.
Fetches template, injects data, renders, and stores binary in DB.
"""
import base64
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import RENDER_DPI
from backend.engine.svg_injector import inject_data, svg_to_string
from backend.engine.renderer import render_all
from backend.engine.template_registry import get_template, resolve_variant
from backend.models import Artwork, OrderItem


async def generate_artwork_for_item(
    db: AsyncSession,
    item: OrderItem,
) -> Artwork:
    """
    Full pipeline for one OrderItem:
      1. Load template from DB
      2. Resolve layout variant
      3. Inject data into SVG
      4. Render PDF + PNG + thumbnail
      5. Store binary in Neon DB
      6. Return Artwork record
    """
    # ── 1. Load template ───────────────────────────────────────────────────
    template = await get_template(db, item.order.design_code)
    if template is None:
        raise ValueError(
            f"No active template found for design code '{item.order.design_code}'. "
            "Please register the template first."
        )

    # ── 2. Build item data dict ────────────────────────────────────────────
    item_data = {
        "bgp_item_id":     item.bgp_item_id,
        "variant_name":    item.variant_name,
        "quantity":        item.quantity,
        "sizes":           item.sizes or {},
        "order_number":    item.order_number or "",
        "product_number":  item.product_number or "",
        "season_code":     item.season_code or "",
        "country_of_origin": item.country_of_origin or "",
        "tape_color":      item.tape_color or "",
        "supplier_style":  item.supplier_style or "",
        "fibre_content":   item.fibre_content or [],
        "care_symbols":    item.care_symbols or {},
        "additional_care": item.additional_care or [],
        # flags for variant selection
        "has_logo":  True,   # can be driven by order data in future
        "has_size":  bool(item.sizes),
    }

    # ── 3. Resolve layout variant ──────────────────────────────────────────
    layout_variant = resolve_variant(item_data, template.variant_rules)
    item.layout_variant = layout_variant

    # ── 4. Inject data into SVG ────────────────────────────────────────────
    svg_root   = inject_data(
        svg_content    = template.svg_content,
        item_data      = item_data,
        field_map      = template.field_map,
        layout_variant = layout_variant,
    )
    svg_bytes = svg_to_string(svg_root)

    # ── 5. Render outputs ──────────────────────────────────────────────────
    rendered  = render_all(svg_bytes, dpi=RENDER_DPI)

    # ── 6. Store / update Artwork record ──────────────────────────────────
    existing = await db.execute(
        select(Artwork).where(Artwork.item_id == item.id)
    )
    artwork_record = existing.scalar_one_or_none()

    if artwork_record:
        artwork_record.pdf_data      = rendered["pdf"]
        artwork_record.png_data      = rendered["png"]
        artwork_record.png_thumbnail = rendered["thumbnail"]
        artwork_record.version       += 1
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
