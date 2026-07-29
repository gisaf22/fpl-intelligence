# Mechanistic within-fixture bonus — scoping (measure before building)

**Status:** scoping (PRE-REGISTERED; verdict below) · **Type:** spec
**Question:** the incumbent bonus term is a **per-player OLS map** `returns_pts → E[bonus]`
(`model/terms/bonus/bonus.py`). It ignores that bonus is **competitive across every appearing
player in the fixture** (both teams, starters + subs who got on) and that the field is stochastic.
Should bonus instead be modelled **mechanistically** — compute each appearing player's BPS from their
contributions, rank all appearances in the fixture, assign 3/2/1 — or is the competitive signal too
small / too unreconstructable to be worth the rewrite?

The prior from `docs/model-redesign-interval-dispersion-scoping.md` (Fork D) is that this is a **small
prize**: the unexplained `Var(bonus | own returns)` is ~0.20–0.23 pt-var per position and Fork D says
**defer**. This scoping tests that prior honestly before any simulator change.

## Pre-registration (written before looking at Q1–Q4 numbers)

Scored population = the incumbent's: `minutes > 0` & non-DGW (`BonusModel.population`). The physical
match is reconstructed by `fixture_id` (from `dal.intermediate.int_player_fixture`, one fixture per
player-GW on non-DGW rows); it groups **all appearing players of both teams** — the competitive field.
Realized `bonus` and `bps` are both mart columns; we measure against realized truth and do **not** trust
the FPL BPS formula — reconstructability is measured empirically.

### Q1 — CEILING (the floor any rewrite must beat)
How much of realized `bonus` does the incumbent per-player map already capture?
- **Metric:** within-`(gw, position)` `Spearman(e_bonus, bonus)` (`grouped_spearman`) and the level
  (`position_bias(e_bonus, bonus)`).
- Reported as the floor: a mechanistic allocator that does not beat this is not worth building.

### Q2 — COMPETITIVE RESIDUAL (is the fixture signal real?)
Does conditioning on the **fixture** improve bonus prediction beyond own returns?
- Within each `fixture_id`, rank appearing players by `returns_pts`. Build two walk-forward
  (`gw < t`) per-position OLS predictors of realized `bonus`, clipped `[0, 3]`:
  - **(a)** `returns_pts` alone (the incumbent).
  - **(b)** `returns_pts` + within-fixture **competitive features of returns**: the count of fixture
    appearances with strictly higher `returns_pts` (`n_ahead`, the deployable competitive count) and the
    gap to the fixture's 3rd-best `returns_pts` (`gap_to_3rd`). These use only modelled returns — no
    realized `bps` — so they are deployable at composition time.
- **Metric:** paired per-`(gw, position)` `Spearman(pred, bonus)` **delta (b − a)**, block-bootstrapped
  over the per-GW series (`block_bootstrap_ci`). Report the point delta, the 95% CI, and n/power
  (n_gw, mean rows/cell) per position.
- **Significance rule:** the competitive signal is **real for a position** iff its 95% CI **excludes 0**.

### Q3 — BPS RECONSTRUCTION (the error a mechanistic allocator inherits)
How much of realized `bps` is reconstructable from the **modelled** contributions?
- Per position, regress realized `bps` on `[goals_scored, assists, clean_sheets, saves,
  defensive_contribution]` (walk-forward OLS). Report `R²`, `Spearman(fitted_bps, bps)`, and the
  **residual `bps` variance** `Var(bps − fitted)`.
- This sizes the BPS a mechanistic allocator **cannot** see (passing / tackles / CBI / recoveries /
  cards). A within-fixture ranking built from modelled contributions inherits this error.
- **Tracking check:** does a within-fixture ranking by *modelled-contribution BPS* place the actual
  3/2/1 recipients in the fixture top-3 at a rate materially above the own-`returns_pts` ranking? Report
  the top-3 hit-rate (share of realized bonus recipients ranked in the fixture's modelled top-3) for the
  modelled-BPS ranking, the returns_pts ranking, and the **oracle** realized-`bps` ranking.

### Q4 — PT-VARIANCE PRIZE (is it material?)
Translate the residual into points-variance per position and compare to the ~0.2 pt-var reference.
- `bonus` **is** points (0/1/2/3 pts), so `Var(bonus | ·)` is already pt-variance.
- Report per position: `Var(bonus)`, `Var(bonus | model a)` (should ≈ the doc's ~0.2), the
  **recoverable** variance `Var(a) − Var(b)` (what the deployable competitive feature actually removes),
  and the **oracle** ceiling `Var(a) − Var(oracle)` using within-fixture realized-`bps` rank (the most a
  perfect within-fixture allocator with perfect BPS could recover).
- **Materiality rule:** the prize is **material** iff the recoverable variance `Var(a) − Var(b)` exceeds
  **0.10 pt-var** at **≥ 2 positions**. (0.10 ≈ half the ~0.2 total residual; mirrors the established
  "material, not merely detectable" bar in `metrics.MATERIAL_BIAS_FRAC`.)

### DECISION RULE (pre-registered — all three required to BUILD)
**BUILD** the mechanistic within-fixture allocator **iff**:
1. **Q2** competitive delta CI excludes 0 at **≥ 2 positions**, AND
2. **Q4** recoverable pt-variance `Var(a) − Var(b)` > **0.10** at **≥ 2 positions**, AND
3. **Q3** BPS residual is small enough that the modelled-contribution fixture-ranking tracks realized
   bonus — operationalized as modelled-BPS top-3 hit-rate materially above the returns_pts baseline
   (and within reach of the oracle).

**Otherwise REFUTED** — keep the OLS map, document why (like parameter-uncertainty and correlated-draws).
Shipping a within-fixture rewrite that buys ~0 pt-variance is the failure mode to avoid.

<!-- RESULTS BELOW — pre-registration above is frozen. -->

---

## Verdict: REFUTED — do not build the mechanistic within-fixture allocator; keep the OLS map

Measured on the scored population: **11,057 player-GW rows, 366 fully-awarded fixtures, GW 1–38**
(DEF 3,797 · MID 5,148 · FWD 1,374 · GK 738). Notebook:
[`model/terms/bonus/mechanistic_scoping.ipynb`](../model/terms/bonus/mechanistic_scoping.ipynb).

All three BUILD conditions **fail**. The premise (bonus **is** the within-fixture BPS-rank — the oracle
recovers it perfectly) holds, but every deployable route to it loses to the incumbent, because the whole
prize lives in **BPS we cannot reconstruct from the modelled contributions**.

### Q1 — CEILING (the floor a rewrite must beat)
Within-`(gw, position)` `Spearman(e_bonus, bonus)` — the incumbent already captures the ranking:

| position | Spearman (ceiling) | n_gw | n | level bias | rel_bias |
|---|---|---|---|---|---|
| GK | 0.508 | 33 | 678 | +0.008 | +3.9% (ok) |
| DEF | 0.526 | 35 | 3,483 | +0.022 | +12.9% |
| MID | 0.554 | 35 | 4,707 | +0.005 | +2.2% (ok) |
| FWD | 0.765 | 35 | 1,276 | +0.036 | +11.0% |

Level bias is a small over-prediction (≤0.04 pt absolute); the DEF/FWD `rel_bias` trips the 10% flag but is
practically negligible. This is a high floor.

### Q2 — COMPETITIVE RESIDUAL (is the fixture signal real *and useful*?)
Paired within-`(gw, position)` `Spearman(pred, bonus)` **delta (competitive − incumbent)**, 95%
block-bootstrap CI. **A useful competitive signal needs the CI above 0.**

| position | delta (b − a) | 95% CI | n_gw | ~rows/cell | verdict |
|---|---|---|---|---|---|
| GK | −0.007 | [−0.015, +0.001] | 33 | 20 | ns (touches 0) |
| DEF | −0.092 | [−0.107, −0.077] | 35 | 100 | **sig NEGATIVE** |
| MID | −0.028 | [−0.034, −0.019] | 35 | 134 | **sig NEGATIVE** |
| FWD | −0.155 | [−0.174, −0.127] | 35 | 36 | **sig NEGATIVE** |

The fixture-competitive returns features (`n_ahead`, `gap_to_3rd`) **degrade** the ranking at every field
position — the CI excludes 0 on the **wrong side**. Robust to feature subset: `n_ahead`-only and
`gap`-only deltas are ≤ 0 everywhere (MID `n_ahead`-only is +0.0008, negligible). Cause: `returns_pts` is
a coarse, tied, cross-position quantity, so a defender's *returns* rank in the fixture is a poor proxy for
their *BPS* rank (defensive BPS isn't in returns) — the feature adds noise, not signal. **Condition 1 fails**
(no position shows a real *improvement*).

### Q3 — BPS RECONSTRUCTION (the error a mechanistic allocator inherits)
Per-position OLS `bps ~ [goals, assists, clean_sheets, saves, defensive_contribution]`:

| position | R² | Spearman | residual bps SD | residual bps var |
|---|---|---|---|---|
| GK | 0.827 | 0.857 | 4.37 | 19.1 |
| DEF | 0.772 | 0.780 | 5.41 | 29.3 |
| MID | 0.806 | 0.837 | 4.67 | 21.9 |
| FWD | 0.922 | 0.771 | 4.08 | 16.6 |

Modelled contributions explain 77–92% of BPS variance, but the **residual is 4–5 BPS SD** — larger than
the BPS gaps that separate bonus tiers. The decisive check is the **fixture top-3 recovery** of the 1,066
realized bonus recipients:

| ranking score | top-3 hit-rate |
|---|---|
| `returns_pts` (incumbent) | **0.812** |
| modelled BPS (from contributions) | 0.715 |
| oracle (realized `bps`) | 1.000 |

Ranking a fixture by *modelled* BPS recovers the actual recipients **worse than plain `returns_pts`** — the
5-feature reconstruction adds noise the incumbent's cleaner proxy avoids. Only the oracle (which we cannot
have) is perfect. **Condition 3 fails.**

### Q4 — PT-VARIANCE PRIZE (is it material?)
`bonus` is points, so `Var(bonus | model)` is pt-variance. `Var(a)` reproduces the interval-dispersion
doc's ~0.20–0.23 residual. Recoverable = `Var(a) − Var(model)`:

| position | Var(bonus) | Var(a) incumbent | recov_b (deployable OLS) | recov_mech (modelled-BPS allocator) | recov_oracle (ceiling) |
|---|---|---|---|---|---|
| GK | 0.425 | 0.280 | 0.005 | 0.049 | 0.280 |
| DEF | 0.345 | 0.226 | 0.004 | −0.002 | 0.226 |
| MID | 0.452 | 0.219 | 0.003 | 0.024 | 0.219 |
| FWD | 0.725 | 0.271 | 0.006 | 0.072 | 0.271 |

The deployable competitive OLS recovers ~**0.005** pt-var; the mechanistic modelled-BPS allocator peaks at
**0.072** (FWD) and is **negative** at DEF — **below the 0.10 bar at every position**. The oracle recovers
essentially the *entire* residual (≈ Var(a)), which means **the whole prize is the BPS-reconstruction gap
(Q3), not the competition structure** — and that gap is exactly what modelled contributions cannot close.
**Condition 2 fails.**

### Decision-rule evaluation

| condition (all required to BUILD) | result |
|---|---|
| 1. Q2 competitive delta CI excludes 0 **above** at ≥2 positions | ❌ every significant delta is **negative** |
| 2. Q4 recoverable pt-var > 0.10 at ≥2 positions | ❌ max deployable 0.006, max mechanistic 0.072 |
| 3. Q3 modelled-BPS fixture ranking beats the returns baseline | ❌ 0.715 < 0.812 top-3 recovery |

→ **REFUTED.** Keep the per-player OLS map. This joins parameter-uncertainty and correlated-draws as a
measured dead end. Shipping the within-fixture rewrite would buy ≈ 0 pt-variance while making the bonus
ranking *worse* and forcing the simulator's row-batching to become fixture-aware — the exact failure mode
this scoping existed to prevent. It also **strengthens** the incumbent: `returns_pts` is a *better*
within-fixture BPS proxy than a 5-feature contribution regression, and the competition cannot be exploited
without realized BPS, which no term can produce.

### What would change the verdict
The prize is bottlenecked by BPS reconstruction (Q3), not by the competition (Q4 oracle ≈ full residual).
So the allocator only becomes worth building if a **materially better BPS estimator** appears — modelling
the *unreturns* BPS (passing / tackles / CBI / recoveries / cards) well enough to lift the modelled-BPS
top-3 recovery **above** the 0.812 `returns_pts` baseline and the mechanistic recoverable pt-var above 0.10
at ≥2 positions. Absent that, the fixture structure is inert. Consistent with Fork D ("defer") in
`docs/model-redesign-interval-dispersion-scoping.md`; the higher-value lever remains **better mean
features** (Fork A), which improve ranking without this dishonesty/complexity risk.

### If ever revisited (BUILD is NOT triggered — noted for completeness)
A future BUILD would re-freeze several goldens and is out of scope here: `test_bonus` (the term contract),
the `simulate.py` seed-pinned regression vector and its rng draw-order (bonus would move from a per-row
`bonus_intercept/slope` map to a per-fixture draw), the calibration vector, and the row-batching in
`_iter_draw_batches` — which would have to become **fixture-aware** (draw all appearing players of a
fixture together via `_draw_team_ga`'s per-fixture grouping, rank by drawn modelled-BPS + a fitted
residual, assign 3/2/1 with FPL tie handling). None of this is implemented, per the REFUTED verdict.
