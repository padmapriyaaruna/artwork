"""
Artwork API — generate artwork and serve PNG/PDF binary responses.
"""
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
