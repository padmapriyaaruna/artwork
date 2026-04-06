"""
Approvals API — internal portal to approve or reject artwork.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import Artwork, ApprovalLog, Order, OrderItem
from backend.schemas import ApprovalRequest, ApprovalResponse

router = APIRouter(prefix="/approvals", tags=["Approvals"])

VALID_ACTIONS = {"approved", "rejected", "revision_requested"}


# ── POST /approvals/{artwork_id} ──────────────────────────────────────────────
@router.post("/{artwork_id}", response_model=ApprovalResponse, status_code=201)
async def submit_approval(
    artwork_id: str,
    payload: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit an approval action (approve / reject / request revision)."""
    if payload.action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {VALID_ACTIONS}"
        )

    # Load artwork
    result = await db.execute(
        select(Artwork)
        .options(selectinload(Artwork.item).selectinload(OrderItem.order))
        .where(Artwork.id == artwork_id)
    )
    artwork = result.scalar_one_or_none()
    if not artwork:
        raise HTTPException(status_code=404, detail="Artwork not found.")

    # Map action to status
    status_map = {
        "approved":           "approved",
        "rejected":           "rejected",
        "revision_requested": "pending",
    }
    artwork.status      = status_map[payload.action]
    artwork.item.status = "approved" if payload.action == "approved" else "pending"

    # Update order status
    order = artwork.item.order
    all_items = order.items
    if all(i.status == "approved" for i in all_items):
        order.status = "completed"
    elif any(i.status == "approved" for i in all_items):
        order.status = "in_progress"

    # Audit log
    log = ApprovalLog(
        artwork_id  = artwork.id,
        action      = payload.action,
        comments    = payload.comments,
        approved_by = payload.approved_by,
        actioned_at = datetime.utcnow(),
    )
    db.add(log)
    await db.commit()

    return ApprovalResponse(
        artwork_id  = artwork_id,
        action      = payload.action,
        comments    = payload.comments,
        approved_by = payload.approved_by,
        actioned_at = log.actioned_at,
    )


# ── GET /approvals/pending ────────────────────────────────────────────────────
@router.get("/pending", summary="List all artwork pending approval")
async def list_pending(db: AsyncSession = Depends(get_db)):
    """Return all artworks in 'pending' status for the approval portal."""
    result = await db.execute(
        select(Artwork)
        .options(
            selectinload(Artwork.item).selectinload(OrderItem.order)
        )
        .where(Artwork.status == "pending")
        .order_by(Artwork.generated_at.desc())
    )
    artworks = result.scalars().all()

    return [
        {
            "artwork_id":     str(a.id),
            "item_id":        str(a.item_id),
            "version":        a.version,
            "variant_name":   a.item.variant_name,
            "order_number":   a.item.order_number,
            "product_number": a.item.product_number,
            "design_code":    a.item.order.design_code,
            "bgp_order_id":   a.item.order.bgp_order_id,
            "customer_name":  a.item.order.customer_name,
            "required_date":  a.item.order.required_date,
            "generated_at":   a.generated_at,
            "thumbnail_url":  f"/artwork/{a.id}/thumbnail",
            "png_url":        f"/artwork/{a.id}/png",
            "pdf_url":        f"/artwork/{a.id}/pdf",
        }
        for a in artworks
    ]


# ── GET /approvals/history/{artwork_id} ───────────────────────────────────────
@router.get("/history/{artwork_id}", summary="Full approval history for an artwork")
async def approval_history(artwork_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full approval audit log for an artwork."""
    result = await db.execute(
        select(ApprovalLog)
        .where(ApprovalLog.artwork_id == artwork_id)
        .order_by(ApprovalLog.actioned_at.asc())
    )
    logs = result.scalars().all()
    return [
        {
            "action":      l.action,
            "comments":    l.comments,
            "approved_by": l.approved_by,
            "actioned_at": l.actioned_at,
        }
        for l in logs
    ]
