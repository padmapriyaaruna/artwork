"""
Complete XML field extraction using attribute-based Variable structure.
Variables use: Variable[@Question] and Variable/Answer/AnswerValues/AnswerValue
"""
import lxml.etree as ET

tree = ET.parse("B0854559 TAG007061 1299052.xml")
root = tree.getroot()

items = root.findall('.//Item')
print("Total Items:", len(items))

for item_idx, item in enumerate(items):
    iv = item.find('ItemID')
    vn = item.find('VariantName')
    qt = item.find('Quantity')
    print()
    print("=" * 70)
    print("ITEM %d: ID=%s  Variant=%s  Qty=%s" % (
        item_idx+1,
        iv.text if iv is not None else '?',
        (vn.text or '')[:60] if vn is not None else '?',
        qt.text if qt is not None else '?'
    ))

    # SizeChart
    sc = item.find('SizeChart')
    if sc is not None:
        for sci in sc.findall('SizeChartItem'):
            children = {}
            for c in sci:
                tag = c.tag.split('}')[-1] if '}' in c.tag else c.tag
                children[tag] = c.text
            print("  Size:", children)

    # Variables - use attributes
    vars_el = item.find('Variables')
    if vars_el is not None:
        for var in vars_el.findall('Variable'):
            question = var.get('Question', '')
            answer_type = var.get('AnswerType', '')
            
            # Get AnswerValue text
            av = var.find('.//AnswerValue')
            val = av.text if av is not None else None
            
            # Get translations
            trans = {}
            for t in var.findall('.//Translation'):
                lang = t.get('Language', '')
                tval = t.get('Value', '')
                if lang and tval:
                    trans[lang] = tval
            
            print("  [%s] %-35s = %r" % (answer_type[:10], question[:35], str(val or '')[:50]))
            if trans:
                print("       translations:", {k: v[:30] for k,v in list(trans.items())[:4]})
    
    if item_idx >= 5:
        print("  ... (only showing first 6 items)")
        break

print()
print("=" * 70)
print("FIELD SUMMARY (unique question names across all items):")
seen = {}
for item in items:
    vars_el = item.find('Variables')
    if vars_el:
        for var in vars_el.findall('Variable'):
            q = var.get('Question', '')
            at = var.get('AnswerType', '')
            av = var.find('.//AnswerValue')
            val = av.text if av is not None else ''
            if q and q not in seen:
                seen[q] = (at, val or '')

for q, (at, val) in seen.items():
    print("  [%-12s] %-35s example=%r" % (at[:12], q[:35], str(val)[:40]))
