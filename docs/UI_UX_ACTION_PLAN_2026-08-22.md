# TAGRO × ECHO OS — UI/UX Study and Action Plan

Date: 2026-08-22
Status: active product-design study; no production-admission claim
Branch: `wo-0012-nonprod-shared-runtime`

## 1. Purpose

ECHO must become one coherent operating environment for real staff, not a collection of individually functioning pages.

The immediate design objective is therefore not to add more visible features. It is to make one real ECHO business day understandable, fast, truthful, recoverable and comfortable on a phone under counter conditions.

The product-design question is:

> Can a real user enter ECHO, understand where they are and what they can do, complete the next business job with minimum thought, survive interruption or network loss, and know exactly what ECHO accepted, what remains local/pending, what needs approval, and what has reached BUSY or another downstream system?

## 2. Study rule

Before redesigning a surface, evaluate the complete chain already required by the Product Design Engineering Contract:

REAL USER / ENVIRONMENT
→ intended job
→ event/evidence
→ authority/risk
→ business logic
→ data contract
→ workflow
→ information architecture
→ interaction
→ visual hierarchy
→ wording
→ mobile behaviour
→ offline/failure/recovery
→ acknowledgement
→ measured usability.

No page is to be redesigned only from visual preference.

## 3. First-pass findings from the current web surface

### 3.1 The home page is a feature directory, not an operating home

The current landing page exposes many destinations as peer actions: Owner ON CALL, Billing, Service, Purchase Order, Stock Count, Reports, Page Toolbox, Counter Ops, Closing Cash, Bank Import, Payments and Print Documents.

This forces the user to understand the system structure before doing a job. It also exposes owner, prototype/admin and operational functions in one field of attention.

**Design implication:** replace feature-directory thinking with role + context + next-job thinking.

### 3.2 Two navigation worlds currently coexist

The landing page has one set of direct action links while `app.js` creates a second prototype navigation world with Dashboard, Sell, Quote, Purchase, Stock, Masters, Reports and Import/Export.

This is duplicate information architecture and creates uncertainty about which surface is authoritative.

**Design implication:** one admitted shell only; prototype surfaces must be explicitly quarantined, hidden from normal staff navigation or retired.

### 3.3 Runtime truth and local-prototype truth are inconsistent across pages

Billing and Stock Count use the authenticated `EchoRuntime` path and scoped queue concepts. Service and Purchase Order still use older direct local-storage/direct-fetch patterns.

A staff user should not need to understand which page belongs to which implementation generation.

**Design implication:** runtime state language, identity scope, offline queueing, acknowledgement and recovery must become a shared product primitive before field admission.

### 3.4 Current pages explain system semantics too loudly

Several operational pages begin with long warnings about canonical planes, runtime acceptance, BUSY state or local evidence. These warnings are valuable engineering truth, but they currently consume primary attention ahead of the job.

**Design implication:** preserve truth, but layer it. The main surface should answer: `What am I doing? What do I enter next? What happened?` Technical/provenance detail should remain available without dominating routine use.

### 3.5 Context is repeatedly entered or hidden inconsistently

Branch appears as free text in Billing and PO, a governed lookup in Stock Count, and a hidden "More details" choice in Service. Actual signed-in user/enterprise context is not presented consistently across the working surfaces.

**Design implication:** create one compact persistent Context Bar/Drawer: enterprise, branch/counter, signed-in person, date/session and network/sync state. Defaults should follow authenticated context; changes require authority and remain attributable.

### 3.6 Core jobs need different interaction geometries

The Purpose-Specific Form Design Contract is correct: Billing is a repeated item-entry problem; Service is a staged machine record; Stock Count is item→count repetition; PO is a requirement/approval journey; Closing Cash is a day reconciliation grid.

**Design implication:** share primitives, not page composition. Do not create a universal card form or universal four-column renderer.

### 3.7 Mobile is responsive, but not yet fully mobile-designed

The shared CSS generally collapses layouts at small width, but true mobile design requires thumb reach, interruption recovery, focus/keyboard behaviour, persistent identity/context, fast repeated entry, limited scrolling and no routine horizontal table dependence.

**Design implication:** 390×844 must be a first-class design canvas, not a reduced desktop canvas.

## 4. Human lenses for the study

Every core journey will be reviewed from at least these operational viewpoints.

### Counter staff
Needs speed, large clear actions, remembered counter context, quick customer/product finding, minimal typing, obvious result and safe offline continuation.

### Service intake / mechanic
Needs machine identity to remain visible, complaint in customer language, low-stress staged work, parts/work access only when relevant, and clear job state without administrative clutter.

### Manager / approver
Needs pending approvals, exceptions, stock/cash concerns and branch context; should not wade through counter-entry controls to find them.

### Owner
Needs ON CALL to surface what requires attention, why, evidence/freshness/confidence and the permitted action. It should not become another dense dashboard.

## 5. Target experience: one complete ECHO business day

The study and redesign will be driven by this end-to-end path:

1. Sign in.
2. ECHO resolves enterprise, person, role and counter.
3. Home shows the few jobs appropriate now.
4. Staff sells / estimates / services / counts / requests purchase as needed.
5. Every action shows one simple state: local draft, pending sync, accepted, needs review/approval, completed/downstream-confirmed as applicable.
6. User can leave and return without losing context.
7. Network loss does not create duplicate truth or false completion.
8. Owner/manager sees only material pending work and anomalies.
9. Closing Cash reconciles the day.
10. BUSY/downstream handoff is shown separately from ECHO acceptance.
11. End-of-day state can be reviewed and recovered.

This day, rather than the number of pages built, is the primary UX acceptance object.

## 6. Action sequence

### Phase A — Complete UX inventory and quarantine map

For every current user-facing file/surface, record:
- intended user;
- job;
- current data/runtime source;
- authority level;
- mobile behaviour;
- offline/recovery behaviour;
- duplicate/legacy/prototype relationship;
- page-ecology defects;
- decision: retain, redesign, merge skill, quarantine or retire.

Output: `UI_SURFACE_INVENTORY.md` and a one-page authoritative navigation map.

No prototype or toolbox page should remain in normal staff navigation merely because it exists.

### Phase B — Map real workflows before drawing screens

Create task maps for:
- Sign in / counter selection;
- Sale / Invoice;
- Estimate / Quotation;
- Service intake → repair → closure;
- Stock Count;
- Purchase requirement → owner approval → supplier instruction;
- Receipt / Payment;
- Closing Cash;
- Owner ON CALL.

Each map must identify the shortest common path, optional/exception path, consequential confirmation, offline path and recovery path.

Output: `CORE_USER_JOURNEYS.md`.

### Phase C — Establish the ECHO shell

Design one shell shared by all admitted operational pages.

Required primitives:
- compact TAGRO × ECHO identity;
- authenticated person + role;
- branch/counter context;
- date/session context;
- unobtrusive network/sync indicator;
- one clear Home/back path;
- role-aware primary actions;
- pending/review attention cue;
- context drawer rather than repeated branch/user fields.

Phone rule: no permanent side rail.
Desktop rule: wider space may reveal secondary context without changing workflow semantics.

### Phase D — Redesign the Home around jobs, not modules

Initial counter home should normally prioritize a very small set such as:
- SELL
- SERVICE
- BILL / RECEIVE MONEY where context requires

Secondary actions can include:
- ESTIMATE / QUOTE
- STOCK COUNT
- PURCHASE REQUEST
- CLOSING CASH

Owner/manager home should be different: attention, approvals, exceptions, branch state and ON CALL.

Admin/import/page-builder functions must not compete with daily operational work.

### Phase E — Build a shared interaction language

Standardize only what should actually be common:
- customer/product lookup;
- number entry;
- primary/secondary/destructive buttons;
- review/confirm pattern;
- local draft persistence;
- pending sync;
- accepted acknowledgement;
- approval/review required;
- offline/stale/freshness cues;
- evidence/provenance disclosure;
- empty/loading/error states;
- mobile share and A4 document transitions.

Do not standardize purpose-specific page geometry.

### Phase F — Redesign the core journeys in rollout order

1. **Login + Home shell** — because every journey begins here.
2. **Billing / Sale** — fastest counter path; customer→item→qty→rate→next item; payment evidence separate and clear.
3. **Service Intake** — customer→machine→complaint→accept, then staged service record.
4. **Stock Count** — item→count→next item with quantity dominant and reference stock secondary.
5. **Purchase Request / PO** — product requirement first, owner approval state visible, supplier instruction separate.
6. **Closing Cash** — day sheet + physical cash + reconciliation; preserve familiar grid semantics without turning it into a generic form.
7. **Owner ON CALL** — attention receiver over the working system, not a competing data-entry shell.
8. **Estimate, Quotation, Receipt, Payment, documents** — purpose-specific follow-on surfaces using the admitted shell and primitives.

### Phase G — Usability proof before field admission

For each core journey, test at minimum:
- 390×844 phone;
- 1366×768 laptop;
- touch targets and one-handed use where plausible;
- keyboard/focus behaviour;
- normal network;
- network loss during entry;
- reconnect and sync;
- interruption / browser close / resume;
- duplicate tap / repeat submit;
- stale reference data;
- missing required data;
- permission failure;
- role mismatch;
- successful acknowledgement;
- review/approval path.

Measure:
- taps/keystrokes for common path;
- repeated typing eliminated;
- time-to-first-action;
- visible decisions per screen;
- errors or hesitations;
- ability to explain current state without technical knowledge.

### Phase H — One-counter pilot day

Do not call the UI finished after screenshots or automated tests.

Run one controlled counter through a complete day in parallel with existing operations. Record friction immediately:
- what staff could not find;
- what they had to ask;
- what they typed twice;
- where they hesitated;
- where wording misled them;
- where phone keyboard/scrolling interrupted work;
- where offline/reconnect state was unclear;
- what owner information was missing at day close.

Use this evidence for the next admitted revision.

## 7. Immediate design decisions

Until the study completes:

1. Do not add another visual form variant merely to explore styling.
2. Do not expand the feature menu.
3. Do not use the current `app.js` prototype navigation as the future OS information architecture.
4. Treat `Page Toolbox`, import/admin utilities and old prototype CRUD surfaces as non-counter lanes unless specifically admitted.
5. Preserve current runtime/backend work; UI redesign should bind to it rather than invent duplicate local truth.
6. Make branch/user/enterprise/network/sync context a first-class shared primitive.
7. Design mobile first, then exploit desktop space without changing the mental model.
8. Use plain operational language first; reveal technical truth/evidence detail progressively.
9. Keep consequential ECHO acceptance separate from BUSY/downstream confirmation.
10. Judge progress by completion of the whole business-day journey, not number of pages.

## 8. First deliverables from this study

The next concrete product-design outputs should be:

1. `UI_SURFACE_INVENTORY.md` — every current user-facing surface and its admit/redesign/quarantine/retire decision.
2. `CORE_USER_JOURNEYS.md` — real workflow maps by role.
3. `ECHO_SHELL_SPEC.md` — phone/desktop shell, context and state language.
4. Low-fidelity wireframes for Home, Billing, Service Intake, Stock Count, PO and Closing Cash.
5. One HTML interaction prototype of the shell + Home using real runtime context but no new business semantics.
6. Then journey-by-journey implementation and testing.

## 9. UX acceptance statement

A core surface is ready for counter trial only when a representative user can complete its common job quickly without understanding ECHO internals, can tell what happened and what remains pending, can recover from interruption/network loss, and cannot accidentally mistake local work, ECHO acceptance, approval, BUSY booking or other downstream state for one another.
