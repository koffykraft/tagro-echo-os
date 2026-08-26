# DEC-0024 — PostgreSQL is the primary ECHO working data field; historical Planar structure is preserved

Status: Owner-approved direction under WO-0014
Date: 2026-08-22

## Decision

ECHO PostgreSQL is the primary shared working database for operational state, historical working memory and database-backed business/intelligence projections.

The existing TAGRO AWS OS warehouse remains a valuable upstream ingestion/transformation system. Its source-specific Busy, Closing Cash, Bank, Service and other evidence is already projected through `databases/planar.sqlite` into entities, events, event-entity links, evidence and relationships. That Planar separation must be preserved when historical material enters PostgreSQL.

Dropbox/AWS source scripts are feeders and refresh mechanisms. Browser local storage is limited to scoped drafts/offline queues/resilience. Neither becomes a parallel primary business truth.

## Required data route

`TAGRO/source updates -> source-specific warehouse stores -> planar.sqlite -> checkpointed ECHO ingestion -> PostgreSQL Planar working memory -> authenticated ECHO APIs -> operational pages / Business / Observer-BIS`

ECHO-generated operational events enter PostgreSQL through authenticated command runtimes and remain provenance-distinguishable from imported historical TAGRO evidence.

## Rejected

- rebuilding another flat historical warehouse beside the existing Planar warehouse;
- making `tagro_history.sqlite`, JSON reports or browser localStorage the primary frontend data source;
- importing Planar records only into a generic blob table and recreating entity/event/evidence relationships later in UI/report code;
- allowing individual pages to create their own duplicate historical truth stores.

## Reason

Database diligence showed that the existing AWS/PostgreSQL runtime already proves shared transactional persistence, while the TAGRO historical warehouse already contains a useful Planar decomposition. Combining those proven strengths provides a stronger future path than preserving either earlier system in isolation.

## Compatibility

Raw/source provenance remains available. Existing ECHO operational schemas retain their meaning. New Operational Twin Planar tables add historical working memory without reinterpreting ECHO-generated events.

## Proof required before completion claim

- migration applied to the actual ECHO PostgreSQL database;
- checkpointed Planar ingestion executed;
- `/twin-source-status` returns Planar counts/freshness from PostgreSQL;
- `/twin-history` retrieves historical events with pagination/filtering;
- an operational write is persisted and read back through the ECHO runtime;
- frontend uses these runtime paths rather than direct SQLite/JSON access.
