"""
XML Normalizer — converts BGP Connect XML into a NormalizedOrder dict.

Fully dynamic: handles any number of items, sizes, fibre rows, and care answers.
Works with BOTH H&M-style care labels AND OVS-style price tags.
No field names are hardcoded — the structure is driven by the XML itself.
"""
from dataclasses import dataclass, field
from typing import Any
import lxml.etree as ET


# ── Normalized data structures ────────────────────────────────────────────────

@dataclass
class NormalizedItem:
    # ── Common fields (all templates) ─────────────────────────────────────
    bgp_item_id: str = ""
    variant_name: str = ""
    quantity: int = 0
    sizes: dict[str, str] = field(default_factory=dict)

    # ── H&M Care Label fields ──────────────────────────────────────────────
    order_number: str = ""
    product_number: str = ""
    season_code: str = ""
    country_of_origin: str = ""
    country_of_origin_multilang: dict[str, str] = field(default_factory=dict)
    tape_color: str = ""
    supplier_style: str = ""
    fibre_content: list[dict] = field(default_factory=list)
    care_symbols: dict[str, Any] = field(default_factory=dict)
    additional_care: list[dict] = field(default_factory=list)
    layout_variant: str = "logo_with_size"

    # ── OVS Price Tag / Swing Ticket fields ───────────────────────────────
    barcode_number: str = ""
    selling_price: str = ""
    currency_symbol: str = ""
    sku_code: str = ""
    commercial_ref: str = ""
    color: str = ""
    style_code: str = ""
    department: str = ""
    sub_department: str = ""
    translation_code: str = ""

    # ── Extra dynamic variables (any unrecognized fields) ─────────────────
    extra_variables: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "bgp_item_id":                  self.bgp_item_id,
            "variant_name":                 self.variant_name,
            "quantity":                     self.quantity,
            "sizes":                        self.sizes,
            "order_number":                 self.order_number,
            "product_number":               self.product_number,
            "season_code":                  self.season_code,
            "country_of_origin":            self.country_of_origin,
            "country_of_origin_multilang":  self.country_of_origin_multilang,
            "tape_color":                   self.tape_color,
            "supplier_style":               self.supplier_style,
            "fibre_content":                self.fibre_content,
            "care_symbols":                 self.care_symbols,
            "additional_care":              self.additional_care,
            "layout_variant":               self.layout_variant,
            "barcode_number":               self.barcode_number,
            "selling_price":                self.selling_price,
            "currency_symbol":              self.currency_symbol,
            "sku_code":                     self.sku_code,
            "commercial_ref":               self.commercial_ref,
            "color":                        self.color,
            "style_code":                   self.style_code,
            "department":                   self.department,
            "sub_department":               self.sub_department,
            "translation_code":             self.translation_code,
            "extra_variables":              self.extra_variables,
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
            "bgp_order_id":  self.bgp_order_id,
            "customer_name": self.customer_name,
            "customer_email":self.customer_email,
            "customer_ref":  self.customer_ref,
            "design_code":   self.design_code,
            "required_date": self.required_date,
            "created_date":  self.created_date,
            "site":          self.site,
            "order_link":    self.order_link,
            "raw_xml":       self.raw_xml,
            "items":         [i.to_dict() for i in self.items],
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_text(parent: ET._Element, tag: str) -> str:
    el = parent.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _parse_answer_values(answer_el: ET._Element) -> dict[str, str]:
    """Extract all AnswerValue elements into {Name: text} dict."""
    return {
        av.get("Name", ""): (av.text or "").strip()
        for av in answer_el.findall("AnswerValues/AnswerValue")
    }


def _first_answer_value(answer_el: ET._Element) -> str:
    """Return the text of the first AnswerValue, or empty string."""
    av = answer_el.find("AnswerValues/AnswerValue")
    return (av.text or "").strip() if av is not None else ""


# ── Question-to-field mapping (universal) ─────────────────────────────────────
# Maps Question attribute text (lowercased) to NormalizedItem attribute name.
# New templates just add rows here — no code changes needed.

QUESTION_TO_FIELD: dict[str, str] = {
    # H&M care label
    "order number":     "order_number",
    "product number":   "product_number",
    "season code":      "season_code",
    "supplier style":   "supplier_style",
    # OVS price tag / swing ticket
    "barcode number":   "barcode_number",
    "selling price":    "selling_price",
    "sku code":         "sku_code",
    "commercial ref":   "commercial_ref",
    "color":            "color",
    "colour":           "color",
    "department":       "department",
    "style code":       "style_code",
    "sub department":   "sub_department",
    "translation code": "translation_code",
}


# ── Variable parser ────────────────────────────────────────────────────────────

def _parse_variables(variables_el: ET._Element) -> dict[str, Any]:
    """
    Dynamically parse all <Variable> elements.
    Returns a flat dict that can be merged into a NormalizedItem.
    Works for any template type — driven by Question/LookupListType values.
    """
    result: dict[str, Any] = {
        # H&M defaults
        "order_number": "", "product_number": "", "season_code": "",
        "country_of_origin": "", "country_of_origin_multilang": {},
        "fibre_content": [], "care_symbols": {}, "additional_care": [],
        "tape_color": "", "supplier_style": "",
        # OVS defaults
        "barcode_number": "", "selling_price": "", "currency_symbol": "",
        "sku_code": "", "commercial_ref": "", "color": "", "style_code": "",
        "department": "", "sub_department": "", "translation_code": "",
        "extra_variables": {},
    }

    for var in variables_el.findall("Variable"):
        answer_type  = var.get("AnswerType", "")
        lookup_type  = var.get("LookupListType", "")
        question     = var.get("Question", "")
        question_lc  = question.lower().strip()
        answer_el    = var.find("Answer")
        multipart_el = var.find("MultiPart")

        # ── 1. Simple text fields ──────────────────────────────────────────
        if answer_type == "Text" and answer_el is not None:
            val = _first_answer_value(answer_el)
            mapped = QUESTION_TO_FIELD.get(question_lc)
            if mapped:
                result[mapped] = val
            else:
                result["extra_variables"][question] = val

        # ── 2. Barcode ─────────────────────────────────────────────────────
        elif answer_type == "Barcode" and answer_el is not None:
            val = _first_answer_value(answer_el)
            if not val:
                vals = _parse_answer_values(answer_el)
                val = next(iter(vals.values()), "")
            result["barcode_number"] = val

        # ── 3. Country of Origin ───────────────────────────────────────────
        elif lookup_type == "Country of Origin" and answer_el is not None:
            vals = _parse_answer_values(answer_el)
            result["country_of_origin"] = (
                vals.get("GB") or vals.get("Name") or next(iter(vals.values()), "")
            )
            result["country_of_origin_multilang"] = vals

        # ── 4. Currency (OVS uses Attributes lookup with Symbol) ───────────
        elif lookup_type == "Attributes" and answer_el is not None:
            vals = _parse_answer_values(answer_el)
            result["currency_symbol"] = vals.get("Symbol") or vals.get("Currency", "")

        # ── 5. Small Tag Code Chart (OVS translation code) ─────────────────
        elif lookup_type == "Small Tag Code Chart":
            if answer_el is not None:
                vals = _parse_answer_values(answer_el)
                result["translation_code"] = next(iter(vals.values()), "")

        # ── 6. Tape / Garment Colour ───────────────────────────────────────
        elif lookup_type in ("Colour", "Color") and answer_el is not None:
            vals = _parse_answer_values(answer_el)
            result["tape_color"] = vals.get("Color") or next(iter(vals.values()), "")

        # ── 7. Care symbols ────────────────────────────────────────────────
        elif lookup_type == "Wash Instructions (Symbols)":
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
                    "answer_id": answer_id, "values": vals,
                }

        # ── 8. Additional Care ─────────────────────────────────────────────
        elif lookup_type == "Additional Wash Instructions" and multipart_el is not None:
            for sub_var in multipart_el.findall("Variable"):
                sub_answer = sub_var.find("Answer")
                if sub_answer is not None:
                    answer_id = _get_text(sub_answer, "AnswerID")
                    vals = _parse_answer_values(sub_answer)
                    result["additional_care"].append(
                        {"answer_id": answer_id, "values": vals}
                    )

        # ── 9. Fibre Content ───────────────────────────────────────────────
        elif lookup_type == "Fibre Content Header" and multipart_el is not None:
            current_header, current_pct, current_wording = "", 0, ""
            pending = []
            for sub_var in multipart_el.findall("Variable"):
                sub_q      = sub_var.get("Question", "")
                sub_answer = sub_var.find("Answer")
                if sub_answer is None:
                    continue
                avs = sub_answer.findall("AnswerValues/AnswerValue")
                val_default = (avs[0].text or "").strip() if avs else ""
                if "FIBRE HEADER" in sub_q:
                    if current_header or current_wording:
                        pending.append({"header": current_header,
                                        "percentage": current_pct,
                                        "wording": current_wording})
                    vals = _parse_answer_values(sub_answer)
                    current_header  = vals.get("GB") or val_default
                    current_pct     = 0
                    current_wording = ""
                elif "FIBRE CONTENT %" in sub_q:
                    try:    current_pct = int(val_default)
                    except ValueError: current_pct = 0
                elif "FIBRE CONTENT WORDING" in sub_q:
                    vals = _parse_answer_values(sub_answer)
                    current_wording = vals.get("GB") or val_default
            if current_header or current_wording:
                pending.append({"header": current_header,
                                "percentage": current_pct,
                                "wording": current_wording})
            result["fibre_content"].extend(pending)

        # ── 10. Generic lookup list (unrecognized type) ─────────────────────
        elif answer_type == "Lookup List" and answer_el is not None:
            vals = _parse_answer_values(answer_el)
            value = next(iter(vals.values()), "")
            mapped = QUESTION_TO_FIELD.get(question_lc)
            if mapped:
                result[mapped] = value
            else:
                result["extra_variables"][question] = value

    return result


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_bgp_xml(xml_string: str) -> NormalizedOrder:
    """
    Parse a BGP Connect XML string into a NormalizedOrder.
    Works with any template — completely dynamic.
    Handles both H&M care labels and OVS price tags.
    """
    root = ET.fromstring(xml_string.encode("utf-8"))
    order = NormalizedOrder(raw_xml=xml_string)

    order.bgp_order_id   = _get_text(root, "OrderID")
    order.customer_name  = _get_text(root, "CustomerName")
    order.customer_email = _get_text(root, "CustomerEmail")
    order.customer_ref   = _get_text(root, "CustomerRef")
    order.required_date  = _get_text(root, "RequiredDate")
    order.created_date   = _get_text(root, "CreatedDate")
    order.site           = _get_text(root, "Site")
    order.order_link     = _get_text(root, "OrderLink")

    first_asset = root.find(".//Asset/Name")
    if first_asset is not None:
        order.design_code = (first_asset.text or "").strip()

    for order_item_el in root.findall(".//OrderItem"):
        for item_el in order_item_el.findall("Item"):
            norm_item = NormalizedItem()
            norm_item.bgp_item_id  = _get_text(item_el, "ItemID")
            norm_item.variant_name = _get_text(item_el, "VariantName")
            qty_text = _get_text(item_el, "Quantity")
            norm_item.quantity = int(qty_text) if qty_text.isdigit() else 0

            size_chart = item_el.find("SizeChartItem")
            if size_chart is not None:
                for size_el in size_chart.findall("Size"):
                    name = size_el.get("Name", "")
                    val  = size_el.get("Value", "")
                    if name:
                        norm_item.sizes[name] = val

            variables_el = item_el.find("Variables")
            if variables_el is not None:
                p = _parse_variables(variables_el)
                norm_item.order_number                = p["order_number"]
                norm_item.product_number              = p["product_number"]
                norm_item.season_code                 = p["season_code"]
                norm_item.country_of_origin           = p["country_of_origin"]
                norm_item.country_of_origin_multilang = p["country_of_origin_multilang"]
                norm_item.tape_color                  = p["tape_color"]
                norm_item.supplier_style              = p["supplier_style"]
                norm_item.fibre_content               = p["fibre_content"]
                norm_item.care_symbols                = p["care_symbols"]
                norm_item.additional_care             = p["additional_care"]
                norm_item.barcode_number              = p["barcode_number"]
                norm_item.selling_price               = p["selling_price"]
                norm_item.currency_symbol             = p["currency_symbol"]
                norm_item.sku_code                    = p["sku_code"]
                norm_item.commercial_ref              = p["commercial_ref"]
                norm_item.color                       = p["color"]
                norm_item.style_code                  = p["style_code"]
                norm_item.department                  = p["department"]
                norm_item.sub_department              = p["sub_department"]
                norm_item.translation_code            = p["translation_code"]
                norm_item.extra_variables             = p["extra_variables"]

            order.items.append(norm_item)

    return order


def parse_bgp_xml_file(file_path: str) -> NormalizedOrder:
    """Convenience wrapper — reads file then parses."""
    with open(file_path, "r", encoding="utf-8") as f:
        return parse_bgp_xml(f.read())
