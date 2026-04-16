"""
Artwork API — generate artwork and serve PNG/PDF binary responses.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
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


# ── POST /artwork/generate-order/{order_id} ───────────────────────────────────
@router.post("/generate-order/{order_id}", status_code=201)
async def generate_artwork_for_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate artwork for ALL items in an order at once."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.artwork))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    results = []
    errors  = []

    for item in order.items:
        # Re-load item with order relationship for service
        item_result = await db.execute(
            select(OrderItem)
            .options(selectinload(OrderItem.order), selectinload(OrderItem.artwork))
            .where(OrderItem.id == item.id)
        )
        full_item = item_result.scalar_one()
        try:
            full_item.status = "generating"
            await db.commit()
            artwork = await generate_artwork_for_item(db, full_item)
            results.append({
                "item_id":    str(full_item.id),
                "artwork_id": str(artwork.id),
                "status":     "generated",
                "png_url":    f"/artwork/{artwork.id}/png",
                "pdf_url":    f"/artwork/{artwork.id}/pdf",
                "thumbnail_url": f"/artwork/{artwork.id}/thumbnail",
            })
        except Exception as e:
            full_item.status = "pending"
            await db.commit()
            errors.append({"item_id": str(full_item.id), "error": str(e)})

    order.status = "completed" if not errors else "in_progress"
    await db.commit()

    return {
        "order_id":    order_id,
        "generated":   len(results),
        "failed":      len(errors),
        "results":     results,
        "errors":      errors,
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
    """Get all structured data for rendering the approval sheet in the UI."""
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

    item = art.item
    order = item.order

    # Find all sibling items (same order, same variant_name/colour group)
    # Eagerly load BOTH .artwork and .order so _approval_variant() can access them
    siblings_result = await db.execute(
        select(OrderItem)
        .options(
            selectinload(OrderItem.artwork),
            selectinload(OrderItem.order),   # needed by _item_to_response
        )
        .where(
            OrderItem.order_id == item.order_id,
            OrderItem.variant_name == item.variant_name,
        )
        .order_by(OrderItem.created_at)      # JSON column cannot be used in ORDER BY
    )
    siblings = siblings_result.scalars().all()

    all_variants = [_approval_variant(sib) for sib in siblings]

    return {
        "buyer":          order.customer_name if order else "OVS",
        "customer_name":  order.customer_name if order else "",
        "design_code":    order.design_code   if order else "",
        "product_code":   item.product_number or item.commercial_ref or "",
        "submitted_date": order.created_date  if order else "",
        "bgp_order_id":   order.bgp_order_id  if order else "",
        "variant_name":   item.variant_name   or "",
        "label_size":     "45mm x 100mm",
        "all_variants":   all_variants,
    }


# ── GET /artwork/{artwork_id}/approval-pdf ─────────────────────────────────
from backend.services.approval_pdf_service import create_approval_sheet_pdf

@router.get("/{artwork_id}/approval-pdf")
async def download_approval_pdf(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """Generate and download the full TOK100-style approval PDF."""
    result = await db.execute(
        select(Artwork)
        .options(selectinload(Artwork.item).selectinload(OrderItem.order))
        .where(Artwork.id == artwork_id)
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    item = art.item
    order = item.order

    # Group sibling items by variant_name
    order_items_result = await db.execute(
        select(OrderItem)
        .options(selectinload(OrderItem.artwork))
        .where(OrderItem.order_id == item.order_id)
        .order_by(OrderItem.created_at)   # JSON column cannot be used in ORDER BY
    )
    all_items = order_items_result.scalars().all()

    groups = {}
    for sib in all_items:
        vname = sib.variant_name or 'Default'
        if vname not in groups:
            groups[vname] = []
        if sib.artwork and sib.artwork.png_data:
            groups[vname].append({
                'png_stream': sib.artwork.png_data,
                'quantity': sib.quantity,
                'sizes': sib.sizes
            })

    variant_groups = []
    for k, v in groups.items():
        variant_groups.append({
            'title': k,
            'variants': v
        })

    order_data = {
        "buyer": "OVS",
        "customer_name": order.customer_name if order else "",
        "design_code": order.design_code if order else "",
        "product_code": item.product_number or item.commercial_ref or "",
        "submitted_date": order.created_date if order else "",
        "bgp_order_id": order.bgp_order_id if order else "",
    }

    # Dummy front tag for simulation (In real app, backend generates or uses uploaded logo PNG)
    # Using the first available label PNG as a placeholder for front tag
    single_front = variant_groups[0]['variants'][0]['png_stream'] if variant_groups and variant_groups[0]['variants'] else None

    pdf_bytes = create_approval_sheet_pdf(order_data, variant_groups, single_front)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=approval_sheet_{order.bgp_order_id if order else 'order'}.pdf"},
    )

