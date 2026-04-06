"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr


# ── Size ────────────────────────────────────────────────────────────────────
class SizeMap(BaseModel):
    EUR: Optional[str] = None
    US: Optional[str] = None
    CA: Optional[str] = None
    MX: Optional[str] = None
    CN: Optional[str] = None
    AUS: Optional[str] = None
    UK: Optional[str] = None
    BR: Optional[str] = None


# ── Fibre Content ────────────────────────────────────────────────────────────
class FibreContent(BaseModel):
    header: str          # e.g. "SHELL"
    percentage: int      # e.g. 45
    wording: str         # e.g. "COTTON"


# ── Order Item ───────────────────────────────────────────────────────────────
class OrderItemCreate(BaseModel):
    bgp_item_id: Optional[str] = None
    variant_name: str
    quantity: int = 0
    sizes: dict[str, str] = {}
    order_number: Optional[str] = None
    product_number: Optional[str] = None
    season_code: Optional[str] = None
    country_of_origin: Optional[str] = None
    tape_color: Optional[str] = None
    supplier_style: Optional[str] = None
    fibre_content: list[FibreContent] = []
    care_symbols: dict[str, Any] = {}
    additional_care: list[dict] = []
    layout_variant: str = "logo_with_size"


class OrderItemResponse(OrderItemCreate):
    id: str
    order_id: str
    status: str
    has_artwork: bool = False
    artwork_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Order ────────────────────────────────────────────────────────────────────
class OrderCreate(BaseModel):
    bgp_order_id: str
    customer_name: str
    customer_email: Optional[str] = None
    customer_ref: Optional[str] = None
    design_code: str
    required_date: Optional[str] = None
    created_date: Optional[str] = None
    site: Optional[str] = None
    order_link: Optional[str] = None
    raw_xml: Optional[str] = None
    items: list[OrderItemCreate] = []


class OrderResponse(BaseModel):
    id: str
    bgp_order_id: str
    customer_name: str
    customer_email: Optional[str]
    design_code: str
    required_date: Optional[str]
    status: str
    item_count: int = 0
    approved_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class OrderDetailResponse(OrderResponse):
    items: list[OrderItemResponse] = []


# ── XML Upload ────────────────────────────────────────────────────────────────
class XMLUploadResponse(BaseModel):
    """Returned when a BGP Connect XML is parsed and an order is created."""
    order_id: str
    bgp_order_id: str
    design_code: str
    item_count: int
    message: str


# ── Artwork ───────────────────────────────────────────────────────────────────
class ArtworkResponse(BaseModel):
    id: str
    item_id: str
    version: int
    status: str
    generated_at: datetime
    png_url: str    # endpoint to fetch PNG
    pdf_url: str    # endpoint to fetch PDF

    class Config:
        from_attributes = True


# ── Approval ──────────────────────────────────────────────────────────────────
class ApprovalRequest(BaseModel):
    action: str              # "approved" | "rejected" | "revision_requested"
    comments: Optional[str] = None
    approved_by: str         # Name or email of approver


class ApprovalResponse(BaseModel):
    artwork_id: str
    action: str
    comments: Optional[str]
    approved_by: str
    actioned_at: datetime


# ── Template ──────────────────────────────────────────────────────────────────
class TemplateCreate(BaseModel):
    design_code: str
    name: str
    description: Optional[str] = None
    svg_content: str
    field_map: dict[str, str] = {}
    variant_rules: list[dict] = []


class TemplateResponse(BaseModel):
    id: str
    design_code: str
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
