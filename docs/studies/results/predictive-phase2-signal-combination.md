# Phase 2.2 — regularized signal combination (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 2.2 — closes A-F1.
**Produced:** 2026-07-08 · `minutes > 0`, DGW excluded, per position, GW > 3, expanding walk-forward.
**Code:** `model/forecast/signal_combination.py` → `walk_forward_signal_combination()`,
`selection_stability()`, `gradient_boosting_ceiling()` (A2.3).
**Question:** does combining the *full salvaged family roster* (re-tested **per component**, not on
`total_points`) under an elastic-net penalty beat **both** the Phase-0 incumbent (`base_season`) **and**
the best single candidate signal, within position, on held-out gameweeks? (Closes A-F1.)

## Model
- Per-component **`statsmodels` GLM.fit_regularized** (elastic net), NOT a Gaussian `sklearn` ElasticNetCV —
  each component keeps its evidence-picked family: goals & assists Poisson, clean sheet Binomial/logistic,
  GK saves Poisson (converted at 3 saves = 1 pt). Composed to E[points] via the FPL scoring rule.
- **Full candidate roster re-tested per component** (A-F1): `xg_roll3/5`, `xa_roll3/5`, `xgi_roll3/5`,
  `minutes_roll3/8`, `minutes_trend` (goals), `transfers_in`, `ownership_count`, `purchase_price`,
  `was_home`, `fdr_avg` (component-appropriate subsets). `xg_roll*`/`xa_roll*` built in-harness lag-safe
  (`.shift(1).rolling()`); mart carries only the composite `xgi_roll` lag-safe. `minutes_trend` is the
  ordinal string mapped to `falling/stable/rising -> -1/0/1`.
- **Both penalty knobs tuned per fit by inner *temporal* validation** (earlier GWs fit, latest 25%
  validate — never random k-fold): strength `alpha ∈ (0, .001, .003, .01, .03, .1)` **and** the L1/L2 mix
  `L1_wt ∈ (0.2, 0.5, 0.8)` (the mix governs collinear-pair grouping, so it is selected, not assumed),
  minimizing family deviance. Features standardized on train stats; intercept never penalized.
- **Best single signal** bar = oracle max `|Spearman(signal, points)|` per position (upper bound on any
  single-signal ranker). Same common eval set for all three bars (identical rows).

## Result (within-position Spearman)

| pos | base_season (incumbent) | best single signal | regularized combination | GBM ceiling | gate: beats both? |
|---|---|---|---|---|---|
| GK  | 0.012 | 0.198 (`fdr_avg`, oracle abs) | 0.118 | 0.185 | ✗ beats incumbent, not the single |
| DEF | 0.162 | 0.217 (`minutes_roll3`) | **0.237** | 0.254 | ✅ **beats both** |
| MID | 0.339 | 0.368 (`minutes_roll3`) | 0.319 | 0.369 | ✗ regresses below incumbent |
| FWD | 0.321 | 0.380 (`minutes_roll3`) | 0.331 | 0.375 | ✗ beats incumbent, not the single |

Gate/ceiling on the common eval set (`n_gw = 32` gate, `33` GBM). *Best-single rho is the winning signal's
signed correlation; the gate compares against its absolute (oracle) strength — GK `fdr_avg` is −0.198, a
0.198 ranker sign-flipped. GBM (A2.3) is an unshipped non-linear ceiling probe, not a gate leg.*

**Coverage note (delta vs the pre-remediation run):** adding `minutes_trend` — undefined in the earliest
GWs — moved the common eval set from 35 → 32 GWs, so *every* bar (incumbent included) shifted; treat these
as the current frozen numbers, not a clean method-only delta. **The verdict is unchanged: DEF is the only
position clearing both gates** (pre-remediation reg: GK 0.083 / DEF 0.248 / MID 0.308 / FWD 0.363). The
remediation tightened the *method* (tuned `L1_wt`, full roster incl. `minutes_trend`, selection receipts),
not the conclusion.

## Selection stability — what the penalty KEEPS per component (the A-F1 receipt)
`selection_freq` = share of walk-forward folds with a non-zero standardized coefficient; `mean_abs_coef` =
its average standardized magnitude. This is what demotes the family "informative" labels to a *prior* — it
shows what survived a fair, tuned elastic-net selection, not just the final composed score.

| component | durably kept (freq ≥ 0.9) | mean abs coef of leaders | weak / marginal (freq < 0.5) |
|---|---|---|---|
| goals | `purchase_price` (1.0), `xg_roll5` (1.0), `xgi_roll5` (1.0), `fdr_avg` (0.94) | 0.17–0.20 | `xg_roll3` .47, `minutes_roll3` .47, `xgi_roll3` .19, `minutes_roll8` .16 |
| assists | `fdr_avg` (1.0), `was_home` (1.0), `xa_roll5` (0.97) | 0.05–0.21 | `minutes_roll3` .40, `minutes_roll8` .43 |
| clean sheets | `fdr_avg` (0.94), `minutes_roll3` (0.94) | 0.27–0.30 | `xgc_roll5` .23, `goals_conceded_roll3` .20 |
| GK saves | `fdr_avg` (1.0) | 0.10 | `minutes_roll3` .40 |

- **Process > realized, at the roll5 horizon** (X6): `xg_roll5`/`xa_roll5` are durably kept (1.0 / 0.97)
  while the roll3 variants are marginal (~0.47) — the penalty prefers the longer process window, and the
  composite `xgi` is retained only at roll5. A concrete confirmation, not a prior.
- **`fdr_avg` is the one signal kept across *every* component** (0.94–1.0) — published fixture difficulty is
  the most consistently informative candidate, vindicating the "fixture re-enters despite family exclusion"
  expectation in the plan.
- **`purchase_price` is a strong goals signal** (freq 1.0, coef 0.18) — price proxies attacking calibre.

### `minutes_trend` (P2 — was it worth re-including?)
Selected in **0.59** of goal folds but with a **tiny coefficient (0.023)** — non-trivially informative, but
immaterial to the ranking. Re-including it was the correct call (it is not zero, so the earlier silent
exclusion was unjustified), yet it is a minor contributor, not a lever. Recorded, retained, immaterial.

### `was_home` placement (P3 — does the penalty reproduce the v2 "defensive-only" finding?)

| component | selection_freq | mean_abs_coef |
|---|---|---|
| goals | 0.531 | 0.017 |
| assists | **1.000** | 0.055 |
| clean sheets | 0.486 | 0.056 |

**No — the v2 hard-coded "venue is a defensive signal, CS-only" placement is *not* reproduced.** The penalty
keeps `was_home` **most consistently for assists (every fold)**, comparably for clean sheets, and about half
the time for goals — magnitudes small everywhere (0.02–0.06). So letting the penalty decide (keeping
`was_home` in all rosters, rather than hard-restricting to CS as in Phase 2.1 v2) was empirically right: a
CS-only restriction would have dropped an informative assists signal. The v2 finding was a ranking-impact
read at DEF; under fair selection `was_home` is a *minor but genuine attacking signal too*, not defensive-only.

## Findings
- **A-F1 closed: the regularized combination clears BOTH gates only at DEF** (0.237 > single 0.217 >
  incumbent 0.162). Under a tuned penalty and a fair per-component re-test, the family roster earns its
  place only at DEF; the "informative" labels are demoted to a prior with receipts (selection table above).
- **MID regresses (0.319 < incumbent 0.339).** A single strong signal (`minutes_roll3`, 0.368) out-ranks
  the composed multi-component model — combining components *dilutes* MID ranking; the assist/CS components
  add noise relative to a clean minutes-led ranker. Honest miss.
- **FWD and GK beat the incumbent but not the best single signal** (`minutes_roll3` at FWD 0.380; `fdr_avg`
  oracle at GK 0.198). The second gate leg (A-F1) is binding — the combination does not justify itself over
  the strongest single feature.
- **A2.3 probe (done): non-linear headroom is real but modest at the rankable positions** (DEF +0.017,
  FWD +0.044 over the reg. combination), larger at the near-chance ones (GK +0.067; MID +0.050). The
  linear-additive compositional structure leaves the most on the table where ranking is hardest — a
  recorded lever, not a reason to ship a GBM now.

## Status — gate: 1 of 4 pass (DEF), honest
Gate = beat incumbent AND best single signal, per position. **DEF ✅ / MID ✗ / FWD ✗ / GK ✗.** Consistent
with Phase 2.1 (DEF the strongest, cleanest win). A-F1 is **resolved**: the family verdicts are demoted to a
prior and the roster only earns its place at DEF under a real, tuned component-level gate — with a selection
table as the receipt. `was_home` is retained across rosters on evidence (P3), `minutes_trend` re-tested and
retained-but-immaterial (P2). Conditional on appearance throughout (X1). Recorded next levers: FWD/MID
single-signal rankers may beat composition; non-linear interactions (A2.3) for the harder positions.
