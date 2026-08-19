from __future__ import annotations
from typing import Any, Iterable, Mapping, Protocol


class RepositoryPort(Protocol):
    """Replaceable persistence boundary.

    Domain engines depend on this contract, not on PostgreSQL, AWS, Dropbox,
    localStorage, BUSY, or any other concrete persistence technology.
    """
    def put(self, collection: str, record_id: str, record: Mapping[str, Any]) -> None: ...
    def get(self, collection: str, record_id: str) -> Mapping[str, Any] | None: ...
    def list(self, collection: str) -> Iterable[Mapping[str, Any]]: ...
    def append(self, stream: str, record: Mapping[str, Any]) -> None: ...


class MemoryRepository:
    def __init__(self): self._collections={}; self._streams={}
    def put(self,collection,record_id,record): self._collections.setdefault(collection,{})[record_id]=dict(record)
    def get(self,collection,record_id):
        row=self._collections.get(collection,{}).get(record_id); return dict(row) if row else None
    def list(self,collection): return [dict(x) for x in self._collections.get(collection,{}).values()]
    def append(self,stream,record): self._streams.setdefault(stream,[]).append(dict(record))
    def stream(self,stream): return [dict(x) for x in self._streams.get(stream,[])]
