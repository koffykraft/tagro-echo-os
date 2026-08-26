# TAGRO ECHO OS — CURRENT HANDOFF

**Status:** authoritative continuity handoff for the active WO-0014 deployment lane  
**Prepared:** 2026-08-24  
**Branch:** `wo-0014-database-primary-pages-deploy`  
**Purpose:** prevent a new AI/human builder from restarting architecture, rebuilding already-proven work, or losing the operating nuances accumulated across TAGRO Automation, Codex, BUSY evidence, AWS deployment and the UI/UX research.

---

## 0. FIRST INSTRUCTION TO THE NEXT BUILDER

**READ THIS FILE COMPLETELY BEFORE DOING ANYTHING. DO NOT REBUILD THE SYSTEM FROM SCRATCH. DO NOT REOPEN THE BASIC ARCHITECTURE DISCUSSION.**

Then read, in this order:

1. `governance/constitution/ECHO_OS_CONSTITUTION.md`
2. `governance/constitution/AMENDMENT_2026-08-22_HISTORICAL_CONTINUITY.md`
3. `governance/directives/TAGRO_VERTICAL_DEPLOYMENT_DIRECTIVE_2026-08-22.md`
4. `governance/state/ECHO_OS_FOUNDATION.json`
5. `governance/state/CURRENT_STATE.json`
6. `governance/decisions/DECISION_LEDGER.md`
7. `governance/history/ECHO_HISTORY_MEMORY.md`
8. `governance/history/ECHO_HISTORY_INDEX.json`
9. `governance/history/PRE_ACTION_REFERENCE_DIRECTIVE.md`
10. `contracts/core/PRODUCT_DESIGN_ENGINEERING_CONTRACT.md`
11. `contracts/core/ECHO_UI_UX_DESIGN_RULES_V2.md`
12. `contracts/core/ECHO_COMFORT_APPEAL_DESIGN_RULES_V1.md`
13. `work-orders/WO-0014.json`
14. the exact files/tests for the component being touched.

### Current-owner override that must not be missed
Some older WO-0014/governance text still contains a broader Planar/Prismatic/intelligence objective. **For the current foundation deployment path, the Owner has explicitly frozen Planar/intelligence work.** Foundation operations come first: products, customers, SELL, SERVICE, STOCK COUNT, PURCHASE, CLOSING CASH, business integrity, BUSY identity/integration and usable staff pages. Do not allow historical Planar wording to send the build sideways before this operating foundation is deployed and proven.

Planar/history material is not deleted or denied; it remains a separate later plane and evidence source. It must not destabilize the current operations lane.

---

## 1. WHAT ECHO IS — AND WHAT TAGRO IS DOING HERE

ECHO is a **new, independent, scalable AWS-first business SaaS operating system**, not a reskin or patch of the older TAGRO OS.

TAGRO is the **first real tenant and execution environment**. TAGRO data and systems are being used for **proof of execution**, not proof of concept. Real TAGRO history, branch differences, stock, sales, service, purchasing, cash and BUSY behaviour are the validation corpus against which ECHO must prove it can run a real business.

The intended future form is multi-tenant and accounting-system neutral. TAGRO currently uses BUSY; another ECHO tenant may use BUSY, Tally, Zoho, QuickBooks, SAP, another system, or none. ECHO operational identity/workflow must not be coupled to BUSY naming or database layout.

Core boundary:

`ECHO SaaS operational core -> business events/state/evidence -> replaceable accounting/integration adapters`

BUSY is an important docked accounting/inventory/MIS engine for TAGRO, but it is not the architecture of ECHO.

---

## 2. OWNER WORKING PROTOCOL — NON-NEGOTIABLE

The Owner has repeatedly required:

- foundation first;
- business-ready tool over architecture discussion;
- due diligence/path inspection before each consequential stride;
- one command at a time when the laptop must be used;
- do not provide a second command until the previous output is seen;
- keep explanations short during command execution;
- distinguish read-only checks from real AWS/database writes;
- do not ask the Owner to paste JWTs/passwords;
- do not create code clutter for later cleanup;
- repair safe defects inline, otherwise leave a precise repair note;
- do not go sideways from the objective of a real usable business OS;
- AWS-hosted runtime/build preferred; laptop is source/control/extraction bridge;
- preserve useful existing ECHO code, remove superseded/legacy code rather than disguising it;
- no mockups presented as operational completion;
- no claim stronger than the evidence achieved.

Canonical rule established during this work:

> **New ECHO architecture stays. Good ECHO code is repaired in place. Superseded/legacy code is removed, not disguised and reused.**

---

## 3. SOURCE PRIORITY AND CONFLICT RESOLUTION

When sources disagree, use this order for the present deployment:

1. explicit latest Owner direction recorded in this handoff;
2. direct observed AWS/database/Git evidence;
3. active Constitution + later owner directives/decision ledger;
4. active UI/UX/product contracts;
5. current code + passing tests;
6. active work order;
7. older current-state/history documents;
8. historical TAGRO/Codex prototypes and old chats.

Do **not** let a stale README, state file, old test, old Cloudflare path, Planar-era instruction or prototype override directly observed current deployment reality.

---

## 4. REPOSITORY / BRANCH / LAPTOP PATHS

### GitHub
- Repository: `koffykraft/tagro-echo-os`
- Active branch: `wo-0014-database-primary-pages-deploy`
- PR #14 exists historically and may contain stale wording. Do not treat its prose as deployment proof.

### Laptop repository
`C:\Users\HP\Dropbox\TAGRO_AUTOMATION\projects\tagro-echo-os-git`

### Tool paths verified
- Git: `C:\Users\HP\AppData\Local\GitHubDesktop\app-3.6.3\resources\app\git\cmd\git.exe`
- AWS CLI: `C:\Program Files\Amazon\AWSCLIV2\aws.exe`
- SAM: `C:\Program Files\Amazon\AWSSAMCLI\bin\sam.cmd`
- Python: `C:\Program Files\Amazon\AWSSAMCLI\runtime\python.exe` (Python 3.13.x on laptop)
- PowerShell: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe`
- `py` launcher is not installed.

### Important local Git state at handoff
The last confirmed local branch head was `6163fd22c8f49c0d8e6c1712d57f8da8d4dbcfb7`.

A later pull failed while Git tried to write a new object:

`error: unable to write file .git/objects/6f/eace40b7c48702b60449137fcce3e2e1f242ef: Permission denied`

`fatal: failed to write object`

`fatal: unpack-objects failed`

This occurred while pulling the remote commit that added `build/` to `.gitignore` (`6feace40...`). The current remote branch is now newer again because this handoff itself is a later commit.

**FIRST LAPTOP TASK IN THE NEXT CHAT:** inspect/repair the `.git/objects` write permission/lock issue. Do not delete/reclone the repository as a first reaction. Determine whether this is filesystem ACL, Dropbox sync/locking, read-only attribute or another local file lock, then fast-forward the clean branch to remote HEAD.

Generated `build/` files are now ignored in the remote repo; do not treat deployment build outputs as source changes.

---

## 5. AWS ORGANISATION / ACCOUNT / REGION

### Management account background
AWS Organization management account exists separately. ECHO NonProd workload is in a dedicated account.

### Active ECHO NonProd
- AWS account: `272037674623`
- Region: `ap-south-1`
- CLI profile: `tagro-echo-nonprod`
- SSO start URL: `https://d-9f6756a2aa.awsapps.com/start`
- runtime stack: `echo-nonprod-runtime`
- runtime CodeBuild project: `echo-nonprod-runtime-build`
- runtime artifact bucket: `echo-nonprod-artifacts-272037674623`

AWS SSO was successfully refreshed immediately before the current deployment attempts.

### PostgreSQL
- RDS endpoint: `echo-nonprod-postgres.ch6ciowm8fzs.ap-south-1.rds.amazonaws.com`
- PostgreSQL 17.10
- DB name: `echoos`
- shared operational truth is PostgreSQL; browser storage is draft/offline support only.

### API
`https://3n1lhlcush.execute-api.ap-south-1.amazonaws.com`

### Cognito
- User pool: `ap-south-1_F9AcKBFpl`
- Client: `7ctjur525ah5c09pb8dk9ajbgp`
- current web config is in `web/runtime-config.js`.
- only `/health` is intentionally unauthenticated; business routes use JWT/server-side membership/capability checks.

### Tenant bootstrap/readback already proved
TAGRO tenant exists and OWNER membership/capabilities were read directly from the deployed runtime. The authoritative TAGRO enterprise ID is:

`ae9dea8e-6021-5833-9d59-7b0613357fbe`

Do not invent or substitute another enterprise ID.

---

## 6. RECOVERY SNAPSHOT

Before catalogue migrations/imports a recovery snapshot was created and verified available:

`echo-nonprod-pre-catalog-20260823-100906`

Do not recreate migrations or catalogue work merely because a new chat lacks memory.

---

## 7. POSTGRESQL CATALOGUE MIGRATIONS — ALREADY DONE

The schema migration Lambda is:

`echo-nonprod-schema-migrate`

The real migration run completed successfully with:

`{"confirm":"APPLY_NONPROD_V0_3"}`

Result:

`status=migration_complete`, starting at migration `0014-catalog-parts-lookup-v0.7`.

Applied:
- 0014 catalogue / parts lookup;
- 0015 GST completeness (`gst_rate` can be NULL; `gst_known` distinguishes unknown from zero);
- 0016 explicit unit conversions only; no inferred conversion.

Do **not** rerun migrations absent a concrete reason.

---

## 8. STIHL FOUNDATION — DEPLOYED AND READ-PROVEN

The Owner required product foundation first using real BUSY evidence and official STIHL part identity.

### Scout source
`C:\Users\HP\Dropbox\TAGRO_AUTOMATION\TAGRO_AWS_RUNTIME\reports\wo0014-stihl-scout\20260823-183131`

Foundation pack:
`...\foundation-import-pack`

Files:
- `00-summary.json`
- `01-canonical-records.json`
- `02-busy-evidence.csv`
- `03-blocked-unit-parts.csv`
- `04-alias-collisions-review.csv`

### Scout totals
- 15,074 accepted evidence rows
- 1,936 proven STIHL part identities
- 1,934 canonical products ready/admitted
- 2 blocked true unit-family conflicts
- 39,487 BUSY runtime aliases in pack
- 7 ambiguous BUSY-name alias keys omitted
- no price admission
- no tax fabrication
- no inferred unit conversion

Blocked unit conflicts:
- `36170001640` — EACH vs LINK
- `40080071000` — EACH vs PKT

Seven intentionally omitted ambiguous SDM `busy_original_name` aliases:
- `Carburetor C1Q-S119B - MS 211`
- `Crankcase C/S MS 462`
- `Deflector kit, FS Medium`
- `Handle molding MS 462`
- `Hose Clip Elbow BR 600`
- `Sleeve, Rubber insert FS 85/120/250`
- `Thrust plate FS 400`

### Real AWS import
Two batches were actually written through `echo-nonprod-observation-import`:

Batch 1:
- 1000 products inserted
- 21,665 aliases upserted
- no prices
- no conversions

Batch 2:
- 934 products inserted
- 19,756 aliases upserted
- no prices
- no conversions

Total:
- **1,934 canonical STIHL products inserted**
- **41,421 aliases upserted** (39,487 BUSY aliases + 1,934 official manufacturer-part aliases)

### Direct read proof
`/reference-data?kind=products&q=1201653...` returned the canonical product:

- SKU / manufacturer part: `00001201653`
- name/model: `Air filter, Wire mesh, MS 460`
- category: `Spare parts`
- unit: `Pcs`
- `gst_known=false`
- `gst_rate=null`

Important nuance: query `1201653` is also a substring of the canonical SKU. That read proves the product is live in PostgreSQL/searchable, but by itself does **not** isolate alias-only resolution. The successful import transaction proves aliases were written; use a non-SKU-like alias for a dedicated alias-resolution proof if needed.

### Freshness caveat
The full BUSY item master source used in the scout was dated **2026-07-10**, while movement evidence runs through **2026-08-15**. Exact part evidence is useful, but this older master is not sufficient to certify current BUSY write-back identity.

---

## 9. PRODUCT IDENTITY / BUSY IDENTITY — TWO DISTINCT LAYERS

This is critical and must not be collapsed.

### ECHO canonical identity
One official STIHL part -> one canonical ECHO product/SKU.

### BUSY branch identity
The same ECHO product can have different branch-local BUSY:
- item code/key;
- item name;
- alias/part field;
- spelling/case/spacing/punctuation/model suffix;
- unit label.

Preserve raw branch evidence. Normalisation is a later governed action, not an excuse to erase source identity.

### BUSY -> ECHO transaction import resolver order
1. branch + BUSY item code/key;
2. branch + BUSY alias/part number;
3. controlled name fallback only when safe.

### ECHO -> BUSY write-back
Use the stored branch-local BUSY key/code, not the normalized ECHO name. **Never write back based on similar names alone.**

### Structural mapping audit already run
Across the 1,934 foundation products:

- Mappings: `13244`
- Exactly one item code: `11445`
- Missing item code: `1772`
- Multiple item codes: `27`
- Missing BUSY alias: `0`
- Multiple BUSY aliases: `1480`
- Missing name: `13`
- Multiple names: `33`

This is why BUSY writeback has **not** been certified yet.

Target classification for the fresh comparison:
- `WRITEBACK_SAFE`
- `IMPORT_ONLY` / `IMPORT_SAFE_ONLY`
- `REVIEW`

Do not classify July-only evidence as current `WRITEBACK_SAFE` without fresh master/readback evidence.

---

## 10. BUSY NORMALISATION / HOUSEKEEPING INTENT

The Owner wants branches to stop drifting into different names in future because ECHO should hold the common canonical database.

Existing evidence folder:

`C:\Users\HP\Dropbox\TAGRO_AUTOMATION\busy_write_tests`

Earlier work in this folder proved useful safety mechanics:
- exact aliases;
- duplicate/collision refusal;
- active/moving item filters;
- source-value recheck before write;
- backup before mutation;
- transactional changes;
- exact one-row mutation requirement;
- post-write readback.

Historical branch normalization runs were recorded as fully verified for subsets (NDD, MDM, PKM, SKT). **Do not reuse the old KVR-as-master rule.** ECHO canonical product identity is now the authority; each branch BUSY record is a mapping/evidence layer.

Direct `.bds` write experiments are historical evidence about BUSY internals; they are **not** the preferred future production write path. Normal production integration should use supported BUSY mechanisms and confirm booking by BUSY result/readback.

---

## 11. CODEX IS ESSENTIAL PROJECT SOURCE MATERIAL — NOT AN ARCHIVE

Folder:

`C:\Users\HP\Dropbox\Codex`

The Owner explicitly clarified that Codex work was created as part of the TAGRO OS ecosystem before token cost made continued Codex work impractical. It contains inevitable/essential predecessor engineering for the envisaged ECHO OS. **Do not ignore it and do not rebuild its solved business logic from scratch.**

After the current portal deployment is completed, return deliberately to `/Codex` and perform a full recursive scout/mind-map/migration plan.

High-value material already identified there includes:
- BUSY copy-first/read-only extraction patterns;
- `Master1`, `Tran1`, `Tran2` field/relationship knowledge;
- branch/year checkpointed extraction/resume logic;
- source preservation/provenance patterns;
- sales voucher line extraction;
- purchase/supplier extraction and supplier normalization;
- stock movement/stock-count evidence;
- Quick Receive mobile service intake;
- mobile/quick-sale POS ideas;
- bank matcher / debit-credit reconciliation;
- GPay parsing and self-transfer distinction;
- daily management exception scanning;
- closing-cash reconciliation principles;
- service incentive evidence;
- historical GST/VAT warehouse segmentation;
- immutable source-register concepts;
- older handoffs and software registers.

Warnings discovered in Codex:
- some old generated BUSY schema datatype descriptions are unreliable; trust field relationships and empirically proven queries, not guessed datatype labels;
- some scripts contain embedded/stale credentials and machine-specific paths; never port secrets;
- old Cloudflare/D1/Dropbox/laptop runtime is not the ECHO target architecture;
- old direct BUSY `.bds` writers are evidence, not the production strategy;
- old simplistic cost/margin assumptions and zero fallbacks must not become financial truth;
- Farmertec catalogue is third-party reference only, never STIHL identity authority.

### Required post-portal Codex project
The Owner requested a **full scouted mind-mapped project report** covering Codex + TAGRO Automation, then:
1. map all reusable programs/data/business rules;
2. classify keep / rewrite / quarantine / retire;
3. map Python, SQL, Git, AWS and local dependencies;
4. install only required programs on AWS and this laptop;
5. reconcile all Python/SQL/Git/AWS rules and versions;
6. map data ingress to evidence/raw/admitted/curated operational destinations;
7. create **one governed runner or the smallest possible runner set** for portal/data shift into AWS;
8. verify readback, idempotency, provenance, security and rollback.

Do this **after the current portal path is deployed**, not instead of finishing it.

---

## 12. OTHER IMPORTANT DROPBOX SOURCES

### TAGRO Automation root
`C:\Users\HP\Dropbox\TAGRO_AUTOMATION`

Treat this as a project evidence ecosystem, not a single code repo.

Important areas:
- `projects\tagro-echo-os-git` — current Git worktree;
- `projects\tagro-data-import` — upstream item/data import work;
- `TAGRO_AWS_RUNTIME\reports` — deployment/scout/import/readback reports;
- `busy_write_tests` — BUSY normalisation/write/readback experiments;
- `td` and TD exports — business source feeds;
- `warehouse_builder` — historical warehouse precursor work;
- older TAGRO OS/service/mobile projects — skill/evidence sources, not copy-wholesale templates.

### STIHL scout report
`C:\Users\HP\Dropbox\TAGRO_AUTOMATION\TAGRO_AWS_RUNTIME\reports\wo0014-stihl-scout\20260823-183131`

### Portal deployment report destination built into runner
`C:\Users\HP\Dropbox\TAGRO_AUTOMATION\TAGRO_AWS_RUNTIME\reports\wo0014-portal-deploy\<timestamp>\deploy-result.json`

---

## 13. BUSINESS INTEGRITY / ROUTINE HOUSEKEEPING VISION

The Owner wants ECHO to continuously help run the business, not merely store transactions.

A future deterministic **Business Integrity** routine should cover:

### Master integrity
- current branch BUSY code/alias/name/unit/tax vs ECHO canonical master;
- detect branch naming drift;
- normalize only through governed mapping/readback.

### Sales price discipline
Inspect **actual invoice lines**, not only master prices:
- authorized selling price / permitted discount;
- actual sale rate;
- unusual discounts/below-floor price;
- GST correctness;
- manual override evidence.

### Purchase discipline
Check:
- supplier identity;
- invoice number/date;
- item identity;
- qty/unit;
- purchase rate;
- GST;
- duplicates;
- resulting stock movement.

### Stock movement integrity
Reconcile opening + inward + transfer + sale + authorized adjustment. Flag:
- negative/odd stock;
- document without movement;
- movement without document;
- unusual quantities;
- stale/dead stock;
- mismatched branches/items.

### Physical cycle count
Owner target: roughly **250 items/month**, enabling a broad quarterly stock verification.

Operational idea:
- around 10 items per count day, several days each week;
- mix random rotation + risk-based selection;
- risk factors include value, movement, odd/negative balance, prior discrepancy, recent purchase/sale anomaly and time since last count.

Count semantics remain:

`COUNT != STOCK MOVEMENT != STOCK POSITION`

A physical discrepancy is evidence. A separate authorized adjustment changes stock.

---

## 14. ATTENDANCE — STANDALONE PHONE PWA REQUIREMENT

An older attendance marker reportedly already exists somewhere under TAGRO Automation; it has **not yet been positively located**. Find/reuse it before creating a competing attendance implementation.

Desired ECHO attendance unit:
- standalone installable PWA / home-screen app;
- staff/device associated once;
- very simple states/actions: morning IN, STEP OUT, BACK/RETURN, evening OUT;
- server time is authoritative;
- location is requested/captured **only when an attendance/status tap occurs**;
- no continuous tracking and no background GPS;
- capture lat/lon/accuracy/device/event identity at tap;
- branch geofence determines inside/outside;
- routine inside-fence coordinates need not be sent to Owner;
- morning/evening marks outside fence become exceptions;
- personal STEP OUT being outside fence is expected and is not itself an exception;
- RETURN can confirm re-entry to the branch fence;
- location denied/unavailable/poor accuracy becomes an exception/review state;
- do not conflate STEP OUT/BACK with actual application authentication logout/login;
- staff should receive the normal OS permission disclosure once; subsequent event capture may be unobtrusive, but do not bypass device permission controls.

Potential route/surface later: `os.tagro.in/attendance` or equivalent ECHO-hosted path after the current portal is established.

---

## 15. UI/UX IS PART OF PRODUCT CORRECTNESS

Do not treat UI as a decorative pass after backend work.

Active authority:
- `contracts/core/PRODUCT_DESIGN_ENGINEERING_CONTRACT.md`
- `contracts/core/ECHO_UI_UX_DESIGN_RULES_V2.md`
- `contracts/core/ECHO_COMFORT_APPEAL_DESIGN_RULES_V1.md`

### Governing experience
> ECHO shows the right work, to the right person, at the right moment, with the least necessary interaction — while keeping identity, authority, evidence, state and consequence unmistakably truthful.

Operational shorthand:
> Hide system complexity without hiding business truth.

### ECHO Eight UI Gate
Every operational surface must be:
1. user-centered;
2. simple;
3. consistent;
4. adaptive;
5. feedback-rich;
6. truthful;
7. recoverable;
8. fast.

### Six UX budgets
- attention;
- reach;
- typing;
- time;
- trust;
- memory.

### Current visual character
`CALM · CLEAN · WARM · OPERATIONAL · PRECISE`

Avoid:
- 1990s/legacy ERP appearance;
- dense chrome;
- huge sidebars stealing work area;
- decorative dashboards;
- excessive cards/shadows;
- visual AI gimmicks;
- tiny controls;
- too much explanatory copy;
- search as a substitute for understandable job navigation.

### Mobile requirements
- phone is first-class, not shrunken desktop;
- touch targets normally about 44–48 CSS px for operational controls;
- editable mobile text generally >=16px;
- safe-area / gesture / system-bar aware;
- keyboard-open state must be tested;
- ordinary mid-range Android is a required representative device;
- interruption/resume and network loss are normal product states;
- local draft, queued, ECHO accepted, approval, BUSY/provider confirmed must never be visually conflated.

### Job-first navigation
Counter jobs include:
- SELL
- SERVICE
- ESTIMATE (only when a real backend contract exists)
- COUNT
- REQUEST PURCHASE
- CLOSING CASH

Do not expose a fake Estimate button until a real transactional estimate/quotation runtime is admitted.

### Branding
Current TAGRO dealership surfaces are **TAGRO STIHL**, using:
- `web/assets/brand/tagro-stihl-mobile.png`
- `web/assets/brand/tagro-stihl-desktop.png`

ECHO is the platform/runtime identity, not a dealership-brand replacement.

---

## 16. EXTERNAL UI/UX RESEARCH — REVISIT LINKS

These sources sharpened the design rules. They are evidence/reference, **not authority over ECHO truth/security/authority contracts**.

### Human-centred design
ISO 9241-210:2019 — Human-centred design for interactive systems  
https://www.iso.org/standard/77520.html

### Accessibility / target size / input/error support
WCAG 2.2  
https://www.w3.org/TR/wcag/

WCAG 2.2 — Understanding Target Size (Minimum)  
https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum

WCAG 2.2 Understanding index (including predictable navigation, error identification, labels, error prevention, redundant entry, accessible authentication)  
https://www.w3.org/WAI/WCAG22/Understanding/

### Android mobile safe-area / system UI
Android — System bars  
https://developer.android.com/design/ui/mobile/guides/foundations/system-bars

Android — Edge-to-edge design  
https://developer.android.com/design/ui/mobile/guides/layout-and-content/edge-to-edge

Android — Window insets  
https://developer.android.com/develop/ui/compose/system/insets

### Mobile UX/context research
Interaction Design Foundation — Mobile User Experience Design  
https://assets.interaction-design.org/literature/topics/mobile-ux-design

Interaction Design Foundation — Context of Use for Mobile  
https://assets.interaction-design.org/literature/article/the-context-of-mobile-usage-the-big-picture

Nielsen Norman Group — Mobile/Tablet research family and mobile imagery/performance guidance  
https://www.nngroup.com/videos/mobile-images/

NN/g touch-target material was also reviewed through its mobile/tablet research reports; when revisiting, prefer current NN/g Mobile & Tablet / Study Guide material rather than copying old pixel rules uncritically.

### Shipped-interface pattern research
Mobbin  
https://mobbin.com/

The Mobbin connector was paywalled/unusable in the latest session, so no claim should be made that it supplied new evidence in that pass.

UX Pilot was used earlier as a secondary mobile-design-trend reference; treat it as inspiration only, never authority.  
https://uxpilot.ai/

---

## 17. CURRENT USER-FACING WEB SURFACE IN REPO

The admitted release is explicitly whitelisted by `web/deploy-manifest.txt`. The release builder refuses unlisted files.

Current admitted 23 files include:
- `404.html`
- `index.html`
- `login.html`
- `runtime-config.js`
- `runtime-client.js`
- Home CSS/JS
- `operation.css`
- `billing.html`
- `service.html`
- `customers.html`
- `stock-count.html`
- `po.html`
- `closing-cash.html`
- `business.html` + business assets
- `on-call.html`
- manifest/icon/service worker
- TAGRO STIHL mobile/desktop brand assets.

Old prototype `web/app.js` was deleted and must not reappear in the release.

### Home
`web/index.html` is the current AWS-backed shell. Primary jobs:
- SELL
- SERVICE
- COUNT STOCK
- REQUEST PURCHASE
- CLOSING CASH
- BUSINESS

Bottom navigation currently:
- Home
- Business
- Attention

The visible Intelligence lane was deliberately removed from the current foundation shell.

Home was repaired to use the real authenticated `/db-health` path instead of depending on a broken technical/Planar-shaped status assumption.

---

## 18. PRIMARY OPERATIONAL PAGES — CURRENT STATUS

These are intended as **real AWS/PostgreSQL-backed forms**, not mockups.

### SELL / Billing
- real `/billing/issue` runtime;
- server-side SELL capability;
- unknown GST is not zero and blocks issue;
- no invented price;
- insufficient stock semantics remain governed;
- first-time customer creation was added;
- local draft recovery preserves working edits;
- payment evidence remains distinct from sale identity/reconciliation;
- BUSY booked state is not claimed without BUSY confirmation/readback.

### SERVICE
- real `/service/intake` runtime;
- SERVICE capability;
- quick intake designed around customer -> machine -> complaint -> accept;
- first-time customer creation added in-place;
- secondary detail is progressively disclosed.

### CUSTOMERS
- `src/aws_runtime/customer_runtime.py` added;
- authenticated `POST /customers` route added;
- allowed for relevant SELL/SERVICE staff;
- canonical PostgreSQL customer, not browser-only fiction.

### STOCK COUNT
- real `/stock-count/record` runtime;
- physical count is observation, not stock mutation;
- branch locks to active session after first observation;
- unfinished count survives interruption;
- recounts remain separate observations;
- new session/branch transition is explicit.

### PURCHASE
- real `POST /purchase-orders` runtime;
- request/draft is not supplier order;
- owner approval remains separate;
- unfinished supplier/item/qty work now survives interruption.

### CLOSING CASH
- real `/cash-days` read/open/entry/submit/save runtime;
- existing branch/day is loaded/resumed rather than falsely recreated;
- UI uses local business date rather than UTC default;
- explicit zero is required for opening cash/declared closing rather than silently defaulting missing evidence to zero;
- unfinished work is recoverable;
- state distinction between evidence entered and day submitted/closed must remain clear.

### ESTIMATE / QUOTATION
Data-model traces exist, but there is **no deployed complete transactional estimate endpoint yet**. Do not ship a fake operational estimate button merely because UX rules mention ESTIMATE as a target job.

---

## 19. CI / REGRESSION / RELEASE GATES

Runtime Gate now performs:
- all Python business/runtime tests;
- admitted web JavaScript syntax check through Node;
- PowerShell deployment-runner syntax check;
- `cfn-lint` on runtime, web and data-foundation templates;
- exact admitted web release build;
- upload of `echo-nonprod-web-release` artifact.

Recent fully green exact head before the later `.gitignore` housekeeping commit:
- Governance Gate #704 SUCCESS
- Runtime Gate #685 SUCCESS
- head `051c1ee8fadc230aa1051cef9a61b28af73d7466`

The `.gitignore` commit adding `build/` was `6feace40...`; it is source-hygiene only but local pull failed due `.git/objects` permission before it could land on the laptop.

The runner has regression coverage for:
- exact NonProd account/profile/confirmation;
- native stderr not being mistaken for failure in Windows PowerShell 5.1;
- UTF-8 without BOM for AWS CLI JSON files;
- refusal of runtime resource removal/replacement;
- no live DNS mutation;
- stable `os.tagro.in` + temporary CloudFront CORS origins;
- private TLS-only CloudFront/S3 web origin;
- `/customers` JWT-protection smoke;
- Dropbox deployment report.

---

## 20. CURRENT AWS FRONTEND / DATA FOUNDATION — PARTLY DEPLOYED

The latest portal runner is:

`scripts/DEPLOY_ECHO_NONPROD_PORTAL.ps1`

It is intended to be the single governed NonProd portal deployment runner.

### Existing live domains BEFORE ECHO cutover
- `os.tagro.in` -> existing Cloudflare Worker / old TAGRO OS surface;
- `service.tagro.in` -> GitHub Pages, CNAME `koffykraft.github.io`.

Do not overwrite either until the AWS smoke portal is tested and approved.

### First portal run achieved these real AWS writes
The runner passed preflight/account/template validation and progressed through:

1. `CREATE/UPDATE DATA FOUNDATION` — succeeded enough for execution to continue;
2. `CREATE/UPDATE WEB HOSTING` — succeeded enough for execution to continue;
3. produced smoke CloudFront URL:
   `https://dx93er03db8nr.cloudfront.net`
4. CodeBuild packaged the exact runtime head and reported `SUCCEEDED`;
5. packaged runtime template was downloaded from the artifact bucket.

Therefore the following stacks should now exist and must be **read back, not blindly recreated**:
- `echo-nonprod-data-foundation`
- `echo-nonprod-web`

Expected data-foundation resources from IaC:
- evidence S3 bucket: `echo-nonprod-evidence-272037674623-ap-south-1`
- warehouse S3 bucket: `echo-nonprod-warehouse-272037674623-ap-south-1`
- EventBridge bus: `echo-nonprod-business-events`
- ingestion SQS + DLQ
- Glue raw/admitted/curated databases
- Athena workgroup `echo-nonprod`.

Expected web foundation:
- private versioned S3 origin;
- Block Public Access;
- TLS-only bucket policy;
- CloudFront Origin Access Control;
- CloudFront security headers;
- CloudFront default certificate for smoke URL;
- no TAGRO DNS mutation.

### What did NOT happen yet
The first real portal run failed **before a runtime change set was successfully created/executed** and **before the web release was published**.

So at this handoff:
- data foundation: likely created — verify read-only;
- web hosting stack: likely created — verify read-only;
- CloudFront smoke domain exists;
- new customer-enabled runtime has **not yet been proven deployed from this latest lane**;
- web release has **not yet been published by the runner**;
- no live DNS cutover occurred.

---

## 21. TWO RUNNER DEFECTS FOUND AND REPAIRED

### Defect 1 — native stderr / PowerShell 5.1
Git normal progress on stderr caused `$ErrorActionPreference='Stop'` to throw `NativeCommandError` even when Git returned exit code 0.

Repair:
`Invoke-Checked` temporarily uses non-terminating stderr handling for the native process, restores PowerShell `Stop`, then decides success/failure by `$LASTEXITCODE`.

Regression test added.

### Defect 2 — UTF-8 BOM in runtime parameters
The second portal attempt reached runtime change-set creation, but AWS CLI failed parsing `runtime-params.json` because Windows PowerShell 5.1 `Set-Content -Encoding UTF8` wrote a BOM. AWS showed leading `∩╗┐[`.

Repair:
runner now uses:

`[System.Text.UTF8Encoding]::new($false)`

and `System.IO.File.WriteAllText` for runtime parameters/report JSON.

Regression test added.

This repair exists remotely. It was **not pulled to the laptop** because the later Git object permission error blocked the pull.

---

## 22. CURRENT BLOCKER — LOCAL GIT OBJECT PERMISSION

Latest laptop attempt failed before rerunning portal deployment:

`error: unable to write file .git/objects/6f/eace40b7c48702b60449137fcce3e2e1f242ef: Permission denied`

This is now the **first blocker**, not an AWS architecture problem.

### Next-chat procedure
1. Do not rebuild or re-clone immediately.
2. Inspect `.git\objects` ACL/attributes and whether Dropbox/another process holds a lock.
3. Repair the smallest local filesystem problem.
4. Confirm clean worktree.
5. fetch/pull `wo-0014-database-primary-pages-deploy` to the latest remote head containing this handoff and BOM/native-command fixes.
6. confirm both gates on that latest head or rerun/inspect them if the handoff/README-only commits triggered new runs.
7. read-only check current CloudFormation stack states for `echo-nonprod-data-foundation`, `echo-nonprod-web`, `echo-nonprod-runtime`.
8. rerun `scripts/DEPLOY_ECHO_NONPROD_PORTAL.ps1 -Confirm DEPLOY_ECHO_NONPROD_PORTAL`.

Because data/web stack deployment is idempotent with `--no-fail-on-empty-changeset`, a successful rerun should converge them, not create a parallel architecture.

---

## 23. RUNTIME CHANGE-SET SAFETY RULE

The runner packages exact Git HEAD in CodeBuild, creates a runtime CloudFormation change set, inspects it and refuses execution if any resource has:
- `Action=Remove`;
- `Replacement=True`;
- `Replacement=Conditional`.

This guard must remain.

Runtime CORS must preserve both:
- stable existing origin `https://os.tagro.in`;
- temporary CloudFront smoke origin.

Do not “fix” CORS by removing the stable origin during smoke deployment.

---

## 24. WEB RELEASE SAFETY RULE

Only `web/deploy-manifest.txt` assets may publish.

The web bucket is not the SAM artifact bucket. Do not reuse `echo-nonprod-artifacts-272037674623` for website hosting.

The web stack is deliberately separate/private behind CloudFront.

No Cloudflare/GitHub Pages/live-domain cutover until:
- release is published to CloudFront;
- public static pages return correctly;
- login works;
- authenticated runtime/CORS works;
- real representative workflows are exercised on phone + desktop;
- Owner inspects ease of use/visual quality/purpose fit.

---

## 25. DESIGN/USABILITY VERIFICATION BEFORE LIVE CUTOVER

The Owner explicitly wants the forms/pages built and inspected **before actual live deployment** so usability and quality can be judged.

Before `os.tagro.in` cutover, test at minimum:
- Home comprehension;
- login/session;
- SELL with existing customer;
- SELL with first-time customer;
- unknown GST block;
- SERVICE quick intake existing/new customer;
- stock count + recount + session branch lock;
- purchase draft interruption/recovery;
- Closing Cash open existing day, explicit zero, save/submit states;
- offline/pending/resume behaviour where admitted;
- 390×844-class phone viewport;
- ordinary mid-range Android;
- portrait with keyboard open;
- desktop/laptop;
- 404/closeable overlays/no inaccessible popups;
- touch target spacing and safe-area/gesture regions;
- no dead buttons or hidden uncloseable large panels.

The Owner has previously rejected UI that looked “1990s” and inaccessible large-screen/pop-up behaviour. Visual quality is a deployment criterion, not optional polish.

---

## 26. CURRENT LIVE-HOSTING OWNERSHIP

Read-only DNS/HTTP inspection established:

### `os.tagro.in`
- currently behind Cloudflare;
- existing TAGRO OS surface;
- HTTP 200;
- not yet cut over to ECHO AWS.

### `service.tagro.in`
- CNAME -> `koffykraft.github.io`;
- GitHub Pages;
- HTTP 200;
- not yet moved.

Do not assume either domain is AWS-hosted just because ECHO AWS frontend now exists.

---

## 27. CODEBUILD / BUILD PATH

Runtime build project:
`echo-nonprod-runtime-build`

Buildspec:
`ci/buildspec-nonprod-runtime.yml`

It:
- installs runtime deps + SAM CLI;
- runs tests;
- validates/builds SAM;
- packages to `echo-nonprod-artifacts-272037674623` under `echo-nonprod/runtime`;
- publishes `packaged-nonprod-runtime.yaml`.

Web buildspec:
`ci/buildspec-nonprod-web.yml`

It builds the admitted release, S3 syncs it to the web bucket, and invalidates CloudFront once web bucket/distribution outputs exist.

The single PowerShell portal runner currently orchestrates the combined path from the laptop.

---

## 28. SECURITY / TRUTH INVARIANTS

Do not relax:
- tenant/enterprise scope is server-side;
- consequential commands are idempotent;
- unknown is not zero;
- count != movement != position;
- sale != payment confirmation;
- queued BUSY handoff != BUSY booked;
- imported observation != canonical truth merely by presence;
- AI suggestion != consequential business truth;
- provenance/source/history must remain visible;
- corrections/supersessions preserve history;
- RDS remains private;
- private S3 buckets remain private;
- do not expose passwords, JWTs, DB credentials or old embedded credentials in repo/reports/chat.

Old Codex/TAGRO scripts containing hard-coded credentials must be treated as compromised legacy evidence and sanitized/retired if ever reused.

---

## 29. WHAT NOT TO DO IN THE NEW CHAT

Do **not**:
- start another architecture discussion;
- recreate Cognito/API/RDS because a new chat does not remember them;
- recreate the STIHL import;
- rerun migrations without evidence;
- import the full STIHL catalogue beyond the vetted foundation merely for completeness;
- fabricate HSN/GST/prices;
- call unknown GST zero;
- call a queued BUSY request booked;
- direct-write BUSY based on normalized names;
- normalize away raw branch evidence;
- replace the existing ECHO architecture with old TAGRO/Cloudflare/D1 architecture;
- resurrect `web/app.js`;
- publish all files under `web/` indiscriminately;
- expose Intelligence/Planar as a foundation navigation priority;
- copy Codex shells wholesale;
- ignore Codex and independently rebuild its solved business logic;
- cut over `os.tagro.in` or `service.tagro.in` before smoke approval;
- delete/reclone the local repo before diagnosing the current Git object permission problem;
- produce large multi-command sequences when the Owner is executing commands interactively.

---

## 30. IMMEDIATE NEXT PATH — EXACT ORDER

### Phase A — repair and finish current portal deployment
1. Repair local `.git/objects` write permission/lock.
2. Fast-forward laptop repo to remote branch HEAD containing this handoff.
3. Confirm worktree clean.
4. Confirm latest Governance + Runtime gates green (or inspect exact failure only).
5. Read-only inspect existing `echo-nonprod-data-foundation` and `echo-nonprod-web` stack statuses/outputs.
6. Rerun `DEPLOY_ECHO_NONPROD_PORTAL.ps1` with exact confirmation.
7. Inspect runtime change set; runner must refuse removals/replacements.
8. Complete runtime update.
9. Publish admitted web bundle.
10. Smoke readback CloudFront + API + CORS + protected `/customers`.
11. Confirm Dropbox deploy report.
12. Open CloudFront URL on phone/desktop and perform real usability inspection.
13. Repair UX defects before live domain cutover.

### Phase B — business execution proof
1. exercise SELL, SERVICE, CUSTOMER, STOCK COUNT, PURCHASE, CLOSING CASH against PostgreSQL;
2. ensure real persisted writes/readbacks;
3. do not use unknown-tax STIHL records for billing until trusted tax enrichment exists;
4. find a tax-complete product for billing proof or admit trusted GST enrichment;
5. start fresh BUSY branch master comparison and identity classification;
6. prove BUSY sales import resolution before BUSY writeback certification.

### Phase C — Codex/Automation portal shift project
After current portal is deployed/proven:
1. recursive scout `/Codex` + relevant `TAGRO_AUTOMATION`;
2. mind-map every program/source/dependency/data flow;
3. classify retained business logic vs obsolete infrastructure;
4. install only required AWS/laptop tools;
5. normalize Python/SQL/Git/AWS runtime rules;
6. design raw -> admitted -> curated/evidence -> PostgreSQL/warehouse flow;
7. build one governed migration/housekeeping runner or minimum runner set;
8. move useful extraction/audit/reconciliation capability into AWS-scalable ECHO architecture;
9. add routine business-integrity scheduling/exception surfaces.

---

## 31. SHORT PROMPT FOR STARTING THE NEXT CHAT

Use this exact instruction or equivalent:

> Continue TAGRO ECHO OS from GitHub repo `koffykraft/tagro-echo-os`, branch `wo-0014-database-primary-pages-deploy`. Read `HANDOFF_CURRENT.md` completely before acting, then follow its mandatory reference sequence. Do not rebuild or reopen architecture. Current first blocker is the laptop `.git/objects` permission failure; repair that narrowly, fast-forward to current branch HEAD, verify existing AWS data/web stacks, and resume the single governed NonProd portal runner. Foundation operations remain ahead of Planar/intelligence. Commands one at a time.

---

## 32. FINAL CONTINUITY STATEMENT

The project is **not** at concept stage. ECHO NonProd already has real AWS runtime, authentication, PostgreSQL, tenant context, migrations and a 1,934-product STIHL foundation. The current work is converting that proven backend into a usable AWS-hosted business portal and then absorbing the accumulated TAGRO/Codex operational ecosystem into the scalable ECHO SaaS architecture.

The next builder's job is **continuation and proof**, not reinvention.
