# TAGRO × ECHO OS — UI/UX Design Rules V1

Status: owner-directed product design authority for ECHO user-facing surfaces
Date: 2026-08-22
Scope: PWA/mobile, tablet, desktop, future native clients, staff/manager/owner operational surfaces

## 1. Authority and intent

These rules operationalize the existing Product Design Engineering Contract, Page Ecology Contract, Purpose-Specific Form Design Contract, ECHO constitutional truth/authority model, and the UI/UX study started on 2026-08-22.

External research used to sharpen these rules includes Nielsen Norman Group mobile usability guidance, Interaction Design Foundation mobile/UI studies, Android system-bar and edge-to-edge guidance, Mobbin shipped-interface research methods, UX Pilot 2026 mobile design analysis, and the owner-supplied Mobile-Friendly UI/UX Design Tips PDF.

External research is evidence and reference, not ECHO authority. Where any research pattern conflicts with ECHO truth, evidence, authority, provenance, offline or correction doctrine, ECHO doctrine wins.

The product goal is not to make a collection of attractive pages. It is to make one coherent operating environment in which a real person can complete business work quickly, understand what happened, survive interruption/network loss, and never confuse local work, ECHO acceptance, approval, BUSY booking or other downstream state.

## 2. Governing UX statement

> ECHO shows the right work, to the right person, at the right moment, with the least necessary interaction — while keeping identity, authority, evidence and system state unmistakably truthful.

A shorter operational test is:

> Hide system complexity without hiding business truth.

## 3. Mobile position

Mobile is a first-class operational environment, not a reduced desktop edition.

A core counter workflow SHALL NOT be admitted if the phone experience is merely a compromise. Desktop and tablet may reveal more context, evidence, history or comparison space, but SHALL preserve the same underlying job, state model and mental model.

Phone: work dominates.
Tablet: work + relevant adjacent context.
Desktop: work + context/evidence/history where useful.

Responsive shrinking alone is not mobile design.

## 4. The ECHO Eight UI Gate

Every admitted operational surface must pass all eight gates.

1. USER-CENTERED — Does the screen reflect the real person, environment and business job?
2. SIMPLE — Is everything visible necessary now, or necessary for continuity/safety?
3. CONSISTENT — Does ECHO behave like ECHO across workflows without forcing identical page geometry?
4. ADAPTIVE — Is the presentation appropriate to role, device, time, branch/context and available space?
5. FEEDBACK-RICH — Does every meaningful action immediately acknowledge what happened or what is happening?
6. TRUTHFUL — Can local, queued, ECHO-accepted, approval, BUSY/downstream and uncertain states ever be mistaken for one another?
7. RECOVERABLE — Can a person interrupt, resume, undo where still reversible, or correct/supersede where already admitted?
8. FAST — Is the common route shorter and easier than the operational alternative it replaces?

Failure of any one gate is product-design debt and can block operational admission.

## 5. The six UX budgets

Every mobile screen has limited capacity. Design SHALL manage six explicit budgets.

### 5.1 Attention budget
Few competing decisions at one time. One dominant current action/state.

### 5.2 Reach budget
Important controls must be touch-safe, comfortably reachable and outside operating-system gesture/navigation conflict areas.

### 5.3 Typing budget
Never ask a person to type something ECHO can safely know, default, calculate, find, scan, suggest or remember.

### 5.4 Time budget
The interface must acknowledge input immediately and get returning users into meaningful work quickly. Target: ordinary return-to-work path should approach one tap; Home comprehension and task start should normally fit within about five seconds under normal device conditions.

### 5.5 Trust budget
Never make the person wonder whether work saved, synchronized, was accepted, needs approval, or reached BUSY/downstream.

### 5.6 Memory budget
Do not force short-term memory across screens. Important task identity and decision context must remain visible or one effortless reveal away.

## 6. Page ecology rule

Every visible element must earn its place.

Before admitting a control, label, card, chart, notice, icon, navigation item or data point, ask:

- Is it needed for the job now?
- Is it required for truth, continuity, authority, recovery, accessibility or safety?
- What useful content does it displace on a phone?
- Is this the correct role/page/region/sequence?
- Is the element bound to canonical data/event/evidence rather than convenient duplicate state?
- Could it create duplicate truth, wrong authority, stale interpretation or false completion?

Feature existence is not a reason for Home-screen presence.

Prototype, toolbox, import, engineering and admin surfaces must not compete with ordinary staff work unless explicitly admitted for that role.

## 7. Job-first information architecture

The user SHALL not need to understand ECHO module architecture to operate ECHO.

Primary navigation is expressed as jobs and attention, not internal subsystems.

Examples:

Counter: SELL, SERVICE, ESTIMATE, COUNT, REQUEST PURCHASE, CLOSING CASH.
Mechanic: TAKE JOB, MY JOBS, PARTS NEEDED.
Manager: TODAY, APPROVALS, EXCEPTIONS.
Owner: NEEDS ATTENTION, APPROVALS, BUSINESS NOW / ON CALL.

Search is appropriate inside a known job for finding an object. Search SHALL NOT replace understandable top-level navigation.

Navigation answers: What can I do?
Search answers: Which thing am I working with?

## 8. Stable shell, adaptive relevance

ECHO may adapt prominence and suggestions by role, branch, time, pending work, history and context, but SHALL preserve stable spatial anchors for familiar primary actions.

Adaptive UI must not make controls unpredictably move around merely because an algorithm changed its ranking.

Preferred pattern:

- stable primary jobs;
- adaptive RECENT / CONTINUE / NEEDS ATTENTION / SUGGESTED areas;
- role-aware visibility;
- contextual prominence without destroying muscle memory.

Prediction may alter prominence; it must not silently alter authority or business truth.

## 9. Context is a system primitive

Enterprise, authenticated person, role, branch/counter, business date/session, network/sync state and relevant device/session identity are shared shell context.

A normal workflow SHALL NOT repeatedly ask for branch code, actor/user, date or other already-known context merely because individual pages were built separately.

Context must be compactly visible and deliberately changeable when authority permits.

Changing consequential context must retain:

- actual authenticated principal;
- selected acting context;
- reason when required;
- time/provenance.

One device must not be treated as permanently one human. Quick lock/switch/re-authentication must be possible in the future shell without mixing one person's local drafts or authority with another's.

## 10. One dominant current action

Each working state should have one visually dominant next action.

Examples:

Service intake: ACCEPT MACHINE.
Stock count: RECORD COUNT.
Billing review: ISSUE BILL.
Purchase request: SEND FOR APPROVAL.
Closing Cash: REVIEW DAY / CONFIRM CLOSE depending state.
Owner review: APPROVE / REVIEW only when authority allows.

Secondary and exceptional controls recede visually but remain discoverable.

Dangerous/opposing actions SHALL not be crowded beside the primary action in ways that invite accidental activation.

## 11. Purpose-specific geometry

Shared primitives are encouraged. Shared page composition is not presumed.

Billing is repeated item entry.
Service is a staged machine record.
Stock Count is item → physical quantity repetition.
Purchase Request is need → approval → supplier instruction.
Closing Cash is a day/reconciliation working sheet.
Receipt and Payment are different money-evidence jobs.
Estimate and Quotation are not invoices waiting to happen.

A generic renderer must not be allowed to erase these distinctions.

## 12. Progressive disclosure

Primary-now information dominates. Secondary-nearby information remains available. Irrelevant information is absent.

Do not make routine users repeatedly read engineering explanations about canonical planes, runtime internals or BUSY adapters.

Use layered truth:

Level 1: plain operational state.
Level 2: useful explanation / evidence / reason on demand.
Level 3: technical provenance, event IDs, confidence, downstream details where role/use requires it.

Do not hide evidence or authority needed for the current decision under the excuse of simplicity.

## 13. Operational language before implementation language

Labels describe what the person is doing, not how ECHO is implemented.

Preferred user-level state vocabulary:

- Draft / Saved on this device
- Waiting to send
- Sent to ECHO / ECHO accepted
- Awaiting approval
- Needs attention / Needs review
- Completed
- BUSY booked / downstream confirmed where separately known

Technical state may be available on demand.

Never use wording that implies a consequence not actually established.

## 14. Feedback and micro-interactions

Every meaningful action must provide immediate feedback.

Feedback answers one or more of:

- I heard you.
- I saved this locally.
- I am sending it.
- ECHO accepted it.
- It needs approval/review.
- The downstream system confirmed it.
- It failed; your work is still safe.

Motion, animation and haptics (where available) are punctuation, not decoration. They may acknowledge, guide attention or clarify a state transition; they must not delay work or obscure status.

No confetti, gratuitous animation or decorative motion in core operations.

## 15. Interruptibility and continuous recovery

Portable means interruptible.

Core mobile work must assume:

- phone call;
- WhatsApp switch;
- customer interruption;
- browser/app backgrounding;
- device sleep;
- network loss;
- browser/process termination;
- user returning minutes later.

Meaningful edits should be continuously locally recoverable where safe. A user should not need to remember to press Save merely to survive normal interruption.

On resume, ECHO restores the job and relevant position/context, not merely the module landing page.

Before consequential admission: Edit / Undo / Back where semantics allow.
After consequential admission: Correction / Supersede, never silent rewrite.

## 16. Offline is a normal state

Offline, reconnect, pending sync, retry and conflict are product states, not error-page afterthoughts.

The UI must distinguish:

- locally retained work;
- queued command;
- acknowledged ECHO event;
- review/conflict;
- downstream confirmation.

Network availability alone must never be displayed as proof that pending work synchronized.

A user may keep working offline only where the workflow contract permits. The UI must not invent shared-state certainty while offline.

## 17. Mobile safe-viewport doctrine

Background and noncritical scrolling content may extend visually to device edges.

Critical text, fields, buttons, drag handles and consequential touch targets must remain inside safe operating space.

The shell must account for:

- status bar / display cutout;
- bottom navigation/gesture area;
- left/right back-gesture conflict zones where applicable;
- safe-area insets in browser/PWA;
- on-screen keyboard;
- portrait/landscape;
- installed-PWA and browser chrome differences.

For current web/PWA surfaces this means deliberate use of `viewport-fit=cover`, `env(safe-area-inset-*)` and tested keyboard/viewport behaviour rather than page-specific patches.

Routine ECHO operations should not depend on hidden edge swipes.

## 18. Touch rules

Touch targets should normally be at least approximately 44–48 CSS px in their interactive dimension, with sufficient spacing and visual affordance. High-frequency and consequential actions may be larger.

A small visible icon may have a larger invisible/contained touch target.

Do not create density by shrinking required controls. Create density by removing unnecessary controls.

Icon + word is preferred for important navigation where an icon genuinely improves recognition. Icon-only actions require universal meaning or an accessible label.

## 19. Input rules

Every field must justify its existence.

For every input ask, in order:

1. Can ECHO already know it from authenticated/context state?
2. Can it default safely?
3. Can it be calculated?
4. Can it be selected from recent/history?
5. Can it be found with type-ahead/search?
6. Can the camera/barcode/QR/voice/device capability reduce typing?
7. Is manual entry still required or needed as a provenance-preserving fallback?

Use the correct mobile input type/inputmode and autocomplete semantics.

Editable text should generally be 16px or larger on iOS/web mobile to avoid focus zoom disruption.

Frequent number workflows must be tested with the numeric keyboard open.

## 20. Keyboard-open is a mandatory design state

No core input workflow passes mobile review only because it looks good with the keyboard closed.

Test:

- primary field remains visible;
- next action remains reachable or predictably reachable;
- total/critical context is not accidentally hidden;
- focus movement does not create disorientation;
- Return/Enter follows task-specific logic where appropriate;
- closing the keyboard is not required after every field.

## 21. Recognition over recall

ECHO should expose known choices and relationships instead of requiring codes or memory.

Prefer:

`MS 382 · Chain brake assembly`

over raw opaque product IDs.

Prefer:

`Jose · MS 382 · Job 1048`

over asking the mechanic to remember which machine/customer they were working on.

Persistent compact identity strips may serve as external memory during staged work.

## 22. Microsessions

Complex systems should expose useful sub-jobs that can be completed in seconds.

Examples:

- Accept this machine.
- Count this item.
- Add this product to a bill.
- Request five of this part.
- Approve this purchase request.
- Record this receipt.

A valid small event should not require the user to traverse the entire surrounding business process.

Future PWA shortcuts may deep-link to stable high-frequency microsessions only after the corresponding journeys are proven.

## 23. AI and agentic UX

AI is primarily a friction-removal layer, not a visual theme.

AI may:

- suggest likely customer/product/machine;
- parse speech/text into structured candidate fields;
- prepare an estimate or purchase request;
- identify likely part compatibility;
- surface anomalies or missing evidence;
- recommend a next action;
- draft explanations/communications.

AI alone must not establish consequential business truth or silently exercise Driver authority.

Preferred flow:

conversation/camera/prediction → structured proposal → human review/confirmation → governed Driver action.

Agentic behaviour must show what ECHO proposes, why where material, and how the person can reject/correct it.

Do not place a large generic AI chat box on every operational screen merely to advertise AI.

## 24. Owner ON CALL rule

Owner ON CALL is an attention receiver, not a conventional ERP dashboard.

Its primary job is to answer:

- What needs my attention now?
- Why?
- How material is it?
- What evidence/freshness/confidence supports it?
- What action, if any, am I permitted to take?

Routine normality should remain quiet.

Dense financial/evidence analysis may exist behind the attention layer, but should not compete with the first owner decision surface.

## 25. Visual character

ECHO should feel:

- calm;
- quick;
- helpful;
- forgiving;
- familiar;
- competent;
- truthful.

It should not look like futuristic AI software, a decorative consumer app, or a dense legacy ERP.

Visual hierarchy, spacing, typography, iconography, contrast and depth must clarify work.

Use depth to communicate state/layer (work surface, drawer, review, confirmation), not fashion.

Colour is not the sole carrier of state. Text/icon/shape must preserve meaning for accessibility.

## 26. Performance and perceived performance

Operational trust depends on both actual and perceived speed.

Consequential taps must never leave the screen apparently dead.

Use immediate local acknowledgement followed by truthful progression, for example:

Saving… → Saved on phone → Sending… → ECHO accepted.

Do not block ordinary work on decorative assets, heavy visual effects or nonessential network requests.

Low-data and variable-connectivity behaviour are inclusive-design requirements for ECHO.

## 27. Self-contained work

Because mobile frequently presents one app at a time, ECHO should surface required related information inside the current job where practical.

Avoid forcing the user to leave ECHO, look something up elsewhere, remember/copy it and return.

Relevant customer history, machine history, product compatibility, prior service, price authority, stock evidence or approval context should be available within the job's evidence/context plane when needed.

WhatsApp/email are normally communication outputs/handoffs from governed ECHO records, not substitute workspaces for completing the record.

## 28. Documents are projections, not separate truths

Working screen, mobile share image and A4/PDF document are separate projections of the same governed record.

Do not make users re-enter information into a separate "Print Documents" tool to obtain an invoice, quotation, estimate, PO or service document.

Document generation belongs to the originating job/event and must inherit its identity, authority, numbering/state and revision history.

## 29. Shipped-interface research rule

Mobbin and other shipped-product libraries may be used to answer a specific unresolved interaction question.

Research process:

real ECHO job → define micro-problem/constraints → inspect multiple shipped patterns → extract repeatable skill → reject inappropriate consumer/engagement tricks → design ECHO-specific solution → test.

Do not copy another product's shell, colours or fashionable treatment merely because it looks polished.

## 30. Real-device acceptance matrix

Before counter trial, each core journey must be inspected/tested at minimum on:

- approximately 390×844 phone viewport;
- 1366×768 laptop;
- real mid-range Android phone;
- Android gesture navigation;
- Android three-button navigation when feasible;
- browser and installed-PWA mode where supported;
- keyboard closed/open;
- normal network;
- slow/unstable network;
- offline entry where allowed;
- reconnect/sync;
- interruption/background/resume;
- duplicate tap/repeat submit;
- stale/missing reference data;
- permission/role failure;
- safe-area/system-bar conditions.

The hand and environment are part of the test. Observe grip changes, hesitation, mis-taps, repeated typing, scrolling, reaching for paper and requests for help.

## 31. Usability evidence

A green API/runtime test does not admit the UI.

For representative workflows record:

- time to first meaningful action;
- taps and keystrokes in the common path;
- repeated information eliminated;
- errors/mis-taps;
- hesitations;
- requests for help;
- interruption recovery success;
- ability to explain current state in ordinary language;
- usefulness;
- ease of use;
- satisfaction / preference versus current operating method.

A useful field question is: Would you prefer to do tomorrow's work this way?

## 32. Rollout design order

UI implementation priority is:

1. authenticated shell/context/state language;
2. role-aware Home;
3. Billing/Sale;
4. Service Intake and staged Service record;
5. Stock Count;
6. Purchase Request/PO approval path;
7. Closing Cash;
8. Owner ON CALL attention surface;
9. Estimate and Quotation;
10. Receipt and Payment;
11. derived documents/share/print;
12. secondary reports/admin/import tools.

No new visual form variant should be created merely for stylistic exploration during this convergence phase.

## 33. First operational proof

The UX is not considered coherent until one controlled counter can complete a truthful business day:

Login → context resolved → customer/product/machine work → sale/service/count/purchase as required → payment evidence → offline/reconnect where tested → ECHO acknowledgement → approval/downstream state → Closing Cash → Owner attention → end-of-day reconciliation → recoverability.

Progress is measured by completion of this day, not by number of pages.

## 34. Final acceptance principle

A representative user should be able to operate ECHO without understanding AWS, database schemas, event sourcing, VIBGYOR, Prism, queues, adapters or BUSY internals.

The system may hide those mechanisms.

It must never hide who acted, where, what was recorded, what is known/unknown, what consequence has actually occurred, what remains pending, what evidence supports it, or how the work can be recovered/corrected.
