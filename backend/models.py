"""
SQLAlchemy ORM models.
All artwork binary data (PDF + PNG) is stored directly in
PostgreSQL to avoid Render's ephemeral filesystem problem.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, LargeBinary, String, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ── Template Registry ───────────────────────────────────────────────────────
class Template(Base):
    """
    Stores SVG templates + their field mapping and variant rules.
    Adding a new template = insert one row here, upload the SVG.
    NO code changes required.
    """
    __tablename__ = "templates"

    id          = Column(UUID, primary_key=True, default=gen_uuid)
    design_code = Column(String(50), unique=True, nullable=False, index=True)
    name        = Column(String(200), nullable=False)
    description = Column(Text)
    svg_content = Column(Text, nullable=False)   # The raw SVG markup

    # Maps SVG element IDs → NormalizedOrder field paths
    # e.g. {"EUR": "sizes.EUR", "Order_number": "order_number"}
    field_map   = Column(JSON, nullable=False, default=dict)

    # Rules to pick the correct layout variant group
    # e.g. [{"condition": {"has_logo": true, "has_size": true}, "group": "logo_with_size"}]
    variant_rules = Column(JSON, nullable=False, default=list)

    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="template")


# ── Order ───────────────────────────────────────────────────────────────────
class Order(Base):
    """Top-level order from BGP Connect. One order may have many items."""
    __tablename__ = "orders"

    id             = Column(UUID, primary_key=True, default=gen_uuid)
    bgp_order_id   = Column(String(50), unique=True, nullable=False, index=True)
    customer_name  = Column(String(200))
    customer_email = Column(String(200))
    customer_ref   = Column(String(100))
    design_code    = Column(String(50), ForeignKey("templates.design_code"))
    required_date  = Column(String(20))
    created_date   = Column(String(20))
    site           = Column(String(200))
    order_link     = Column(String(500))
    raw_xml        = Column(Text)    # Keep original XML for audit

    status = Column(
        Enum("pending", "in_progress", "completed", "rejected", name="order_status"),
        default="pending"
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template   = relationship("Template", back_populates="orders")
    items      = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# ── OrderItem ────────────────────────────────────────────────────────────────
class OrderItem(Base):
    """
    One size variant within an order.
    Each item generates one artwork label.
    """
    __tablename__ = "order_items"

    id             = Column(UUID, primary_key=True, default=gen_uuid)
    order_id       = Column(UUID, ForeignKey("orders.id"), nullable=False)
    bgp_item_id    = Column(String(50), index=True)
    variant_name   = Column(String(300))
    quantity       = Column(Integer, default=0)

    # Size values per market — stored as JSON for flexibility
    # e.g. {"EUR": "44", "US": "<0-1M", "CA": "<0-1M", "CN": "45/40"}
    sizes          = Column(JSON, default=dict)

    order_number   = Column(String(100))
    product_number = Column(String(100))
    season_code    = Column(String(50))
    country_of_origin = Column(String(200))
    tape_color     = Column(String(50))
    supplier_style = Column(String(100))

    # Structured data stored as JSON for full flexibility
    fibre_content  = Column(JSON, default=list)   # [{header, percentage, wording}]
    care_symbols   = Column(JSON, default=dict)   # {wash, bleach, iron, dry_clean, tumble_dry}
    additional_care = Column(JSON, default=list)  # [{"id": 52634, "values": {"GB": "...", "FR": "..."}}]

    # Which SVG layout variant should be used for this item
    layout_variant = Column(String(100), default="logo_with_size")

    status = Column(
        Enum("pending", "generating", "ready", "approved", "rejected", name="item_status"),
        default="pending"
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order   = relationship("Order", back_populates="items")
    artwork = relationship("Artwork", back_populates="item", uselist=False, cascade="all, delete-orphan")


# ── Artwork ──────────────────────────────────────────────────────────────────
class Artwork(Base):
    """
    Generated artwork stored as binary in the DB.
    Avoids Render's ephemeral filesystem problem entirely.
    """
    __tablename__ = "artworks"

    id           = Column(UUID, primary_key=True, default=gen_uuid)
    item_id      = Column(UUID, ForeignKey("order_items.id"), nullable=False, unique=True)
    version      = Column(Integer, default=1)

    pdf_data     = Column(LargeBinary)    # Full PDF binary
    png_data     = Column(LargeBinary)    # Preview PNG binary
    png_thumbnail = Column(LargeBinary)   # Small thumbnail for list view

    generated_at = Column(DateTime, default=datetime.utcnow)

    status = Column(
        Enum("pending", "approved", "rejected", name="artwork_status"),
        default="pending"
    )

    item     = relationship("OrderItem", back_populates="artwork")
    approvals = relationship("ApprovalLog", back_populates="artwork", cascade="all, delete-orphan")


# ── ApprovalLog ───────────────────────────────────────────────────────────────
class ApprovalLog(Base):
    """Full audit trail of every approval action."""
    __tablename__ = "approval_logs"

    id          = Column(UUID, primary_key=True, default=gen_uuid)
    artwork_id  = Column(UUID, ForeignKey("artworks.id"), nullable=False)
    action      = Column(Enum("approved", "rejected", "revision_requested", name="approval_action"))
    comments    = Column(Text)
    approved_by = Column(String(200))   # Name/email of approver
    actioned_at = Column(DateTime, default=datetime.utcnow)

    artwork = relationship("Artwork", back_populates="approvals")
