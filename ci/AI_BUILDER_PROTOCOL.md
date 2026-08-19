# TAGRO ECHO OS — AI Builder Protocol

Status: Mandatory

The AI builder is disposable. Governance is persistent.

## Entry gate — required before mutation
1. Read `governance/constitution/ECHO_OS_CONSTITUTION.md`.
2. Read `governance/state/ECHO_OS_FOUNDATION.json`.
3. Read `governance/state/CURRENT_STATE.json`.
4. Read `governance/decisions/DECISION_LEDGER.md`.
5. Read contracts/schemas for every component to be touched.
6. Read the active Work Order.
7. Identify allowed paths/resources and forbidden paths/resources.
8. Identify existing facts, assumptions and unresolved contradictions.
9. Do not mutate until scope is understood.

## Work discipline
- Do not import legacy TAGRO code by convenience.
- Do not fix out-of-scope defects; record them for later review.
- Do not alter Constitution or core contracts during ordinary feature work.
- Do not claim a capability complete because files/routes/tables exist.
- Do not convert `planned`, `candidate` or `experiment` into `active` without the stated acceptance gate.
- Do not infer AWS resources, credentials, database state or integrations from documentation.
- Do not let AI-generated observations bypass the owning domain's confirmation/authority contract.
- Preserve evidence and provenance.

## Evidence classes for claims
Use the strongest class actually achieved:
- documented intent
- file exists
- parses/validates
- unit test passed
- integration path passed
- end-to-end journey passed
- deployed and observed
- externally reconciled/confirmed

Never report a weaker check as a stronger one.

## Exit gate
Before ending a work session, record:
- work order;
- files/resources changed;
- tests actually run and exact outcome;
- runtime/deployment changes actually made;
- open defects and unresolved questions;
- architecture/constitutional changes, normally NONE;
- next safe action;
- session ledger entry.

Update Current State when reality materially changes.

## Scope breach handling
If work reveals a flaw outside the active Work Order:
1. do not modify it;
2. record an observation with evidence;
3. explain why it may matter;
4. leave it for a future authorised Work Order.

The AI may challenge the architecture. It may not silently replace it.
