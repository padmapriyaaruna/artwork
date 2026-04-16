import fitz # PyMuPDF
import io

def create_approval_sheet_pdf(order_data: dict, variant_groups: list[dict], single_front_png_bytes: bytes) -> bytes:
    """
    Creates a landscape PDF matching the TOK100 design.
    """
    # A2 Landscape size
    width, height = 2004.0, 1417.0
    doc = fitz.open()

    for group in variant_groups:
        page = doc.new_page(width=width, height=height)

        # Draw Header Table
        # X: ~300 to 1700
        # Y: 100 to 200
        table_rect = fitz.Rect(300, 100, 1700, 200)
        page.draw_rect(table_rect, color=(0.7, 0.7, 0.7), width=1)

        # Dividing lines for the 3 columns
        page.draw_line(fitz.Point(800, 100), fitz.Point(800, 200), color=(0.7, 0.7, 0.7), width=1)
        page.draw_line(fitz.Point(1400, 100), fitz.Point(1400, 200), color=(0.7, 0.7, 0.7), width=1)

        # Cell 1: Logo
        page.insert_text(fitz.Point(400, 160), "🎨 Sainmarks®", fontsize=28, color=(0.3, 0.6, 0.3), fontname="helv")

        # Cell 2: Details
        # Internal lines
        ys = [120, 140, 160, 180]
        for y in ys:
            page.draw_line(fitz.Point(800, y), fitz.Point(1400, y), color=(0.7, 0.7, 0.7), width=1)

        texts = [
            f"BUYER : {order_data.get('buyer', 'OVS')}",
            f"CUSTOMER : {order_data.get('customer_name', '')}",
            f"DESIGN CODE : {order_data.get('design_code', '')}",
            f"PRODUCT CODE : {order_data.get('product_code', '')}",
            f"SUBMITTED DATE : {order_data.get('submitted_date', '')}"
        ]
        
        y_text = 115
        for t in texts:
            page.insert_text(fitz.Point(820, y_text), t, fontsize=12, color=(0.3, 0.3, 0.3), fontname="helv")
            y_text += 20

        # Cell 3: ARTWORK FOR APPROVAL
        page.insert_text(fitz.Point(1500, 140), "ARTWORK\nFOR\nAPPROVAL", fontsize=14, color=(0.3, 0.3, 0.3), fontname="helv")

        # Red Title
        variant_title = group.get('title', f"Order: {order_data.get('bgp_order_id')}")
        page.insert_text(fitz.Point(700, 260), variant_title, fontsize=18, color=(0.8, 0.1, 0.1), fontname="helv-bo")
        page.insert_text(fitz.Point(900, 290), "45mm x 100mm", fontsize=16, color=(0, 0, 0), fontname="helv-bo")

        # Images Table Line
        page.draw_line(fitz.Point(300, 320), fitz.Point(1700, 320), color=(0.7, 0.7, 0.7), width=1)
        page.insert_text(fitz.Point(450, 340), "Front", fontsize=16, color=(0, 0, 0), fontname="helv-bo")
        page.insert_text(fitz.Point(620, 340), "Back", fontsize=16, color=(0, 0, 0), fontname="helv-bo")
        page.draw_line(fitz.Point(300, 360), fitz.Point(1700, 360), color=(0.7, 0.7, 0.7), width=1)
        # Vertical divider
        page.draw_line(fitz.Point(600, 320), fitz.Point(600, 900), color=(0.7, 0.7, 0.7), width=1)

        # Place Front Tag (reused for all groups if there's only 1 front tag globally, or per group)
        if single_front_png_bytes:
            rect_front = fitz.Rect(350, 380, 520, 780)
            page.insert_image(rect_front, stream=single_front_png_bytes)

        x_start = 650
        y_img = 380
        img_width = 150
        img_height = 400
        gap = 180

        # Place Back Tags
        for i, v in enumerate(group.get('variants', [])):
            png_bytes = v.get('png_stream')
            if png_bytes:
                rect = fitz.Rect(x_start + i*gap, y_img, x_start + i*gap + img_width, y_img + img_height)
                page.insert_image(rect, stream=png_bytes)

            page.insert_text(fitz.Point(x_start + i*gap + 40, y_img + img_height + 40), f"Qty - {v.get('quantity', 0)}", fontsize=14, color=(0, 0, 0), fontname="helv-bo")

    out_bytes = doc.write()
    doc.close()
    return out_bytes
