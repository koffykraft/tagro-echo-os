# TAGRO × ECHO OS — Mobile Foundations Review

Date: 2026-08-22
Status: design-study evidence; no production-admission claim
Branch: `wo-0012-nonprod-shared-runtime`

## Sources reviewed

1. User-supplied PDF: **Mobile-Friendly UI/UX Design Tips and Tricks** (Yashika Yarshney / Medium, 2024).
2. Android Developers: **Android system bars**, current documentation reviewed 2026-08-22; page updated 2026-08-03.
3. Android Developers: **Edge-to-edge design**, current documentation reviewed 2026-08-22; page updated 2026-08-03.

The PDF is a useful general mobile checklist. The Android documentation adds an important system-level layer: mobile UX must account for status bars, navigation modes, gesture zones, cutouts, keyboard transitions, safe insets and adaptive screen geometry. This is not merely platform decoration; it changes where ECHO may safely place consequential controls.

## 1. What the PDF contributes to ECHO

The strongest applicable principles are:

- simple, clean layouts;
- touch-sized controls rather than desktop-sized click targets;
- fast-loading pages for limited/variable connectivity;
- responsive behaviour across screen sizes;
- simple navigation;
- strongest priority for key content/actions;
- mobile-first composition rather than desktop shrink-down;
- forms with suitable input types and autofill where appropriate;
- minimum typing through lookup, choices and remembered context;
- testing on actual mobile devices and iterating from observed use.

For ECHO, these are not aesthetic preferences. They support the Product Design Engineering Contract: counter work must be quick, low-cognitive-load, interruption-safe and usable under imperfect connectivity.

## 2. What the Android system-bars guidance adds

Android treats the status bar, navigation bar, gesture-navigation areas, keyboard and display cutouts as part of the usable-layout problem.

The key design rule for ECHO is:

> **Backgrounds may extend edge-to-edge; critical content and interactive controls must remain inside a safe interaction zone.**

Android recommends edge-to-edge presentation, transparent/translucent system bars where appropriate, correct inset handling, and avoiding touch/drag targets beneath gesture-navigation insets.

This matters particularly to ECHO because many core actions are consequential and are currently designed as sticky or bottom-positioned actions: Issue, Accept, Record Count, Save Draft, Review, Confirm, Close Day and similar controls.

## 3. PWA/web translation

The current ECHO client is a browser/PWA surface, not a native Jetpack Compose application. Therefore Android's `WindowInsets` API is not directly the implementation mechanism for the present client.

The equivalent web/PWA design responsibilities are:

- retain `viewport-fit=cover` when using edge-to-edge layouts;
- use `env(safe-area-inset-top)` for top app-bar/content protection;
- use `env(safe-area-inset-bottom)` for bottom action bars and navigation protection;
- account for left/right safe-area insets, especially landscape and cutout devices;
- avoid primary/destructive touch targets at the extreme left/right edges where Android back gestures originate;
- ensure sticky/fixed controls remain visible and tappable when the on-screen keyboard appears;
- use purpose-appropriate `inputmode`, keyboard type, autocomplete and focus order;
- test installed-PWA and ordinary-browser behaviour separately where they differ;
- preserve visible ECHO state when viewport height changes because of keyboard/system UI.

A future native Android wrapper/application should translate the same doctrine to proper `WindowInsets`, edge-to-edge and keyboard-animation APIs rather than invent a second UX model.

## 4. Immediate audit finding in the current ECHO web shell

The existing shared `styles.css` already contains a partial safe-area idea: on small screens the header top padding uses `env(safe-area-inset-top)`.

However, this is incomplete as an OS-wide doctrine:

- bottom safe-area handling is not a common primitive;
- sticky bottom actions are page-specific;
- left/right cutout/landscape protection is not established as a shared rule;
- gesture-edge conflicts are not explicitly tested;
- keyboard-open behaviour is not an acceptance gate across forms;
- system-bar/background contrast is not treated consistently across surfaces.

Example: Billing currently has a sticky bottom action region but its local styling does not establish a shared bottom-safe-area contract. This may be visually acceptable on one phone yet become uncomfortable or obstructed on another navigation mode/device.

Do **not** patch individual pages independently. Solve this in the admitted ECHO shell/mobile primitives so every purpose-specific workflow inherits the same safe viewport behaviour.

## 5. ECHO Mobile Safe-Viewport Doctrine

The ECHO shell SHALL adopt the following rules before field admission.

### 5.1 Edge-to-edge is visual, not interactive

Background surfaces, dividers, imagery and non-consequential scrolling content may extend behind system-bar regions where suitable.

Text, form controls, primary actions, destructive actions and draggable elements must remain clear of system bars, display cutouts and gesture-priority regions.

### 5.2 Top app bar

The top region must account for the status-bar/cutout safe inset while keeping the visual surface continuous to the physical top edge.

The header must remain compact. System-bar awareness must not create another oversized toolbar.

### 5.3 Bottom actions

Consequential actions near the bottom of the display must remain above or safely padded through the device navigation/gesture region.

A shared bottom-action primitive should use safe-area padding rather than arbitrary fixed footer space.

The common working action should remain easy to reach, but not so close to the system gesture handle that an intended ECHO tap/swipe competes with Home/Overview navigation.

### 5.4 Horizontal gesture edges

Do not place routine swipe gestures, tiny controls or destructive affordances directly on the extreme left/right screen edge. Android's back gesture owns those edges in gesture-navigation mode.

ECHO should prefer explicit buttons, rows and deliberate drag handles away from the OS gesture edge.

### 5.5 Keyboard

The keyboard is part of the mobile layout state.

When it opens:

- the active field must stay visible;
- the next required action must remain reachable;
- the screen must not jump unpredictably;
- totals/context must not permanently disappear;
- bottom bars must not sit underneath the keyboard;
- dismissing the keyboard must restore the prior working context cleanly.

Numeric jobs such as quantity, price, counted stock and Closing Cash should summon the most appropriate keyboard/input mode.

### 5.6 Navigation modes

ECHO must be usable under at least:

- Android gesture navigation;
- Android three-button navigation;
- browser mode;
- installed PWA mode.

No screen may be approved after testing only one emulator/device configuration.

### 5.7 Cutouts and orientation

Critical content must remain safe on devices with camera/sensor cutouts and in landscape.

Landscape is not necessarily a primary counter workflow, but it must not make consequential actions inaccessible or hidden.

### 5.8 Contrast/system-bar relationship

When the PWA/native shell can influence system-bar appearance, foreground icons must retain adequate contrast with content drawn behind them. Do not create opaque decorative bands merely to simulate a desktop window frame.

## 6. Impact on the ECHO shell design

The shell specification must therefore own:

- top safe-area treatment;
- bottom safe-area/action treatment;
- left/right safe areas;
- keyboard viewport behaviour;
- network/sync-state placement that does not compete with the system status bar;
- one compact context/header model;
- one shared consequential bottom-action model when a workflow needs it;
- role-aware navigation that is distinct from Android system navigation.

Purpose-specific pages can then concentrate on the human job: Billing, Service, Stock Count, PO, Closing Cash, etc., without each reinventing phone geometry.

## 7. Revised mobile acceptance matrix

Before a core ECHO surface enters counter trial, verify at minimum:

1. 390×844 compact portrait viewport.
2. At least one real Android phone using gesture navigation.
3. At least one Android three-button-navigation configuration if available.
4. Device/display with non-zero safe-area/cutout conditions where available.
5. Browser and installed-PWA launch modes.
6. Keyboard open/close on every primary input path.
7. Primary bottom action with keyboard closed and open.
8. Left/right-edge back gesture while the user is midway through an unsaved job.
9. Network loss/reconnect while keyboard/form state is active.
10. Rotate/resume/interruption where supported; no loss or false completion.
11. Touch targets inspected for comfortable one-handed counter use.
12. No routine horizontal scrolling for the primary phone path.

Record the failure as product-design debt, not merely CSS polish, whenever it can cause mistaken action, abandoned input, duplicate submission, hidden state or inability to recover.

## 8. Design synthesis

The PDF's advice to simplify, prioritize, reduce typing and test on real phones should remain the human-level mobile rule.

The Android guidance supplies the missing physical-device rule: **the screen rectangle is not entirely ours**. The OS, gestures, keyboard, cutouts and system bars occupy dynamic regions that ECHO must respect.

This strengthens the existing Page Ecology doctrine. A control can be semantically correct and still be wrongly placed if the device environment makes it obscured, hard to reach or competitive with system navigation.

For ECHO, mobile-first therefore means more than responsive CSS:

> **Design the job, the hand, the keyboard, the network and the operating-system edges as one working environment.**
