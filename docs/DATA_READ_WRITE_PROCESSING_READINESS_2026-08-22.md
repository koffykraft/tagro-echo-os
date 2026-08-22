# TAGRO × ECHO — Data Read/Write/Processing Readiness

Date: 2026-08-22
Status: verified repository/runtime review for the isolated ECHO Operational Twin; not a production-readiness claim

## Executive conclusion

ECHO can already perform authenticated, server-side, transactional writes into the shared NonProd PostgreSQL database for admitted runtime paths. Billing is the clearest proven implementation: a bill admission writes sale header, lines, stock movements, payment evidence where applicable, and ECHO audit events in one database transaction with server-side membership/capability checks and idempotency protection.

ECHO also has authenticated readback paths for tenant context, governed reference data, Owner ON CALL, Closing Cash day readback and import reconciliation. These demonstrate that written/shared operational information can be retrieved and processed into higher-level projections.

The ECHO validation environment is now explicitly an Operational Twin. Imported TAGRO historical and multi-branch data from inception is a realistic baseline for running ECHO as though it were a live business. ECHO-generated validation writes have zero writeback authority into TAGRO actual operations. Imported baseline records and ECHO-generated events remain distinguishable by provenance so comparison remains meaningful.

The repository already contains domain structures for sales, customers, products, stock, stock counts, transfers, purchases/PO, service, cash, payments, bank evidence, reports, documents, enterprise/authority, events and evidence. This is sufficient structural ground for business and intelligence projections.

Two important technical gaps remain, but they are now test objectives rather than reasons to artificially constrain the twin:

1. BUSY live write/readback is not yet implemented in the ECHO runtime. BUSY Dock v1 is deliberately read-oriented. It can resolve BUSY nodes/bindings, use stored snapshots, prepare idempotent handoff envelopes and record returned results, but it does not itself open or mutate a BUSY database.
2. The long-horizon warehouse/Observer runtime is not yet active as a unified analytical service. Existing TAGRO historical data may nevertheless be used as the Operational Twin baseline while governed historical-query/warehouse services are built.

## 1. ECHO write path — PRESENT

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

Operational Twin consequence: these paths should be exercised with realistic branch/customer/product/history context, not merely synthetic happy-path records.

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

## 3. Historical information and Operational Twin comparison

ECHO's event and domain-table architecture is suitable for historical reads because meaningful events retain event time, recorded time, actor, location, subject, authority/provenance and payload. Domain tables retain business records such as sales and cash days.

The imported TAGRO history provides the realistic long-run comparison field now. The objective is not merely to display old records. ECHO should be able to:

- retrieve historical customer/product/branch/service/stock/financial context;
- compare periods and branches;
- replay realistic operating questions against the data;
- generate ECHO recommendations and forecasts;
- run new ECHO Operational Twin events beside the historical baseline;
- compare ECHO outputs with historical/actual TAGRO outcomes;
- identify where ECHO improves speed, visibility, accuracy, follow-up or control.

Current runtime readback is not yet a universal historical-query API. The next data layer should therefore expose governed historical/query endpoints rather than browser-direct database queries.

The future warehouse remains the correct scalable long-horizon analytical receiver, but the absence of that service does not prevent realistic Operational Twin development using the imported history already available.

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

The correct next proof is a fully isolated ECHO BUSY twin/company/database path. Because it has zero impact on TAGRO actual books, we should exercise it like a real accounting environment:

ECHO transaction → BUSY write → BUSY voucher/result → BUSY readback → ECHO reconciliation → report/MIS consumption.

State vocabulary remains truthful during development:

ECHO accepted → BUSY handoff prepared/queued → BUSY result returned → BUSY booked/confirmed.

Once the isolated BUSY twin write/readback is proven, realistic volume and workflow testing should continue rather than stopping at a single smoke test.

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

The intelligence layer should read governed operational events, imported historical context and projections and produce:

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
- historical-vs-ECHO Operational Twin comparisons
- evidence-quality/freshness warnings
- AI prepared recommendations with provenance

The Observer/BIS layer remains read-only to operational truth. It may prepare or recommend a Driver action; it may not silently execute consequential changes.

## 7. UI consequence

Two structural surfaces are justified and have now been created as candidates:

### BUSINESS
A governed current-business workspace: Today, Sales, Cash/Finance, Stock, Service, Purchase, Logistics, Customers and downstream/BUSY state.

### INTELLIGENCE
A read-only Observer/BIS workspace: Needs Attention, Trends, Opportunities, Risks, Forecasts, Recommendations, Data Health and Evidence/Confidence.

These are projections over the same operational truth and Operational Twin history, not new stores of truth.

## 8. Development rule for the pages

Use real Operational Twin data wherever a governed read path exists or can be safely added. Do not cripple the simulation because the baseline came from TAGRO actual history.

When a read adapter is not yet available, the page may show the intended receiver/state but must not invent a number. The correct development response is to add the missing governed read/query path and then exercise it against the Operational Twin dataset.
