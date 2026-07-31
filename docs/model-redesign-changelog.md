# Model redesign — changelog (frozen record)

**Type:** `changelog` · **Parent:** [model-redesign-spec.md](model-redesign-spec.md)

The spec keeps the *timeline* as a changelog rather than as file structure (spec §7, §251). This file
**is** that changelog: one dated entry per shipped or measured slice, each carrying its verdict and the
headline numbers, so the individual per-slice specs no longer need to live as loose files. It folds in
eleven docs that were completed between 2026-07-17 and 2026-07-29; each entry names the doc it replaces
(recoverable from git history).

Doc types (spec §228): `spec` (live, build against) · `frozen-result` (a verdict — the deliverable) ·
`changelog` (this file) · `archived`. The two docs still typed `spec` and kept as separate files are
[model-redesign-spec.md](model-redesign-spec.md) (the north star) and
[model-redesign-mean-features-plan.md](model-redesign-mean-features-plan.md) (the live mean-features
program). Everything below is done or measured.

**Reading guide**
- [Shipped slices](#shipped-slices) — structural changes now embodied in code (the plan is superseded by the code).
- [Measured dead-ends](#measured-dead-ends) — pre-registered hypotheses that were **REFUTED**; the code
  cannot reconstruct these (it silently omits the rejected feature), so this is the only record of
  *"tried it, measured it, don't rebuild it."*
- [Gate completeness](#gate-completeness-loose-ends-closure-2026-07-30) — the level-gate closure pass: every term gated on both axes, and what wiring it revealed.
- [Open items carried forward](#open-items-carried-forward) — surfaced by these slices, statuses updated by the pass above.

---

## Shipped slices

### team_goals_against extraction (2026-07-17)
*Replaces: model-redesign-team-goals-against-slice.md*

The joint model the contract split was designed for: D-D proved `clean_sheet = 1{GA=0}` and the conceded
penalty `-floor(GA/2)` are the **same** random variable (team goals-against), so **one** Model emits
**both** Terms — the *Model-emits-many-Terms* shape, proven early. Faithful strangle of
`points_model.walk_forward_team_ga` into `model/terms/team_goals_against/` (Poisson at `team_gw` grain;
`minimal = ga_roll3`, `selected` over `ga_roll3/5, xgc_roll3/5, was_home, fdr_avg`). Added the missing
infra: a `team_gw → player_gw` **`broadcast`** in `model/features/build.py` (explicit checked join, no
row multiplication). `minimal`/`selected` reproduce `p_cs` / `e_conceded_pts` bit-identical to the
god-file on a fixed panel. A proper minutes-aware team xGC feature (`team_xgc_minutes_aware`) was declared
as an unmaterialized pool candidate, **deferred**. Frozen numbers:
[docs/studies/results/predictive-phase3-points-model.md](studies/results/predictive-phase3-points-model.md).

### simulate.py extraction (2026-07-18)
*Replaces: model-redesign-simulate-slice.md*

Terms → **points distribution** (P(haul), captaincy ceiling `p90`, downside `p10`), not just the mean.
Extracted `_draw_team_ga` / `_simulate_rows` / `simulate_points` from `forecast/simulator.py` onto a new
`compose_parameters(mart)` raw-parameter panel (single view-collection path; `compose_points` refactored
onto it). Sampling law kept **local** to `simulate.py` (the §2 Term contract stays point-valued — contract
change deferred).

**The reproducibility invariant changed form** for this first stochastic step (this is "Fork B", cited by
`model/terms/test_simulate.py`): a Monte-Carlo sim cannot be bit-identical to the old god-file, and
`sim_mean` cannot equal compose `e_points` to 4dp even in principle (bonus clip + saves floor are real
nonlinearities). So the gate split in two: **(1)** a seed-pinned regression vector
(`sim_mean/sim_sd/p10/p50/p90/p_haul`, 4dp) as the repro gate, and **(2)** a `sim_mean ≈ compose e_points`
**tolerance** check on non-GK rows, GK excluded and its divergence logged (the deliberate robust-`p60`
improvement). DGW rows are not scored (compose drops them) — recorded as a scope limit, not silently wrong.

### god-file deletion — strangler migration complete (2026-07-19)
*Replaces: model-redesign-godfile-deletion-slice.md*

Deleted `model/forecast/{component_forecast, signal_combination, simulator}.py` (and, after the P(play)
slice below, `points_model.py`) — the whole `model.forecast.*` god-file cluster is gone. Three stages,
each behind the reproduction gate: **(A)** all 7 term goldens frozen onto inline vectors via
`model/terms/_freeze.assert_frozen` (zero behaviour change) so `model/terms` imports nothing from
`model/forecast`; **(B)** eval consumers (`calibration.py`, `captaincy_backtest.py`) repointed onto
`compose`/`model.simulate` (`full_pts` → compose `e_points`; GK numbers shift by design); **(C)** delete +
**3-CS reconciliation** — the player-Binomial CS and the signal-combination CS are gone; the extracted
`team_goals_against` model is the single clean-sheet source. Two live diagnostics were **relocated, not
lost**, into `model/eval/forecast_diagnostics.py`. Dropped the dead `p21_pts` Phase-2.1 comparator
(`base_season` remains the incumbent bar). `count_models.py`/`level_estimators.py`/`shrinkage.py` are
**not** god-files and were kept.

### position specification in the count models (2026-07-26)
*Replaces: model-redesign-position-specification-results.md — the first slice to move shipped predictions*

The `goals`/`assists` Poisson GLM fit **one model across all four positions with `position` absent** — the
one file breaking a convention the other five components already followed. Three fixes in the shared
machinery: a **per-position intercept** (slope stays shared — every position still borrows strength;
evidence: intercept is ~99% of the fix, full slope separation bought nothing and cost 2× the DEF ranking);
**`fit_positions`** so structurally degenerate targets aren't estimated (GK `goals` realized mean is
**exactly 0.0000** over 668 keeper-GWs → structural `0.0`); and **retiring the `_GOAL_POS` scoring gate**
(the model emits the honest value at source; regressions now caught by the term's own level gate).

Headline — compose level bias (`e_points` − realized, pts/GW):

| position | before | after (incl. saves fix) |
|---|---|---|
| GK | +0.599 | **+0.025** |
| DEF | +0.351 | **+0.064** |
| MID | −0.041 | +0.098 |
| FWD | −0.413 | **+0.038** |

**The DEF↔FWD relative distortion — which lands on every defender-vs-forward decision — went 0.764 → 0.026
pts (97% reduction).** Ranking verdicts were **unchanged** (no position flipped). The level gate *earned
its keep*: it caught an over-reach where `assists` was given GK's structural-zero — keepers assist rarely
but **not** structurally (realized 0.0060/GW), so `assists` fits all four positions.

Follow-on fixed here: the **saves Jensen gap** — FPL pays `floor(S/3)` but compose scored `E[S]/3`
(payout-of-expectation vs expectation-of-payout, ~0.33 pt at a typical keeper rate). Fixed with
`saves_points_expectation(e_saves) = E[floor(S/3)]` over the Poisson support; the simulator was already
correct (draws then floors) so no golden/draw moved. This drop absorbed the previously-flagged clean-sheet
+0.09 residual — GK is now essentially unbiased. Also fixed a **CI collection gap**: `testpaths = ["tests"]`
was collecting **none** of the co-located `model/` term tests (87 including every golden); `testpaths` now
includes `model` (1327 → 1414 tests).

### Phase-4 calibration — are the distributions trustworthy? (2026-07-20 – 07-21)
*Replaces: model-redesign-phase4-calibration-slice.md + model-redesign-phase4-calibration-results.md*

Made `model/eval/calibration.py` trustworthy + reproducibility-gated (extracted the public
`iter_sample_blocks` draw primitive; dropped calibration's 3 private imports + duplicated draw loop; own
seeded rng for PIT tie-jitter; seed-pinned frozen vector on a synthetic panel with a power assertion), then
ran it on the real mart (n = 10,110, conditional population). Pre-registered: haul ECE ≤ 0.02; 80% coverage
∈ [0.75, 0.85].

- **Haul calibration — PASS.** Raw haul ECE **0.0160 ≤ 0.02** before any recalibration; one walk-forward
  pass → 0.0017/0.0005.
- **The distribution is genuinely informative — PASS (CRPS).** `crps_sim` beats point and Poisson(mean) at
  every position and beats (in-sample) climatology at 3 of 4 (GK the exception).
- **GK over-dispersion — fixed.** Root cause: the pooled goals model emitted a spurious `e_goals ≈ 0.063`
  for keepers × the 10-pt GK-goal weight → `Var ≈ 6.3`, the entire GK over-dispersion. The position-
  eligibility gate (later generalized by the position-specification slice) drops it; `sim_sd`/realized 1.48
  → 0.97.

**Coverage-metric correction (2026-07-20) — the coverage gate was broken; see the [coverage-metric
dead-end note](#coverage-metric-artifact) below.** After the fix the corrected per-position coverage
verdict is: GK **0.802 ✅**, DEF **0.801 ✅**, MID **0.713 ❌** (*was a false pass*), FWD **0.654 ❌**.

### coverage-metric discreteness correction (2026-07-20)
*Replaces: model-redesign-coverage-metric-slice.md*

<a id="coverage-metric-artifact"></a>
FPL points are **atomic**, so `np.percentile` lands inside an atom and `[p10,p90]` is not an 80% interval:
the simulator put **47.5% of its FWD mass at/below its own `p10`**. The bonus term sharpened it — bonus adds
a continuous sliver to a discrete score, so `p10` lands at 1.02 and the modal FWD outcome `y=1` scores as
*below* the interval (76 of 154 FWD below-`p10` misses were exactly this). Replaced the gate with
**randomized-PIT coverage** (`0.10 ≤ u ≤ 0.90`, discreteness-correct by construction, reusing the PIT the
suite already computes; **no new randomness**). The pre-registered band [0.75, 0.85] is unmoved — only the
quantity it applies to changed. Both columns stay in the report: `coverage` (what a consumer of the shipped
`p10`/`p90` experiences) and `coverage_pit` (the gate). Net: MID goes pass → **fail** (recorded plainly);
DEF/GK "over-coverage" dissolves as artifact.

### scoring-rule conformance guard (2026-07-26)
*Replaces: model-redesign-scoring-conformance-slice.md*

A standing guard (`model/eval/scoring_conformance.py`, `assert_conformance`) that compose's point estimate
for each term equals `E[rule(X)]`, not `rule(E[X])` — the bug class the saves gap belonged to, which no
existing gate could see. FPL has exactly three nonlinear rules: `floor(S/3)` (saves — now exact),
`-floor(GA/2)` (conceded — always exact), `clip(·,0,3)` (bonus). **Verdict (real mart, n_sims=4000):**
every exactly-computed term conforms within Monte-Carlo error; **`bonus` is the sole non-conformer** and
its gap *is* the entire compose↔sim residual (GK −0.043, DEF −0.017, MID −0.027, FWD −0.006). Fork B ruled
**B1 — accept + document**: report the bonus clip under tolerance rather than couple `compose_points` to a
Monte-Carlo run for <0.05 pt. Generalizes `simulator_consistency` (which excluded GK — the exclusion that
hid the saves gap) to per-term, GK included. A test proves the guard trips at exactly `(GK, saves)` if the
old `E[S]/3` bug returns.

### P(play) + blank-tail — the ex-ante universe (spec X1)
*Replaces: model-redesign-pplay-blanktail-slice.md*

Score the ex-ante universe **including potential blanks**, so captaincy no longer needs the god-file's
`walk_forward_points(predict_all=True)` (the last consumer pinning `points_model.py`). Appearance is a
ladder: **P(play)** = P(minutes>0), **p60** = P(minutes≥60 | played). p60 already existed (the `minutes`
term); P(play) did not. Added `model/terms/p_play/` as its **own** per-position term (population = **all**
rows, target `played`; pool `minutes_roll3/5` + `starts_roll3`) — an upgrade over captaincy's crude pooled
inline logistic. Threaded a **`keep_all`** flag through both term bases (population retains `minutes==0`
rows; training stays `minutes>0`; prediction covers all rows) so every existing golden stays bit-identical
at the default `keep_all=False`. Compose owns de-conditioning: `compose_points(keep_all=True)` =
`p_play × E[points | played]` (the unconditional expectation over the ex-ante universe, spec X1). This
unblocked deleting the final god-file (`points_model.py`). Captaincy numbers shift by design (the universe
grows; no shipped golden to hold).

---

## Measured dead-ends

Pre-registered hypotheses that were **REFUTED** on the real mart. The code carries no trace of these (a
rejected feature is simply absent), so this section is the guardrail against rebuilding them. Each records
*what would change the verdict*.

### Correlated component draws — REFUTED (2026-07-20/21)
*Recorded in the coverage-metric + phase4 correction; `goals ⊥ assists` is now MEASURED in `model/simulate.py`.*

FWD interval narrowness was attributed to independent component draws; a "correlated draws" slice was
proposed. **Probed and rejected.** A shared attacking latent `Z ~ Gamma(1/φ, φ)` (means preserved) per
player- and team-fixture, with `goals|Z ~ Pois(λ_g·Z)`, `assists|Z ~ Pois(λ_a·Z)` — the exact mechanism —
moves FWD coverage by **−0.002** and CRPS by **0.000** even at an implausible φ=0.8 (closing the ratio this
way needs φ ≈ 6). Direct check agrees: residual `corr(g−e_goals, a−e_assists)` is DEF −0.008, MID +0.019,
FWD +0.038, **every 95% CI contains 0**; cost of assuming independence is ≤4% of attacking-points variance.
And correlation is **spread-only** — `E[4G+3A]` is unchanged by dependence, so it cannot move rankings /
transfers / captaincy at all. *Changes the verdict:* nothing plausible; the correlation isn't there to
capture.

### Parameter-uncertainty propagation — REFUTED (2026-07-26)
*Replaces: model-redesign-interval-dispersion-scoping.md*

<a id="interval-dispersion"></a>
The standing hypothesis for the residual MID/FWD interval under-coverage was that the simulator "treats its
fitted rates as exact." **Refuted, both senses measured negligible.** (1) **Coefficient uncertainty**: delta-
method `Cov(β̂) → Var(λ)` is ≤ 0.16% of the count variance everywhere (FWD goals 0.54% the max) — widens
intervals < 0.3%. (2) **Count overdispersion given λ**: Pearson dispersion is mild (DEF 1.14, FWD goals
1.16, FWD assists 1.23) — ~0.5 pt-variance total, and `check_assumptions` already judges Poisson adequate.
The narrowness is **omitted** variance, not **uncertain** rates. Honest decomposition of the residual:
mild attacking overdispersion (~0.5 pt-var), **excluded negative events** (the sim claims a defender never
gets carded — P(yellow) DEF 0.15; this matches the PIT left-skew), unsampled **bonus competitive residual**
(~0.2 pt-var), and the balance is **mean-model error** — *which interval work cannot honestly fix* (padding
uncertainty to cover a wrong mean is dishonest calibration). Ruling: **Fork A — accept the residual,
redirect to the mean model** (this became the live
[mean-features program](model-redesign-mean-features-plan.md)). Do **not** build the parameter-uncertainty
machine. Negative events (Fork B) are a valid *correctness* fix but must be mean-neutral and close only
~10–15% of the gap; NB counts (C) and bonus-residual sampling (D) are small and deferred. *Changes the
verdict:* if a mean-features slice lands and MID/FWD coverage is *still* materially short with an accurate
mean, that residual is genuine irreducible dispersion and NB counts (C) become the honest next lever —
**mean first, dispersion second.**

### Mechanistic within-fixture bonus — REFUTED (2026-07-29)
*Replaces: model-redesign-bonus-mechanistic-scoping.md · notebook: `model/terms/bonus/mechanistic_scoping.ipynb`*

Should bonus be modelled mechanistically (reconstruct each appearing player's BPS, rank all appearances in
the fixture, assign 3/2/1) instead of the incumbent per-player OLS map? **REFUTED** — all three pre-
registered BUILD conditions fail (n = 11,057 rows, 366 fully-awarded fixtures). The premise holds (bonus
*is* the within-fixture BPS rank — the oracle recovers it perfectly) but every **deployable** route loses,
because the whole prize lives in **BPS we cannot reconstruct from modelled contributions**:
- **Q2 competitive signal**: fixture-competitive returns features (`n_ahead`, `gap_to_3rd`) **degrade**
  ranking at every field position — paired Spearman delta DEF −0.092, MID −0.028, FWD −0.155, all CIs
  excluding 0 on the **wrong** side.
- **Q3 BPS reconstruction**: modelled-BPS fixture ranking recovers the actual bonus recipients in the top-3
  **worse** than plain `returns_pts` (0.715 vs 0.812 hit-rate; oracle 1.000).
- **Q4 pt-variance prize**: deployable recoverable ≈ 0.005 pt-var, mechanistic peaks 0.072 (FWD) and is
  negative at DEF — **below the 0.10 bar everywhere**; the oracle recovers ≈ the entire residual, proving
  the bottleneck is the BPS gap, not the competition structure.

Keep the OLS map — `returns_pts` is a *better* within-fixture BPS proxy than a 5-feature contribution
regression, and shipping the rewrite would force the simulator's row-batching to become fixture-aware for
≈ 0 gain. *Changes the verdict:* only a materially better BPS estimator (modelling passing/tackles/CBI/
recoveries/cards well enough to lift modelled-BPS top-3 recovery above 0.812) — absent that, the fixture
structure is inert.

---

## Gate completeness (loose-ends closure, 2026-07-30)

A finishing pass — no new capability. Every shipped term is now gated on **both** axes (ranking **and**
level), and the calibration record is brought to an honest terminal state.

- **Level gate wired into all nine terms.** `bonus`, `clean_sheet`, and `conceded` used custom `validate`
  methods that returned a ranking-only `GateResult`, so `passed_all` **silently defaulted** their level
  verdict to pass (`.get(p, True)`). Extracted a shared `model.eval.metrics.level_gate` helper (DRY;
  routes all nine terms so a *future* term inherits the level check), and a parametrised invariant test
  (`tests/test_level_gate_coverage.py`) now fails if any term ranks a position without levelling it.
- **What wiring the gate revealed (measured, documented — not fixed here):**
  - `clean_sheet` over-predicts the *player-awarded* clean-sheet rate at DEF (+33%) / MID (+49%) — a
    **grain caveat** (raw team-CS probability vs the ≥60′-gated player outcome; the bias tracks p60). See
    `team_goals_against/ASSUMPTIONS.md` §8.
  - `conceded` over-predicts the penalty at DEF (+35%), same grain mechanism.
  - `bonus` mildly over-predicts realized bonus at DEF (+12%) / FWD (+10%), absolute ≤0.034 pt — bounded
    by the accepted `clip(·,0,3)` band (Fork B1), distinct from the compose-vs-sim clip number. See
    `bonus/ASSUMPTIONS.md` §8.
  - None cascade: nothing in `serve/`/governance consumes `passed_calibration`, so no shipped number moved.

---

## Open items carried forward

Status as of the gate-completeness pass above.

- **Mean-model features** — the highest-value lever from the parameter-uncertainty refutation: opponent-
  forward / team attacking context that improves *ranking* and tightens calibration honestly. This is the
  live [mean-features program](model-redesign-mean-features-plan.md). **Open — data-gated** (odds / multi-season).
- **MID/FWD interval coverage** (`cover_pit` ~0.72/0.65, below band) — **closed as a documented residual**:
  intrinsic atomicity (the 1-pt appearance atom dominates MID/FWD, which have no downside term), not mean
  bias and not under-dispersion. A distributional-PIT recalibrator was rejected (metric-gaming, and its only
  motivation — captaincy strategies — is decision value, not calibration). See `model/eval/calibration.py`.
- **Per-position mean bias** — **closed by the position-specification slice.** The figure once recorded here
  (DEF +0.39 / FWD −0.40) *predated* that fix; post-fix the compose level bias is small and near-uniform
  (~+0.06 to +0.10 pt/GW across positions), and the DEF↔FWD cross-position distortion is gone.
- **DC unverifiable** — **documented, data-blocked** (`defensive_contribution/ASSUMPTIONS.md` §8): DC now
  runs the level gate, but against a target *derived* from unverified CBIT thresholds — there is no
  independent realized-DC column on the mart. Closing it is an ingest dependency, not a modelling change.
- **Excluded negative events** — the simulator gives every appearance 0 for yellow/red cards, own goals,
  penalty misses (P(yellow) DEF 0.15). A valid mean-neutral correctness fix (closes ~10–15% of the FWD
  coverage gap), not yet built. **Open — small, deferred.**
