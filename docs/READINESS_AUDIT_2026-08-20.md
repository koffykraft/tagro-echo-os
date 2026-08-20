# TAGRO ECHO OS — Three-Day Onboarding Readiness Audit

Date: 2026-08-20
Status: candidate under WO-0011

## Objective
Prepare the current TAGRO ECHO OS body for rapid mobile onboarding without claiming production integrations that do not yet exist. Service Memory is intentionally deferred until after deployment verification.

## Verified body already present
- Enterprise Directory with configurable hierarchy.
- Multiple users per enterprise with independent roles/tool packs.
- Multi-node BusyNode registry with material-centre and voucher-series bindings.
- BUSY Engine Dock v1: capability routing, offline normalized snapshots, idempotent online handoff envelopes, no credential storage and no false live-I/O claim.
- Closing Cash Engine v1: physical/noncash separation, expenses versus allocations, deposits/transfers, service receipts, declared variance, lifecycle, supersession, actor audit and idempotent offline entries.
- Sales, purchases, quotations, customers, suppliers, products/prices, stock ledger, stock counts, transfers, purchase orders, payments, printable documents, bank evidence normalization, reports, import/export and accounting export prototypes.
- Mobile pages for counter operations, service, Closing Cash, bank import, payments and documents.

## Mobile/offline readiness added in WO-0011
- Web application manifest.
- Standalone mobile display candidate.
- Local app icon.
- Service worker caching all core pages and static shell.
- Network-status banner distinguishing online availability from confirmed synchronization.
- Core workflows retain browser-local operation during disconnection.
- No core page may depend on an external CDN for basic operation.

## Critical truth boundaries
- Local/offline data is not shared-server truth until synchronized and acknowledged.
- BUSY snapshot data may be stale and must be labelled stale.
- A BUSY handoff request is not a booked voucher until result/readback confirms it.
- BUSY sales do not prove cash receipt.
- Bank credit does not prove customer payment.
- Closing Cash allocation/contra is not an expense.
- Missing data does not become zero.
- User access to an enterprise does not automatically grant every tool or approval right.

## Remaining blockers before production onboarding
1. Shared production persistence is not deployed. Current web prototypes use browser localStorage plus non-production repository abstractions.
2. Production authentication/authorization is not deployed. Enterprise role/tool assignments exist, but server-side enforcement still requires the deployed application boundary.
3. Live BUSY bridge is not admitted. Existing TAGRO native-write/read work is evidence/reference; ECHO BUSY Dock v1 currently prepares/serves contracts and snapshots only.
4. Cloudflare transport/Dropbox queue and local Windows BUSY agent need to be connected to the ECHO BusyNode registry and tested against a non-production/copied BUSY company before production write admission.
5. Closing Cash synchronization needs the same shared persistence/identity boundary.
6. Production domain URL/hosting and install verification on representative Android/iPhone devices remain to be completed.
7. Backup/recovery drill and first-counter rollback procedure remain to be proven on deployed infrastructure.

## Three-day onboarding sequence
### Day 1 — body and audit
- Freeze application scope: no new Service Memory or unrelated features.
- Complete BUSY Dock v1 and Closing Cash v1.
- Complete PWA/offline shell and automated readiness checks.
- Audit every core page, role surface, import/export contract and truth boundary.
- Produce explicit blocker list rather than hiding missing integrations.

### Day 2 — shared runtime and bridge
- Deploy one controlled shared application runtime and authentication boundary.
- Configure first real Enterprise, its users/roles/tool packs and one BusyNode/material-centre mapping.
- Connect Cloudflare/Dropbox transport to a local BUSY bridge in read-only/copied-company mode first.
- Synchronize Closing Cash and core counter records.
- Verify offline create -> reconnect -> idempotent sync -> acknowledged state.

### Day 3 — first-counter parallel run
- Run one counter in parallel with existing procedures.
- Compare ECHO sales/stock/Closing Cash against BUSY and physical evidence.
- Verify role separation for franchisee owner, staff and TAGRO area executive.
- Test offline operation during deliberate network loss.
- Perform rollback/recovery drill.
- Admit production use only for the workflows that pass evidence-based acceptance.

## Deliberately deferred
- Service Memory historical aggregation and handwritten-sheet ingestion.
- Counter Intelligence AI/vision provider.
- Large-scale warehouse/logistics plugins.
- Full network rollout beyond the first verified counter.

These remain structurally allowed but must not delay the first controlled deployment.
