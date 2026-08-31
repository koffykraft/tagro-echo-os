# TAGRO ECHO Design System — Closing Cash

Status: page override under `design-system/MASTER.md`.

## Job

Answer, with the least necessary interaction: what came into/out of the physical cash plane today, what physical cash remains, and does it reconcile?

This page preserves raw cash-plane evidence. It does not silently convert every value in the historical EXPENSES column into a P&L expense.

## Canonical geometry

### Desktop

Use a two-plane working layout:

1. Primary day sheet — Excel-like four-column grid: SALE | BILL | EXPENSES | PARTICULARS.
2. Reconciliation plane — Cash Count above Closing.

The day sheet is dominant. SALE and EXPENSES remain narrow numeric columns; BILL remains a narrow reference column; PARTICULARS is moderately wider but never consumes arbitrary residual browser width. The reconciliation plane is compact and continuously visible when viewport height allows.

Target at 1366×768: ordinary entry plus reconciliation should be visible without a large empty region or page-level horizontal scrolling.

### Phone

Order is:

1. compact top bar/context;
2. ENTRIES;
3. CASH COUNT;
4. CLOSING.

The four-column evidence sheet remains recognizably a sheet. Do not transform it into unrelated generic cards. At 390 px, use fixed purposeful column proportions with a tightly bounded horizontal sheet scroller only when needed for the evidence grid itself; the page and the reconciliation sections must remain vertical and must not side-scroll. Keep the active cell visible when the keyboard opens.

## Evidence colors

- SALE cells: quiet pale green.
- EXPENSES/cash-movement cells: quiet pale yellow.
- Calculated/read-only cells: neutral grey.

Headers and labels always state the meaning; color is supplementary.

## Context

The top bar shows compact Date · Branch · Actor context. Full context belongs in the drawer. The drawer preserves these canonical IDs and meanings:

- `businessDate`
- `branch`
- `enteredBy`
- `onBehalfOf`
- `switchReason`
- `openingCash`

A consequential context change may require a reason and must retain the actual principal separately from acting context.

## Entry path

Keyboard behavior is contractual:

- SALE → BILL → next SALE.
- EXPENSES → PARTICULARS → next EXPENSES.
- denomination Qty → next denomination Qty.
- Tab remains conventional desktop navigation.

Navigation derives from the focused column/control, never from a hidden mode toggle.

## Reconciliation hierarchy

Display in this order:

Yesterday Closing
Today Sale
TOTAL
Expenses / cash movements
Balance Due
Cash in Hand
Difference

Difference is visually strong but not alarmist when zero. A non-zero difference must be readable in text/numbers, not color alone.

Formula chain:

`TOTAL = Yesterday Closing + Today Sale`

`Balance Due = TOTAL - physical cash out / cash movements represented by the sheet`

`Difference = Cash in Hand - Balance Due`

Any richer cash/non-cash classification remains governed by the Closing Cash engine and must not be inferred by the presentation layer.

## State and actions

Top bar priority:

1. page identity and compact context;
2. truthful state pill;
3. Review as dominant next action;
4. Undo/Correct as secondary actions when available.

Use SVG/text controls, not emoji icons.

The ordinary flow is:

`Edit day sheet → Count cash → inspect Difference → Review → Edit or Confirm Save`

Review must faithfully show the exact pending day sheet, physical count, formula chain, difference, and context. Confirmation is consequential and remains explicit.

## Review plane

Review is a full working state. On desktop it may present an A4-like document centered in a quiet overlay. On phone the document preview may scale/scroll internally, but Edit and Confirm Save remain safely reachable. Print/PDF and Share are secondary to confirmation.

## Motion

No ornamental motion. Drawer and overlay transitions, if used, should be brief and disabled/reduced under `prefers-reduced-motion`.

## Acceptance checklist

- 1366×768: sheet + reconciliation purposeful and compact.
- 390×844: page vertical; no routine page side-scroll.
- Editable phone fields 16 px minimum.
- Frequent phone controls 44–48 px.
- Visible focus state for every editable cell/control.
- SALE/BILL Return path verified.
- EXPENSES/PARTICULARS Return path verified.
- denomination Return path verified.
- Review exactly represents the pending state.
- state/correction/sync meaning is textual as well as visual.
- opening/date/branch/actor logic is unchanged by styling.
