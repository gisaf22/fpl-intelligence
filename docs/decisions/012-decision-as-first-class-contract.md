# ADR-012 — A Decision Is a First-Class Contract

**Status:** Proposed — 2026-08-02; amended 2026-08-03 (§6 evaluation placement corrected — see the Amendment).
Phases 1–3 shipped as code (engine, specs, composition root); the evaluation harness (Phase 4) is in scoping.
**Applies to:** a new `domain` decision contract, `serve/{captain,value,transfers}.py` (to become implementations),
`model/predictions.assemble_forecast`, `model/eval/captaincy_*`, `tests/helpers/{captain,value,transfers}.py`,
and a new operational composition root.
**Relates to:** [ADR-010](010-layered-decision-model.md) (per-layer authority; the layer-decision table this ADR
places new components against) and [ADR-011](011-model-forecast-supersedes-composites.md) (the forecast that
decisions now rank by, and the single-step lag-safety boundary this ADR inherits). Supersedes nothing.

---

## Context

The predictive layer is validated and the serve composites are retired (ADR-011): `captain`, `value`, and
`transfers` now rank by the model forecast. But **the "decision" is not a concept the architecture holds** — it is
three parallel functions plus scattered evaluation. Two facts, measured on the current tree, force this ADR:

**1. There is no operational path from forecast to recommendation.** No production module both calls
`assemble_forecast` and a `rank_*` function. The only code that enriches the mart with the forecast and ranks is
`tests/helpers/{captain,value,transfers}.py`; `outputs/` has never contained a decision recommendation. The
"operational runner" ADR-011 refers to does not exist — it is prose and test scaffolding. `serve/__init__.py`'s
documented usage (`rank_captain_candidates(load_mart().mart, …)`) raises, because the DAL mart carries no forecast
columns, and points at a `docs/operational-intelligence.md` that does not exist.

**2. The three decisions share a control-flow shape, not a mass of logic.** Each is ~47 code lines; ~8 lines of
*logic* are identical across all three (the forecast-column guard, the `target_gw` slice + empty checks, the two
return shapes); another ~7 share shape with differing substance; the remaining ~32 are decision-specific. So the
motivation is **not** DRY (collapsing would save ~30 lines — that alone would be over-engineering). The motivation
is that the *variation across the three real decisions is a small, closed set* — and that set is the contract a
`Decision` should name, so every future decision fills the same slots and the missing runner and a generalised
evaluator have a single seam to attach to.

**The measured variation surface** (the empirical basis for the interface — grounded vs not):

| Field | Captain | Value | Transfers | Status |
|---|---|---|---|---|
| Required forecast columns | `p_haul, p90, e_points_uncond` | `e_points_uncond` | `e_points_uncond` | **grounded** |
| Eligibility predicate | `minutes_roll3≥45`, not warmup | `price≥3.5`, `minutes_roll5≥30`, `max_price?` | `minutes_roll5≥30`, `position?` | **grounded** |
| Objective / score | `p_haul` (ceiling) | `e_points_uncond/price` (per-£) | `e_points_uncond` (mean) | **grounded** |
| Tie-break | `p90` | — | — | **grounded** |
| Optional constraints | — | `max_price` | `position` | **grounded** (scalar filters only) |
| Output columns | decision-specific | decision-specific | decision-specific | **grounded** |
| Forecast horizon | single-step (`target_gw`) | single-step | single-step (multi-week = leak, ADR-011) | *reserved* |
| Evaluation binding | `model/eval` + test helper | test helper only | test helper only | *homeless* |
| Squad objective / constraints | — | — | — | *out of scope* |

**3. Decision evaluation is architecturally split.** Evaluating a *pick* needs the ranker's output and the actual
outcome (`dal`). The naive coupling — importing the `serve` ranker into `model` — is upward and disallowed, which is
why `model/eval/captaincy_*` today evaluates the *forecast* directly while `tests/helpers/captain.py` evaluates the
shipped `serve` ranker: two captain evaluations, neither consolidated. §6 gives evaluation a single home
(`model/eval` + `kernels`) by **injecting** the ranker as data rather than importing it.

This ADR is **groundwork research**, not a product build: it fixes the *conceptual model* of a decision so that
next season's work is accumulating evidence against a stable contract, not against three drifting functions. It
deliberately writes almost no code (Phase 1); it specifies the contract the later phases mechanise.

## Decision

### 1. A Decision is a declared contract, not a module (LOCKED)

Introduce `DecisionSpec`: a decision is a value that **declares** its slots and defers all shared machinery
(validation, slicing, eligibility application, within-position ranking, output projection, evaluation) to a generic
engine. `Captain`, `Value`, `Transfers` become three `DecisionSpec` values, not three hand-written functions.

The invariant, in the spirit of ADR-010 §1: **one canonical spec per decision; the shared lifecycle is not
re-originated per decision.** A decision is a *violation* of this contract if it re-implements slicing, ranking, or
output projection instead of declaring its slots.

### 2. The frozen interface — grounded fields only

`DecisionSpec` (v1) carries exactly the fields the measured variation justifies:

| Slot | Type (informal) | Meaning |
|---|---|---|
| `name` / `slug` | str | stable identity (the decision's namespace, cf. ADR-004) |
| `required_forecast_cols` | tuple[str, …] | the `assemble_forecast` columns the runner must have merged |
| `eligibility` | `(frame, params) -> mask` | who is a candidate (minutes floor, price floor, warmup exclusion, optional filters) |
| `objective` | `(frame) -> Series` | the score to rank by — the decision's *objective made explicit* (ceiling vs mean vs per-cost) |
| `tie_break` | tuple[str, …] | secondary sort keys (empty for single-key decisions) |
| `params` | typed, optional | the scalar constraints that exist today (`max_price`, `position`) |
| `output_cols` | list[str] | the projection the recommendation carries for explainability |

Everything the three functions do *around* these slots — `validate_intelligence_inputs`, the missing-column guard,
the `target_gw` slice + empty handling, `dropna` on the score, `groupby(position).rank`, `head(n)` — becomes engine
machinery declared **once**.

### 3. Reserved fields — named, not built

Marked in the contract as reserved and validated only when a real decision needs them (the term-gate discipline:
do not carry what does not yet carry):

- **`horizon`** — v1 is single-step (`target_gw`) only, inheriting ADR-011's leak boundary (summing the precomputed
  forecast forward leaks post-decision state). Multi-step, deadline-frozen forecasts are a `model` piece; the field
  is reserved so the interface admits it later without a break.
- **`evaluation`** — the binding to a backtest (see §5) is part of the contract; the generalised evaluator ships in
  its own phase (the evaluation harness, Phase 4), homed in `model/eval` + `kernels` (§6) — not bundled into the
  engine, and not in `serve`.
- **squad objective / constraints** — see §4.

### 4. Taxonomy — v1 models per-player ranking only (the hard call)

Every decision that exists today is a **per-player ranking** decision: score each candidate independently, rank,
take the top. `DecisionSpec` models exactly this family and no more.

**Squad-constrained selection** (Wildcard, Free Hit, Bench order, multi-week transfer planning) is a *different
family*: constrained optimisation over a squad + budget + transfer count, not independent per-player scoring.
[docs/system-purpose.md §Explicitly excluded](../system-purpose.md) already rules it out of scope
("Transfer market optimisation — constrained squad selection is a separate problem"). This ADR **honours that
exclusion**: squad selection is *not* an extension of `DecisionSpec`; it will be its own abstraction (which may
later *compose* `DecisionSpec` objectives as inputs), decided by its own ADR when a decision actually demands it.

Baking squad optimisation into the base interface now would over-fit an imagined future and violate the "one model
× one context" restraint the project applies to features. The interface stays honest and small.

### 5. Lifecycle and the three contracts

A decision's lifecycle: **candidate universe → eligibility → objective/score → rank → recommendation →
evaluation → (feedback)**. Three contracts bound it, each named against real symbols:

- **Forecast contract (upstream).** A decision consumes the columns of `model.predictions.assemble_forecast`
  (`e_points`, `e_points_uncond`, `p10/p50/p90`, `p_haul`, `sim_*`, the `DECOMP_COLUMNS`) as **data**, merged on
  `(player_id, gw)`. Serve never imports model (import-linter `no_serve_to_research_or_model`); the forecast arrives
  as columns. Lag-safety at `target_gw` is inherited from ADR-011.
- **Evaluation contract.** A decision is backtested by a generic, **serve-agnostic** walk-forward driver in
  `model/eval/`, producing decision-outcome metrics (`top1_return`, `hit_rate`, `regret`, `return_variance`,
  `downside_rate`) — promoted from `tests/helpers/` to sit beside the forecast metrics — under a leakage guard, with
  the baseline-relative **paired CI drawn from `research/kernels`** (`model→kernels` is permitted). The driver takes
  the ranker as an injected `pick_fn`; only the `operational` composition root binds `run_decision` to it. *(Placement
  corrected — see the Amendment; supersedes the earlier `serve` claim.)*
- **Output contract.** Every recommendation is a frame at the decision's `output_cols`, always carrying the
  forecast reads it ranked by, so a pick is explainable through the gated terms (ADR-011 traceability).

### 6. Layer placement — closing the composition-root gap

Placed against ADR-010's layer-decision table:

- **The contract is ontology → `domain`.** `DecisionSpec`, the lifecycle types, and the registry protocol are
  *meaning/vocabulary*, so they live in `domain/` (the shared leaf every layer may import). Domain decides what a
  decision *is*; it enforces nothing operational.
- **The engine and the specs are execution → `serve`.** The generic engine and the Captain/Value/Transfers specs
  live in `serve/`; they read the forecast as data and import no upstream layer.
- **Decision evaluation is measurement → `model/eval` (+ `kernels` for statistics), NOT `serve`.** *(Corrected — see
  the Amendment.)* Backtesting a *pick* is an evaluation concern and belongs beside the forecast walk-forward already
  in `model/eval/` (`walkforward.py`, `metrics.py`, `baselines.py`). The reusable paired/bootstrap CI lives in
  `research/kernels/inferential/resampling.py` (next to `_percentile_ci`) — `model→kernels` is permitted (the
  `no_model_to_research_analysis` contract exempts kernels), whereas `serve↛research` is exactly why the evaluator
  *cannot* sit in serve (a serve evaluator would be forced to duplicate the CI — the smell that revealed the
  mis-placement). The driver stays **serve-agnostic via dependency injection**: it takes a `pick_fn: (mart, gw) ->
  picks` (plus baseline pick-fns) and never imports `serve`. This consolidates the two split captain evaluations
  (`model/eval/captaincy_*` forecast-level and `tests/helpers/captain` ranker-level) into one home, and reuses the
  outcome metrics/baselines promoted from `tests/helpers/`.
- **The runner is the composition root — above both layers.** The one component that must call *both*
  `assemble_forecast` (model) and the serve engine cannot live in either (`serve↛model`; `model` is below `serve`).
  It is therefore an **operational entry point outside the layered libraries** (the top-level `operational/` package)
  whose job is exactly this wiring: `dal.load → assemble_forecast → merge → engine.run(spec, target_gw) →
  recommendation`; and for a backtest it **injects `run_decision(spec, …)` as the evaluator's `pick_fn`**. Naming this
  composition root is the missing piece ADR-011 hand-waved as "an operational runner"; it is what `tests/helpers/*`
  stands in for today.

### 7. The freeze (interface, not implementations)

Once ratified, the **`DecisionSpec` interface is frozen**: adding or changing a *slot* is an ADR-level act, exactly
as changing the DAL data contract is. Implementations (new decisions, tuned thresholds, new objectives) are free and
expected. The research payoff of next season depends on this: evidence that "decisions plug into a stable contract
cleanly" is only interpretable if the contract holds still. A frozen decision interface is the operational analogue
of the frozen data contract in [docs/system-purpose.md](../system-purpose.md).

## Migration path (phased; each independently shippable + green)

- **Phase 1 — this ADR. ✅ done.** The contract, the frozen fields (§2), the reserved fields (§3), the per-player
  taxonomy (§4), and the layer placement (§6, as amended).
- **Phase 2 — the engine + collapse the three. ✅ done.** `domain/decision.py` (`DecisionSpec`); `serve/decision_engine.py`
  (`run_decision`); Captain/Value/Transfers re-expressed as specs, behaviour-preserving (golden
  `tests/test_intelligence_outputs.py` unmoved). *(Deferred within Phase 2: fold the per-module `_MIN_MINUTES_ROLL*`
  constants into the threshold registry. The evaluator is NOT here — see Phase 4.)*
- **Phase 3 — the composition root. ✅ done.** `operational/` (outside the layer graph): `dal → assemble_forecast →
  merge → run_decision → outputs/decisions/gw{N}/`. First real recommendations emitted; Verification-1 gap closed.
- **Phase 4 — the evaluation harness (current scope).** A **serve-agnostic** decision backtest in `model/eval/`:
  the walk-forward driver + `EvalSpec` (horizon, return-extractor, baselines, metric family), with the decision-outcome
  metrics and baselines **promoted from `tests/helpers/`** to sit beside the forecast eval, and the baseline-relative
  **paired CI from `research/kernels`**. `operational` binds the `serve` ranker in as the `pick_fn`. **Full replacement**
  of the `tests/helpers` evaluators; v1 covers **all three** decisions; regression-anchored to reproduce their outputs
  to the decimal.
- **Phase 5 — add decisions (deferred).** Triple Captain is a captaincy *payoff* variant (low novelty); the hard part
  is chip *timing* — a `horizon`/multi-week problem gated on multi-step forecasts. Squad-family decisions await their
  own ADR (§4).

## Mechanization

Per ADR-010 §5 (govern by executable contract), Phase 2 mechanises what it can:
- A test that every registered `DecisionSpec` satisfies the interface and every declared `required_forecast_cols`
  is a real `assemble_forecast` column (fail-closed, like the current missing-column guard, but once).
- A drift test that the collapsed specs reproduce the pre-Phase-2 golden recommendations.
- Interface-freeze is enforced by review + this ADR, not a linter (a slot change is a design act, not a regression).
- Phase 4: a regression test that the `model/eval` driver reproduces `evaluate_{captain,value,transfers}_heuristic`'s
  outputs before the `tests/helpers` originals are deleted (the behaviour-preservation anchor).

## Amendment — 2026-08-03: evaluation placement corrected

The original §6 placed the decision evaluator in `serve` ("everything it needs is reachable without importing
model"). **That was wrong.** A `serve` evaluator cannot reach `research/kernels`, where the reusable CI machinery
lives (`serve↛research`), which forced a *duplicate* CI in serve — the smell that revealed the mis-placement.

Grounding (all verified in-repo): `research/kernels/inferential/resampling.py` already hosts the bootstrap CIs
(`bootstrap_spearman_ci`, `_percentile_ci`, `_two_sided_p`); `model/eval/` already hosts the forecast walk-forward,
metrics, and baselines; `model→kernels` is permitted (the `no_model_to_research_analysis` contract exempts kernels)
while `model↛serve` is the layer order; and `model/eval` currently imports neither `serve` nor `kernels`.

**Corrected placement:** evaluation machinery → `model/eval` (+ `kernels` for statistics), serve-agnostic via an
injected `pick_fn`; only the ranker binding sits in `operational`. §3, §5, §6, and the migration path are updated to
match. Recorded decisions: v1 covers all three decisions; the `tests/helpers` evaluators are **fully replaced** (not
shimmed). A related, flag-only cleanup: `model/eval/metrics.py` already reimplements `block_bootstrap_ci` /
`clustered_mean_ci` that `kernels` could own — kernels is under-used by `model/eval` today, and the paired CI should
land there, with those two migrating later.

## Consequences

- **Positive:** a decision becomes one reviewable declaration; the runner and evaluator get a single seam; the
  broken public path (§Context/1) is closed with a named composition root; evaluation gets a home and the
  forecast-level vs pick-level confusion is resolved; adding per-player decisions is near-zero-cost.
- **Costs / deferred:** the multi-step forecast (`horizon`), the squad-selection abstraction, and the composition
  root's exact module home remain open (below). The line-savings are modest by design — the value is the contract,
  not the diff.
- **Unchanged:** the `dal → research → model → serve` (+ `domain` leaf) topology and every import-linter contract;
  ADR-011's forecast semantics and single-step lag-safety.

## Alternatives considered

- **Keep three parallel ranker functions.** Rejected: no named contract, no runner seam, evaluation stays homeless,
  and every new decision copies the shape. This is the status quo the review flagged.
- **DRY-only refactor (extract shared helpers, no contract).** Rejected: saves ~30 lines and names nothing; it
  would be refactor-for-its-own-sake and would not give the runner or evaluator a seam. The measured duplication
  (§Context/2) is too small to justify a refactor on DRY grounds alone — the justification is the contract.
- **Model squad optimisation in the base interface now.** Rejected (§4): over-fits an imagined future, contradicts
  the system-purpose exclusion, and no current decision needs it.
- **Design the ontology abstractly (all of Candidate/Objective/Constraint/Horizon/Feedback as live fields).**
  Rejected: the disciplined interface is grounded in the six fields that vary in real code; the rest are reserved
  and marked, so the contract cannot over-promise.
- **Put the runner inside `serve` (or `model`).** Rejected: it must depend on both layers; only a composition root
  above the libraries can, without breaking `serve↛model` or the layer order.

## Open decisions

- **The composition root's home** — a top-level `operational/`/`app/` package vs an extended root `pipeline.py`.
  Decide at Phase 3.
- **Whether pick-level backtest fully absorbs `model/eval/captaincy_backtest`** or the two coexist (forecast-level
  vs pick-level). Lean coexist; confirm in Phase 2.
- **Squad-family ADR** — deferred until a squad decision is actually scheduled (§4).
