# Owner Deployment Directive — TAGRO vertical identity and deploy authority

Date: 2026-08-22
Authority: Owner explicit direction
Status: ACTIVE

## 1. Vertical identity
TAGRO's current operating dealership vertical is STIHL. Current TAGRO staff operating surfaces shall therefore use the approved TAGRO STIHL identity and supplied TAGRO STIHL brand assets.

ECHO is a separate vertical. The ECHO platform/runtime may power or support operating capabilities, but the user-facing TAGRO STIHL dealership identity must not be visually conflated with an ECHO dealership identity.

Internal API schemas, runtime identifiers, database objects and audit vocabulary may retain ECHO technical names where those names identify the platform rather than the dealership brand.

## 2. Deployment authority
For the furtherance of an effective and improved TAGRO ECHO deployment, the Owner explicitly authorises builders to rewrite or supersede governance text, constitutional implementation rules, validators, tests, work orders, documentation, user-interface code, routing and integration code where the existing form is an obstacle, stale assumption or poorer solution.

This authority is not permission to weaken truth, security, auditability or evidence requirements.

## 3. Protected structures by default
Existing engines, databases, warehouse structures and admitted data-model semantics are protected by default. They must not be redesigned, replaced or structurally changed merely for convenience, aesthetics, test compatibility or builder preference.

A change to an engine or database build/structure requires a concrete deployment obstacle to be identified and recorded first, together with the smallest necessary change, migration impact, rollback path and evidence that the protected structure is the cause of the obstacle.

## 4. Stale governance and tests
When a validator or test asserts an intentionally superseded implementation detail, old UI placement, retired capability name, obsolete migration boundary or superseded integration model, the validator/test shall be updated to the current admitted contract.

Builders must not revert a demonstrably improved implementation merely to make a stale test green.

Tests shall prefer observable invariants and business truth over incidental variable names, exact comments, capitalization or retired navigation placement.

## 5. Invariants that remain protected
The following are not relaxed by this directive:
- identity and server-side authority;
- idempotency for consequential commands;
- evidence/provenance separation;
- unknown is not zero;
- stale/inferred/queued states remain explicit;
- Driver and Observer authority separation;
- AI alone does not establish consequential business truth;
- stock count, stock movement and stock position remain distinct;
- payment claim and reconciliation remain distinct;
- BUSY handoff and BUSY confirmed booking/readback remain distinct;
- corrections/supersessions preserve history;
- cross-enterprise scope may not be widened by client input.

## 6. Branding assets admitted for the current TAGRO vertical
Canonical TAGRO dealership pages shall use:
- `web/assets/brand/tagro-stihl-mobile.png` for compact/mobile presentation;
- `web/assets/brand/tagro-stihl-desktop.png` for larger presentation.

These are responsive derivatives of the Owner-supplied TAGRO STIHL artwork and do not redefine the source brand.

## 7. Pre-action reference rule
Before substantial future action, builders must read the current Constitution, Current State, this directive, the historical/supersession record, affected contracts and relevant recent test/deployment evidence. A prior implementation is evidence, not automatic authority.

## 8. Deployment test
A proposed change is preferred when it improves real deployment or operation while preserving the protected invariants above. Where governance/test wording conflicts with that outcome because the wording represents superseded implementation history, update the wording rather than degrading the system.
