"""
Orders API — create orders from XML, ZIP (BRAT), or manual form.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.engine.xml_normalizer import parse_bgp_xml
from backend.engine.zip_extractor import extract_zip
from backend.engine.pdf_to_svg import is_poppler_available
from backend.engine.dynamic_template_builder import build_variablized_svg
from backend.engine.template_registry import get_template, register_template_from_svg
from backend.models import Order, OrderItem, Artwork
from backend.schemas import (
    OrderCreate, OrderResponse, OrderDetailResponse,
    OrderItemResponse, XMLUploadResponse,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


# ── Helper: build item response ───────────────────────────────────────────────
def _item_to_response(item: OrderItem) -> dict:
    art = item.artwork
    order = item.order
    return {
        "id":               str(item.id),
        "order_id":         str(item.order_id),
        "bgp_item_id":      item.bgp_item_id,
        "variant_name":     item.variant_name,
        "quantity":         item.quantity,
        "sizes":            item.sizes or {},
        "order_number":     item.order_number,
        "product_number":   item.product_number,
        "season_code":      item.season_code,
        "country_of_origin": item.country_of_origin,
        "tape_color":       item.tape_color,
        "supplier_style":   item.supplier_style,
        "fibre_content":    item.fibre_content or [],
        "care_symbols":     item.care_symbols or {},
        "additional_care":  item.additional_care or [],
        "layout_variant":   item.layout_variant,
        # OVS Price Tag fields
        "barcode_number":   item.barcode_number,
        "selling_price":    item.selling_price,
        "currency_symbol":  item.currency_symbol,
        "sku_code":         item.sku_code,
        "commercial_ref":   item.commercial_ref,
        "color":            item.color,
        "style_code":       item.style_code,
        "department":       item.department,
        "sub_department":   item.sub_department,
        "translation_code": item.translation_code,
        "extra_variables":  item.extra_variables or {},
        # Status
        "status":           item.status,
        "has_artwork":      art is not None,
        "artwork_id":       str(art.id) if art else None,
        "artwork_status":   art.status if art else None,
        "created_at":       item.created_at,
        # Order-level fields needed for approval sheet
        "customer_name":    order.customer_name if order else None,
        "design_code":      order.design_code if order else None,
        "bgp_order_id":     order.bgp_order_id if order else None,
        "order_date":       order.created_date if order else None,
        "required_date":    order.required_date if order else None,
        "site":             order.site if order else None,
    }


# ── Shared helper: persist order + items ─────────────────────────────────────
async def _create_order_in_db(normalized, db: AsyncSession) -> Order:
    """Create Order and OrderItem rows. Caller must commit."""
    order = Order(
        bgp_order_id   = normalized.bgp_order_id,
        customer_name  = normalized.customer_name,
        customer_email = normalized.customer_email,
        customer_ref   = normalized.customer_ref,
        design_code    = normalized.design_code,
        required_date  = normalized.required_date,
        created_date   = normalized.created_date,
        site           = normalized.site,
        order_link     = normalized.order_link,
        raw_xml        = normalized.raw_xml,
        status         = "pending",
    )
    db.add(order)
    await db.flush()

    for norm_item in normalized.items:
        item = OrderItem(
            order_id          = order.id,
            bgp_item_id       = norm_item.bgp_item_id,
            variant_name      = norm_item.variant_name,
            quantity          = norm_item.quantity,
            sizes             = norm_item.sizes,
            # H&M fields
            order_number      = norm_item.order_number,
            product_number    = norm_item.product_number,
            season_code       = norm_item.season_code,
            country_of_origin = norm_item.country_of_origin,
            tape_color        = norm_item.tape_color,
            supplier_style    = norm_item.supplier_style,
            fibre_content     = norm_item.fibre_content,
            care_symbols      = norm_item.care_symbols,
            additional_care   = norm_item.additional_care,
            # OVS fields
            barcode_number    = norm_item.barcode_number,
            selling_price     = norm_item.selling_price,
            currency_symbol   = norm_item.currency_symbol,
            sku_code          = norm_item.sku_code,
            commercial_ref    = norm_item.commercial_ref,
            color             = norm_item.color,
            style_code        = norm_item.style_code,
            department        = norm_item.department,
            sub_department    = norm_item.sub_department,
            translation_code  = norm_item.translation_code,
            extra_variables   = norm_item.extra_variables,
            status            = "pending",
        )
        db.add(item)
    return order


# ── POST /orders/upload-zip ───────────────────────────────────────────────────
@router.post("/upload-zip", response_model=XMLUploadResponse, status_code=201)
async def upload_zip(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a BRAT ZIP file (.zip containing XML + optional PDF template).

    Fully autonomous flow:
      1. Unzip → extract XML + optional PDF
      2. Parse XML to get all real field values from first item
      3. Check if template already exists in DB
      4. If NEW template:
           a. PDF must be present in ZIP
           b. Convert PDF → SVG (poppler pdftosvg)
           c. Use actual XML field values to find + replace matching text in SVG
           d. Register variablized SVG in DB under detected template_id
      5. Save order + items to DB
    """
    content = await file.read()

    # ── Step 1: Unzip ──────────────────────────────────────────────────
    try:
        zip_contents = extract_zip(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read ZIP: {e}")

    xml_string  = zip_contents.xml_string
    template_id = zip_contents.template_id
    pdf_bytes   = zip_contents.pdf_bytes

    # ── Step 2: Parse XML NOW (needed for dynamic template matching) ─────────
    try:
        normalized = parse_bgp_xml(xml_string)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid XML: {e}")

    if not normalized.bgp_order_id:
        raise HTTPException(status_code=400, detail="Could not find OrderID in XML.")

    # Duplicate order check
    existing_order = await db.execute(
        select(Order).where(Order.bgp_order_id == normalized.bgp_order_id)
    )
    if existing_order.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Order {normalized.bgp_order_id} already exists.",
        )

    # ── Step 3: Check if template exists ─────────────────────────────────
    template_note = ""
    existing_template = await get_template(db, template_id)

    if not existing_template:
        # ── Step 4a: New template — PDF required ──────────────────────────
        if not pdf_bytes:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Template '{template_id}' is not registered. "
                    f"Please include the customer's PDF template inside the ZIP "
                    f"for the first order using this design."
                ),
            )

        if not is_poppler_available():
            raise HTTPException(
                status_code=500,
                detail="PDF conversion tool (poppler) is not available on this server.",
            )

        # ── Step 4b+c: PDF → SVG + dynamic value-driven field matching ───────
        # Use the first parsed item's real field values to match elements in the PDF
        try:
            first_item_data = normalized.items[0].to_dict() if normalized.items else {}
            variablized_svg, field_map = build_variablized_svg(pdf_bytes, first_item_data)
        except RuntimeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Auto template creation failed: {e}"
            )

        print(
            f"[TemplateRegistry] Auto-created '{template_id}' — "
            f"{len(field_map)} fields mapped dynamically from XML values."
        )

        # ── Step 4d: Register in DB ───────────────────────────────────────
        await register_template_from_svg(
            db=db,
            design_code=template_id,
            name=f"{template_id} (auto-generated)",
            svg_content=variablized_svg,
            field_map=field_map,
            variant_rules=[],
            description=(
                f"Dynamically generated from PDF upload on first order. "
                f"{len(field_map)} fields auto-detected using XML values."
            ),
        )
        template_note = (
            f" New template '{template_id}' auto-created: "
            f"{len(field_map)} fields detected from XML data."
        )
    else:
        template_note = f" Using existing template '{template_id}'."

    # ── Step 5: Save order ────────────────────────────────────────────────
    order = await _create_order_in_db(normalized, db)
    await db.commit()

    return XMLUploadResponse(
        order_id     = str(order.id),
        bgp_order_id = order.bgp_order_id,
        design_code  = order.design_code,
        item_count   = len(normalized.items),
        message      = (
            f"Order {order.bgp_order_id} created with "
            f"{len(normalized.items)} item(s). Ready for artwork generation."
            + template_note
        ),
    )


# ── POST /orders/upload-xml ───────────────────────────────────────────────────
@router.post("/upload-xml", response_model=XMLUploadResponse, status_code=201)
async def upload_xml(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a BGP Connect XML file directly (legacy / simple flow).
    For the full BRAT ZIP flow use POST /orders/upload-zip instead.
    """
    content = await file.read()
    try:
        xml_string = content.decode("utf-8")
        normalized = parse_bgp_xml(xml_string)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid XML: {e}")

    if not normalized.bgp_order_id:
        raise HTTPException(status_code=400, detail="Could not find OrderID in XML.")

    existing = await db.execute(
        select(Order).where(Order.bgp_order_id == normalized.bgp_order_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Order {normalized.bgp_order_id} already exists."
        )

    order = await _create_order_in_db(normalized, db)
    await db.commit()

    return XMLUploadResponse(
        order_id      = str(order.id),
        bgp_order_id  = order.bgp_order_id,
        design_code   = order.design_code,
        item_count    = len(normalized.items),
        message       = f"Order {order.bgp_order_id} created with "
                        f"{len(normalized.items)} item(s). Ready for artwork generation.",
    )


# ── POST /orders (manual form) ────────────────────────────────────────────────
@router.post("/", response_model=XMLUploadResponse, status_code=201)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create an order from the web form (simulated BGP Connect)."""
    existing = await db.execute(
        select(Order).where(Order.bgp_order_id == payload.bgp_order_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Order {payload.bgp_order_id} already exists."
        )

    order = Order(**{k: v for k, v in payload.dict().items() if k != "items"})
    db.add(order)
    await db.flush()

    for item_data in payload.items:
        item = OrderItem(order_id=order.id, **item_data.dict())
        db.add(item)

    await db.commit()

    return XMLUploadResponse(
        order_id     = str(order.id),
        bgp_order_id = order.bgp_order_id,
        design_code  = order.design_code,
        item_count   = len(payload.items),
        message      = f"Order {order.bgp_order_id} created successfully.",
    )


# ── GET /orders ───────────────────────────────────────────────────────────────
@router.get("/", response_model=list[OrderResponse])
async def list_orders(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all orders (newest first)."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.artwork))
        .order_by(Order.created_at.desc())
        .offset(skip).limit(limit)
    )
    orders = result.scalars().all()

    response = []
    for o in orders:
        approved = sum(
            1 for i in o.items
            if i.artwork and i.artwork.status == "approved"
        )
        response.append({
            "id":             str(o.id),
            "bgp_order_id":   o.bgp_order_id,
            "customer_name":  o.customer_name,
            "customer_email": o.customer_email,
            "design_code":    o.design_code,
            "required_date":  o.required_date,
            "status":         o.status,
            "item_count":     len(o.items),
            "approved_count": approved,
            "created_at":     o.created_at,
        })
    return response


# ── GET /orders/{order_id} ────────────────────────────────────────────────────
@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Get full order detail including all items and artwork status."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.artwork))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    approved = sum(
        1 for i in order.items
        if i.artwork and i.artwork.status == "approved"
    )

    return {
        "id":             str(order.id),
        "bgp_order_id":   order.bgp_order_id,
        "customer_name":  order.customer_name,
        "customer_email": order.customer_email,
        "design_code":    order.design_code,
        "required_date":  order.required_date,
        "status":         order.status,
        "item_count":     len(order.items),
        "approved_count": approved,
        "created_at":     order.created_at,
        "items":          [_item_to_response(i) for i in order.items],
    }
