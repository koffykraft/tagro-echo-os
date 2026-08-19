# TAGRO ECHO OS Runtime Skeleton v0.1

Status: WO-0002 candidate runtime skeleton. Not production. No AWS resources are implied by this document.

## Purpose

Turn the founding skeleton into replaceable software boundaries without binding the system to a particular AWS service, database, AI model, accounting package, UI framework or mobile implementation.

## Dependency direction

```text
             +-----------------------+
             |        CORE           |
             | events / identity refs|
             | evidence / authority  |
             +-----------+-----------+
                         ^
              reads/uses | reads/uses
                         |
          +--------------+---------------+
          |                              |
+---------+---------+          +---------+---------+
|      DRIVER       |          |     OBSERVER      |
| operational       |          | read-only         |
| command boundary  |          | finding boundary  |
+-------------------+          +-------------------+
```

Rules:

1. Core imports neither Driver nor Observer.
2. Driver may depend on Core contracts.
3. Observer may depend on Core contracts.
4. Observer must not import Driver or expose Driver execution interfaces.
5. Driver does not need Observer to perform deterministic operational work.
6. Findings do not become operational events merely because they exist.
7. A future automated response to a finding must enter through an authorised Driver component with its own contract.

## Core

`src/core/event.py` is the first executable representation of admitted events.

It carries:
- event identity and type;
- version;
- event, recorded and source-effective time;
- location;
- authenticated authority context;
- entity references;
- evidence references;
- provenance;
- confidence where relevant;
- idempotency key;
- causal links;
- supersession link;
- domain payload.

Domain payload is intentionally open at this layer. Stock, cash, sale, service and other domains will receive their own schemas/contracts rather than expanding Core for every business detail.

## Driver

`src/driver/ports.py` defines the operational command boundary.

A Driver implementation receives a command and returns a result plus admitted events. A real Driver component must separately prove:
- authentication and authority;
- deterministic business validation;
- idempotency;
- durable write semantics;
- failure/retry behaviour;
- evidence/audit trail;
- replacement contract.

The current port does not implement any business operation.

## Observer

`src/observer/ports.py` receives admitted events and emits findings.

It has no operational execution method and no Driver dependency. Findings contain evidence/event references, compared components, rule/model identity, assumptions, confidence, message and recommended review.

The current port does not implement an AI model or autonomous monitoring service.

## Replaceability test

A compliant replacement must be possible behind the relevant port without changing the meaning of admitted historical events.

A replacement may change implementation technology. It may not silently change:
- event meaning;
- authority meaning;
- evidence lineage;
- idempotency semantics;
- correction/supersession semantics;
- Observer read-only authority.

If meaning must change, a versioned migration/decision is required.

## Current verification

An independent execution mirror of the committed runtime skeleton ran five unit tests successfully on 2026-08-19:
- valid event accepted;
- missing idempotency rejected;
- unauthenticated authority rejected;
- Observer interface has no `execute` method;
- Observer module does not import `src.driver`.

This is source-level/runtime-boundary evidence only. It is not AWS, database, load, security or production acceptance evidence.
