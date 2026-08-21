from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BOUNDARY = "2026-03-31"
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE warehouse_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE sources(source_id INTEGER PRIMARY KEY,source_hash BLOB NOT NULL UNIQUE);
CREATE TABLE vouchers(voucher_id INTEGER PRIMARY KEY,stable_id BLOB NOT NULL UNIQUE,branch TEXT NOT NULL,financial_year TEXT NOT NULL,vch_code TEXT NOT NULL,vch_type INTEGER NOT NULL,vch_date TEXT NOT NULL,vch_no TEXT,series_code TEXT,party_code TEXT,party_name TEXT,total_amount REAL NOT NULL,taxable_amount REAL NOT NULL,cancelled INTEGER NOT NULL,vch_cancelled INTEGER NOT NULL,auto_vch_no TEXT,source_id INTEGER NOT NULL REFERENCES sources(source_id),record_hash BLOB NOT NULL);
CREATE TABLE voucher_items(item_line_id INTEGER PRIMARY KEY,stable_id BLOB NOT NULL UNIQUE,voucher_id INTEGER NOT NULL REFERENCES vouchers(voucher_id) ON DELETE CASCADE,sr_no TEXT,item_code TEXT,item_name TEXT,unit_code TEXT,unit_name TEXT,qty REAL,unit_rate REAL,taxable_amount REAL,total_amount REAL,d1 TEXT,d3 TEXT,d4 TEXT,d6 TEXT,d7 TEXT,short_narration TEXT,source_id INTEGER NOT NULL REFERENCES sources(source_id),record_hash BLOB NOT NULL);
CREATE TABLE voucher_ledger(ledger_line_id INTEGER PRIMARY KEY,stable_id BLOB NOT NULL UNIQUE,voucher_id INTEGER NOT NULL REFERENCES vouchers(voucher_id) ON DELETE CASCADE,rec_type TEXT,sr_no TEXT,ledger_code TEXT,ledger_name TEXT,value1 REAL,value2 REAL,value3 REAL,d1 TEXT,d2 TEXT,d3 TEXT,d4 TEXT,d5 TEXT,short_narration TEXT,source_id INTEGER NOT NULL REFERENCES sources(source_id),record_hash BLOB NOT NULL);
CREATE TABLE voucher_narration(voucher_id INTEGER PRIMARY KEY REFERENCES vouchers(voucher_id) ON DELETE CASCADE,party_code TEXT,party_name TEXT,narration1 TEXT,narration2 TEXT,voucher_notes TEXT,search_text TEXT,source_id INTEGER NOT NULL REFERENCES sources(source_id),record_hash BLOB NOT NULL);
CREATE INDEX idx_vouchers_branch_date ON vouchers(branch,vch_date);
CREATE INDEX idx_items_voucher ON voucher_items(voucher_id);
CREATE INDEX idx_ledger_voucher ON voucher_ledger(voucher_id);
"""

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('--runtime-root',default=r'T:\TAGRO_AWS_RUNTIME'); args=ap.parse_args()
    root=Path(args.runtime_root)
    source=root/'data/canonical/tagro-data-platform/tagro_history.sqlite'
    dest=root/'data/canonical/tagro-data-platform/partitions/tagro_evidence_locked_to_2026-03-31.sqlite'
    catalog=root/'data/canonical/tagro-data-platform/partitions/warehouse_catalog.json'
    if not source.is_file(): raise SystemExit(f'Missing canonical history: {source}')
    expected=None
    if catalog.is_file():
        c=json.loads(catalog.read_text(encoding='utf-8-sig')); expected=((c.get('locked') or {}).get('counts') or {}).get('vouchers')
    src=sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True)
    quick=src.execute('pragma quick_check').fetchone()[0]
    n=src.execute('select count(*) from vouchers where vch_date<=?',(BOUNDARY,)).fetchone()[0]
    latest=src.execute('select max(vch_date) from vouchers where vch_date<=?',(BOUNDARY,)).fetchone()[0]
    src.close()
    if quick!='ok' or n<=0 or latest>BOUNDARY: raise SystemExit(f'Canonical historical preflight failed quick={quick} count={n} max={latest}')
    if expected is not None and int(expected)!=int(n): raise SystemExit(f'Historical voucher count differs from verified catalog: catalog={expected} canonical={n}')
    dest.parent.mkdir(parents=True,exist_ok=True); temp=dest.with_suffix('.building.sqlite')
    for p in (temp,Path(str(temp)+'-wal'),Path(str(temp)+'-shm')): p.unlink(missing_ok=True)
    con=sqlite3.connect(temp); con.create_function('hexblob',1,lambda x: bytes.fromhex(x) if x else b''); con.executescript(SCHEMA); con.execute('attach database ? as src',(str(source),))
    con.execute("insert or ignore into sources(source_hash) select distinct hexblob(source_sha256) from src.vouchers where vch_date<=?",(BOUNDARY,))
    con.execute("""insert into vouchers(stable_id,branch,financial_year,vch_code,vch_type,vch_date,vch_no,series_code,party_code,party_name,total_amount,taxable_amount,cancelled,vch_cancelled,auto_vch_no,source_id,record_hash)
      select hexblob(v.voucher_id),v.branch,v.financial_year,v.vch_code,v.vch_type,v.vch_date,v.vch_no,v.series_code,v.party_code,v.party_name,v.total_amount,v.taxable_amount,v.cancelled,v.vch_cancelled,v.auto_vch_no,s.source_id,hexblob(v.record_sha256)
      from src.vouchers v join sources s on s.source_hash=hexblob(v.source_sha256) where v.vch_date<=?""",(BOUNDARY,))
    con.execute("""insert into voucher_items(stable_id,voucher_id,sr_no,item_code,item_name,unit_code,unit_name,qty,unit_rate,taxable_amount,total_amount,d1,d3,d4,d6,d7,short_narration,source_id,record_hash)
      select hexblob(i.item_line_id),tv.voucher_id,i.sr_no,i.item_code,i.item_name,i.unit_code,i.unit_name,i.qty,i.unit_rate,i.taxable_amount,i.total_amount,i.d1,i.d3,i.d4,i.d6,i.d7,i.short_narration,s.source_id,hexblob(i.record_sha256)
      from src.voucher_items i join src.vouchers sv on sv.voucher_id=i.voucher_id join vouchers tv on tv.stable_id=hexblob(i.voucher_id) join sources s on s.source_hash=hexblob(i.source_sha256) where sv.vch_date<=?""",(BOUNDARY,))
    con.execute("""insert into voucher_ledger(stable_id,voucher_id,rec_type,sr_no,ledger_code,ledger_name,value1,value2,value3,d1,d2,d3,d4,d5,short_narration,source_id,record_hash)
      select hexblob(l.ledger_line_id),tv.voucher_id,l.rec_type,l.sr_no,l.ledger_code,l.ledger_name,l.value1,l.value2,l.value3,l.d1,l.d2,l.d3,l.d4,l.d5,l.short_narration,s.source_id,hexblob(l.record_sha256)
      from src.voucher_ledger l join src.vouchers sv on sv.voucher_id=l.voucher_id join vouchers tv on tv.stable_id=hexblob(l.voucher_id) join sources s on s.source_hash=hexblob(l.source_sha256) where sv.vch_date<=?""",(BOUNDARY,))
    con.execute("""insert into voucher_narration(voucher_id,party_code,party_name,narration1,narration2,voucher_notes,search_text,source_id,record_hash)
      select tv.voucher_id,n.party_code,n.party_name,n.narration1,n.narration2,n.voucher_notes,n.search_text,s.source_id,hexblob(n.record_sha256)
      from src.voucher_narration n join src.vouchers sv on sv.voucher_id=n.voucher_id join vouchers tv on tv.stable_id=hexblob(n.voucher_id) join sources s on s.source_hash=hexblob(n.source_sha256) where sv.vch_date<=?""",(BOUNDARY,))
    now=datetime.now(timezone.utc).isoformat(); con.executemany('insert into warehouse_meta(key,value) values(?,?)',{'state':'SEALED','boundary':BOUNDARY,'created_at':now,'source':source.name,'immutable_evidence':'true'}.items()); con.commit()
    out_n=con.execute('select count(*) from vouchers').fetchone()[0]; out_max=con.execute('select max(vch_date) from vouchers').fetchone()[0]; fk=list(con.execute('pragma foreign_key_check')); oq=con.execute('pragma quick_check').fetchone()[0]
    con.execute('detach database src'); con.execute('vacuum'); con.close()
    if oq!='ok' or fk or out_n!=n or out_max>BOUNDARY: temp.unlink(missing_ok=True); raise SystemExit(f'Sealed build verification failed quick={oq} fk={len(fk)} expected={n} actual={out_n} max={out_max}')
    dest.unlink(missing_ok=True); temp.replace(dest)
    print(json.dumps({'status':'sealed_history_ready','path':str(dest),'vouchers':out_n,'max_date':out_max,'sha256':sha256_file(dest),'canonical_write':False},indent=2))

if __name__=='__main__': main()
