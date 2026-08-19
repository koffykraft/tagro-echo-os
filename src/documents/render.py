from __future__ import annotations
from html import escape
from decimal import Decimal


def _money(v): return f'₹{Decimal(str(v)):,.2f}'
def _page(title,body):
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>body{{font-family:Arial,sans-serif;color:#111;margin:32px}}header{{display:flex;justify-content:space-between;border-bottom:2px solid #111;padding-bottom:12px}}table{{width:100%;border-collapse:collapse;margin-top:22px}}th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}.num{{text-align:right}}.total{{font-size:20px;font-weight:700}}@media print{{button{{display:none}}body{{margin:14mm}}}}</style></head><body>{body}<p><button onclick="print()">Print / Save PDF</button></p></body></html>'''

def render_commercial_document(document_type,document_id,branch,party,items,created_at,status='draft',notes=''):
    if document_type not in {'quote','invoice','purchase_order','purchase'}: raise ValueError('unsupported document type')
    rows=[]; grand=Decimal('0')
    for i,x in enumerate(items,1):
        qty=Decimal(str(x['quantity'])); price=Decimal(str(x['unit_price'])); discount=Decimal(str(x.get('discount',0))); gst=Decimal(str(x.get('gst_rate',0)))
        taxable=qty*price-discount; tax=taxable*gst/Decimal('100'); total=taxable+tax; grand+=total
        rows.append(f'<tr><td>{i}</td><td>{escape(str(x.get("description") or x.get("product_id")))}</td><td class="num">{qty}</td><td class="num">{_money(price)}</td><td class="num">{gst}%</td><td class="num">{_money(total)}</td></tr>')
    body=f'''<header><div><b>TAGRO × ECHO</b><br><small>{escape(document_type.replace('_',' ').upper())}</small></div><div><b>{escape(document_id)}</b><br>{escape(str(created_at))}<br>Status: {escape(status)}</div></header><h2>{escape(str(party.get('name','')))}</h2><p>{escape(str(party.get('phone','')))} {escape(str(party.get('gstin','')))}</p><p>Counter: {escape(str(branch.get('code','')))} · {escape(str(branch.get('name','')))}</p><table><thead><tr><th>#</th><th>Item</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">GST</th><th class="num">Total</th></tr></thead><tbody>{''.join(rows)}</tbody><tfoot><tr><td colspan="5" class="num total">Grand total</td><td class="num total">{_money(grand)}</td></tr></tfoot></table><p>{escape(notes)}</p>'''
    return _page(f'TAGRO ECHO {document_type} {document_id}',body)
