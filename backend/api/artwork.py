"""
Artwork API — generate artwork and serve PNG/PDF binary responses.
"""
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db, AsyncSessionLocal
from backend.models import Order, OrderItem, Artwork
from backend.schemas import ArtworkResponse
from backend.services.artwork_service import (
    generate_artwork_for_item,
    get_artwork_png_bytes,
    get_artwork_pdf_bytes,
    get_artwork_thumbnail_bytes,
)

router = APIRouter(prefix="/artwork", tags=["Artwork"])


# ── POST /artwork/generate/{item_id} ──────────────────────────────────────────
@router.post("/generate/{item_id}", status_code=201)
async def generate_artwork(
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger artwork generation for a single OrderItem.
    Synchronous — returns when generation is complete.
    """
    result = await db.execute(
        select(OrderItem)
        .options(selectinload(OrderItem.order), selectinload(OrderItem.artwork))
        .where(OrderItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="OrderItem not found.")

    try:
        item.status = "generating"
        await db.commit()
        artwork = await generate_artwork_for_item(db, item)
    except Exception as e:
        item.status = "pending"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    return {
        "artwork_id":   str(artwork.id),
        "item_id":      str(artwork.item_id),
        "version":      artwork.version,
        "status":       artwork.status,
        "generated_at": artwork.generated_at,
        "png_url":      f"/artwork/{artwork.id}/png",
        "pdf_url":      f"/artwork/{artwork.id}/pdf",
        "thumbnail_url": f"/artwork/{artwork.id}/thumbnail",
    }


# ── Background worker ──────────────────────────────────────────────────────────

async def _generate_order_background(order_id: str) -> None:
    """
    Background task: generates artwork for every item in the order.
    Uses its own DB session so it runs independently of the HTTP request.
    Items are marked 'generating' while in progress, then 'ready' when done.
    The order status flips to 'completed' (or 'in_progress' on partial failure).
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.artwork))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            return

        errors = []

        for item in order.items:
            # Re-load item with order relationship
            item_result = await db.execute(
                select(OrderItem)
                .options(selectinload(OrderItem.order), selectinload(OrderItem.artwork))
                .where(OrderItem.id == item.id)
            )
            full_item = item_result.scalar_one()
            try:
                full_item.status = "generating"
                await db.commit()
                await generate_artwork_for_item(db, full_item)
            except Exception as e:
                full_item.status = "pending"
                await db.commit()
                errors.append(str(e))
                print(f"[ArtworkBG] Item {full_item.id} failed: {e}")

        order.status = "completed" if not errors else "in_progress"
        await db.commit()
        print(f"[ArtworkBG] Order {order_id} done — {len(errors)} error(s).")


# ── POST /artwork/generate-order/{order_id} ───────────────────────────────────
@router.post("/generate-order/{order_id}", status_code=202)
async def generate_artwork_for_order(
    order_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger artwork generation for ALL items in an order.

    Returns 202 Accepted immediately — processing happens in the background.
    Poll GET /orders/{order_id} to track readiness; items will transition
    from 'pending' → 'generating' → 'ready' as each one completes.
    """
    result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Mark order as in_progress immediately so the UI knows work started
    order.status = "in_progress"
    await db.commit()

    background_tasks.add_task(_generate_order_background, order_id)

    return {
        "order_id":  order_id,
        "status":    "processing",
        "message":   "Artwork generation started. Poll GET /orders/{order_id} for progress.",
    }


# ── GET /artwork/{artwork_id}/png ─────────────────────────────────────────────
@router.get("/{artwork_id}/png")
async def get_png(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """Serve full artwork PNG."""
    data = await get_artwork_png_bytes(db, artwork_id)
    if not data:
        raise HTTPException(status_code=404, detail="Artwork not found.")
    return Response(content=data, media_type="image/png")


# ── GET /artwork/{artwork_id}/pdf ─────────────────────────────────────────────
@router.get("/{artwork_id}/pdf")
async def get_pdf(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """Serve artwork PDF for download."""
    data = await get_artwork_pdf_bytes(db, artwork_id)
    if not data:
        raise HTTPException(status_code=404, detail="Artwork not found.")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=artwork_{artwork_id}.pdf"},
    )


# ── GET /artwork/{artwork_id}/thumbnail ───────────────────────────────────────
@router.get("/{artwork_id}/thumbnail")
async def get_thumbnail(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """Serve small thumbnail PNG for list views."""
    data = await get_artwork_thumbnail_bytes(db, artwork_id)
    if not data:
        raise HTTPException(status_code=404, detail="Artwork not found.")
    return Response(content=data, media_type="image/png")


# ── GET /artwork/{artwork_id} ─────────────────────────────────────────────────
@router.get("/{artwork_id}")
async def get_artwork_info(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """Get artwork metadata (no binary)."""
    result = await db.execute(
        select(Artwork).where(Artwork.id == artwork_id)
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Artwork not found.")
    return {
        "id":          str(art.id),
        "item_id":     str(art.item_id),
        "version":     art.version,
        "status":      art.status,
        "generated_at": art.generated_at,
        "png_url":     f"/artwork/{art.id}/png",
        "pdf_url":     f"/artwork/{art.id}/pdf",
        "thumbnail_url": f"/artwork/{art.id}/thumbnail",
    }


# ── Helper: build lean variant info for approval sheet ────────────────────────
def _approval_variant(item: OrderItem) -> dict:
    """Lightweight item dict for approval sheet rendering — no order access needed."""
    art = item.artwork
    return {
        "id":              str(item.id),
        "variant_name":    item.variant_name,
        "quantity":        item.quantity,
        "sizes":           item.sizes or {},
        "barcode_number":  item.barcode_number,
        "selling_price":   item.selling_price,
        "currency_symbol": item.currency_symbol,
        "color":           item.color,
        "commercial_ref":  item.commercial_ref,
        "style_code":      item.style_code,
        "has_artwork":     art is not None,
        "artwork_id":      str(art.id) if art else None,
        "artwork_status":  art.status if art else None,
    }


# ── GET /artwork/{artwork_id}/approval-sheet ───────────────────────────────────
@router.get("/{artwork_id}/approval-sheet")
async def get_approval_sheet_data(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns structured data for the Approval Preview UI page.

    Groups sibling items by country_of_origin, matching the TOK100 layout
    (one page / group per market: WARM, COLD, MIDDLE EAST, etc.).
    """
    result = await db.execute(
        select(Artwork)
        .options(
            selectinload(Artwork.item)
            .selectinload(OrderItem.order)
        )
        .where(Artwork.id == artwork_id)
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    item  = art.item
    order = item.order

    # ── Load ALL items in this order (with their artwork) ──────────────────
    all_items_result = await db.execute(
        select(OrderItem)
        .options(
            selectinload(OrderItem.artwork),
        )
        .where(OrderItem.order_id == item.order_id)
        .order_by(OrderItem.created_at)
    )
    all_items = all_items_result.scalars().all()

    # ── Group by (supplier_style, country_of_origin) ── same as TOK100 pages
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for sib in all_items:
        key = sib.country_of_origin or "UNKNOWN"
        groups[key].append(_approval_variant(sib))

    # Build ordered list starting with the group that contains the clicked item
    current_group_key = item.country_of_origin or "UNKNOWN"
    ordered_keys = [current_group_key] + [k for k in groups if k != current_group_key]

    country_groups = []
    for k in ordered_keys:
        group_items = groups[k]
        # Red title format: "supplier_style - country_of_origin - color - bgp_order_id"
        first = group_items[0] if group_items else {}
        supplier  = item.supplier_style or ""
        color     = item.color or ""
        order_id  = order.bgp_order_id if order else ""
        red_title = f"{supplier} - {k} - {color} - {order_id}"
        country_groups.append({
            "country":    k,
            "title":      red_title,
            "label_size": "45mm x 100mm",
            "variants":   group_items,
        })

    # Derive a safe product_code: prefer commercial_ref, fall back to sku_code
    product_code = item.commercial_ref or item.sku_code or item.product_number or ""

    return {
        "buyer":          "OVS",
        "customer_name":  order.customer_name  if order else "",
        "design_code":    order.design_code    if order else "",
        "product_code":   product_code,
        "submitted_date": order.created_date   if order else "",
        "bgp_order_id":   order.bgp_order_id   if order else "",
        "label_size":     "45mm x 100mm",
        "country_groups": country_groups,          # NEW: list of groups for multi-page preview
        "all_variants":   [_approval_variant(sib) for sib in all_items],  # flat list for simple views
    }


# ── GET /artwork/{artwork_id}/approval-pdf ─────────────────────────────────
from backend.services.approval_pdf_service import create_approval_sheet_pdf

@router.get("/{artwork_id}/approval-pdf")
async def download_approval_pdf(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """Generate and download the full TOK100-style multi-page approval PDF."""
    result = await db.execute(
        select(Artwork)
        .options(
            selectinload(Artwork.item)
            .selectinload(OrderItem.order)
        )
        .where(Artwork.id == artwork_id)
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    item  = art.item
    order = item.order

    # Load all items in this order with their artwork PNG data
    order_items_result = await db.execute(
        select(OrderItem)
        .options(selectinload(OrderItem.artwork))
        .where(OrderItem.order_id == item.order_id)
        .order_by(OrderItem.created_at)
    )
    all_items = order_items_result.scalars().all()

    # Build {artwork_id: png_bytes} lookup for the PDF service
    png_streams: dict = {}
    for sib in all_items:
        if sib.artwork and sib.artwork.png_data:
            png_streams[str(sib.artwork.id)] = sib.artwork.png_data

    # Group items by country_of_origin (one PDF page per group)
    from collections import defaultdict
    by_country: dict = defaultdict(list)
    for sib in all_items:
        country_key = sib.country_of_origin or "UNKNOWN"
        by_country[country_key].append(sib)

    variant_groups = []
    for country_key, sibs in by_country.items():
        supplier = sibs[0].supplier_style or ""
        color    = sibs[0].color or ""
        order_id = order.bgp_order_id if order else ""
        red_title = f"{supplier} - {country_key} - {color} - {order_id}"

        variants = []
        for sib in sibs:
            variants.append({
                "artwork_id":      str(sib.artwork.id) if sib.artwork else None,
                "quantity":        sib.quantity,
                "sizes":           sib.sizes or {},
                "barcode_number":  sib.barcode_number,
                "selling_price":   sib.selling_price,
                "currency_symbol": sib.currency_symbol,
            })

        variant_groups.append({
            "country":    country_key,
            "title":      red_title,
            "label_size": "45mm x 100mm",
            "variants":   variants,
        })

    order_data = {
        "buyer":          "OVS",
        "customer_name":  order.customer_name  if order else "",
        "design_code":    order.design_code    if order else "",
        "product_code":   item.commercial_ref or item.sku_code or item.product_number or "",
        "submitted_date": order.created_date   if order else "",
        "bgp_order_id":   order.bgp_order_id   if order else "",
    }

    pdf_bytes = create_approval_sheet_pdf(order_data, variant_groups, png_streams)

    filename = f"approval_sheet_{order.bgp_order_id if order else 'order'}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


