# TAGRO × ECHO — Data Read/Write/Processing Readiness

Date: 2026-08-22
Status: verified repository/runtime review; not a production-readiness claim

## Executive conclusion

ECHO can already perform authenticated, server-side, transactional writes into the shared NonProd PostgreSQL database for admitted runtime paths. Billing is the clearest proven implementation: a bill admission writes sale header, lines, stock movements, payment evidence where applicable, and ECHO audit events in one database transaction with server-side membership/capability checks and idempotency protection.

ECHO also has authenticated readback paths for tenant context, governed reference data, Owner ON CALL, Closing Cash day readback and import reconciliation. These demonstrate that written/shared operational information can be retrieved and processed into higher-level projections.

The repository already contains domain structures for sales, customers, products, stock, stock counts, transfers, purchases/PO, service, cash, payments, bank evidence, reports, documents, enterprise/authority, events and evidence. This is sufficient structural ground for business and intelligence projections.

However, two important limits remain:

1. BUSY live write is NOT yet proven. BUSY Dock v1 is deliberately read-oriented. It can resolve BUSY nodes/bindings, use stored snapshots, prepare idempotent handoff envelopes and record returned results, but it does not itself open or mutate a BUSY database. A queued BUSY handoff is not a booked BUSY transaction.
2. The warehouse/Observer production intelligence runtime is not yet active. Current intelligence surfaces therefore must consume governed runtime readbacks and clearly label unavailable or unproved domains rather than inventing a unified historical intelligence store.

## 1. ECHO write path — VERIFIED IN CODE / NONPROD RUNTIME CANDIDATE

The current billing runtime performs atomic PostgreSQL writes for:

- sale_headers
- sale_lines
- stock_movements
- payment_receipts where payment is staff-affirmed
- payment_allocations
- echo_events for sale/payment audit truth

The runtime checks authenticated principal, enterprise membership, capability, branch, product ownership, GST consistency, stock evidence state and idempotency before admission.

Other admitted POST routes exist for:

- service intake
- purchase orders
- stock-count observation
- cash-day open
- cash entries
- cash-day submit
- cash-document save

These routes pass through the authenticated Lambda/runtime boundary and server-side capability checks.

## 2. ECHO readback — PRESENT AND USABLE

Current authenticated GET/readback routes include:

- /tenant-context
- /reference-data
- /owner-on-call
- /cash-days
- /import-reconciliation
- /db-health

Owner ON CALL already proves the intended pattern: operational records are read from shared persistence and transformed into a higher-level management projection with evidence/freshness/confidence semantics.

Closing Cash readback proves historical day retrieval over date/branch filters.

Reference data proves shared master retrieval for products/branches and other admitted kinds.

## 3. Historical information

ECHO's event and domain-table architecture is suitable for historical reads because meaningful events retain event time, recorded time, actor, location, subject, authority/provenance and payload. Domain tables retain business records such as sales and cash days.

Current runtime readback is not yet a universal historical-query API. Therefore the business/intelligence UI may expose existing readbacks now, while future historical services should add governed query endpoints rather than direct browser SQL.

The future warehouse remains the correct long-horizon analytical receiver. It should continuously ingest admitted operational events and external evidence without modifying operational truth.

## 4. BUSY accounting/finance/MIS

BUSY remains a docked specialist engine.

Current BUSY Dock v1 supports:

- masters read capability
- transaction reads
- stock reads
- balances
- ledgers
- report catalogue
- reports
- offline last-known snapshots with stale=true
- idempotent handoff-envelope preparation
- returned handoff-result recording

Current BUSY Dock v1 explicitly does NOT mutate BUSY itself.

Therefore ECHO UI state vocabulary must remain:

ECHO accepted → BUSY handoff prepared/queued → BUSY result returned → BUSY booked/confirmed

Only the last confirmed state may be shown as BUSY booked.

A live BUSY bridge must be implemented and proven against a copied/test company first, with write, readback, reconciliation, idempotency and failure/retry evidence, before production BUSY write is admitted.

## 5. Business processing receivers

The same admitted event/data can legitimately project to multiple receivers without becoming multiple truths.

### Financial / accounting
Sales, payment evidence, cash, expenses, bank evidence, BUSY results, allocations and reconciliation can feed financial projections and accounting handoff/readback.

### Logistics
Order/dispatch/shipment/delivery events can project to Amazon Shipping, Delhivery or another replaceable carrier adapter. Carrier acknowledgements and tracking updates remain evidence linked to the ECHO shipment.

### Storekeeping / stock
Sale movements, purchase receipts, transfers, service part use and physical-count observations can project into canonical/provisional stock views, variance, reorder suggestions and exception queues.

### Reordering / purchasing
Usage, stock position, outstanding requirements, service-part demand, supplier lead time, cost and sales velocity can produce purchase recommendations. AI may recommend; governed authority creates the PO/order.

### Customer follow-up
Customer, sale, service, delivery, warranty and communication events can create follow-up receivers such as due follow-up, service-ready notification, post-delivery call, renewal/warranty attention and feedback request.

### Service live tracking
Service intake, responsibility/take-job, observation, diagnosis, estimate/approval, parts, work, ready, billing, delivery and customer confirmation can be projected as a live job timeline.

### Consignment / delivery / inspection
Dispatch, carrier handoff, transit, delivery, receipt inspection, discrepancy/damage evidence, return and customer acknowledgement can be maintained as separate time-stamped events linked to the same consignment/order.

### After-work / confirmation / feedback
Completed work can project to customer confirmation, after-work inspection, follow-up due date, warranty evidence and structured feedback without overwriting the service completion event.

## 6. Intelligence / BIS direction

The intelligence layer should read governed operational events and projections and produce:

- current situation
- exceptions / needs attention
- trends
- forecasts
- reorder candidates
- service bottlenecks
- customer follow-up candidates
- cash/finance warnings
- stock anomalies
- logistics exceptions
- branch comparisons
- evidence-quality/freshness warnings
- AI prepared recommendations with provenance

The Observer/BIS layer remains read-only to operational truth. It may prepare or recommend a Driver action; it may not silently execute consequential changes.

## 7. UI consequence

Two new structural surfaces are justified:

### BUSINESS
A governed current-business workspace: Today, Sales, Cash/Finance, Stock, Service, Purchase, Logistics, Customers and downstream/BUSY state.

### INTELLIGENCE
A read-only Observer/BIS workspace: Needs Attention, Trends, Opportunities, Risks, Forecasts, Recommendations, Data Health and Evidence/Confidence.

These are projections over the same operational truth, not new stores of truth.

## 8. Admission rule for the pages

A tile/card may show real numbers only when an admitted readback currently supports them. Otherwise it must show `Not connected`, `Awaiting readback`, `No current evidence` or equivalent. UI structure may precede a data adapter; invented figures may not.
