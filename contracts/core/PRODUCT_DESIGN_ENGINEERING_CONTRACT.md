# TAGRO ECHO OS — Product Design Engineering Contract

Status: owner-directed foundation contract
Scope: all ECHO user-facing pages, workflows, imported page skills and future SaaS surfaces

## Premise

Engineering correctness, data correctness, algorithms, workflow planning and final UI/UX are one product system. UI/UX is not a cosmetic layer applied after backend completion. A technically correct function that is difficult, ambiguous, badly placed, context-poor or disruptive in the real operating environment is not complete.

The prior TAGRO Service, TAGRO OS, TAGRO.in and Jain irrigation page families are evidence sources and experiments. They are not templates to copy wholesale. Their useful design, wording, labels, controls, sequence logic, data relationships, responsive behaviours and workflow ideas may be admitted only through governed evaluation.

## Design chain

Every user-facing capability SHALL be designed and reviewed through the complete chain:

REAL USER / ENVIRONMENT
-> intended job
-> event and evidence
-> authority and risk
-> algorithm / business logic
-> data contract
-> workflow sequence
-> information architecture
-> interaction design
-> visual hierarchy
-> wording / labels
-> responsive / mobile behaviour
-> failure / offline / recovery behaviour
-> feedback / acknowledgement
-> measured usability outcome

No stage may be treated as an afterthought when its absence can alter the event horizon, create ambiguity, generate static, conceal state or cause an incorrect consequence.

## Cohesion rule

A page belongs to a larger page world. It SHALL be evaluated both locally and planarly:

1. Does every present element have a reason to exist here?
2. Is every required element present where its absence would disrupt continuity or truth?
3. Is each element in the correct page, region, sequence, role, authority and environmental context?
4. Is the page connected to the correct canonical data/event/evidence source rather than a convenient duplicate?
5. Does entering or leaving the page preserve the user's operational context?
6. Can the user understand current state, next permitted action, uncertainty and outcome without reconstructing system internals?
7. Does the page behave correctly under phone use, counter pressure, poor connectivity, interruptions and partial data?

## Reuse from older resources

For every candidate skill from Service, OS, TAGRO.in, Jain or another older resource, record at minimum:

- source resource and location;
- user/job it served;
- observed strength;
- observed failure or friction;
- reusable design principle;
- data dependencies;
- authority dependencies;
- environmental assumptions;
- correct ECHO receiver/page context;
- VIBGYOR/spectral relevance where applicable;
- admission, redesign, quarantine or retirement decision.

Reuse means extracting the proven skill, not copying the old shell.

## UI/UX completion gate

A capability is not complete merely because its API, schema and tests pass. Before admission as an operational surface, it SHALL also demonstrate:

- clear task entry and exit;
- minimum necessary cognitive load;
- readable hierarchy and touch-safe controls;
- labels that describe user intent rather than implementation jargon;
- preservation of branch, user, customer, machine, plot, job or other relevant context;
- appropriate evidence, freshness and confidence cues;
- correct loading, empty, stale, offline, conflict, validation, permission and failure states;
- acknowledgement of consequential actions;
- no dead controls, orphan navigation, hidden required state or duplicate truth;
- mobile/counter suitability for the intended environment;
- an explicit usability test against a representative real workflow.

## Workflow-first design

Complex tools SHALL be designed as coherent journeys rather than collections of pages. Example irrigation journey:

customer/context
-> map
-> plot/boundary
-> sketch
-> measured geometry
-> design inputs
-> hydraulic/design calculation
-> BOM
-> estimate/document
-> communication / handoff
-> retained evidence/history

Each transition must carry only the dimensions required by the next receiver while preserving the whole originating event/evidence history.

## Product-design debt

A known UX discontinuity, misleading label, missing state, broken context handoff or unnecessary repeated input is product-design debt and SHALL be tracked with the same seriousness as technical debt when it can cause user error, abandonment, duplicate truth, loss of evidence or operational delay.

## Acceptance principle

ECHO shall not repeat the pattern of spending engineering effort on isolated working surfaces that fail to combine into one usable operating system. The target is not a collection of good pages. The target is one coherent operational environment in which engineering, algorithms, information architecture and human experience reinforce the same underlying truth.
