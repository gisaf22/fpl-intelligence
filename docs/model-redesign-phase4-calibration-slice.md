# Phase-4 calibration finalization — plan + decision doc (Track A: trust the distributions)

**Status:** approved (forks A–D ruled) · **Type:** spec
**Parent:** [docs/model-redesign-spec.md](model-redesign-spec.md) (§ calibration in `model/eval`) · [simulate slice](model-redesign-simulate-slice.md)
**Goal:** make the calibration suite **trustworthy + reproducibility-gated**, then **run it on the real mart
and record the verdict** against the tolerances already pre-registered in `model/eval/calibration.py`
(haul ECE ≤ 0.02; 80% coverage ∈ [0.75, 0.85]).

## Scope fence (pre-registered)

Phase-4 calibrates the **conditional-on-appearance** distribution — the simulator's population
(`minutes>0`, DGW-excluded, GW>3) against realized `total_points`. It does **NOT** calibrate the
*unconditional* `p_play × conditional` path. "Does `P(play) × E[points]` match realized-incl-blanks?" is a
real but **separate, later** question — folding it in here would import the X1 blank tail into the target
and manufacture spurious miscalibration. Sim and target share one population.

## Why this is real work (not just "run it")

The suite (`calibration.py`) is well-located and rigorous (pre-registered tolerances, no-leakage
walk-forward recalibration) but has two gaps: (a) it reaches into `simulate.py`'s **privates**
(`_REQUIRED`, `_draw_team_ga`, `_simulate_rows`) and **duplicates** the draw loop; (b) it has **no
seed-pinned regression vector** — every test is structural, so a numeric drift in ECE/PIT/CRPS passes
silently, violating the project's "frozen numbers reproduce" invariant. And it has only ever been
*structurally* tested — never run on the real mart to read the verdict.

## Forks (ruled)

- **A — draw primitive shape:** a **generator** `iter_sample_blocks(params, n_sims, seed, batch_rows)`
  yielding `(block, draws)` (team-GA once up front, then per batch — memory-bounded), NOT a single
  full-matrix return. Matches the current batching.
- **B — PIT tie-jitter rng:** the **scoring** layer gets its **own** seeded rng (clean draw/score
  separation). This deliberately changes calibration's pre-refactor draw numbers — acceptable because no
  golden exists yet; **refactor first, freeze after**. (`simulate_points` has no PIT jitter, so its golden
  is unaffected.)
- **C — freeze scope:** bit-freeze only the numpy/scipy-stable outputs (PIT deciles, raw ECE, coverage,
  CRPS); pin the **sklearn**-recalibrated ECE under a **tolerance** (isotonic/Platt output can drift across
  library versions — a 4dp golden there is brittle).
- **D — verdict home:** a dedicated `docs/` **Phase-4 results doc** (matches the "frozen record" the term
  notebooks already point to), not inline in ASSUMPTIONS.

## Sequence (one reviewable commit each)

1. **Extract the public draw primitive** in `simulate.py`: `iter_sample_blocks` (same rng order — team-GA
   up front, then per-block `_simulate_rows`). Refactor `simulate_points` onto it. **Gate: the
   `simulate` seed-pinned regression vector reproduces to the bit** (pure extraction). + a primitive test.
2. **Repoint `calibration.simulate_eval`** onto `iter_sample_blocks`; drop the 3 private imports + the
   duplicated loop; give the PIT tie-jitter its **own** seeded rng. Structural tests stay green.
3. **Add calibration's reproducibility gate**: a seed-pinned frozen vector on a **synthetic** panel
   (`tests._synthetic_mart`), pinning stable metrics to 4dp + recal-ECE under tolerance, + a per-position
   event-count (power) assertion.
4. **Run `calibration_report(mart)` on the real mart**, record the verdict in the Phase-4 results doc: PIT /
   haul+return ECE (raw+recal) / coverage / CRPS per position, **event counts + power flag**, pass/fail vs
   the pre-registered tolerances. Conditional population only. At most **one** recalibration pass.

## Stress-test constraints (honor these — the real traps)

1. **Golden safety:** Step 1 is a *pure* extraction; `simulate_points`' rng call order is unchanged
   (team-GA, then per-block), so its 4dp golden stays bit-identical — that is the Step-1 gate.
2. **No brittle goldens:** do not bit-freeze the sklearn-recalibrated ECE (Fork C) — pin it under a
   tolerance; freeze only numpy/scipy metrics to the bit.
3. **Power first:** haul (≥10) events are rare on one season. Interpretation is **power-gated** — count
   events per position; below a floor → "**inconclusive/underpowered**," never "miscalibrated." Do not
   recalibrate on noise.
4. **Recalibration honesty:** report the common recalibratable-set `n`; a sub-noise ECE "improvement" is
   **no material difference**; one pass only; walk-forward (fit `gw<t`, apply `gw==t`) — no leakage.
5. **Population discipline:** conditional only (`minutes>0`, GW>3); sim and target share the population —
   the P(play) unconditional path is out of scope (see fence).
6. **Freeze on synthetic, interpret on real:** the frozen vector is computed on a fixed synthetic panel
   (the real mart is non-deterministic across data refreshes); the *verdict* is read on the real mart.
7. **Climatology caveat:** the CRPS climatology comparator is in-sample (uses the rows' realized `y`) — a
   generosity to the *comparator*, documented, not a model leak.
8. **No scope creep:** the deliverable is the trust **verdict + one recalibration pass**, not model surgery
   to *fix* any miscalibration found (that is a separate track).

## Invariant
`simulate` golden bit-identical post-refactor · import-linter 6/6 · ruff clean · full `pytest` green each
step · conditional population only · pre-registered tolerances unmoved · interpretation power-gated.
