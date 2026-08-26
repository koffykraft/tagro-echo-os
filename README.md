# TAGRO ECHO OS

> **CURRENT CONTINUITY GATE — READ FIRST:** Before any architecture, build, migration or deployment work, read [`HANDOFF_CURRENT.md`](HANDOFF_CURRENT.md) completely. It records the currently deployed AWS/PostgreSQL/STIHL foundation, active portal deployment state, Dropbox/Codex sources, UI/UX doctrine, known blockers and exact continuation path. **Do not rebuild from this README or from chat memory.**

Status: FOUNDATION / ACTIVE NONPROD EXECUTION
Created: 19 August 2026

TAGRO ECHO OS is a new, independent, AWS-first, mobile-first operating system for TAGRO's ECHO venture and future scalable business-SaaS use.

It is not a skin over the older TAGRO business system, not a copy of the legacy OS, and not a product website with accounting added later. TAGRO is the first real tenant/execution environment and is used for proof of execution against actual business evidence, not merely proof of concept.

The operating assumption is mobile first. A phone must be sufficient for normal counter work. Desktop and laptop access are optional enhanced surfaces, not prerequisites.

## Independence boundary

TAGRO ECHO OS has its own repository, authentication/authorization, AWS runtime, PostgreSQL operational database, event/evidence/warehouse foundations, mobile/web surfaces and governed integration boundary.

No writable dependency may casually point into the older TAGRO/Stihl/Jain operational system. Existing TAGRO and Codex work is essential evidence/source material for proven business rules, data mappings, workflows and failure lessons; useful skills are to be vetted and re-expressed in the ECHO AWS architecture rather than copied wholesale or ignored and rebuilt.

## Core operating idea

ECHO is the primary operational/orchestration system. BUSY is a docked accounting, inventory and MIS engine for the TAGRO tenant and remains replaceable behind governed identity, handoff and readback contracts.

Every meaningful business action should become attributable evidence/event/state: enquiry, estimate, order, sale, payment, stock receipt, stock move, counter transfer, expense, closing cash, bank receipt, service intake, repair work, part use, dispatch, delivery, return, warranty event, staff action and management decision.

These events feed both current operational state and historical/analytical material with explicit provenance.

## Skeleton

Identity · Event · Evidence · Relationship · Time · Location · Authority · State · Provenance · Confidence

Around the skeleton are replaceable systems: Driver, Observer, warehouse, intelligence, adapters and user experiences.

## Governing rule

Future AI builders do not carry TAGRO ECHO OS forward from chat memory. Repository governance and `HANDOFF_CURRENT.md` carry continuity.

Every builder must read the Constitution, Foundation Manifest, Current State, Decision Ledger, affected contracts, active Work Order and the latest directly observed runtime/deployment evidence before mutation.

## Current truth

A real ECHO NonProd AWS environment exists in account `272037674623`, region `ap-south-1`, including Cognito, API Gateway/Lambda runtime, private RDS PostgreSQL, migrated catalogue schema, TAGRO tenant context and a live 1,934-product STIHL foundation. A separate NonProd data-foundation and private S3/CloudFront web-hosting stack were created during the current WO-0014 portal deployment lane; the portal publication/runtime update is still being completed and must be resumed from `HANDOFF_CURRENT.md` rather than recreated.

The existing live `os.tagro.in` and `service.tagro.in` surfaces have **not** yet been cut over to this AWS portal.

Primary laptop engineering worktree:
`C:\Users\HP\Dropbox\TAGRO_AUTOMATION\projects\tagro-echo-os-git`

Broader source/evidence ecosystems:
- `C:\Users\HP\Dropbox\TAGRO_AUTOMATION`
- `C:\Users\HP\Dropbox\Codex`
