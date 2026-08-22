# TAGRO × ECHO OS — UI/UX Structural Design Rules V2

Status: active core structural design authority
Effective: 2026-08-22
Supersedes: `ECHO_UI_UX_DESIGN_RULES_V1.md` as the active UI/UX authority
Companion: `ECHO_COMFORT_APPEAL_DESIGN_RULES_V1.md`
Authority: Constitution v1.1, DEC-0021, DEC-0022

## 1. Structural status
UI/UX is a structural layer of ECHO. It is not a decorative pass over backend work.

User-facing architecture shapes:
- how identity, branch, role and session context are carried;
- how real jobs are entered and resumed;
- how authority and consequential boundaries are understood;
- how event/evidence/state is projected without becoming duplicate truth;
- how interruption, offline work and recovery behave;
- how mobile, tablet and desktop environments differ;
- how integrations appear to humans without exposing provider mechanics;
- how AI reduces friction without becoming an authority substitute.

A technical design that makes the correct business model uncomfortably or confusingly operable is incomplete.

## 2. First-stage implementation rule
Existing ECHO pages, frameworks, navigation, CSS, PWA choices, runtime clients and prototypes are evidence and candidate implementation, not permanent constraints.

Preserve proven truth, event semantics, evidence, authority, idempotency and recovery obligations.
Do not preserve accidental layout, workflow, framework or tool shape merely because it was built first.

If a materially better user environment or implementation becomes credible, apply the Planar/Prismatic Evolution Rule.

## 3. Governing experience statement
> ECHO shows the right work, to the right person, at the right moment, with the least necessary interaction — while keeping identity, authority, evidence, state and consequence unmistakably truthful.

Operational shorthand:
> Hide system complexity without hiding business truth.

## 4. Mobile-first structural requirement
Phone operation is a first-class ECHO environment.

Phone: work dominates.
Tablet: work + relevant adjacent context.
Desktop: work + context/evidence/history where useful.

Responsive shrinking alone is not mobile design.
A core counter journey is not admitted when the phone is merely a compromised version of desktop.

## 5. ECHO Eight UI Gate
Every admitted user-facing operational surface must be:
1. USER-CENTERED — reflects the real person, place and job;
2. SIMPLE — only current-job and necessary continuity/safety information competes for attention;
3. CONSISTENT — behaves like ECHO without forcing identical geometry;
4. ADAPTIVE — appropriate to role, device, context, time and space;
5. FEEDBACK-RICH — meaningful actions are immediately acknowledged;
6. TRUTHFUL — local, queued, accepted, approved, BUSY/provider and uncertain states cannot be confused;
7. RECOVERABLE — interruption, undo/edit where reversible, and correction/supersession are designed in;
8. FAST — the ordinary route is materially easier than the process it replaces.

Failure of one gate is design debt and may block admission.

## 6. Six UX budgets
Every screen manages:
- Attention budget — few competing decisions;
- Reach budget — touch-safe, OS-safe controls;
- Typing budget — do not ask for what ECHO can safely know/find/default/calculate/scan/suggest;
- Time budget — get into meaningful work quickly and acknowledge immediately;
- Trust budget — always show what happened and what remains pending;
- Memory budget — keep important job identity/context visible or one effortless reveal away.

## 7. Context is structural
Enterprise, person, role, branch/counter, business date/session, network/sync state and relevant device/session identity are shell primitives.

Individual forms must not repeatedly ask for known branch, actor or date because earlier pages were implemented separately.

Changing consequential context must retain the actual authenticated principal, selected acting context, reason where required, time and provenance.

## 8. Job-first information architecture
Users operate jobs, not architecture.

Counter examples:
SELL · SERVICE · ESTIMATE · COUNT · REQUEST PURCHASE · CLOSING CASH

Mechanic:
TAKE JOB · MY JOBS · PARTS NEEDED

Manager:
TODAY · APPROVALS · EXCEPTIONS

Owner:
NEEDS ATTENTION · APPROVALS · BUSINESS NOW

Search finds the thing inside a known job. It must not replace understandable top-level job navigation.

## 9. Stable shell, adaptive relevance
Core positions remain stable enough for muscle memory.

Role/time/history may adapt prominence and content in areas such as:
- CONTINUE;
- RECENT;
- WAITING TO SEND;
- NEEDS ATTENTION;
- SUGGESTED.

Prediction may change prominence, not authority or truth, and must not make primary controls randomly migrate.

## 10. One dominant next action
Each working state should have one visually dominant next action.

Examples:
ACCEPT MACHINE
RECORD COUNT
ISSUE BILL
SEND FOR APPROVAL
REVIEW DAY
CONFIRM CLOSE
APPROVE

Secondary/dangerous actions remain discoverable but do not compete for hurried touch.

## 11. Purpose-specific geometry
Shared primitives do not imply identical page composition.

Billing is repeated item entry.
Service is staged machine work.
Stock Count is item → count → next item.
Purchase is requirement → approval → supplier instruction.
Closing Cash is a familiar day/reconciliation working sheet.
Receipt is not Payment.
Estimate/Quotation are not Invoice.

A generic renderer must never erase the real shape of the job.

## 12. Progressive truth disclosure
Level 1: plain operational state.
Level 2: useful reason/evidence on demand.
Level 3: technical provenance/event/provider details when role/use requires them.

Routine staff must not be forced to read architecture terminology to operate ECHO.
Required evidence/authority for a current decision must not be hidden in the name of simplicity.

## 13. Operational language
Prefer user language:
- Draft / Saved here
- Waiting to send
- ECHO accepted
- Awaiting approval
- Needs attention
- Completed
- BUSY booked
- Payment confirmed
- Shipment booked / Picked up / Delivered

Do not use provider screens, QR display, queue creation or HTTP success as proof of a business consequence not actually established.

## 14. Interruptibility
Portable work is interruptible.

Design assumes:
- phone calls;
- WhatsApp switches;
- customer interruption;
- app backgrounding;
- device sleep;
- network loss;
- process termination;
- later resume.

Meaningful edits should be locally recoverable where safe.
Resume restores the actual job/context, not merely the module landing page.

## 15. Offline is normal
Offline, reconnect, pending sync, retry and conflict are normal product states.

Distinguish:
- local retained work;
- queued command;
- ECHO acknowledgement;
- review/conflict;
- BUSY/provider/downstream confirmation.

Network available is not the same as synchronized.

## 16. Safe mobile viewport
Use safe-area-aware layouts and test:
- status bar/cutout;
- bottom gesture/navigation zone;
- left/right OS gesture zones;
- on-screen keyboard;
- portrait/landscape;
- installed PWA/browser differences.

Background may extend edge-to-edge. Consequential controls may not blindly occupy OS interaction zones.

## 17. Touch and input
Touch targets normally approximate 44–48 CSS px minimum interactive size, larger where frequent/consequential.

Every field must justify its existence. Ask first whether ECHO can know, default, calculate, recall, search, scan or suggest it.

Use correct keyboard/inputmode/autocomplete.
Test core entry with keyboard open.

## 18. Recognition over recall
Expose human-readable relationships, not opaque IDs.

Prefer:
`Jose · MS 382 · Job 1048`
not raw identifiers the user must remember.

Persistent compact job identity is allowed as external memory.

## 19. Microsessions
Expose useful small jobs that can complete in seconds:
- Accept this machine;
- Count this item;
- Add this product;
- Request this part;
- Approve this request;
- Record this receipt.

A valid small event should not require traversing the entire surrounding business process.

## 20. AI experience rule
AI is a friction-removal layer, not a visual theme.

AI may find, parse, extract, suggest, prepare, compare and explain.
Preferred path:
input/camera/voice/prediction → structured proposal → human review/confirmation → governed Driver action.

Do not advertise intelligence through a large generic chatbot where contextual assistance is better.

## 21. External-provider experience
Amazon Shipping, Delhivery, UPI gateways, BUSY and other providers are docked services.

The user sees ECHO business state first, provider detail second.

Examples:
`Payment pending` is ECHO state with gateway evidence behind it.
`Shipment booked` is distinct from `Picked up` and `Delivered`.

Provider replacement must not require users to relearn the underlying ECHO job unless the new solution materially improves the job and passes structural review.

## 22. Owner ON CALL
ON CALL is an attention receiver before it is an analytics dashboard.

First answer:
- what needs attention;
- why;
- materiality;
- evidence freshness/confidence;
- permitted action.

Normality stays quiet. Detailed analytics remain behind the first decision layer.

## 23. Comfort and appeal
Apply `ECHO_COMFORT_APPEAL_DESIGN_RULES_V1.md`.

Target character:
CALM · CLEAN · WARM · OPERATIONAL · PRECISE

Comfort is product engineering because it affects error, fatigue, hesitation and adoption.

The current preferred initial visual family is the soft-neutral Option-3 direction; it is a candidate visual expression, not an immutable style lock. A better future design may supersede it through the normal evidence/review process.

## 24. Better-solution trigger
When persistent UX flaws, repeated workarounds, poor adoption, unsuitable device behaviour, accessibility failure, platform constraints or a materially better user environment/tool appear, invoke `PLANAR_PRISMATIC_EVOLUTION_RULE_V1.md`.

Possible outcomes include:
- redesign current PWA;
- replace UI framework;
- split mobile/desktop compositions;
- introduce native/hybrid client;
- change navigation model;
- introduce better device capabilities;
- replace design system;
- change external service/provider;
- retain the existing solution because total evidence still favors it.

No current UI choice is protected merely by first-stage implementation or sunk cost.

## 25. Admission evidence
Before field admission, core journeys must be tested on real representative devices and conditions, including:
- ordinary mid-range Android phone;
- 390×844-class viewport;
- laptop/desktop;
- touch;
- keyboard-open entry;
- normal network;
- network loss/reconnect;
- interruption/resume;
- duplicate submit;
- stale/missing reference state;
- permission/role failure;
- safe-area/gesture conditions;
- actual staff use where possible.

Measure hesitation, taps/typing, time to first action, errors, repeated input, paper fallback and ability to explain current state.

## 26. Final structural rule
The UI is ready only when the business structure and the human experience agree.

ECHO must not force people to operate the architecture. It must let them perform the real job while the architecture preserves truth underneath.
