# TAGRO ECHO OS — Stock Planes / Prismatic Count Doctrine

Status: design doctrine for the immediate deployment route and post-deploy stock intelligence.
Date: 2026-08-21
Branch: wo-0012-nonprod-shared-runtime

## 1. Governing correction

BUSY stock balances are not reliable enough to establish ECHO opening stock truth.

Existing physical stock-count lists and future real-time counts are stronger direct observations, but they remain fallible: items can be missed, misnamed, duplicated, misplaced, counted against the wrong part number, or counted at the wrong location.

Therefore ECHO must not collapse `stock count`, `stock movement`, `BUSY stock`, and `canonical stock position` into one event/state.

## 2. Separate planes

### Plane A — Count Observation Plane

Every count entered on a phone/device is an immutable observation event:

- count/session ID
- enterprise / branch / physical location
- observed item identity as entered
- candidate canonical part/product identity when available
- quantity observed
- counter/user/device
- observed time and admitted time separately
- evidence references (photo, shelf note, barcode, list source, etc.)
- confidence / identity confidence / location confidence
- source type (`live_count`, `historical_count_list`, etc.)

A count event does not itself mutate stock movement history.

### Plane B — Provisional Stock Plane

The latest defensible count for a branch/item/location may establish `temporary_truth` for operational use.

States include at minimum:

- `temporary_truth`
- `corroborated`
- `contested`
- `identity_uncertain`
- `location_uncertain`
- `superseded_by_recount`
- `admitted_baseline`

This plane is allowed to guide normal operations while clearly remaining provisional. Missing count evidence is UNKNOWN, never zero merely because BUSY reports zero or PostgreSQL has no movement row.

### Plane C — Canonical Movement Plane

Purchases, sales, accepted transfers, returns, governed adjustments and other admitted stock movements remain separate events. Canonical stock position is projected from these admitted movements.

A provisional count must not silently rewrite this plane.

### Plane D — Universal Part-History Plane

A separate universal engine reconstructs the lifetime evidence history of a part/product identity across TAGRO branches from the earliest available history.

Evidence may include:

- purchases
- sales
- branch transfers
- returns
- service part use
- historical stock lists
- live count observations
- adjustments
- aliases / renamed or miscoded items
- candidate movements where source evidence is incomplete

Errors are preserved as evidence rather than deleted. The engine may propose relationships/chords between apparently similar or equivalent items, but must not overwrite raw observations merely to create a neat history.

## 3. Prism behaviour

The stock Prism disperses each observation into separable rays before attempting judgement:

- identity / part-number confidence
- branch/location confidence
- quantity confidence
- time confidence
- movement plausibility
- cross-branch similarity
- source reliability
- reconciliation consequence

When two item identities, locations, or histories are too close to separate reliably, the Prism steps outward to a broader unresolved state rather than forcing precision.

New evidence may later split that broader ray more accurately.

## 4. VIBGYOR presentation semantics

Colour is a presentation of evidence state, not the underlying truth itself. Candidate semantics:

- Violet — raw observation / newly counted
- Indigo — identity or location uncertain
- Blue — historical relationship/chord found
- Green — corroborated / reconciled sufficiently for normal operational reliance
- Yellow — material variance or unresolved comparison
- Orange — strong anomaly / likely alias, misplacement, missed transfer, or count conflict requiring review
- Red — contradiction or material risk that should block consequential stock action until reviewed

Colours must always be accompanied by machine-readable state and confidence; colour alone is not authority.

## 5. Count-by-count route after deployment

For every real-time count:

`Count observation -> provisional stock plane -> universal part-history sweep -> Prism comparison -> chord proposals -> reconciliation state -> optional governed baseline/adjustment admission`

The count remains an independent event even after it is reconciled.

## 6. Historical reconstruction

For each part number / product identity, the universal engine should be able to produce a branch-by-branch timeline from the earliest available TAGRO history.

The purpose is not to fabricate a perfect ledger retrospectively. It is to expose:

- known movements
- likely related movements
- gaps
- aliases / naming drift
- branch-to-branch patterns
- items that appear to leave one branch and appear in another
- count discontinuities
- persistent unexplained stock
- historical confidence bands

This timeline is a separate analytical/event dimension and must not be confused with the current canonical stock movement plane.

## 7. Deployment consequence

The previous convoy assumption `BUSY opening stock -> canonical stock baseline` is rejected.

Before daily-production billing, ECHO needs a safe operational stock policy:

1. import / capture the most recent defensible physical count evidence by branch;
2. place it in the provisional stock plane, not canonical movement truth;
3. allow billing/stock checks to distinguish `provisional available`, `canonical available`, `unknown`, and `contested` stock;
4. never convert missing movement history to zero merely because the canonical movement plane is not yet reconstructed;
5. progressively reconcile provisional counts with the universal historical engine;
6. only admit baseline/adjustment movements through a separate governed action when evidence/authority supports doing so.

## 8. Priority split

### Main-road / pre-production

- count-observation schema and runtime
- provisional stock projection
- billing stock-check semantics that understand provisional/unknown/contested states
- branch-scoped count evidence import from existing stock-count lists
- no BUSY stock value treated as opening truth

### Side-lane / may continue after first deployment

- full lifetime universal part-history reconstruction
- alias/name-drift inference
- cross-branch candidate movement chords
- advanced VIBGYOR historical tables and visualizations
- automatic anomaly narratives

The side-lane work must not rewrite raw evidence or block normal count capture while it is still learning.

## 9. Structural invariant

`COUNT != MOVEMENT != STOCK POSITION != HISTORICAL INFERENCE`

They may be connected by evidence-backed chords, but remain separate events/planes.
