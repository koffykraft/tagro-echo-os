from __future__ import annotations
import json
from pathlib import Path


class JsonSnapshotRepository:
    """Simple replaceable file repository for non-production/offline use."""
    def __init__(self,path): self.path=Path(path); self._data={'collections':{},'streams':{}}; self.load()
    def load(self):
        if self.path.exists(): self._data=json.loads(self.path.read_text(encoding='utf-8'))
        return self
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps(self._data,indent=2,sort_keys=True),encoding='utf-8')
    def put(self,collection,record_id,record): self._data['collections'].setdefault(collection,{})[record_id]=dict(record)
    def get(self,collection,record_id):
        row=self._data['collections'].get(collection,{}).get(record_id); return dict(row) if row else None
    def list(self,collection): return [dict(x) for x in self._data['collections'].get(collection,{}).values()]
    def append(self,stream,record): self._data['streams'].setdefault(stream,[]).append(dict(record))
    def stream(self,stream): return [dict(x) for x in self._data['streams'].get(stream,[])]
    def export_snapshot(self): return json.loads(json.dumps(self._data))
    def import_snapshot(self,payload):
        if set(payload)!={'collections','streams'}: raise ValueError('invalid snapshot shape')
        self._data=json.loads(json.dumps(payload)); return self
