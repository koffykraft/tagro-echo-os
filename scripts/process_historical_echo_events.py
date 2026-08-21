from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "tagro.echo-os.historical-event-candidates/1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(*parts: object) -> str:
    raw = '|'.join('' if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def read_checkpoint(path: Path) -> dict:
    if not path.is_file():
        return {"schema":"tagro.echo-os.historical-sweep-checkpoint/1","completed":[],"failed":[]}
    return json.loads(path.read_text(encoding='utf-8'))


def write_checkpoint(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def process_slice(con: sqlite3.Connection, branch: str, fy: str, output: Path, source_sha: str) -> dict:
    vouchers = con.execute(
        """
        select voucher_id, stable_id, vch_code, vch_type, vch_date, vch_no, series_code,
               party_code, party_name, total_amount, taxable_amount, cancelled,
               vch_cancelled, auto_vch_no, hex(record_hash)
        from vouchers where branch=? and financial_year=? order by vch_date,vch_code
        """, (branch, fy)
    ).fetchall()
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix('.building.jsonl')
    count = 0
    with tmp.open('w', encoding='utf-8', newline='\n') as w:
        for v in vouchers:
            voucher_id = v[0]
            items = con.execute(
                "select sr_no,item_code,item_name,unit_code,unit_name,qty,unit_rate,taxable_amount,total_amount,d1,d3,d4,d6,d7,short_narration,hex(record_hash) from voucher_items where voucher_id=? order by item_line_id",
                (voucher_id,)
            ).fetchall()
            ledger = con.execute(
                "select rec_type,sr_no,ledger_code,ledger_name,value1,value2,value3,d1,d2,d3,d4,d5,short_narration,hex(record_hash) from voucher_ledger where voucher_id=? order by ledger_line_id",
                (voucher_id,)
            ).fetchall()
            narration = con.execute(
                "select party_code,party_name,narration1,narration2,voucher_notes,search_text,hex(record_hash) from voucher_narration where voucher_id=?",
                (voucher_id,)
            ).fetchone()
            event = {
                "schema": SCHEMA,
                "event_candidate_id": stable_id('historical-busy-voucher', branch, fy, v[2], v[4]),
                "event_type": "accounting.voucher_observed",
                "event_state": "historical_observation",
                "canonical_write": False,
                "branch": branch,
                "financial_year": fy,
                "occurred_on": v[4],
                "voucher": {
                    "source_voucher_id": voucher_id,
                    "stable_id": v[1].hex() if isinstance(v[1], (bytes, bytearray)) else str(v[1]),
                    "vch_code": v[2], "vch_type": v[3], "vch_no": v[5], "series_code": v[6],
                    "party_code": v[7], "party_name": v[8], "total_amount": v[9],
                    "taxable_amount": v[10], "cancelled": bool(v[11]), "vch_cancelled": bool(v[12]),
                    "auto_vch_no": v[13], "record_hash": (v[14] or '').lower(),
                },
                "items": [
                    {"sr_no":r[0],"item_code":r[1],"item_name":r[2],"unit_code":r[3],"unit_name":r[4],"qty":r[5],"unit_rate":r[6],"taxable_amount":r[7],"total_amount":r[8],"d1":r[9],"d3":r[10],"d4":r[11],"d6":r[12],"d7":r[13],"short_narration":r[14],"record_hash":(r[15] or '').lower()} for r in items
                ],
                "ledger": [
                    {"rec_type":r[0],"sr_no":r[1],"ledger_code":r[2],"ledger_name":r[3],"value1":r[4],"value2":r[5],"value3":r[6],"d1":r[7],"d2":r[8],"d3":r[9],"d4":r[10],"d5":r[11],"short_narration":r[12],"record_hash":(r[13] or '').lower()} for r in ledger
                ],
                "narration": None if narration is None else {"party_code":narration[0],"party_name":narration[1],"narration1":narration[2],"narration2":narration[3],"voucher_notes":narration[4],"search_text":narration[5],"record_hash":(narration[6] or '').lower()},
                "provenance": {
                    "source_system": "TAGRO_AWS_OS_WAREHOUSE",
                    "source_class": "sealed_historical_evidence",
                    "source_database_sha256": source_sha,
                    "source_partition": "locked_to_2026-03-31",
                    "source_subject_ref": f"busy:{branch}:{fy}:{v[2]}",
                },
                "confidence": 1.0,
            }
            w.write(json.dumps(event, ensure_ascii=False, separators=(',',':')) + '\n')
            count += 1
    tmp.replace(output)
    return {"branch":branch,"financial_year":fy,"events":count,"output":str(output),"sha256":sha256_file(output),"status":"complete"}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--runtime-root', default=r'T:\TAGRO_AWS_RUNTIME')
    args = p.parse_args()
    root = Path(args.runtime_root)
    source = root / 'data/canonical/tagro-data-platform/partitions/tagro_evidence_locked_to_2026-03-31.sqlite'
    out_root = root / 'data/echo-historical/event-candidates'
    state_root = root / 'state/echo-historical'
    checkpoint_path = state_root / 'checkpoint.json'
    status_path = state_root / 'status.json'
    log_path = state_root / 'historical-sweep.log'
    if not source.is_file():
        raise SystemExit(f'Missing sealed historical partition: {source}')
    source_sha = sha256_file(source)
    uri = f"file:{source.as_posix()}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    quick = con.execute('pragma quick_check').fetchone()[0]
    if quick != 'ok':
        raise SystemExit(f'Historical source quick_check failed: {quick}')
    slices = con.execute("select branch,financial_year,count(*) from vouchers group by branch,financial_year order by financial_year,branch").fetchall()
    checkpoint = read_checkpoint(checkpoint_path)
    completed = {(x['branch'],x['financial_year']) for x in checkpoint.get('completed',[])}
    checkpoint.update({"source":str(source),"source_sha256":source_sha,"updated_at":now_iso(),"status":"running","canonical_write":False})
    write_checkpoint(checkpoint_path, checkpoint)
    state_root.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as log:
        for branch, fy, expected in slices:
            key = (branch, fy)
            if key in completed:
                continue
            try:
                result = process_slice(con, branch, fy, out_root / fy / f'{branch}.jsonl', source_sha)
                result['expected_vouchers'] = expected
                checkpoint.setdefault('completed', []).append(result)
                checkpoint['updated_at'] = now_iso()
                write_checkpoint(checkpoint_path, checkpoint)
                line = json.dumps(result, ensure_ascii=False)
                print(line, flush=True); log.write(line + '\n'); log.flush()
            except Exception as exc:
                fail = {"branch":branch,"financial_year":fy,"status":"failed","error":str(exc),"at":now_iso()}
                checkpoint.setdefault('failed', []).append(fail)
                checkpoint['updated_at'] = now_iso()
                write_checkpoint(checkpoint_path, checkpoint)
                line = json.dumps(fail, ensure_ascii=False)
                print(line, flush=True); log.write(line + '\n'); log.flush()
                continue
    con.close()
    checkpoint['status'] = 'complete_with_failures' if checkpoint.get('failed') else 'complete'
    checkpoint['finished_at'] = now_iso()
    write_checkpoint(checkpoint_path, checkpoint)
    status = {
        "schema":"tagro.echo-os.historical-sweep-status/1",
        "status":checkpoint['status'],
        "source":str(source),"source_sha256":source_sha,
        "completed_slices":len(checkpoint.get('completed',[])),
        "failed_slices":len(checkpoint.get('failed',[])),
        "canonical_write":False,
        "checkpoint":str(checkpoint_path),
        "output_root":str(out_root),
        "finished_at":checkpoint['finished_at'],
    }
    write_checkpoint(status_path, status)
    print(json.dumps(status, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
