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

Events carry dimensions and values such as subject, actor, time, place, quantity, money, evidence, authority, confidence, sensitivity and relationship potential. Those dimensions together describe the Event; later filters do not rewrite the Event itself.

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

## 7. VIBGYOR prismatic filter
The whole Event is analogous to white light: its dimensions and values coexist in one admitted reality record.

A governed prismatic filter may decompose that Event into spectral projections labelled V, I, B, G, Y, O and R. These are routing/filter bands, not seven independent truths and not seven fixed universal business meanings. Their operational meaning is admitted by the owning Vector/Chord contract.

The core rule is spectral matching:
- the Event remains whole and unchanged;
- the prism selects and decomposes relevant dimensions into one or more spectral streams;
- each spectral stream retains Event identity and provenance;
- a receiver may act only on spectral bands it is explicitly admitted to receive;
- a non-matching spectral stream has no business meaning at that receiver, even if transport accidentally delivers it there;
- mere presence at a receiver cannot create a Chord, relationship or consequence;
- matching colour is necessary but may still be insufficient: passage, authority, evidence, timing and Chord rules continue to apply.

This separates transport from semantics. A signal may physically traverse shared infrastructure while remaining semantically inert outside its admitted spectral receiver set.

The purpose is not to force every Event into all seven colours. It is to make decomposition explicit, sparse and testable so noise is reduced before Chord formation.

## 8. Vector strength and entry vs passage
Entry into the governed event universe is not a right of passage.

An admitted Event may create one or more candidate Vectors. Each Vector has a strength class and weight used by its owning contract for attention and passage decisions.

Initial classes:
- A: high materiality/urgency/authority;
- B: operationally important;
- C: ordinary business signal;
- D: weak/incomplete/low-priority signal;
- Q: quarantined/contradictory/unsafe.

Strength does not equal truth. Passage requires the owning gate conditions.

Spectral band and strength are separate dimensions. Colour answers relevance/matching; strength answers attention/weight. Neither by itself proves truth or grants consequence.

## 9. Chords
A Chord is an owner/admitted combination of Vectors whose business meaning has passed due diligence.

A Chord Contract must define why the combination matters, required vectors, spectral bands where applicable, minimum evidence/authority, valid time/location/Enterprise context, conflict behaviour, confirmation policy, consequence, correction/reversal and audit requirements.

AI may propose candidate Chords or relationships. It does not admit consequential truth by itself.

Example: a bank credit may combine amount, time, account, open-invoice, narration/reference and Enterprise vectors into a reconciliation candidate. Amount/date similarity alone is not proof.

## 10. Passage gates
A Vector or Chord waits unless its gate is satisfied. Gates may consider spectral match, class, weight, Enterprise, recipient, evidence, timing, authority, sensitivity, conflicts, rate/capacity and owning contract.

Allowed lifecycle examples:
- waiting;
- eligible;
- passed/confirmed;
- blocked/rejected;
- quarantined;
- expired;
- retired from active circulation.

Retirement never silently deletes the originating Event or Evidence.

## 11. Sweeper doctrine
Silent, orphaned, stalled and long-waiting signals must not accumulate indefinitely as operational static.

Sweepers inspect unresolved Vector and Chord populations at governed intervals correlated to strength, urgency and volume. A-class signals may be inspected within minutes; weaker classes may use hourly/daily/weekly intervals as their contracts require.

A Sweeper may:
- re-evaluate;
- escalate;
- quarantine;
- retire from active circulation;
- flag congestion or abnormal waiting volume;
- flag spectral misrouting where a signal reached a non-matching receiver.

It must not erase admitted reality or fabricate resolution.

## 12. Event transport
Future event transport may use EventBridge and SQS according to existing architecture decisions.

Transport is not truth. The admitted Event and its provenance remain authoritative; buses and queues merely carry selected effects to authorised receivers.

The target is harmonic transmission, not maximum broadcast. Spectral filtering should reduce unnecessary delivery before transport where practical, while receiver-side matching remains a final semantic guard.

## 13. Security at scale
- clients never receive standing AWS credentials;
- database access remains server-side/private;
- Enterprise context and membership are resolved server-side;
- capability entitlement does not itself grant user authority;
- sensitive receivers may be unaware of events outside their permitted vectors/spectral bands;
- compromised user devices must be limited by server-side role, Enterprise and consequence gates;
- platform administration must remain separately controlled and auditable.

## 14. Build now vs later
Build/preserve now:
- Enterprise ownership;
- Principal/membership separation;
- capability/entitlement primitive;
- tenant-safe identifiers and scoped uniqueness;
- event provenance and Enterprise context;
- Vector/Chord/Passage/Sweeper primitives;
- VIBGYOR spectral-band registry and receiver-matching primitive;
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

## 15. TAGRO phased move-house validation
TAGRO should move into ECHO in phases, not as one opaque lift-and-shift. Each phase is both migration and observation of how Event dimensions separate into Vectors, spectral streams, Chords and receiver consequences.

Recommended order:
1. Enterprise, branches and human identities.
2. Products, prices, customers and suppliers.
3. Stock history/current balances with provenance and reconciliation.
4. Sales, purchases, purchase orders, transfers and counts.
5. Machines, service jobs and service history.
6. Cash closings, payments and bank evidence.
7. BUSY mappings/read-side reconciliation.
8. Older archives and historical data as separately provenance-marked ingestion sets.

For each phase record:
- source system/file and source timestamp;
- imported Event/entity identities;
- dimensional decomposition;
- generated candidate Vectors;
- spectral band assignment;
- matching/non-matching receivers;
- Chords formed or deliberately not formed;
- waiting/static population and Sweeper outcome;
- reconciliation differences;
- authority used to admit the migrated truth.

This makes the migration itself an empirical test of the Planar/VIBGYOR model rather than merely a data-loading exercise.

## 16. Design tests
Before adding a table/module/integration ask:
1. Is this storing reality, or accidentally copying a projection as new truth?
2. Which Enterprise owns it?
3. Is identity independent of current hierarchy/location/vendor?
4. Which Event dimensions matter?
5. Which Vectors and spectral bands may exist, and who is allowed to receive them?
6. Would a non-matching receiver remain semantically inert even if it saw the transport payload?
7. What Chord/gate establishes consequential meaning?
8. What happens if it waits, conflicts, becomes stale or remains silent?
9. Can the component be removed/replaced without unknowable consequences?
10. Can the Enterprise export what it owns?

If these cannot be answered, the feature remains outside the active platform.
