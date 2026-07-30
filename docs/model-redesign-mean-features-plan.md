# Smarter mean models — systematic feature program (one model × one context at a time)

**Status:** plan (grounded in a measurement; step 1 confirmed) · **Type:** spec
**Parent:** [interval-dispersion scoping](model-redesign-interval-dispersion-scoping.md) (fork A:
improve the mean, not the interval). **Goal:** improve the *mean* forecasts by adding fixture/opponent/team
context, one feature at a time, each accepted only if it passes **both** gates (ranking **and** level) out
of sample. Better means help ranking *and* tighten calibration honestly.

## Which models — and why these

The mean models feeding `e_points`, with their current context and headroom:

| model | uses fixture/opponent context today? | ranking now (Spearman) | priority |
|---|---|---|---|
| **assists** | **no** — own rolling form only | DEF 0.07, MID 0.10, FWD 0.11 | **1 (weakest rank, high stakes)** |
| **goals** | **no** — own rolling form only | DEF 0.03, MID 0.15, FWD 0.17 | **2 (haul stakes at FWD; DEF near-chance)** |
| team_goals_against → CS/conceded | **yes** (`was_home`, `fdr_avg`) | already contextual | 4 (add opponent *attack*) |
| saves | no (own xGC form) | GK only, modest | 5 |
| minutes / p_play | no (own minutes form) | availability, different signal class | 6 (rotation/injury, not "smarter rate") |

The headline: **the defensive side already uses fixture context; the attacking side (goals, assists) does
not.** That asymmetry is the opportunity — attacking returns are where the unused opponent signal lives and
where the stakes (hauls, captaincy) are highest.

## Which context — grouped, with build cost

| # | context feature | what it captures | on the mart? | cost |
|---|---|---|---|---|
| **A** | `fdr_avg` (fixture difficulty) | crude tier of how hard the opponent is | **yes** | none — test now |
| B | `opp_xgc_forward` (opponent's conceded xG, rolling) | the *specific* opponent's defensive weakness — sharper than A | no | opponent join |
| C | `team_xg_roll3` (own team attacking form) | is my team creating chances (a striker in a hot attack) | no | team aggregation |
| D | `was_home` (home/away) | flat home advantage | yes | none — but **measured weak, deprioritize** |
| E | opponent *attacking* strength | for CS/conceded: how likely the opponent scores | no | opponent join |

## Step 2 result (B `opp_xgc_forward` — BUILT, MEASURED, **REFUTED**)

The sharper opponent signal was built and tested against the crude tier, and **it loses.** A dynamic,
defence-specific rolling conceded-xG does **not** beat FPL's static one-number-per-team `fdr_avg`.

Built exactly as scoped: `dal.pipeline.load_opponent_map` (sibling of `load_fixture_map`) recovers the
opponent identity the mart drops; `model.features.build.add_opponent_xgc_forward` aggregates `xgc` to a
team-fixture frame, lag-rolls it at TEAM grain (`shift(1).rolling(5)` — lag-safe at opponent-team grain,
asserted by `assert_lag_safe_team`, first fixture NaN), and broadcasts it onto players keyed on the
**opponent**. Coverage holes (an opponent playing a DGW that gw has no team row) are filled with the
strictly-prior league-average conceded-xG, so the scored population is same-`n` as fdr-only (measured
NaN rate on the scored population = 0.0000, no silent row loss).

Walk-forward on the full 2025-26 mart, pooled per-(gw, position) Spearman with a block-bootstrap CI:

| | BEATS: opp_xgc − fdr | ABLATION: drop opp_xgc from (fdr+opp) | verdict |
|---|---|---|---|
| **goals** | **−0.0126**, CI [−0.0206, −0.0031] | −0.0032, CI [−0.0083, +0.0020] | worse standalone; not complementary |
| **assists** | **−0.0183**, CI [−0.0351, −0.0032] | −0.0034, CI [−0.0092, +0.0015] | worse standalone; not complementary |

Absolute pooled ρ makes it plain: goals base 0.117 → **+fdr 0.128** → +opp_xgc **0.115** (below the
no-opponent base — net-negative noise); assists base 0.092 → **+fdr 0.107** → +opp_xgc **0.089**. Adding
opp_xgc *on top of* fdr degrades fdr; dropping fdr from the both-design significantly hurts (goals
+0.0094 SIG) — fdr is **not** subsumed. Well-powered (105/107 cells, 35 gws × positions); level gate OK;
w3 correlates 0.83 with w5, so the window does not rescue it.

**Read.** FPL's `fdr_avg` (a low-variance 2–5 tier, market/strength-derived) is a *cleaner* monotone
difficulty signal than a noisy 5-game mean-per-appeared-player conceded-xG (minutes-entangled crude
proxy). "Redesign our own FDR from rolling conceded-xG" is refuted — the crude tier wins. **Decision:**
keep `fdr_avg`; do **not** materialize `opp_xgc_forward` into `selected` (no opponent join paid in prod);
`opp_xgc_forward` removed from both pools. The build + accessor + lag-safety machinery are kept as tested
infrastructure should the minutes-aware opponent variant (`team_xgc_minutes_aware`) ever be revisited.

## Step 3 result (C `team_xg_roll3` — MEASURED, **REFUTED / NULL**)

Own-team attacking form (sum of the team's xG, rolled over 3 games, broadcast to the team's players)
adds **nothing** to the shipped design. Walk-forward, pooled per-(gw, position) Spearman, block-bootstrap CI:

| | ADD team_xg to shipped selected(+fdr) | ADD team_xg to a THIN base (no own xG/xA rolls) |
|---|---|---|
| **goals** | +0.0003, CI [−0.0013, +0.0021] (ns) | −0.0007, CI [−0.0031, +0.0019] (ns) |
| **assists** | −0.0008, CI [−0.0025, +0.0013] (ns) | −0.0027, CI [−0.0058, +0.0012] (ns) |

Per-position CIs all span 0 (goals DEF/MID/FWD; assists too — the assists-GK "SIG" is a degenerate
n=4 point-interval artifact). It is not merely *subsumed* by the own-xG rolls (it's null even without
them): within a (gw, position) ranking cell `team_xg` is the **same value for every player on a team**,
so it can only separate players by which team they're on — and a player's own involvement roll + `fdr`
already carry that. **Decision:** do not ship; removed from both pools. (Same failure family as step-2:
a context re-aggregation of data already in the design, fighting through the ~88%-weekly noise floor.)

### The attacking/defensive asymmetry (the mechanistic "why")

Matching signal to return exposes why the attacking-side gains are so small. Fixture context (`fdr`)
is a **weak** lever for attacking returns but a **strong** one for defensive returns:

| axis | value of `fdr` context | does a rolling form feature beat / add to `fdr`? |
|---|---|---|
| attacking returns (goals/assists, player grain) | **+0.01** Spearman | no — opp_xgc, team_xg all null/worse |
| defensive returns (clean sheets, team grain) | **+0.12** Spearman [+0.06,+0.20] | no — opp attack-xG roll is −0.11 vs fdr, +0 on top |

A clean sheet is a team-level, opponent-driven event (are you facing City or a relegation side?); a goal
is a rare, luck-heavy individual event (~88% of a player's week-to-week points variance is irreducible).
So fixture context *matters ~10× more on the defensive side* — but (a) the magnitudes are on different
grains (team CS-ranking vs player goal-ranking), so it is a direction not a clean 10×, and (b) **`fdr_avg`
already captures it**: `team_goals_against` ships `fdr_avg` (that is why it is the "contextual" model).
On both attack and defence the fixture axis is real but **owned by `fdr`**; no rolling own/opponent form
re-encoding beats or supplements it. The remaining headroom is new information (odds / implied fixture
goals) or a different axis (minutes / availability — the largest *predictable* weekly lever), not more
context aggregations of past results.

## Measurement so far (step-A confirmed, the method demonstrated)

Adding the already-materialized `fdr_avg` to the attacking designs, walk-forward, within-position Spearman
delta vs the shipped model:

| | goals | assists |
|---|---|---|
| DEF | +0.008 | **+0.021** |
| MID | +0.010 | +0.009 |
| FWD | **+0.014** | **+0.020** |

Positive everywhere; largest for assists and for FWD goals (the haul position). `was_home` added on top:
mixed and near-zero — dropped. **Read:** opponent difficulty is a real, unused ranking signal for
attacking returns, and even the crude tier helps — so the sharper `opp_xgc_forward` (B) is worth building.
Caveat: deltas are **small** (0.01–0.02). Attacking returns are low-rate and noisy; gains here are
incremental and compound, not transformative — and each must clear a significance bar, not the eyeball.

## The test protocol (the discipline — identical for every cell)

For each (model × one context feature):
1. Add **one** feature to that model's `selected` design; refit walk-forward (fit `gw<t`), per position.
2. **Accept iff** it improves the **ranking gate** (within-position Spearman) *and* does not worsen the
   **level gate** (`position_bias` — no new per-position mean bias). Both gates already exist.
3. **Significance, not eyeball:** paired block-bootstrap the Spearman delta over gameweeks
   (`metrics.block_bootstrap_ci`); the delta's CI must exclude 0. Deltas are 0.01–0.02, so this matters.
4. One feature at a time so each effect is attributable (no confounded bundles), mirroring the
   position-intercept slice.

## Cost-ordered sequence (one reviewable commit each)

1. **A → goals + assists (now, zero build).** Materialize `fdr_avg` into the two attacking `selected`
   pools; keep it only where steps 2–3 of the protocol pass. Ships immediately (confirmed positive). Test
   `was_home` in the same commit; expect to drop it.
2. **Build + test B (`opp_xgc_forward`). — DONE, REFUTED (see "Step 2 result" above).** Built the
   opponent join + team-grain roll; measured it **worse** than the crude `fdr_avg` on both goals and
   assists (significantly negative beats-fdr CI). Kept fdr; shelved opp_xgc; kept the build machinery.
3. **Build + test C (`team_xg_roll3`). — DONE, REFUTED / NULL (see "Step 3 result" above).** Own-team
   attacking form adds ~0 to goals/assists (CIs span 0), even without the own-xG rolls. Removed from both
   pools. The defensive-side probe showed fixture context is ~10x more valuable for clean sheets — but
   `fdr_avg` already holds it (shipped in `team_goals_against`).
4. **E for the CS/conceded side** (opponent attacking strength) — the defensive analogue. **Previewed
   during step-3** (opponent rolling attack-xG on the team-GA clean-sheet ranking): it is −0.11 vs `fdr`
   and adds ~0 on top of it — same result as the attacking side. `fdr_avg` (already shipped in
   `team_goals_against`) owns the defensive fixture signal too; a rolling opponent-attack feature is not
   worth building. Not pursued further.
5. saves (opponent shot volume) and minutes/p_play context — lower priority, revisit after 1–4.

## Guardrails
- Every candidate is **declared in the term's `spec.py`** (features are data, not hardcoded) before it is
  drawn — the pools already list B/C/E as not-yet-built candidates, so this is materializing the plan of
  record, not inventing features.
- `minimal` stays the fixed mechanistic bar; new context enters `selected` only.
- Both gates green + block-bootstrap significance before any feature ships. A feature that fails the
  bootstrap is **inconclusive** and dropped, not shipped on a positive point estimate.
- Full `pytest` + 6/6 contracts + ruff each commit; re-freeze the affected term goldens (a design change
  moves shipped numbers, as with the position slice).

## Recommendation (updated after steps 1–3)

Step 1 shipped `fdr_avg` (small but real, +0.01). Steps 2 and 3 — and the step-4 defensive preview — all
came back **null-or-worse**: no rolling own-team or opponent form re-encoding (conceded-xG, goals
conceded, clean-sheet rate, minutes-aware variants, team attack-xG, Elo, opponent-attack) beats or
supplements `fdr_avg`, on either the attacking or the defensive side. Combined with the variance
decomposition (**~88% of a player's week-to-week points variance is irreducible weekly noise**; only
~12% is stable between-player signal), the read is that **the fixture/context axis is essentially
saturated by `fdr_avg`** — the mart's current features have exhausted the easily-reachable predictable
ranking signal.

**Where the remaining headroom is** (not more context aggregations of past results):
- **New information** the mart lacks — bookmaker odds / implied fixture goals (the one thing likely to
  carry signal `fdr` doesn't: it prices injuries, rotation, and motivation in real time), or set-piece /
  penalty-taker role.
- **The availability axis** — a benched player scores ~0, which is far more *predictable* than whether a
  goal fires; the largest predictable weekly lever, and a different modelling problem (the `minutes` /
  `p_play` terms) than rate-sharpening context features.

Steps 5+ (saves/minutes context) are lower priority; the honest next bet is odds ingestion or the
availability axis, not another feature in this table.
