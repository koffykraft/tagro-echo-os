# TAGRO × ECHO OS — Core User Journeys and Micro-Moments

Date: 2026-08-22
Status: active design input for shell and low-fidelity prototypes
Authority: ECHO Constitution + Product Design Engineering Contract + Page Ecology + Purpose-Specific Forms + UI/UX Design Rules V1

## 1. Design premise

ECHO is not designed around modules. It is designed around people performing short real jobs inside a complete business day.

The user should not need to know whether a task belongs to Billing, Stock, Cash, Prism, BUSY, AWS, a queue or a database table.

Each journey therefore has two scales:

- MICRO-MOMENT — the immediate job the person wants to complete now;
- JOURNEY — the larger business process in which that small event belongs.

The OS must make the micro-moment fast without losing the larger event/evidence relationship.

## 2. Shared opening journey

### Returning staff

Goal: get from opening ECHO to meaningful work with almost no administration.

1. Open ECHO.
2. Existing secure session/passive auth state is resolved where valid.
3. ECHO shows compact context: person, role, counter/branch, date and sync/network state.
4. Home shows role-appropriate primary jobs.
5. User taps the job.

Target experience:

`Open → understand context → begin work`

Normal target: within about five seconds and preferably one tap after Home for the dominant job.

Do not ask again for branch/user/date unless context is missing, expired or intentionally changed.

### New/expired session

1. Sign in securely.
2. Resolve enterprise membership.
3. Resolve/default permitted branch/counter.
4. Enter role-aware Home.

If multiple enterprises/branches are valid, selection is a context decision, not a repeated form field.

## 3. Counter staff — Home

### What this person normally needs

Primary stable jobs:

- SELL
- SERVICE
- ESTIMATE / QUOTE where enabled

Secondary/contextual jobs:

- COUNT
- REQUEST PURCHASE
- RECEIVE MONEY where separate receipt is required
- CLOSING CASH later in day

Adaptive areas:

- CONTINUE
- RECENT
- WAITING TO SEND
- NEEDS ATTENTION

The user should not see Page Toolbox, Bank Import, Masters, engineering reports or prototype utilities as peer actions.

## 4. Sale / Billing journey

### Micro-moment A — Start a sale

User intent: customer wants to buy now.

Common path:

1. Tap SELL.
2. Existing customer can be found by name/phone; Cash customer path is immediate where policy permits.
3. Find/scan/select product.
4. Qty defaults to 1.
5. Authorized rate/tax comes from governed product/price context.
6. Add next product.
7. Payment evidence/mode is selected/recorded appropriately.
8. Review total.
9. ISSUE BILL.
10. Immediate state acknowledgement.

Target navigation:

Customer → Item → Qty → Rate if editable/needed → next Item → Review/Issue.

### What ECHO should remember/know

- signed-in person;
- branch/counter;
- business date;
- common/recent products;
- governed product identity;
- GST/tax defaults;
- authorized/default price;
- recent customer matches.

### What must not dominate routine entry

- raw product IDs;
- branch code typing;
- ECHO event IDs;
- BUSY adapter explanations;
- stock-plane theory;
- technical queue state.

### State language

During work: Draft.
If saved locally/offline: Saved on device / Waiting to send.
After ECHO admission: ECHO accepted / Bill issued.
BUSY: separately Booked / Waiting / Not confirmed.

### Interruption recovery

Return to exact bill with customer, lines and current work state.

### Exceptional paths

- product cannot be resolved;
- price override requires authority;
- stock evidence insufficient/contested;
- payment evidence incomplete;
- duplicate submit;
- offline issue allowed/limited by contract;
- runtime rejection/review.

Exceptions should interrupt only when they become relevant.

## 5. Service Intake journey

### Micro-moment — Accept this machine

User intent: customer has brought a machine for repair/service.

Common path:

1. Tap SERVICE.
2. Find/create customer.
3. Find/identify machine or type model quickly.
4. Capture complaint in customer words.
5. ACCEPT MACHINE.
6. Immediate acknowledgement with service-job identity.

Core first screen:

Customer
Machine
Complaint

ACCEPT

Optional details are progressive:

- serial number;
- accessories received;
- visible condition;
- known product identity;
- special notes.

### First-screen rule

Do not make reception complete diagnosis, parts planning or technician administration before accepting the machine.

### Result

ECHO creates/queues the intake evidence and gives a compact identity such as:

`Jose · MS 382 · Job 1048`

This identity becomes external memory through later service stages.

## 6. Mechanic / staged Service journey

### Mechanic Home

Stable jobs:

- TAKE NEXT JOB
- MY JOBS
- PARTS NEEDED

### Micro-moment A — Take job

1. Tap a job / TAKE NEXT JOB.
2. Machine identity remains visible.
3. Customer complaint is visible in original language.
4. Mechanic accepts responsibility / starts work where policy requires.

### Micro-moment B — Bench observation

Primary input: Bench Note / observed condition.

Optional assistance:

- guided diagnostic suggestions;
- known machine history;
- likely parts/manual links;
- photo/voice evidence.

AI/diagnostic suggestions remain proposals.

### Micro-moment C — Need a part

1. Within current job tap PART NEEDED.
2. Find/scan part.
3. Qty.
4. Save requirement.

Do not force mechanic into the Purchase module.

The event can later project into stock/PO/approval receivers.

### Micro-moment D — Work done / ready

1. Record work done and parts used.
2. Mark ready / next permitted status.
3. Consequential billing/closure remains appropriately separated by role/authority.

## 7. Stock Count journey

### Micro-moment — Count this item

User intent: record what is physically here now.

Common path:

1. Tap COUNT.
2. Find/scan product.
3. Quantity field receives immediate focus/numeric keyboard.
4. Enter physical count.
5. RECORD.
6. Immediate acknowledgement.
7. Product search is ready for next item.

Target loop:

Item → Count → next Item.

### Visual priority

Physical counted quantity is dominant.
Expected/canonical/reference quantities are secondary evidence and must not visually compete with the observation.

### Truth

Count observation does not silently mutate canonical movement stock.
Unknown expected stock remains unknown, not zero.

### Variance/recount

Large/interesting variance may create a separate review/recount route rather than interrupt every ordinary count entry.

## 8. Purchase Requirement / PO journey

### Counter/mechanic micro-moment — We need this item

1. From current context or Home tap REQUEST PURCHASE / PART NEEDED.
2. Find product.
3. Qty required.
4. Optional reason/job linkage.
5. SEND FOR APPROVAL / SAVE REQUIREMENT.

Do not require supplier ID at the earliest requirement-capture moment unless the user's role/job truly chooses supplier.

### Manager/owner approval micro-moment

1. Attention shows request with branch, product, qty, reason and relevant stock/usage evidence.
2. Approver sees suggested/known supplier and commercial evidence where available.
3. APPROVE / RETURN / REJECT with reason as required.

### Supplier instruction

Approved requirement becoming an actual supplier PO is a separate consequential step/state.

The UI must preserve:

Requirement → Awaiting approval → Approved → Supplier instruction sent/confirmed.

## 9. Receipt / Money In journey

### Micro-moment — Money came in

Amount is primary.

1. Enter amount.
2. Identify source type/reference where known: invoice, customer, service, cash box, transfer, other.
3. Identify receiving mode/account/cash box.
4. Add reference/narration/evidence only as needed.
5. RECORD RECEIPT.

A bank credit/cash movement is not automatically revenue or a customer payment.

Allocation may follow or be suggested, but must remain explicit when consequential.

## 10. Payment / Money Out journey

### Micro-moment — Money went out

Amount is primary, but purpose/source are co-primary for truth.

1. Enter amount.
2. Purpose/item/head.
3. Payee where known.
4. Source cash/bank/mode.
5. Reference/evidence.
6. Approval if required.
7. RECORD / SEND FOR APPROVAL depending authority.

Do not simply mirror the Receipt screen.

## 11. Closing Cash journey

### Micro-moment A — Work the day sheet

The familiar day-working geometry is primary.

- SALE
- BILL
- EXPENSES / raw cash-offset movement
- PARTICULARS

Entry should preserve the user's familiar rhythm rather than force classification before raw evidence exists.

### Micro-moment B — Count physical cash

Denomination → Qty → next denomination.

### Micro-moment C — Reconcile

Show:

- yesterday/opening cash;
- current physical cash-plane inflows/outflows as governed by contract;
- expected closing;
- declared cash;
- difference.

### Micro-moment D — Review/confirm

User sees the exact day sheet and cash count before consequential save/submit.

After confirmation, correction is by supersession/correction—not silent overwrite.

### Time-aware relevance

Closing Cash may become more prominent on Home toward closing time, but the stable Home structure remains recognizable.

## 12. Manager journey

Manager is not a counter form with more buttons.

Primary Home:

- TODAY
- APPROVALS
- EXCEPTIONS

### Micro-moment — Approve

Show one decision object:

- what is requested;
- branch/person/context;
- amount/qty/materiality;
- relevant evidence;
- reason;
- current state;
- permitted actions.

Then APPROVE / RETURN / REJECT as governed.

Do not make the manager navigate to the originating entry form merely to make the approval decision unless editing is intentionally required.

## 13. Owner journey / ON CALL

Owner Home should answer first:

What needs my attention now?

### First layer

Examples:

- Cash difference at KVR.
- Purchase request awaiting approval.
- Unusual sale/discount/value needing review.
- Stock evidence conflict.
- Material unresolved financial movement.

Normal branches/events remain quiet.

### Attention card content

- plain-language issue;
- branch/person/time;
- material amount/quantity;
- evidence freshness/confidence where relevant;
- why it is here;
- allowed action.

### Second layer

Business Today / financial overview:

- sales;
- known/estimated margin/contribution where evidence supports it;
- cash/bank positions where actually known;
- branch summaries;
- evidence quality.

### Third layer

Detailed provenance, confidence breakdown, Prism state and analytical evidence.

Owner should not need to parse the third layer to discover the first-layer problem.

## 14. Shared CONTINUE experience

ECHO must support interruption across jobs.

Home may show a compact CONTINUE area, for example:

- Bill draft · Jose · 3 items
- Service · MS 382 · complaint captured
- Stock count · 17 observations this session

Continue items must be scoped to authenticated person/enterprise/device policy and must not leak one user's pending work into another's authority.

## 15. Shared WAITING TO SEND experience

When offline/pending work exists, do not create a separate engineering queue application for ordinary staff.

Home/context may show:

`2 waiting to send`

Tap reveals human-readable items:

- Bill draft · Jose · ₹12,480
- Stock count · MS 382 Chain · 12

Possible states:

- Waiting to send
- Sending
- ECHO accepted
- Needs attention

Technical queue identifiers remain secondary detail.

## 16. Shared NEEDS ATTENTION experience

Attention is a receiver, not a module.

An event may project here because of:

- approval requirement;
- conflict;
- stale/missing evidence;
- unusual value/frequency/timing;
- unresolved sync/reconciliation;
- owner/manager decision requirement.

Attention never means wrongdoing or error by itself.

## 17. Micro-moment design questions

Before wireframing any ECHO task, answer:

1. What does the person want right now?
2. What is the minimum information ECHO needs?
3. What can ECHO already know or safely suggest?
4. What is the single dominant action?
5. What identity/context must remain visible?
6. What happens if interrupted now?
7. What happens if network disappears now?
8. What acknowledgement proves the action was heard?
9. What consequence has actually occurred?
10. What is the next likely micro-moment?

## 18. Shell implications derived from journeys

The shell must provide, without each page rebuilding it:

- TAGRO × ECHO identity;
- authenticated person + role;
- branch/counter;
- business date/session;
- network/sync state;
- Home/back continuity;
- CONTINUE;
- WAITING TO SEND;
- NEEDS ATTENTION;
- safe context-change path;
- stable role-aware primary navigation;
- phone safe-area handling;
- interruption/resume support.

The shell should not permanently consume large screen space. On phone, context and secondary destinations belong in compact bars/drawers/sheets.

## 19. First wireframe order

Low-fidelity design should proceed in this order:

1. Returning-user Home / shell.
2. SELL common path.
3. SERVICE intake common path.
4. COUNT repeat loop.
5. REQUEST PURCHASE common path.
6. CLOSING CASH working/review path.
7. Owner NEEDS ATTENTION / ON CALL hierarchy.

Only after these common paths are coherent should exception-heavy details and secondary tools be expanded.

## 20. Acceptance target

A staff member should not feel that they are operating a software architecture.

They should feel that ECHO already knows who/where they are, gives them the few jobs they actually need, remembers work through interruption, reduces typing/searching, clearly acknowledges every action, and tells the truth about what has and has not happened.
