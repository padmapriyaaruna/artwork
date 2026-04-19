
# Create visual comparison montage
from PIL import Image, ImageDraw, ImageFont

def add_label(img, text, position="top"):
    labeled = Image.new("RGB", (img.width, img.height + 30), (240, 240, 240))
    labeled.paste(img, (0, 0 if position == "bottom" else 30))
    draw = ImageDraw.Draw(labeled)
    draw.rectangle([0, 0, img.width, 29], fill=(50, 50, 50))
    draw.text((5, 8), text, fill=(255, 255, 255))
    return labeled

def make_comparison(gen_path, actual_path, out_path, title):
    gen = Image.open(gen_path)
    actual = Image.open(actual_path)
    
    # Scale both to same height for comparison
    target_h = max(gen.height, actual.height, 100)
    
    def scale_to_height(img, h):
        ratio = h / img.height
        return img.resize((int(img.width * ratio), h), Image.LANCZOS)
    
    gen_scaled = scale_to_height(gen, target_h)
    actual_scaled = scale_to_height(actual, target_h)
    
    gen_labeled = add_label(gen_scaled, "GENERATED (v10)")
    actual_labeled = add_label(actual_scaled, "ACTUAL REFERENCE")
    
    gap = 10
    total_w = gen_labeled.width + actual_labeled.width + gap
    total_h = gen_labeled.height + 40
    
    combined = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    combined.paste(gen_labeled, (0, 40))
    combined.paste(actual_labeled, (gen_labeled.width + gap, 40))
    
    draw = ImageDraw.Draw(combined)
    draw.rectangle([0, 0, total_w, 39], fill=(30, 30, 80))
    draw.text((5, 10), title, fill=(255, 220, 50))
    
    combined.save(out_path)
    print(f"Saved: {out_path} ({combined.size})")

make_comparison("crop_gen_currency.png", "crop_actual_currency.png", 
                "compare_currency.png", "CURRENCY SYMBOL SIZE")
make_comparison("crop_gen_barcode.png", "crop_actual_barcode.png",
                "compare_barcode.png", "BARCODE HEIGHT")
make_comparison("crop_gen_sizechart.png", "crop_actual_sizechart.png",
                "compare_sizechart.png", "SIZE CHART LAYOUT")
