# TAGRO ECHO Design System — MASTER

Status: working design authority for UI/UX implementation. It does not supersede business, data, governance, evidence, authority, idempotency, recovery, or purpose-specific form contracts.

## Authority order

1. TAGRO ECHO business/data/governance contracts and admitted event semantics.
2. Purpose-specific form contracts and task geometry.
3. This TAGRO ECHO design system.
4. UI/UX Pro Max recommendations and searchable guidance.

When a recommendation conflicts with business truth or a purpose-specific workflow, the recommendation is rejected.

## Product character

CALM · CLEAN · WARM · OPERATIONAL · PRECISE

ECHO is an operating environment, not a marketing site. Design optimizes for fast recognition, low error, interruption/recovery, touch use, keyboard use, truthful status and repeated daily work.

## Visual family

- Soft-neutral operational surfaces.
- White working sheets on a warm-neutral application background.
- Thin, legible boundaries instead of decorative shadows.
- Orange is reserved for the dominant next action and small emphasis, never as ambient decoration.
- Green and yellow evidence columns may retain their familiar Closing Cash meanings, but meaning must also be carried by labels/text and never by color alone.
- No glassmorphism, neon, AI gradients, ornamental dashboard chrome, excessive card nesting, emoji-as-interface-icons, or animation for decoration.

## Core tokens

```css
--echo-ink: #181818;
--echo-muted: #62625f;
--echo-line: #c9c7c0;
--echo-line-strong: #77746d;
--echo-paper: #ffffff;
--echo-surface: #f6f5f1;
--echo-surface-raised: #fbfaf7;
--echo-sale: #d7f4d7;
--echo-expense: #fff49a;
--echo-calc: #e9e8e3;
--echo-accent: #e95d21;
--echo-accent-strong: #c94a17;
--echo-ok: #247a45;
--echo-danger: #b52b23;
--echo-focus: #1769d2;
--echo-radius-sm: 6px;
--echo-radius-md: 10px;
--echo-shadow-overlay: 0 16px 48px rgba(0,0,0,.18);
```

Use the system UI font stack. Do not introduce a network font dependency for operational forms.

## Density and spacing

- Desktop forms should be compact enough for repeated entry without feeling cramped.
- Default spacing scale: 4, 6, 8, 12, 16, 24 px.
- Repeated spreadsheet cells may be 36–40 px high on desktop.
- Frequent touch controls and consequential controls target 44–48 px minimum on phone.
- Editable phone text is at least 16 px to avoid disruptive iOS focus zoom.
- Avoid large empty hero regions, oversized headings, and residual full-browser columns.

## Typography

- Page title: 18–20 px, 750–800 weight.
- Section label: 11–12 px, 800 weight, modest letter spacing where useful.
- Body/input: 13–14 px desktop; 16 px editable controls on phone.
- Supporting/status text: 11–12 px; never below 10 px for operationally necessary content.
- Numeric totals use tabular numbers where supported.

## Interaction hierarchy

Each working state has one dominant next action. Primary buttons use the accent color. Secondary actions remain quiet. Dangerous/corrective actions must not visually compete with the ordinary route.

Statuses must use plain operational language such as Draft, Saved here, Waiting to send, ECHO accepted, Awaiting approval, Needs attention, Completed. Provider/network state must not masquerade as a business consequence.

## Inputs and focus

- Every input has a visible label or table header association.
- Focus is unmistakable: 2 px focus ring with sufficient contrast; do not remove outlines without replacement.
- `:focus-visible` is preferred for buttons/links; focused data-entry cells may show an inset focus ring.
- Use correct `inputmode`, `autocomplete`, and native semantics.
- Enter/Return behavior follows each form’s contract; Tab remains conventional on desktop.
- Disabled and read-only states must be distinguishable without relying on opacity alone.

## Icons

Use a small, consistent SVG icon set or text labels. No emoji icons in operational chrome. Every icon-only control has an accessible name and at least a 44 px touch target on phone.

## Responsive planes

Responsive design is not desktop shrinking.

### Phone — 390×844 class
- Work dominates.
- Primarily vertical movement.
- No routine horizontal page scroll.
- Context is compact and one effortless reveal away.
- Side evidence moves immediately below the primary work when the task contract specifies it.
- Keyboard-open state must leave the active field and next action usable.

### Tablet
- Work remains dominant with adjacent context where it genuinely helps.

### Desktop — 1366×768 class
- Work plus relevant evidence/context may coexist.
- Avoid gratuitous full-width stretching.
- Common task should fit with useful density and without accidental horizontal page scroll.

## Overlays and drawers

- Drawers and review overlays trap neither focus nor the user.
- Escape/backdrop/explicit close behavior must be predictable where safe.
- Review is a distinct state, not a cosmetic modal.
- Respect `prefers-reduced-motion`; motion is brief and functional only.

## Accessibility / Pro Max admission checks

Before a page is admitted:
- text contrast normally meets WCAG AA (4.5:1 for normal text);
- focus states are visible;
- controls have correct semantics and accessible names;
- status meaning does not rely on color alone;
- text reflows without clipping at narrow widths/zoom/text scaling;
- reduced-motion preference is respected;
- 375/390, 768, 1024 and 1366/1440 classes are inspected;
- touch targets are safe for frequent mobile use;
- ordinary task can be completed without pointer-only interaction.

## Truth and recovery

Visual simplification must never hide local-vs-shared state, pending sync, correction/supersession, actor identity, evidence provenance, or consequential review/confirmation. Local drafts and interrupted work should recover to the real job/context where the underlying contract allows it.

## Page overrides

Page-specific rules live under `design-system/pages/`. A page override may specialize geometry and hierarchy but may not weaken the authority order or the accessibility/truth requirements above.
