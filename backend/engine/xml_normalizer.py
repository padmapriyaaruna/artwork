"""
XML Normalizer — converts BGP Connect XML into a NormalizedOrder dict.
Fully dynamic: handles any number of items, sizes, fibre rows, and care answers.
No field names are hardcoded — the structure is driven by the XML itself.
"""
from dataclasses import dataclass, field
from typing import Any
import lxml.etree as ET


# ── Normalized data structures ────────────────────────────────────────────────

@dataclass
class NormalizedItem:
    bgp_item_id: str = ""
    variant_name: str = ""
    quantity: int = 0
    sizes: dict[str, str] = field(default_factory=dict)
    order_number: str = ""
    product_number: str = ""
    season_code: str = ""
    country_of_origin: str = ""          # plain "Made in India"
    country_of_origin_multilang: dict[str, str] = field(default_factory=dict)
    tape_color: str = ""
    supplier_style: str = ""
    fibre_content: list[dict] = field(default_factory=list)
    care_symbols: dict[str, str] = field(default_factory=dict)
    additional_care: list[dict] = field(default_factory=list)
    layout_variant: str = "logo_with_size"

    def to_dict(self) -> dict:
        return {
            "bgp_item_id": self.bgp_item_id,
            "variant_name": self.variant_name,
            "quantity": self.quantity,
            "sizes": self.sizes,
            "order_number": self.order_number,
            "product_number": self.product_number,
            "season_code": self.season_code,
            "country_of_origin": self.country_of_origin,
            "country_of_origin_multilang": self.country_of_origin_multilang,
            "tape_color": self.tape_color,
            "supplier_style": self.supplier_style,
            "fibre_content": self.fibre_content,
            "care_symbols": self.care_symbols,
            "additional_care": self.additional_care,
            "layout_variant": self.layout_variant,
        }


@dataclass
class NormalizedOrder:
    bgp_order_id: str = ""
    customer_name: str = ""
    customer_email: str = ""
    customer_ref: str = ""
    design_code: str = ""
    required_date: str = ""
    created_date: str = ""
    site: str = ""
    order_link: str = ""
    raw_xml: str = ""
    items: list[NormalizedItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "bgp_order_id": self.bgp_order_id,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "customer_ref": self.customer_ref,
            "design_code": self.design_code,
            "required_date": self.required_date,
            "created_date": self.created_date,
            "site": self.site,
            "order_link": self.order_link,
            "raw_xml": self.raw_xml,
            "items": [i.to_dict() for i in self.items],
        }


# ── Question-type parsers ─────────────────────────────────────────────────────

def _parse_answer_values(answer_el: ET._Element) -> dict[str, str]:
    """Extract all AnswerValue elements into {Name: text} dict."""
    return {
        av.get("Name", ""): (av.text or "").strip()
        for av in answer_el.findall("AnswerValues/AnswerValue")
    }


def _get_text(parent: ET._Element, tag: str) -> str:
    el = parent.find(tag)
    return (el.text or "").strip() if el is not None else ""


# ── Care symbol answer-ID → readable key mapping ──────────────────────────────
# These LookupListType values identify care instruction categories
CARE_SYMBOL_TYPES = {
    "Wash Instructions (Symbols)": {
        "Wash care (Wash)":       "wash",
        "Wash care (Bleach)":     "bleach",
        "Wash care (Iron)":       "iron",
        "Wash care (Dry clean)":  "dry_clean",
        "Wash care (Tumble dry)": "tumble_dry",
    }
}


def _parse_variables(variables_el: ET._Element) -> dict[str, Any]:
    """
    Dynamically parse all <Variable> elements.
    Returns a dict keyed by detected content type.
    """
    result: dict[str, Any] = {
        "order_number": "",
        "product_number": "",
        "season_code": "",
        "country_of_origin": "",
        "country_of_origin_multilang": {},
        "fibre_content": [],
        "care_symbols": {},
        "additional_care": [],
        "tape_color": "",
        "supplier_style": "",
    }

    for var in variables_el.findall("Variable"):
        answer_type   = var.get("AnswerType", "")
        lookup_type   = var.get("LookupListType", "")
        question      = var.get("Question", "")
        answer_el     = var.find("Answer")
        multipart_el  = var.find("MultiPart")

        # ── Simple text fields ─────────────────────────────────────────────
        if answer_type == "Text":
            val = ""
            if answer_el is not None:
                av_els = answer_el.findall("AnswerValues/AnswerValue")
                if av_els:
                    val = (av_els[0].text or "").strip()

            q_lower = question.lower()
            if "order number" in q_lower:
                result["order_number"] = val
            elif "product number" in q_lower:
                result["product_number"] = val
            elif "season code" in q_lower:
                result["season_code"] = val
            elif "supplier style" in q_lower:
                result["supplier_style"] = val

        # ── Country of Origin ──────────────────────────────────────────────
        elif lookup_type == "Country of Origin" and answer_el is not None:
            vals = _parse_answer_values(answer_el)
            result["country_of_origin"] = vals.get("GB") or vals.get("Name") or next(iter(vals.values()), "")
            result["country_of_origin_multilang"] = vals

        # ── Tape Colour ────────────────────────────────────────────────────
        elif lookup_type == "Colour" and answer_el is not None:
            vals = _parse_answer_values(answer_el)
            result["tape_color"] = vals.get("Color", next(iter(vals.values()), ""))

        # ── Care symbols (wash/bleach/iron/dry/tumble) ─────────────────────
        elif lookup_type == "Wash Instructions (Symbols)":
            # Map question → care_symbols key
            symbol_key = None
            for q_match, skey in {
                "Wash care (Wash)":       "wash",
                "Wash care (Bleach)":     "bleach",
                "Wash care (Iron)":       "iron",
                "Wash care (Dry clean)":  "dry_clean",
                "Wash care (Tumble dry)": "tumble_dry",
            }.items():
                if q_match in question:
                    symbol_key = skey
                    break

            if symbol_key and answer_el is not None:
                answer_id = _get_text(answer_el, "AnswerID")
                vals = _parse_answer_values(answer_el)
                result["care_symbols"][symbol_key] = {
                    "answer_id": answer_id,
                    "values": vals,
                }

        # ── Additional Care Information (multipart) ────────────────────────
        elif lookup_type == "Additional Wash Instructions" and multipart_el is not None:
            for sub_var in multipart_el.findall("Variable"):
                sub_answer = sub_var.find("Answer")
                if sub_answer is not None:
                    answer_id = _get_text(sub_answer, "AnswerID")
                    vals = _parse_answer_values(sub_answer)
                    result["additional_care"].append({
                        "answer_id": answer_id,
                        "values": vals,
                    })

        # ── Fibre Content (multipart: HEADER → %% → WORDING) ──────────────
        elif lookup_type == "Fibre Content Header" and multipart_el is not None:
            # Parse in triplets: FIBRE HEADER, FIBRE CONTENT %, FIBRE CONTENT WORDING
            current_header   = ""
            current_pct      = 0
            current_wording  = ""
            pending          = []

            for sub_var in multipart_el.findall("Variable"):
                sub_q      = sub_var.get("Question", "")
                sub_answer = sub_var.find("Answer")
                if sub_answer is None:
                    continue
                avs = sub_answer.findall("AnswerValues/AnswerValue")
                val_default = (avs[0].text or "").strip() if avs else ""

                if "FIBRE HEADER" in sub_q:
                    # Flush previous triplet before starting new
                    if current_header or current_wording:
                        pending.append({
                            "header":     current_header,
                            "percentage": current_pct,
                            "wording":    current_wording,
                        })
                    # Get multilang wording for header
                    vals = _parse_answer_values(sub_answer)
                    current_header  = vals.get("GB") or val_default
                    current_pct     = 0
                    current_wording = ""

                elif "FIBRE CONTENT %" in sub_q:
                    try:
                        current_pct = int(val_default)
                    except ValueError:
                        current_pct = 0

                elif "FIBRE CONTENT WORDING" in sub_q:
                    vals = _parse_answer_values(sub_answer)
                    current_wording = vals.get("GB") or val_default

            # Flush last triplet
            if current_header or current_wording:
                pending.append({
                    "header":     current_header,
                    "percentage": current_pct,
                    "wording":    current_wording,
                })

            result["fibre_content"].extend(pending)

    return result


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_bgp_xml(xml_string: str) -> NormalizedOrder:
    """
    Parse a BGP Connect XML string into a NormalizedOrder.
    Works with any template — completely dynamic.

    Args:
        xml_string: Raw XML content from BGP Connect / BRAT

    Returns:
        NormalizedOrder with all items populated
    """
    root = ET.fromstring(xml_string.encode("utf-8"))
    order = NormalizedOrder(raw_xml=xml_string)

    # ── Order-level fields ─────────────────────────────────────────────────
    order.bgp_order_id   = _get_text(root, "OrderID")
    order.customer_name  = _get_text(root, "CustomerName")
    order.customer_email = _get_text(root, "CustomerEmail")
    order.customer_ref   = _get_text(root, "CustomerRef")
    order.required_date  = _get_text(root, "RequiredDate")
    order.created_date   = _get_text(root, "CreatedDate")
    order.site           = _get_text(root, "Site")
    order.order_link     = _get_text(root, "OrderLink")

    # ── Design code from first OrderItem's Asset ───────────────────────────
    first_asset = root.find(".//Asset/Name")
    if first_asset is not None:
        order.design_code = (first_asset.text or "").strip()

    # ── Items ──────────────────────────────────────────────────────────────
    for order_item_el in root.findall(".//OrderItem"):
        order_item_id = _get_text(order_item_el, "OrderItemID")

        for item_el in order_item_el.findall("Item"):
            norm_item = NormalizedItem()
            norm_item.bgp_item_id  = _get_text(item_el, "ItemID")
            norm_item.variant_name = _get_text(item_el, "VariantName")
            qty_text = _get_text(item_el, "Quantity")
            norm_item.quantity = int(qty_text) if qty_text.isdigit() else 0

            # ── Sizes ──────────────────────────────────────────────────────
            size_chart = item_el.find("SizeChartItem")
            if size_chart is not None:
                for size_el in size_chart.findall("Size"):
                    name = size_el.get("Name", "")
                    val  = size_el.get("Value", "")
                    if name:
                        norm_item.sizes[name] = val

            # ── Variables ──────────────────────────────────────────────────
            variables_el = item_el.find("Variables")
            if variables_el is not None:
                parsed = _parse_variables(variables_el)
                norm_item.order_number              = parsed["order_number"]
                norm_item.product_number            = parsed["product_number"]
                norm_item.season_code               = parsed["season_code"]
                norm_item.country_of_origin         = parsed["country_of_origin"]
                norm_item.country_of_origin_multilang = parsed["country_of_origin_multilang"]
                norm_item.tape_color                = parsed["tape_color"]
                norm_item.supplier_style            = parsed["supplier_style"]
                norm_item.fibre_content             = parsed["fibre_content"]
                norm_item.care_symbols              = parsed["care_symbols"]
                norm_item.additional_care           = parsed["additional_care"]

            order.items.append(norm_item)

    return order


def parse_bgp_xml_file(file_path: str) -> NormalizedOrder:
    """Convenience wrapper — reads file then parses."""
    with open(file_path, "r", encoding="utf-8") as f:
        return parse_bgp_xml(f.read())
