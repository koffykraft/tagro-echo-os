# TAGRO × ECHO OS — Shell Specification V1

Status: candidate under WO-0013
Visual direction: Option 3 first; Option 1 secondary influence; Option 5 reserved for high-contrast/dark mode exploration

## 1. Purpose

The shell is the stable human environment around all admitted ECHO work. It must reduce repeated context entry, preserve orientation, surface pending/review state, and provide a consistent mobile-safe frame without forcing every business page into identical geometry.

## 2. Visual character

Primary visual family follows the owner's Option 3 preference:
- soft neutral/off-white background;
- clean white work surfaces;
- restrained borders and very light depth;
- dark charcoal typography;
- TAGRO orange used for active/primary action and attention only;
- generous but economical spacing;
- icon + word for high-value navigation;
- calm rather than dashboard-like.

Option 1 contributes warmth and larger action emphasis. Option 5 may later inform dark/high-contrast accessibility, not the default shell.

## 3. Mobile shell anatomy

Top safe area
- system status/cutout handled by safe-area inset;
- no critical touch target in gesture/conflict area.

Brand row
- TAGRO × ECHO identity;
- compact menu/context action;
- no engineering subtitle on routine Home.

Context card
- authenticated person/email/name where available;
- role where resolved;
- branch/counter where resolved;
- unobtrusive online/offline/sync state;
- tap opens context drawer in future version.

Primary work area
- role heading such as COUNTER;
- stable job actions;
- Counter default candidate: SELL, SERVICE, ESTIMATE;
- secondary actions remain below/future contextual region.

Continuity area
- CONTINUE;
- WAITING TO SEND;
- NEEDS ATTENTION;
- each appears only when meaningful where runtime data is available.

Bottom bar
- Home;
- Search;
- Create/quick action;
- Attention;
- Menu;
- safe-area padded;
- labels retained; not icon-only.

## 4. State language

Network alone does not prove sync.

Shell may show:
- Online
- Offline
- Waiting to send · N
- Needs review · N

Detailed queue IDs remain behind the ordinary surface.

## 5. Runtime binding

The candidate shell reuses `runtime-config.js` and `runtime-client.js`.

It must:
- redirect unsigned users to `login.html`;
- use existing `EchoRuntime.loadContext()`;
- display the selected enterprise membership when available;
- use `EchoRuntime.pendingQueue()` and `reviewQueue()` for local sync indicators;
- listen for online/offline and `echo:queue-updated` changes;
- never create duplicate business truth.

The shell itself creates no consequential event.

## 6. Role projection

V1 candidate may default to counter-oriented actions while the role is rendered from enterprise membership if the tenant context exposes it.

Future role projection:
- Counter: SELL / SERVICE / ESTIMATE
- Mechanic: TAKE JOB / MY JOBS / PARTS NEEDED
- Manager: TODAY / APPROVALS / EXCEPTIONS
- Owner: NEEDS ATTENTION / APPROVALS / BUSINESS NOW

Role projection changes visible actions, not underlying identity or truth.

## 7. Phone comfort

- primary tap targets >= 52px high where practical;
- editable text >= 16px;
- no permanent side rail;
- no routine horizontal scrolling;
- bottom navigation clears `env(safe-area-inset-bottom)`;
- side padding accounts for left/right safe insets;
- page remains usable with browser chrome or installed PWA;
- visual density comes from removing irrelevant content.

## 8. Desktop adaptation

At wider widths:
- phone mental model remains;
- central work area gains width;
- continuity/attention may appear in adjacent column;
- context may expand;
- no different module taxonomy is introduced.

## 9. Candidate links

The first shell candidate may link to existing pages for SELL, SERVICE and ESTIMATE only as temporary destinations. Their current page design/runtime generation is not thereby admitted.

## 10. Admission boundary

This shell remains a candidate until:
- runtime context is visually verified with a real authenticated NonProd user;
- 390×844 and 1366×768 layouts are inspected;
- Android gesture-nav and keyboard-open behavior are tested;
- interruption/resume and offline queue display are verified;
- owner/staff review confirms comfort and navigation direction;
- replacement of `index.html` is explicitly authorised.
