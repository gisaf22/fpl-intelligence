# decisions/

One folder per FPL manager-facing decision. Each folder holds that decision's **artefacts**:
the decision statement, its success metric, its capability inventory, its design, its harness
code, and its frozen results.

The colocation is deliberate. The metric governs the harness — what counts as success
determines what the harness must measure and which baselines are worth beating.

**Self-contained means the artefacts, not every symbol they use.** A decision folder is a
consumer of the layers below it and reuses them in place rather than copying them in. In
`starting_xi/` the ranker implementations live in the folder but the statistics they call do
not — `expanding_prior_mean` stays in `model/eval/`, `p_play` stays in `model/terms/`, and the
squad quota and legal formations live in `domain/` so a second squad-family decision inherits
them without a new dependency edge. The rule that governs which of those a given module may
reach is the folder's own import contract
([`starting_xi/DESIGN.md`](starting_xi/DESIGN.md) §3), not this principle.

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

- `starting_xi/` — designed, not built. Contains `DECISION.md` (what is decided),
  `METRIC.md` (how success is measured), `INVENTORY.md` (what exists in the repository) and
  `DESIGN.md` (how the harness is built). No code yet.

No other decision folder exists yet.
