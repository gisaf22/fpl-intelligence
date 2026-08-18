# decisions/

One folder per FPL manager-facing decision. Each folder is self-contained: the decision
statement, its success metric, its harness, its baselines, and its frozen results live
together.

The colocation is deliberate. The metric governs the harness — what counts as success
determines what the harness must measure and which baselines are worth beating. Splitting
the documents from the code that implements them is how a metric and its evaluation drift
apart, so they sit in one folder and move together.

## Why this is not `docs/decisions/`

`docs/decisions/` holds two things, and neither is this. Per its own README's "Which do I
write?" test: a **verdict** on whether a signal or study worked is a decision slug, and a
**design choice** about how the system is built is an ADR. That folder's audience is
someone changing the system.

This folder holds the decisions an FPL manager makes — the FPL Decision Framework's
entries. Different subject, different audience. A document here answers "what is being
decided, and how would we know we got it right", not "how is the repository built".

## Relationship to ADR-012

[`docs/decisions/012-decision-as-first-class-contract.md`](../docs/decisions/012-decision-as-first-class-contract.md)
§4 restricts the `DecisionSpec` family to per-player ranking and explicitly excludes
squad-constrained selection — Wildcard, Free Hit, Bench order, multi-week transfer
planning — as a different family: constrained optimisation over a squad, not independent
per-player scoring. It reserves that family for "its own abstraction (which may later
*compose* `DecisionSpec` objectives as inputs), decided by its own ADR when a decision
actually demands it."

`starting_xi/` is that family. The formal ADR amendment will follow once this slice is
built and its shape is known. It is deliberately **not written yet** — an ADR describing
the abstraction for unbuilt work would be recording an intention, not a decision, and the
repository already carries one document pointing at work that was never done (ADR-006).

## Current contents

- `starting_xi/` — specified, not built. Contains `DECISION.md` only.

Nothing else exists here yet.
