# TAGRO ECHO OS — Database Diligence Before Page Engineering

Date: 2026-08-22
Work order: WO-0014
Status: engineering diligence; implementation follows this conclusion

## 1. Question

Before building/deploying the actual pages, confirm that ECHO can use one primary shared database for current operations, historical memory, cross-domain business processing, BIS/AI and frontend population, while preserving the existing Planar/Prismatic separation of TAGRO history.

## 2. Evidence inspected

- AWS NonProd shared runtime: Cognito -> API Gateway -> Lambda -> private PostgreSQL `echoos` is already proven reachable and authenticated.
- ECHO billing/cash/service/purchase/stock runtimes already contain PostgreSQL-backed command paths.
- Dropbox/AWS daily source pipeline currently refreshes Busy, Closing Cash, bank, service and historical evidence into SQLite/JSON/report products.
- `/TAGRO_AUTOMATION/TAGRO_AWS_OS_WAREHOUSE` already builds separated source databases and `databases/planar.sqlite`.
- Latest inspected warehouse manifest (2026-08-21 run) reports Planar with 498,014 events and 498,014 evidence records, plus source-specific Busy, Closing Cash, Bank and Service databases, all integrity `ok`.
- ECHO repo `WAREHOUSE_MOVE_PHASE1_CONTRACT.json` already identifies `planar.sqlite` as the historical backbone.
- Existing ECHO PostgreSQL Operational Twin importer is idempotent but currently persists historical material into generic `twin_source_records`.

## 3. Diligence finding

### Proven and suitable

1. **PostgreSQL is suitable as primary ECHO working database.** It already supports private shared transactional persistence and authenticated runtime access.
2. **ECHO operational writes can persist in PostgreSQL.** Billing, cash, service intake, purchase order and stock count runtime code use the shared database boundary.
3. **Historical information exists in sufficient depth.** TAGRO has long multi-branch Busy history, service history, Closing Cash and bank evidence.
4. **The historical warehouse has already performed a valuable Planar decomposition.** The source databases and `planar.sqlite` must be preserved as an upstream transformation/evidence process rather than bypassed.
5. **Frontend should consume ECHO APIs backed by PostgreSQL.** LocalStorage/JSON remains offline draft/cache support only.

### Defect found

The current Operational Twin PostgreSQL importer preserves source provenance but collapses the already-separated Planar material into a generic record table. This is not destructive to source evidence, but it is an inefficient working structure for Business/BIS/AI and risks recreating the Planar model later in page code.

### Required correction

Add explicit PostgreSQL Operational Twin Planar tables:

- `twin_planar_entities`
- `twin_planar_events`
- `twin_planar_event_entities`
- `twin_planar_evidence`
- `twin_planar_relationships`
- sync/checkpoint metadata

Keep `twin_source_records` only as a raw/audit intake layer when useful.

## 4. Primary data route

```text
TAGRO live/branch sources
  -> Dropbox/AWS intake scripts
  -> source-specific warehouse stores (Busy / Closing Cash / Bank / Service / others)
  -> Planar filter (`planar.sqlite`)
  -> checkpointed Planar export
  -> private ECHO ingestion Lambda
  -> ECHO PostgreSQL explicit Planar tables
  -> authenticated ECHO read/write APIs
  -> operational pages + Business + Intelligence/BIS
```

ECHO-generated transactions enter PostgreSQL through their operational command runtimes and remain distinguishable from imported TAGRO historical evidence through provenance/source fields.

## 5. Read capability required

The database-backed read layer must support at minimum:

- date/branch/domain/event type filters;
- customer/party/item/machine/service search;
- historical event timelines;
- source/provenance drill-down;
- branch comparisons;
- recent/current operational state;
- aggregated business metrics for reports;
- evidence sets for BIS/AI retrieval;
- pagination/cursors so history does not require loading the entire warehouse to the browser.

The UI must not read arbitrary SQLite files directly.

## 6. Business processing enabled by this structure

The same database can support separate authorised projections for:

- finance and accounting reconciliation;
- sales and margins;
- stock position, count observations, movements and historical inference as separate planes;
- purchase/reordering;
- storekeeping and transfers;
- customers and follow-up;
- service intake, live job status, parts/work and customer confirmation;
- consignments, shipments, delivery, inspections and returns;
- after-work/customer confirmation and feedback;
- branch performance;
- management attention;
- BIS/AI retrieval, comparison, anomaly detection and recommendations.

These are projections/receivers over shared events/evidence, not duplicate truth stores.

## 7. BUSY diligence

ECHO -> BUSY request/envelope capability and registry exist, but **live BUSY mutation/readback has not yet been directly proven by the ECHO runtime**. Therefore page wording must distinguish:

- ECHO recorded/accepted;
- BUSY waiting;
- BUSY booked/read back;
- reconciliation required.

WO-0014 may implement and test the bridge, but no page may label a transaction BUSY-booked before readback evidence exists.

## 8. Frontend consequence

Actual page engineering may proceed once the explicit Planar PostgreSQL ingestion/read API is present in code. The canonical frontend will use:

- authenticated runtime context;
- database-backed reference/history/business read APIs;
- PostgreSQL command APIs for writes;
- explicit offline drafts/queues;
- one coherent responsive shell.

## 9. Brand assets

Approved source assets were located in:

`/Echo Equipment 2026/Echo GPT/00_SOURCE/Echo India Aug 2026/`

Including:

- `tagro echo logo.png`
- `tagro_echo_900-240.png`
- `tagro_echo_1600_400.png`

Use responsive logo sources: compact asset for phone header/splash and larger asset for tablet/laptop/desktop. The actual source files must be copied into the deployed web asset bundle rather than hot-linked to private Dropbox URLs.

## 10. Decision

**Proceed.**

The architecture is capable of write -> persist -> readback -> historical retrieval -> business projection -> BIS/AI processing. The required correction is to make the already-established Planar historical structure explicit in PostgreSQL and connect the scheduled source pipeline to it before treating the new pages as database-complete.
