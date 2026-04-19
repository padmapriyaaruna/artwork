"""
Find the actual label design pages in master PDF + full XML analysis.
"""
import fitz
import lxml.etree as ET
import os

os.makedirs('compare_output', exist_ok=True)

# 1. Master PDF page survey
print("=== MASTER PDF PAGE SURVEY ===")
doc = fitz.open("_OVS KIDS 2023.pdf")
print("Total pages:", doc.page_count)

for i in range(min(doc.page_count, 15)):
    page = doc[i]
    blks = page.get_text('dict')['blocks']
    texts = []
    for b in blks:
        if b['type'] == 0:
            for l in b['lines']:
                for s in l['spans']:
                    t = s['text'].strip()
                    if t:
                        texts.append(t)
    imgs = [b for b in blks if b['type'] == 1]
    paths = page.get_drawings()
    print("  Page %02d: size=%dx%d  texts=%d  images=%d  paths=%d" % (
        i+1, page.rect.width, page.rect.height, len(texts), len(imgs), len(paths)))
    if texts:
        preview = texts[:8]
        print("           texts:", preview)

# Render pages 2-10
for i in range(1, min(11, doc.page_count)):
    mat = fitz.Matrix(1.5, 1.5)
    pix = doc[i].get_pixmap(matrix=mat)
    pix.save('compare_output/master_p%02d.png' % (i+1))
    print("  -> rendered master page", i+1)

doc.close()

# 2. XML structure
print()
print("=== XML STRUCTURE ===")
tree = ET.parse("B0854559 TAG007061 1299052.xml")
root = tree.getroot()

tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
print("Root:", tag)
print("Root children:")
for child in root[:5]:
    ctag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
    print("  <" + ctag + ">  children:", len(child))
    for sub in child[:3]:
        stag = sub.tag.split('}')[-1] if '}' in sub.tag else sub.tag
        stxt = (sub.text or '').strip()[:50]
        print("    <" + stag + "> =", repr(stxt))

# Find repeating elements
from collections import Counter
cnt = Counter()
for el in root.iter():
    etag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
    cnt[etag] += 1

print()
print("Most frequent tags:")
for tag2, count in cnt.most_common(15):
    print("  %-30s %d" % (tag2, count))

# Find the items
most_common_tag = cnt.most_common(1)[0][0] if cnt else None
items = root.findall('.//' + most_common_tag) if most_common_tag else []
print()
print("Using tag:", most_common_tag, "-> found", len(items), "elements")
if items:
    first = items[0]
    print("First item fields:")
    for child in first:
        ctag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        txt = (child.text or '').strip()
        if txt:
            print("  %-30s = %r" % (ctag, txt[:80]))
        for sub in child:
            stag = sub.tag.split('}')[-1] if '}' in sub.tag else sub.tag
            stxt = (sub.text or '').strip()
            if stxt:
                print("    %-28s = %r" % (stag, stxt[:80]))
