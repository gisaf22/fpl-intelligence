# DECISION.md — Free Hit Squad Construction & Selection

Sibling to `decisions/starting_xi/DECISION.md`. Follows the same structure.
Status: Specified in conversation, revised after a five-expert stress-test
pass. Not yet built.

## §1 — What decision

This measures **timing-independent construction quality** — a deliberately
narrower question than "is Free Hit worth using, or when." Given a target
gameweek, construct a full 15-player squad from scratch (unconstrained by
any existing squad), then select a starting XI and bench order from it.
This is a measurement/research question — "is our construction+selection
method good, across a defined set of gameweeks" — not a live single-
gameweek recommender tool.

There is no such thing as scoring a raw 15-player squad. Every comparison
— our candidate, every naive baseline, every external reference — is
scored by running that 15 through the existing (unchanged) starting_xi
selection harness: 15 → best legal XI → +autosub bench contribution →
realized total score. Construction is the new problem; selection+bench is
a proven, reused, unchanged unit applied identically to every candidate.

**Explicitly named limitation of this framing:** real Free Hit deployment
is gameweek-selective by nature (managers choose to play it on fixture-
anomaly or high-opportunity weeks). Measuring "construction quality" on a
gameweek population as if the choice of gameweek were incidental is a
narrower and different question than "does Free Hit help, when actually
used." This document answers the narrower question only. See §3 for the
gameweek population this applies to, and §7 for what's left open.

## §2 — Whose goal

Built for other managers in the abstract, not conditioned on a specific
manager's existing squad, bank, transfer history, or overall rank.
Objective is total expected-points maximization for that single gameweek.
Protect-rank vs rank-chase variants are not modeled (same exclusion
starting_xi made).

## §3 — What's given

- A target gameweek, drawn from a **single-gameweek, non-DGW/non-BGW
  population for v1** — mirrors starting_xi's own DGW/BGW handling
  precedent. Double- and blank-gameweeks are excluded from the core
  evaluation set, not silently inherited or silently included: a flat
  100m budget and per-player scoring change meaning under a DGW (roughly
  doubled ceiling for a captured player) and under a BGW (reduced pool),
  so mixing them into the same statistics would confound construction
  quality with fixture-anomaly effects. Construction quality specifically
  on DGW/BGW weeks — arguably where real managers most often use this
  chip — is named as a **flagged future extension**, not covered here.
- Exact GW range/season scope (fixed season vs. sampled subset vs.
  multi-season) is an open INVENTORY.md data-availability question, not
  pinned here — INVENTORY.md must state what's available before this is
  finalized.
- Budget: fixed 100m, applied uniformly to our candidate and every
  baseline compared, for v1. **Known limitation, explicitly unresolved:**
  real managers' effective budgets grow across the season via team-value
  appreciation, so fixed 100m may understate realistic affordability in
  later gameweeks. Whether the mart holds season-average-team-value-by-GW
  data to support a future variable-budget sensitivity pass is an open
  INVENTORY question.
- Full player pool for that gameweek: prices, positions, club, and
  existing leakage-free as-of signals (as-of PPG, rolling PPG, fdr_avg,
  fixture data).
- Standard FPL squad-legality constraints: 15 players, 2 GK/5 DEF/5
  MID/3 FWD, ≤3 players per club, budget ≤ given budget.
- **Legality-checking mechanism is TBD, not assumed.** `sampler.py`'s
  existing feasibility logic is whole-squad, uniform-draw-and-reject —
  built for a different access pattern. A greedy constructor needs
  incremental, partial-squad feasibility ("can the remaining quota still
  be filled inside the remaining budget after this pick"), which nothing
  in the repo currently exposes as a reusable primitive. INVENTORY.md
  must confirm whether one exists, needs building once and shared across
  all construction candidates (naive and future ILP alike), or is
  currently at risk of each candidate hand-rolling its own — with the
  risk that naive baselines and a future ILP candidate silently disagree
  on what "legal" means.

## §4 — Context / evidence (forward pointers to METRIC)

- Selection+bench layer (best-legal-XI, bench order, auto-sub replay) is
  unchanged and proven from the starting_xi slice (matroid-optimal, mean
  regret 0.108–0.116 pts/GW) — reused identically for every candidate
  and baseline squad here.
- Construction regret = candidate's realized total (via the standard
  harness) minus a given baseline's realized total (via the same
  harness), same gameweek.
- Selection regret = unchanged, direct port from starting_xi, applies
  within any given 15 regardless of who built it.
- Combined regret = realized total vs. baseline realized total, all-in.
  As written, this and the Construction regret bullet above do not name
  distinct formulas — both are "candidate's harness-realized total minus
  a given baseline's, same gameweek." `METRIC.md` §1.4 confronts this
  directly and resolves it by treating them as **the same computed
  quantity reported under two framings**: Construction regret is the
  per-baseline series, always kept disaggregated, that feeds the verdict
  machinery; Combined regret is that same series read as the single
  end-to-end "did the candidate do better" number, with no attempt at
  decomposition. That is `METRIC.md`'s interpretive choice, adopted here
  for consistency between the two documents rather than re-derived
  independently — `METRIC.md` §1.4 also names, and leaves open rather
  than adopts, an alternative reading in which Combined regret is instead
  an explicit sum of Construction regret and a Selection-regret term.
- Three naive construction baselines — season-PPG greedy, value
  (PPG-per-price) greedy, recent-form (rolling PPG) greedy — tracked as
  separate series across the season, not collapsed to a per-GW max.
  Relative strength may shift with time of season (e.g. recent-form
  weaker early on due to small sample); that shift is a finding to
  observe, not noise to average away. **The pass/fail verdict rule
  against these three (independent paired tests with a stated
  multiple-comparison correction, vs. a best-of-three composite, vs.
  something else) is explicitly METRIC.md's decision, not pinned here —
  flagged so it isn't silently decided by default.**
- Top-10k average and overall average (FPL-published): real managers'
  own realized totals, already inclusive of their own XI/bench choices —
  used strictly as an **unscored reference point in reporting**, never as
  a design target and never folded into the pass/fail bar. Flagged:
  top-10k managers are disproportionately near-template and their picks
  are correlated (herding), not independent draws — so this number must
  never be read as a percentile or spread, only as a single contextual
  figure. This is a narrower use than the out-of-scope exclusion of
  template/EO-weighted *construction* (§5) — using a template-correlated
  number as passive context is not the same as building toward template
  awareness, but the distinction must stay visible in any report that
  cites it.
- True global-oracle construction (best possible 15, full hindsight):
  deferred, not built for v1 — real combinatorial optimization with
  uncertain payoff over the naive floor; revisit only if naive-vs-
  candidate headroom (once actually measured) looks large enough to
  justify it.
- **Sequencing, reframed:** a cheap non-forecasting composite candidate
  (PPG + fdr_avg + value) is built and measured before any forecasting/
  ILP-driven constructor. This is a build-cost/sequencing choice only —
  it is **not** backed by a known-small-headroom finding the way the
  bench-order weighted-score-before-Markov deferral was. That precedent
  closed only after both a cheap and an expensive candidate were actually
  built and measured against each other, finding a near-zero gap
  (≈0.0004 pts/squad-week) — headroom was known before the decision, not
  assumed. Construction's headroom is genuinely unknown and likely much
  larger, given the decision space (15-of-several-hundred under
  constraints vs. bench order's 6 permutations of 3 players). The ILP/
  forecasting candidate's fate is left open, contingent on what the cheap
  composite's measured regret against the naive floor actually shows —
  not pre-judged as unnecessary.

## §5 — Out of scope

- Chip timing (when to play Free Hit) — see §1 for how this document's
  scope relates to timing rather than simply excluding it.
- Chip interaction (Free Hit combined with other chips same GW).
- Multi-week Free Hit horizon planning.
- Variable/live budget (fixed at 100m for v1; see §3 limitation).
- Manager-specific context: existing squad, current rank, bank balance,
  prior transfer history.
- Ownership/EO-weighted or template-driven construction as a design
  target (distinct from using top-10k average as passive unscored
  context — see §4).
- True global-oracle construction as a scored benchmark (deferred, may
  return as a stretch goal).
- Forecasting-model-driven/ILP-optimized construction as the FIRST
  candidate (not permanently excluded — see §4's reframed sequencing
  note; its fate is open, not pre-decided).
- Construction quality specifically on DGW/BGW gameweeks (see §3 — named
  future extension, not covered by v1's core evaluation set).

## §6 — Architectural note, not yet resolved

Free Hit is plausibly the "second squad-family decision" that ADR-012 §4
named as the trigger for formalizing a deferred squad-constrained-
selection abstraction, once starting_xi shipped and its shape was known.
That abstraction still hasn't been written. This document proceeds
without it as a **conscious choice to defer again**, not an oversight —
but that choice should be revisited before more one-off harness/
construction code is written for this slice, not silently repeated a
third time if a third squad-family decision ever arrives.

## §7 — Status

Specified, revised after expert review, not yet written to repo as a
committed file until this pass. INVENTORY.md is the next document and
must resolve, before DESIGN.md is attempted:
1. Gameweek population availability (season/GW range, DGW/BGW flag
   accessibility — confirmed present in the mart at the fact layer,
   accessibility at this layer to be verified).
2. Whether team-value-by-GW data exists to eventually support a variable-
   budget sensitivity pass.
3. Whether a reusable incremental-feasibility primitive exists, or must
   be built once and shared, for greedy construction candidates.
4. Whether a naive greedy constructor is genuinely Tier-A-buildable
   (no forecasting/model import) under the same Tier wall discovered in
   the starting_xi slice.