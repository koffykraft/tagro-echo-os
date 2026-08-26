# TAGRO × ECHO OS — UI Surface Inventory

Date: 2026-08-22
Status: Phase A active; first inspected set
Design authority: `contracts/core/ECHO_UI_UX_DESIGN_RULES_V1.md`

## 1. Purpose

This inventory separates current user-facing surfaces into:

- ADMIT / RETAIN — structurally aligned enough to remain an authoritative lane, though refinement may continue;
- REDESIGN — business capability is valid, current human interaction/shell is not;
- EXTRACT SKILL — preserve useful interaction/data/semantic behaviour but do not preserve the page as the future surface;
- QUARANTINE — keep for engineering/history/test use but remove from normal staff navigation;
- RETIRE — obsolete duplicate once replacement/evidence obligations are satisfied.

No file is admitted merely because it works or has tests.

## 2. First-pass authoritative navigation conclusion

The current `web/index.html` is a feature directory and must not define the final information architecture.

The current `web/app.js` creates a second prototype navigation world and must not coexist as a competing operational shell.

Target direction:

COUNTER HOME
- SELL
- SERVICE
- ESTIMATE / QUOTE where enabled
- COUNT
- REQUEST PURCHASE
- CLOSING CASH when relevant
- CONTINUE / PENDING / NEEDS ATTENTION contextually

MECHANIC HOME
- TAKE JOB
- MY JOBS
- PARTS NEEDED

MANAGER HOME
- TODAY
- APPROVALS
- EXCEPTIONS

OWNER HOME
- NEEDS ATTENTION
- APPROVALS
- BUSINESS NOW / ON CALL

Admin/import/toolbox/report-detail functions become secondary lanes rather than peer Home actions.

## 3. Inspected surfaces

| Surface | Current role | Current state | Decision | Main reason / reusable skill |
|---|---|---|---|---|
| `web/login.html` | Staff authentication | Cognito/runtime-aware | REDESIGN / RETAIN LOGIC | Keep authenticated context resolution and enterprise selection. Simplify routine return/re-auth experience later; shell context begins here. |
| `web/index.html` | Current Home | 12 peer links + network notice | REDESIGN | Feature directory exposes architecture, owner/admin/prototype and counter jobs at one level. Replace with role/job Home. |
| `web/app.js` | Older all-in-one prototype IA | Local CRUD prototype | QUARANTINE / EXTRACT SKILL | Contains old Dashboard/Sell/Quote/Purchase/Stock/Masters/Reports/Import-Export world. Preserve evidence of earlier workflow/data experiments; do not use as future shell. |
| `web/styles.css` | Shared old shell styles | Responsive baseline | EXTRACT SKILL / REPLACE AS SHELL SYSTEM | Useful simple typography/cards/touch baseline and top safe-area start. Missing full bottom/side safe-area, purpose-specific interaction system and admitted state language. |
| `web/billing.html` | Phone Billing | Authenticated EchoRuntime + queue | REDESIGN / RETAIN RUNTIME PATH | Strongest current runtime path. Preserve issue/idempotency/offline queue semantics. Remove repeated branch entry; redesign item entry, product lookup, payment evidence, context and mobile keyboard flow. |
| `web/service.html` | Quick Service Intake | Local prototype state + direct fetch | REDESIGN / EXTRACT INTAKE SKILL | Customer → Machine → Complaint → ACCEPT is the correct microsession. Runtime/offline/context model is inconsistent with Billing/Stock. Preserve the fast intake concept, not current implementation shell. |
| `web/stock-count.html` | Physical count observation | Authenticated EchoRuntime + governed reference lookup/queue | REDESIGN / RETAIN CORE PATH | Semantics are strong: count != stock mutation; product lookup and local reconciliation useful. Make item → count → next item much faster; remembered branch/context belongs in shell; reference evidence should be secondary. |
| `web/po.html` | Purchase Order draft | Local draft + direct fetch | REDESIGN / EXTRACT REQUIREMENT SKILL | Correctly distinguishes draft/owner approval/supplier send, but asks for IDs and is built like a small form rather than requirement capture. Future flow should be need-first and approval-aware. |
| `web/cash.html` | Older Closing Cash prototype | Local prototype | QUARANTINE / EXTRACT SEMANTICS | Contains important cash-in/out/noncash/contra semantics and lifecycle ideas but is an engineering form, not the familiar day-working experience. Superseded as design candidate by purpose-specific Closing Cash lane. |
| `web/forms/closing-cash.html` | New purpose-specific Closing Cash candidate | Local design candidate | REDESIGN / CANDIDATE LANE | Stronger geometry: familiar entry grid, context drawer, review layer, cash count + reconciliation. Useful design source, but still requires shell/runtime integration, safe-area/keyboard/phone proof and field validation before admission. |
| `web/on-call.html` | Owner financial projection | Governed runtime read-only | REDESIGN / RETAIN EVIDENCE LOGIC | Excellent evidence/freshness/confidence discipline; first view is too dashboard-dense. Future ON CALL should lead with material attention/approval, with financial/evidence depth behind it. |
| `web/reports.html` | Essential Reports | Mixes localStorage evidence + link to governed ON CALL | QUARANTINE / REDESIGN REPORT LANE | Mixed authority generations on one page. Reports should derive from governed runtime/event planes, not combine device-local prototypes as if one report world. |
| `web/payments.html` | Receive/allocate payment | Explicit local prototype | QUARANTINE / EXTRACT EVIDENCE MODEL | Important principle: payment != sale/bank transaction and allocation is explicit. Current UI is ID-heavy and prototype-local. Future Receipt and Payment need separate purpose-specific surfaces. |
| `web/documents.html` | Generic document maker | Explicit local prototype | RETIRE AFTER REPLACEMENT / EXTRACT PRINT SKILL | Separate re-entry tool violates rule that documents are projections of originating records. Preserve local preview/print learning only; documents should originate from Invoice/Quote/PO/etc. |
| `web/counter.html` | Mixed counter prototype | Offline local event/queue experiment | QUARANTINE / EXTRACT OFFLINE SKILLS | Bundles PO, transfer, count and evidence in one engineering page. Useful early offline/event evidence; should not survive as a user-facing counter app once purpose-specific journeys are admitted. |
| `web/bank.html` | Normalized bank import | Local engineering prototype | QUARANTINE / ADMIN LANE | Correct evidence principle, wrong audience for daily counter Home. Future bank ingestion is controlled admin/adapter work, not peer staff navigation. |

## 4. Immediate page-ecology defects found

### 4.1 Duplicate information architecture
`index.html` and `app.js` expose different top-level product worlds.

Action: future shell gets one canonical role-aware navigation model. Old prototype navigation becomes non-counter/engineering only.

### 4.2 Mixed authority generations
Billing/Stock Count use newer authenticated runtime queueing; Service/PO/Payments/Cash/Counter/Reports retain older local-state patterns.

Action: shell/state/offline primitives must converge before field admission.

### 4.3 Context re-entry
Branch/user/date/context are inconsistently typed, selected, hidden or inferred.

Action: enterprise/person/role/branch/date/network/sync become shell primitives.

### 4.4 Engineering truth dominates some routine surfaces
Several pages explain runtime/evidence semantics before the user can begin the job.

Action: progressive disclosure. Plain operational truth first; detailed provenance/evidence available on demand.

### 4.5 Generic utility pages create duplicate work
`documents.html` requires manual reconstruction of documents already implied by operational records.

Action: document/share/print becomes a projection from the originating governed record.

### 4.6 Owner surface is analysis-first rather than attention-first
`on-call.html` contains strong evidence logic but asks the owner to parse many metrics/confidence figures before seeing the highest-value attention work.

Action: preserve evidence depth; invert hierarchy to attention → reason/materiality → action → deeper financial/evidence detail.

### 4.7 Reports mix local and governed truth
`reports.html` combines device-local prototype counts with governed ON CALL entry.

Action: do not admit a report until its provenance/authority is coherent.

## 5. Skills already worth preserving

The convergence work must not throw away useful interaction/semantic learning.

### Billing
- authenticated runtime command;
- idempotency key;
- signed-in scoped local queue;
- separate ECHO issued vs BUSY state;
- live total calculation.

### Service
- very short intake microsession;
- complaint in customer words;
- hidden optional details;
- obvious ACCEPT action.

### Stock Count
- physical count dominant;
- search/reference lookup;
- system quantity may be unknown;
- count does not mutate canonical stock;
- local observation reconciliation.

### Purchase
- draft != supplier instruction;
- owner approval explicit.

### Closing Cash
- familiar four-column working geometry;
- raw movement evidence preserved before classification;
- cash count + reconciliation;
- review before confirmed save;
- correction/supersession direction.

### Owner ON CALL
- read-only observer posture;
- unknown remains visible;
- freshness/confidence/provenance;
- no invented financial value.

### Payment/Bank prototypes
- receipt/payment/bank evidence kept separate until explicit allocation/classification.

## 6. Surfaces inspected completely in this phase

Fully read for this first inventory pass:

- `web/login.html`
- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `web/billing.html`
- `web/service.html`
- `web/stock-count.html`
- `web/po.html`
- `web/cash.html`
- `web/on-call.html`
- `web/reports.html`
- `web/payments.html`
- `web/documents.html`
- `web/counter.html`
- `web/bank.html`
- `web/forms/closing-cash.html`

Also read as design authorities:

- `contracts/core/PRODUCT_DESIGN_ENGINEERING_CONTRACT.md`
- `contracts/core/PAGE_ECOLOGY_CONTRACT.json`
- `web/forms/PURPOSE_DESIGN_CONTRACT.md`
- `contracts/core/ECHO_UI_UX_DESIGN_RULES_V1.md`

## 7. Not yet fully audited in this inventory

Do not infer a final design decision from filenames for these until read:

- `web/page-builder.html`
- remaining `web/forms/` implementation files including the generic renderer/CSS and canonical billing lane in their current head state;
- all historical Closing Cash V02–V11 files as individual interaction experiments;
- any additional user-facing surfaces outside `web/` discovered in later repository scan;
- current service progression/detail surfaces if located outside the inspected quick-intake file;
- future/side-lane pages not linked from current Home.

These will be classified in the next inventory pass.

## 8. Convergence order from this inventory

1. Finish inventory/quarantine map.
2. Define `CORE_USER_JOURNEYS.md` and micro-moment list.
3. Define `ECHO_SHELL_SPEC.md` including safe viewport, context and state language.
4. Build low-fidelity shell + role-aware Home before restyling individual forms.
5. Bind shell to current authenticated runtime context.
6. Redesign Billing first against the shell.
7. Then Service Intake, Stock Count, Purchase Request and Closing Cash.
8. Reframe Owner ON CALL around attention.
9. Build Estimate/Quotation/Receipt/Payment purpose-specific lanes.
10. Derive documents from the originating record.
11. Keep engineering/admin/import tools outside ordinary staff navigation.

## 9. Current conclusion

The repository contains enough correct domain/runtime work and enough useful UI experiments to avoid a restart.

The required work is convergence:

- one shell;
- one context model;
- one understandable state language;
- role/job navigation;
- purpose-specific interaction geometry;
- common interruption/offline/recovery behaviour;
- explicit quarantine of prototype worlds;
- real-device field validation.

The next design artifact should be the real-user/micro-moment journey map, not another styled page.
