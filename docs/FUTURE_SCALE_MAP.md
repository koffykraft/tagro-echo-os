# TAGRO ECHO OS Future Scale Map

Status: Owner-directed architecture map under WO-0012
Purpose: preserve scale, SaaS composability and replaceability without building speculative features prematurely.

## 1. Scale objective
ECHO must be able to grow from one operating Enterprise to many independent Enterprises and from a few capabilities to many verticals without redefining the meaning of identity, event, evidence, authority or ownership.

Scaling may require larger or partitioned infrastructure. It should not require rewriting what an Enterprise, Principal, Event, Capability, Vector or Chord means.

## 2. SaaS ownership boundary
- Enterprise is the primary business-data ownership boundary.
- TAGRO is the first operating Enterprise, not a hard-coded special case.
- Human/system identity is independent from Enterprise membership.
- A principal may hold different memberships, roles and tool packs in different Enterprises.
- Branch codes, SKUs, customer references and other operational identifiers are normally Enterprise-scoped rather than assumed globally unique.
- Globally stable internal IDs remain suitable for later partitioning and migration.

## 3. Composable capability model
ECHO is not defined by a fixed menu.

Enterprise subscription/entitlement + user authority + current context determine which capabilities and tiles are available.

Default packs may exist, but they are templates, not permanent product boundaries. Capabilities may be enabled, disabled, suspended, archived and later resumed without silently deleting owned history.

Future examples include Sales, Stock, Service, Purchase, Warehouse, Cash, Banking, Projects, Rentals, HR and governed AI staff.

## 4. Data ownership and portability
Enterprise-owned operational data must remain exportable in documented open forms. Stopping a capability or subscription must not silently erase historical truth.

Future subscription states may allow:
- active use;
- disabled capability with retained history;
- paid archival storage;
- complete export and departure;
- validated re-import and continuation.

Implementation of self-service billing, archive pricing and restore UX is deferred until admitted by later work orders.

## 5. Planar Principle engineering interpretation
Reality produces events. An event exists once and may project into many authorised planes without those projections becoming independent copies of truth.

An Event carries potential beyond its originating action. It does not wait for every department or module to search for it later.

Examples of planes/receivers include Stock, Service, Finance, CRM, Audit, Management, BUSY adapters and AI observers.

A change in organisational grouping, capability selection or receiver does not rewrite the originating event.

## 6. Selective propagation: vectors
A Vector is an admitted, governed direction/filter through which selected dimensions of an Event may seek passage.

Vector contracts answer, as relevant:
- who;
- what;
- which subject;
- why the signal matters;
- where;
- when;
- how;
- Enterprise context;
- authority;
- evidence/provenance;
- confidence;
- materiality;
- sensitivity;
- intended receiver.

Not every receiver is entitled to know every Event exists. Visibility itself may be mediated by Vector policy.

## 7. Vector strength and entry vs passage
Entry into the governed event universe is not a right of passage.

An admitted Event may create one or more candidate Vectors. Each Vector has a strength class and weight used by its owning contract for attention and passage decisions.

Initial classes:
- A: high materiality/urgency/authority;
- B: operationally important;
- C: ordinary business signal;
- D: weak/incomplete/low-priority signal;
- Q: quarantined/contradictory/unsafe.

Strength does not equal truth. Passage requires the owning gate conditions.

## 8. Chords
A Chord is an owner/admitted combination of Vectors whose business meaning has passed due diligence.

A Chord Contract must define why the combination matters, required vectors, minimum evidence/authority, valid time/location/Enterprise context, conflict behaviour, confirmation policy, consequence, correction/reversal and audit requirements.

AI may propose candidate Chords or relationships. It does not admit consequential truth by itself.

Example: a bank credit may combine amount, time, account, open-invoice, narration/reference and Enterprise vectors into a reconciliation candidate. Amount/date similarity alone is not proof.

## 9. Passage gates
A Vector or Chord waits unless its gate is satisfied. Gates may consider class, weight, Enterprise, recipient, evidence, timing, authority, sensitivity, conflicts, rate/capacity and owning contract.

Allowed lifecycle examples:
- waiting;
- eligible;
- passed/confirmed;
- blocked/rejected;
- quarantined;
- expired;
- retired from active circulation.

Retirement never silently deletes the originating Event or Evidence.

## 10. Sweeper doctrine
Silent, orphaned, stalled and long-waiting signals must not accumulate indefinitely as operational static.

Sweepers inspect unresolved Vector and Chord populations at governed intervals correlated to strength, urgency and volume. A-class signals may be inspected within minutes; weaker classes may use hourly/daily/weekly intervals as their contracts require.

A Sweeper may:
- re-evaluate;
- escalate;
- quarantine;
- retire from active circulation;
- flag congestion or abnormal waiting volume.

It must not erase admitted reality or fabricate resolution.

## 11. Event transport
Future event transport may use EventBridge and SQS according to existing architecture decisions.

Transport is not truth. The admitted Event and its provenance remain authoritative; buses and queues merely carry selected effects to authorised receivers.

The target is harmonic transmission, not maximum broadcast.

## 12. Security at scale
- clients never receive standing AWS credentials;
- database access remains server-side/private;
- Enterprise context and membership are resolved server-side;
- capability entitlement does not itself grant user authority;
- sensitive receivers may be unaware of events outside their permitted vectors;
- compromised user devices must be limited by server-side role, Enterprise and consequence gates;
- platform administration must remain separately controlled and auditable.

## 13. Build now vs later
Build/preserve now:
- Enterprise ownership;
- Principal/membership separation;
- capability/entitlement primitive;
- tenant-safe identifiers and scoped uniqueness;
- event provenance and Enterprise context;
- Vector/Chord/Passage/Sweeper primitives;
- controlled migration and auditability.

Design now, implement later when admitted:
- self-service signup and payment;
- usage/storage/AI metering;
- SaaS pricing plans;
- archive/download/re-import UX;
- vertical template marketplace;
- dedicated-tenant infrastructure;
- third-party developer ecosystem.

Scale later only when evidence requires:
- database sharding;
- dedicated clusters/accounts;
- multi-region replication;
- international data-residency partitions.

## 14. Design tests
Before adding a table/module/integration ask:
1. Is this storing reality, or accidentally copying a projection as new truth?
2. Which Enterprise owns it?
3. Is identity independent of current hierarchy/location/vendor?
4. Which Vectors may exist, and who is allowed to receive them?
5. What Chord/gate establishes consequential meaning?
6. What happens if it waits, conflicts, becomes stale or remains silent?
7. Can the component be removed/replaced without unknowable consequences?
8. Can the Enterprise export what it owns?

If these cannot be answered, the feature remains outside the active platform.
