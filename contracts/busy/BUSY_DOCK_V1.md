# BUSY Dock v1 Contract

Status: candidate under WO-0009

## Purpose
BUSY Dock is the replaceable accounting, finance and MIS engine boundary for TAGRO ECHO. It routes requests to one of many registered BusyNodes without making BUSY identity equal enterprise identity.

## Topology
Enterprise -> BusyBinding -> BusyNode -> company/database/material centre/voucher series.

A BusyNode may serve many enterprises. One enterprise may use multiple role-scoped BusyBindings. A counter may have many users; user permissions are resolved at Enterprise assignment level and do not alter the BusyBinding.

## Read operations
- masters
- transactions
- stock
- balances
- ledgers
- report_catalogue
- report

Each operation requires the corresponding declared BusyNode capability.

## Offline mode
The dock may serve the latest normalized snapshot for the selected node and operation. Offline results MUST be marked `source=offline_snapshot` and `stale=true`; missing snapshots remain unavailable, never zero.

## Online handoff
When an online/local BUSY bridge is available, the dock prepares an idempotent envelope containing enterprise, node, actor, operation, material-centre mapping, voucher-series mapping, parameters, payload hash and provenance. Cloud/edge transport does not open a BUSY database directly.

## Result truth
A queued handoff is not a completed BUSY operation. Completion requires a returned result linked to the envelope. BUSY write admission is outside v1.

## Security
No BUSY password, database credential or secret is stored in Enterprise Directory or BusyNode registry. Local bridge credentials remain outside application records and must be provisioned separately.

## Failure isolation
Failure/unavailability of one BusyNode must not corrupt another node or convert stale/missing data into current truth.

## Replacement
BUSY is a docked engine. The same Node -> Adapter -> Contract -> Transport -> Engine -> Result pattern may later host other accounting, supplier, warehouse, logistics, coffee or field-delivery nodes without changing enterprise identity.
