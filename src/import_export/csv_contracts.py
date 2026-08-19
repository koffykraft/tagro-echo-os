from __future__ import annotations

import csv, io
from typing import Iterable, Mapping

FIELDSETS={
 'users':('user_id','name','email','role','branch_id','active'),
 'branches':('branch_id','code','name','district','branch_type','active'),
 'products':('product_id','sku','model','name','category','gst_rate','unit','serial_tracked','active'),
 'prices':('price_id','product_id','price_type','amount','effective_from','effective_to','branch_id'),
 'customers':('customer_id','name','phone','email','gstin','district'),
 'suppliers':('supplier_id','name','phone','email','gstin'),
 'quotes':('quote_id','branch_id','customer_id','created_at','status','total'),
 'quote_lines':('quote_id','line_no','product_id','quantity','unit_price','discount','gst_rate','line_total'),
 'sales':('sale_id','branch_id','customer_id','created_at','payment_status','source_quote_id','total'),
 'sale_lines':('sale_id','line_no','product_id','quantity','unit_price','discount','gst_rate','line_total'),
 'purchases':('purchase_id','branch_id','supplier_id','created_at','supplier_invoice_no','total'),
 'purchase_lines':('purchase_id','line_no','product_id','quantity','unit_price','discount','gst_rate','line_total'),
 'stock':('branch_id','product_id','quantity'),
 'stock_movements':('movement_id','branch_id','product_id','quantity_delta','movement_type','occurred_at','reference_type','reference_id','note'),
 'machines':('machine_id','customer_id','product_id','model','serial_no','purchase_date','source'),
 'service_jobs':('job_id','branch_id','customer_id','machine_id','opened_at','complaint','status','observations','estimate_id'),
 'service_events':('event_id','job_id','occurred_at','event_type','note','actor_id'),
 'cash_closings':('closing_id','branch_id','business_date','opening_cash','cash_sales','other_cash_in','cash_expenses','cash_deposits_or_transfers','declared_closing','expected_closing','variance','recorded_at','actor_id','note'),
 'bank_transactions':('transaction_id','statement_id','source_file','source_row','account_id','transaction_date','value_date','direction','amount','narration','reference','balance')
}

class ImportContractError(ValueError): pass

def template_csv(dataset):
    out=io.StringIO(); csv.writer(out).writerow(FIELDSETS[dataset]); return out.getvalue()

def read_csv(dataset,text):
    expected=FIELDSETS[dataset]; reader=csv.DictReader(io.StringIO(text)); actual=tuple(reader.fieldnames or ())
    if actual!=expected: raise ImportContractError(f'{dataset} header mismatch: expected {expected}, got {actual}')
    return [dict(row) for row in reader]

def write_csv(dataset,rows:Iterable[Mapping[str,object]]):
    out=io.StringIO(); fields=FIELDSETS[dataset]; w=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore'); w.writeheader()
    for row in rows: w.writerow({k:_plain(row.get(k,'')) for k in fields})
    return out.getvalue()

def _plain(v):
    if v is None:return ''
    if isinstance(v,bool):return 'true' if v else 'false'
    if hasattr(v,'isoformat'):return v.isoformat()
    return str(v)
