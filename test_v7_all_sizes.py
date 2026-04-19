import sys
sys.path.insert(0, 'backend')
from engine.tok100_label_builder import build_label_png

sizes = [
    ('4-5',  '110', '8051553298798'),
    ('5-6',  '116', '8051553298804'),
    ('6-7',  '122', '8051553298811'),
    ('7-8',  '128', '8051553298828'),
    ('8-9',  '134', '8051553298835'),
    ('9-10', '140', '8051553298842'),
]

for yrs, cm, bc in sizes:
    safe = yrs.replace('-', '_')
    data = {
        'sizes': {'YEARS': yrs, 'IT': yrs, 'MEX': yrs, 'CM': cm},
        'barcode_number': bc,
        'department': '230', 'sub_department': '3632', 'sku_code': '2768957',
        'style_code': '2768957', 'commercial_ref': 'PR711 AI08',
        'country_of_origin': 'WARM',
        'currency_symbol': chr(128), 'selling_price': '29,95', 'quantity': 128,
    }
    png = build_label_png(data, dpi=150)
    fname = f'test_v7_{safe}.png'
    with open(fname, 'wb') as f:
        f.write(png)
    print(f'{yrs}: {len(png):,} bytes  -> {fname}')

print('All 6 sizes OK')
