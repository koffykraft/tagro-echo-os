# Closing Cash Engine v1 Contract

Status: candidate under WO-0010

## Purpose
Closing Cash is the enterprise-scoped operational record of what happened to the day's money. It is independent from BUSY books while remaining reconcilable with BUSY, bank and service evidence.

## Daily identity
One active closing per enterprise and business date. A corrected closing supersedes the prior record rather than silently rewriting it.

## Entry classes
Physical cash in: cash sale, cash receipt, service cash receipt, other cash in.

Physical cash out: cash expense, cash deposit, cash transfer out, cash allocation.

Non-cash in: UPI receipt, card receipt, bank receipt, service non-cash receipt.

Non-cash out: non-cash expense, bank transfer out.

Allocations/contra are not expenses. BUSY sales are not automatically cash received. A bank credit is not automatically a customer payment.

## Arithmetic
Expected physical cash = opening physical cash + physical cash inflows - physical cash outflows.
Non-cash movements are reported separately and do not change expected physical cash.
Variance = declared physical closing cash - expected physical cash.

## Lifecycle
Draft -> Submitted -> Approved.
Submitted/approved records are not edited in place. Corrections create a replacement closing with `supersedes_closing_id` and the previous closing becomes superseded.

## Multi-user
Any authorized enterprise user may contribute entries according to role/tool permissions. Each entry preserves actor identity. Final submit and approval actors are explicit and may be different people.

## Offline/mobile
Entries carry idempotency keys. Offline replay of the identical payload returns the original entry; the same idempotency key with changed payload is rejected. Offline state must never hide that BUSY/bank reconciliation is pending.

## Reconciliation
`reference_type`, `reference_id`, evidence references and metadata may point to BUSY voucher candidates, service records, bank evidence or other sources. A reference does not by itself prove reconciliation.

## Evidence
Receipts, photos, payment screenshots and other source evidence may be linked by `evidence_ref`; raw evidence remains separate from classification.
