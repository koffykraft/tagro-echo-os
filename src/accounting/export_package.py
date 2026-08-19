from __future__ import annotations
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
import csv, io, json, hashlib


def _plain(v):
    if is_dataclass(v): v=asdict(v)
    if isinstance(v, Decimal): return str(v)
    if isinstance(v, datetime): return v.isoformat()
    if isinstance(v, dict): return {k:_plain(x) for k,x in v.items()}
    if isinstance(v, (list,tuple)): return [_plain(x) for x in v]
    return v


def csv_text(rows):
    rows=[_plain(x) for x in rows]
    if not rows: return ''
    fields=sorted({k for r in rows for k in r})
    out=io.StringIO(newline=''); w=csv.DictWriter(out,fieldnames=fields); w.writeheader(); w.writerows(rows)
    return out.getvalue()


def build_accounting_package(*, sales=(), purchases=(), payments=(), allocations=(), source='tagro-echo-os'):
    files={
      'sales.csv':csv_text(sales), 'purchases.csv':csv_text(purchases),
      'payments.csv':csv_text(payments), 'payment_allocations.csv':csv_text(allocations)
    }
    manifest={'schema':'tagro.echo-os.accounting-export/1','created_at':datetime.now(timezone.utc).isoformat(),
              'source':source,'mode':'file-export-only','production_write':False,
              'files':{name:{'sha256':hashlib.sha256(text.encode()).hexdigest(),'bytes':len(text.encode())} for name,text in files.items()}}
    files['manifest.json']=json.dumps(manifest,indent=2,sort_keys=True)
    return files
