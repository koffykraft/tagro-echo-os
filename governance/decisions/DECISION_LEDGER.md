# TAGRO ECHO OS Decision Ledger

Status: Active
Rule: Decisions are durable records. They may be superseded only by a later owner-approved decision that names the decision it replaces.

## DEC-0001 — Independent ECHO Operating System
Decision: TAGRO ECHO OS is independent of the older TAGRO/STIHL/Jain operating environment.
Reason: ECHO has a different operating model, projected scale, cloud posture and counter topology.
Rejected: extending the older OS as the live ECHO runtime.
Approved: Owner, 2026-08-19.

## DEC-0002 — AWS is the operational cloud
Decision: AWS is the target operational cloud for TAGRO ECHO OS.
Rejected: treating Cloudflare as the governing operational cloud merely because earlier TAGRO systems used it.
Approved: Owner, 2026-08-19.

## DEC-0003 — TAGRO ECHO OS is operational truth; BUSY is an adapter
Decision: operational sales, stock, customer, service, cash, logistics and related events originate in TAGRO ECHO OS. BUSY is a controlled accounting/statutory adapter.
Rejected: BUSY-first operational architecture.
Approved: Owner, 2026-08-19.
Status: BUSY-role wording superseded by DEC-0019; ECHO operational-orchestration principle remains active.

## DEC-0004 — Front-seat Driver and rear-seat Observer are separated
Decision: operational command and observation/intelligence are structurally separated. The Driver changes authorised operational state. The Observer is read-only and creates findings/attention, not operational commands.
Approved: Owner, 2026-08-19.

## DEC-0005 — AI cannot establish consequential truth by itself
Decision: AI may propose observations, identities, quantities, classifications, drafts and actions. Consequential truth requires deterministic validation and the authority/confirmation specified by the owning domain.
Approved: Owner, 2026-08-19.

## DEC-0006 — Replaceability includes the skeleton
Decision: every component, provider and even the versioned core skeleton may be replaced if found flawed. Replacement must preserve/reconcile evidence and explicitly migrate meaning.
Approved: Owner, 2026-08-19.

## DEC-0007 — Honesty is composite
Decision: correctness must be evaluated at component, relationship and composite-result levels.
Approved: Owner, 2026-08-19.

## DEC-0008 — Persistent governance controls AI builders
Decision: continuity is stored in Constitution, machine-readable foundation/state, decisions, contracts, schemas, work orders and session ledger. Chat memory is not authority.
Approved: Owner, 2026-08-19.

## DEC-0009 — Counter Intelligence is a core capability layer
Decision: mobile camera, OCR, barcode/QR, voice, text, serial/machine recognition, shelf/workbench observation and customer-history resolution are first-class counter inputs.
Constraint: AI observations remain evidence/suggestions until confirmed/admitted under owning contracts.
Approved: Owner, 2026-08-19.

## DEC-0010 — Warehouse begins empty and receives continuous governed feeds
Decision: the ECHO warehouse begins with no inherited TAGRO operational history and is designed for continuous receipt of ECHO accounting, bank, cash, stock, service, logistics, marketing and other admitted events/evidence.
Approved: Owner, 2026-08-19.

## DEC-0011 — AWS workload separation begins multi-account
Decision: production and non-production ECHO workloads are to be separated at AWS account level before production launch; workload accounts are not organized by district/reporting hierarchy.
Reason: account boundaries provide security, blast-radius and operational isolation; AWS guidance recommends separating production from non-production and organizing by security/operational needs.
Status: architecture admitted; accounts not yet created/verified.
Approved under: WO-0003, 2026-08-19.

## DEC-0012 — Primary AWS Region begins with Mumbai assumption
Decision: `ap-south-1` (Asia Pacific Mumbai) is the first admitted primary Region for implementation planning.
Reason: the business is initially India-based and the primary workload should begin near its operating geography; this remains testable and replaceable.
Constraint: no DR Region is admitted yet and no Region-specific service availability is assumed without checking at provisioning time.
Status: architecture admitted; no resources provisioned.
Approved under: WO-0003, 2026-08-19.

## DEC-0013 — Mobile ingress begins Cognito + HTTP API + Lambda
Decision: the first implementation candidate is Amazon Cognito User Pools for staff authentication and API Gateway HTTP API with Lambda application handlers for the governed server boundary.
Reason: mobile clients need token-based authentication and a server-side command boundary without holding standing AWS IAM credentials or writing directly to the operational database.
Constraint: application authorization remains server-side domain policy; service selection remains replaceable behind contracts.
Status: architecture admitted; no resources provisioned.
Approved under: WO-0003, 2026-08-19.

## DEC-0014 — Operational database semantics are PostgreSQL-compatible; managed mode deferred
Decision: the canonical operational store requires PostgreSQL-compatible relational/transactional semantics. Exact managed AWS mode is not yet fixed between RDS PostgreSQL and Aurora PostgreSQL/Serverless v2.
Reason: architecture must follow required business semantics first; exact managed mode depends on measured load, connection behaviour, availability and cost rather than product preference.
Status: database semantics admitted; service/machine mode not yet admitted and no database exists.
Approved under: WO-0003, 2026-08-19.

## DEC-0015 — Domain events use explicit async transport, not hidden coupling
Decision: EventBridge custom bus and SQS are the first admitted AWS candidates for asynchronous event routing/consumption; FIFO is used only where ordering/deduplication materially requires it.
Constraint: transport does not establish business truth. The Driver/domain transaction admits the event; adapters consume it with explicit retry/reconciliation behaviour.
Status: architecture admitted; no event resources provisioned.
Approved under: WO-0003, 2026-08-19.

## DEC-0016 — Evidence and warehouse begin on S3 with catalog/query separation
Decision: S3 is the first admitted object/evidence and analytical storage boundary; the initial analytical pattern is S3 + Glue Data Catalog + Athena, with heavier ETL/governance services admitted only when needed.
Constraint: S3 Object Lock is not automatically admitted; retention/WORM policy requires a separate governance decision.
Status: architecture admitted; no buckets/catalogs/query workgroups provisioned.
Approved under: WO-0003, 2026-08-19.

## DEC-0017 — Enterprise identity is independent of organizational hierarchy
Decision: every ECHO operating enterprise/counter has a durable enterprise identity that does not depend on its current parent grouping, physical location, BUSY company, material centre, voucher series or assigned users. Parent-child relationships are configurable so counters may later be grouped by district, region, operator, warehouse, vertical or another admitted structure without identity migration.
Reason: future scale and franchise/operator structures must not require core schema redesign.
Status: executable registry admitted under WO-0008.
Approved: Owner, 2026-08-20.

## DEC-0018 — BUSY is represented as a multi-node ecosystem
Decision: ECHO addresses BUSY through registered BUSY nodes and explicit enterprise bindings. A BUSY node may represent a company/environment and may serve multiple enterprises through material-centre/voucher-series mappings; an enterprise may have more than one role-scoped BUSY binding when explicitly configured. BUSY credentials are not part of the Enterprise Directory.
Reason: the network may begin with counters as material centres but later include separate BUSY companies, multi-location operators, districts/regions or other combinations. The bridge must fetch/write/process across different iterations of the same BUSY ecosystem without changing enterprise identity.
Constraint: this decision defines topology and registry behavior only; it does not admit production BUSY write or credentials.
Status: executable registry admitted under WO-0008.
Approved: Owner, 2026-08-20.

## DEC-0019 — BUSY is a docked accounting, finance and MIS engine
Decision: BUSY is an independent docked specialist engine used to process, consolidate and store accounting/financial information and to produce accounting, inventory and MIS outputs. ECHO orchestrates users, enterprises, operational context and presentation; BUSY may be authoritative for the accounting/books result it processes. This supersedes DEC-0003 only where DEC-0003 described BUSY merely as an adapter.
Reason: existing TAGRO evidence proves BUSY is a mature accounting/inventory engine and native read/write/report capability already exists. Rebuilding those calculations in ECHO would create unnecessary duplication.
Constraint: BUSY remains replaceable, multi-node, governed and separately reconciled. A queued request is not a booked BUSY transaction until BUSY result/readback confirms it.
Status: BUSY Dock v1 implementation under WO-0009.
Approved: Owner, 2026-08-20.

## DEC-0020 — Mobile operation is offline-capable by design
Decision: ordinary counter work must remain usable on mobile during intermittent connectivity. Local/offline state is explicit, queued mutations are idempotent, stale BUSY/report snapshots are labelled stale, and online synchronization/readback must not silently reinterpret offline activity.
Reason: ECHO counters are mobile-first and may have unreliable network availability; the operating system must degrade calmly rather than stop.
Constraint: offline capability does not authorize bypassing permissions or fabricating current server/BUSY state.
Status: active design rule from WO-0009 onward.
Approved: Owner, 2026-08-20.
