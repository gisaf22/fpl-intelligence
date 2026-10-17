# Captaincy on a realistic pool — were the pooled tests measuring the wrong decision?

**Audits:** [predictive-phase5-decisions.md](predictive-phase5-decisions.md),
[predictive-phase5-captaincy-diagnostic.md](predictive-phase5-captaincy-diagnostic.md),
[predictive-phase5-captaincy-diagnostic-rerun.md](predictive-phase5-captaincy-diagnostic-rerun.md).
**Produced:** 2026-08-14 · **Run against commit:** `c475873` (working tree: `model/eval/captaincy_backtest.py`
and `model/eval/captaincy_diagnostics.py` modified; frozen study numbers no longer reproduce against
current code — see *Drift* below).
**Code:** `model/eval/captaincy_backtest.py` (`lagged_ownership`, `captaincy_paired_deltas`, pool
attrs on `captaincy_backtest`), `model/eval/captaincy_diagnostics.py` (`oracle_rank_hits`).
35 GWs, N=2000 sim draws, `minutes_roll3 >= 45` availability gate throughout.

## Why

Every captaincy test to date scored strategies over the pool-free universe — a **median of 219
eligible candidates per gameweek**. No manager makes that decision; they captain from the 15 they own,
realistically 2–4 credible options. If the decision being measured is not the decision being made, the
"largely irreducible" verdict may be an artifact of the universe rather than a fact about captaincy.

## Ownership provenance — pre-deadline, confirmed

**Column used: `ownership_lag`**, constructed by `lagged_ownership()` as the GW-(N−1) snapshot of
`ownership_count` (shift-1 within player, then forward-fill). This is **pre-deadline under any reading**.

The mart carries only `ownership_count`, sourced from the FPL `selected` field
(`dal/staging/contracts/player_histories.yaml`, *"number of FPL managers who owned this player at
fixture time"*). That is deadline-locked for the GW it is recorded against, so it is arguably already
ex-ante — but it is the value recorded *for the GW being scored*, so the conservative GW-1 snapshot was
used as instructed. Measured evidence that the contemporaneous column is nonetheless close to clean:

| test | value | reading |
|---|---|---|
| corr(Δownership[N], points[N−1]) | **+0.368** | ownership moves in response to *last* GW — the pre-deadline signature |
| corr(Δownership[N], points[N]) | +0.116 | would be the leak, if real |
| …partialling out points[N−1] | **+0.033** | collapses 72% — mediated by points autocorrelation (+0.236), not a direct same-GW leak |
| corr(own[N], points[N]) vs corr(own[N−1], points[N]) | 0.232 vs 0.222 | a 0.010 gap; a post-hoc snapshot would show far more |

One correctness detail: BGW rows carry a contract-imposed `ownership_count = 0`
(`dal/fct/fct_player_gameweek.py:143`) — an absence-of-fixture marker, not an ownership reading. These
are masked to NaN before the shift so a blank gameweek does not drop a player out of the pool at a
spurious zero.

**This also fixes a latent issue in the frozen work:** the Phase-5 secondary "ownership top-50" view
built its pool from *contemporaneous* `ownership_count`. Per the measurement above the practical
impact is small, but the frozen doc's secondary view was selecting on the scored GW's own reading.

## Benchmark warning (carried per instruction)

**`template` ranks by ownership — the same variable that defines a top-N pool.** Its task gets
mechanically easier as N shrinks (in a top-10 pool it is choosing among the 10 most-owned, and its own
ranking criterion is that ownership). Its numbers are **not comparable across pool sizes** and it is
not used as a benchmark anywhere below. **`base_season` is the primary benchmark throughout.**

## Test 2 — headroom (run first)

| pool | median n | oracle pts/GW | oracle 95% CI | best strategy | **headroom** | realized spread (range) | spread (IQR) |
|---|---|---|---|---|---|---|---|
| full | 219 | 16.66 | [15.97, 17.54] | model_mean 6.14 | **10.51** | 18.00 | 3.16 |
| top-50 | 50 | 15.20 | [14.54, 16.17] | base_season 6.00 | **9.20** | 15.57 | 4.27 |
| top-20 | 20 | 12.89 | [11.54, 14.11] | base_season 6.06 | **6.83** | 12.94 | 4.24 |
| top-10 | 10 | 11.69 | [10.06, 13.23] | base_season 6.06 | **5.63** | 11.14 | 3.76 |

Full-pool oracle reproduces at **16.66**, matching the frozen doc exactly — the harness is sound.

**Stopping-rule judgment (pre-registered): DO NOT STOP.** The rule was to halt if restricted-pool
headroom were small relative to the ~1.1 pts/GW best-to-worst strategy spread already seen on the full
pool. It is not: headroom is **5.63 pts/GW at top-10 (5.1× the 1.1 reference)** and **6.83 at top-20
(6.2×)**. Even in the tightest pool a manager leaves ~5.6 pts/GW on the table, and the realized
within-GW range is 11.14 pts. There is plenty to play for. Test 1 proceeds.

### Position composition — restricting by ownership changes the decision

| pool | pool mix | realized oracle mix |
|---|---|---|
| full | MID 42.5% / DEF 38.4% / FWD 9.9% / GK 9.1% | MID 15 / DEF 13 / FWD 7 / GK 0 |
| top-50 | DEF 33.3% / MID 31.9% / GK 18.0% / FWD 16.7% | MID 14 / FWD 12 / DEF 7 / GK 2 |
| top-20 | MID 34.4% / DEF 33.7% / FWD 20.9% / GK 11.0% | **FWD 15** / DEF 12 / MID 6 / GK 2 |
| top-10 | MID 30.6% / FWD 27.4% / DEF 25.4% / GK 16.6% | **FWD 15** / DEF 9 / MID 9 / GK 2 |

**The best captain flips from midfielder to forward as the pool tightens.** On the full pool the
oracle is a MID in 15/35 GWs and a FWD in 7; inside a top-20 pool the oracle is a **FWD in 15/35** and
a MID in only 6. Forwards are 9.9% of the full pool but 27.4% of a top-10 pool — highly-owned players
skew forward, and among them forwards win the week most often. GKs never win the full-pool oracle but
take 2 GWs in every restricted pool.

This matters for interpretation: the pooled tests were characterising a MID-dominated decision, while
the decision managers actually face is FWD-dominated. It does **not**, however, rescue any strategy —
see Test 1.

## Test 1 — does the choice matter within a realistic set?

### Paired deltas vs base_season (block-bootstrap CI on the within-GW difference)

| pool | strategy | mean Δ vs base_season | 95% CI | beats benchmark? |
|---|---|---|---|---|
| full | model_mean | +0.14 | [−1.46, +1.29] | no |
| | ceiling_phaul | 0.00 | [−1.46, +1.40] | no |
| | ceiling_p90 | −0.46 | [−1.97, +0.60] | no |
| top-50 | ceiling_phaul | −0.26 | [−1.63, +1.06] | no |
| | model_mean | −0.29 | [−1.89, +0.89] | no |
| | ceiling_p90 | −0.51 | [−2.09, +0.63] | no |
| top-20 | ceiling_phaul | −0.83 | [−1.86, 0.00] | no |
| | ceiling_p90 | −1.34 | [−2.66, **−0.51**] | no — *significantly worse* |
| | model_mean | −1.46 | [−2.83, **−0.57**] | no — *significantly worse* |
| | model_mean_x_pplay | −1.54 | [−2.94, **−0.63**] | no — *significantly worse* |
| top-10 | ceiling_phaul | −0.09 | [−1.40, +1.26] | no |
| | model_mean | −0.57 | [−1.89, +0.77] | no |
| | ceiling_p90 | −0.74 | [−1.91, +0.12] | no |

**Pre-registered win condition not met in any pool.** No strategy beats `base_season` with a delta CI
excluding zero — not at top-50, top-20, or top-10. Restricting to a realistic pool does not rescue the
model. At **top-20 the result runs the other way**: `model_mean`, `model_mean_x_pplay` and
`ceiling_p90` are *significantly worse* than a season average (CIs entirely below zero). `ceiling_phaul`
is the most robust model strategy — nearest to parity in every pool and never significantly worse —
but "never significantly worse than a season average" is not a win.

### hit@1 against the correct per-pool chance baseline

This is where the frozen doc was most misleading. Its Q2 read *"hit@1 ≈ chance for every strategy
(base 0.03 … chance 0.005)"* — but 0.03 vs 0.005 is **6× chance**, described as "≈ chance". With the
proper baseline (1/N) and an exact binomial test:

| pool | chance | base_season | e_points | p90 | p_haul | ownership |
|---|---|---|---|---|---|---|
| full (n=219) | 0.005 | 1/35, p=0.15 | 1/35, p=0.15 | 1/35, p=0.15 | 1/35, p=0.15 | 1/35, p=0.15 |
| top-50 | 0.020 | **5/35, p=0.0006** | 3/35, p=0.033 | 3/35, p=0.033 | **4/35, p=0.005** | 3/35, p=0.033 |
| top-20 | 0.050 | **8/35, p=0.0003** | 4/35, p=0.096 | 5/35, p=0.029 | **6/35, p=0.007** | 6/35, p=0.007 |
| top-10 | 0.100 | **11/35, p=0.0004** | 9/35, p=0.006 | 10/35, p=0.002 | **11/35, p=0.0004** | 8/35, p=0.020 |

**The oracle IS identifiable above chance inside a realistic pool.** At top-10, `base_season` and
`p_haul` each land the exact best captain in 11 of 35 GWs against a 3.5-GW chance expectation
(p=0.0004). The frozen "unpredictable ex-ante" conclusion was an artifact of a 219-candidate universe
where every strategy scores exactly one hit and nothing is separable — genuinely non-significant there
(p=0.15), but the right description was *underpowered*, not *≈ chance*.

## Verdict

**The pooled tests were measuring a decision no manager faces — but fixing that does not change the
answer.** Both halves must be stated:

1. **The universe critique is valid and the frozen tests understated skill.** There is real headroom in
   a realistic pool (5.6–6.8 pts/GW), the oracle is significantly identifiable there (p<0.01 for four
   of five strategies at top-10, vs an uninterpretable p=0.15 on the full pool), and the decision
   changes character — it becomes FWD-dominated rather than MID-dominated.
2. **No strategy converts that into points over a season average.** Every paired delta CI includes
   zero, in every pool. `base_season` is *also* above chance — in fact it has the best or joint-best
   hit@1 in all three restricted pools — so all the identification skill on offer is skill a season
   average already has. At top-20 the model strategies are measurably worse.

So **"largely irreducible" survives the realistic-pool test**, but the reason is now sharper and less
defeatist than the frozen framing. It is not that the best captain is unknowable — inside a real pool
he is found ~3× more often than chance. It is that **`base_season` already extracts essentially all of
the available identification, and the model adds nothing on top of it.** The residual 5.6 pts/GW of
headroom is haul-timing variance that no strategy tested here converts.

For the shipped ranker (`serve/captain.py`, which ranks by `p_haul`): `ceiling_phaul` is the only model
strategy never significantly worse than `base_season` in any pool, and it ties `base_season` for best
hit@1 at top-10 (11/35). That is a defensible thing to ship — but this evidence does not establish it
beats a season average, and the doc should not be read as saying so.

## Drift — frozen numbers do not reproduce

Run against `c475873`. Full-pool strategy means have moved since the frozen Phase-5 doc (2026-07-09):
`model_mean` now **6.14** (was 4.89) and is the full-pool leader; `ceiling_phaul` **6.00** (was 5.17);
`base_season` **6.00** (unchanged); `template` **4.97** (unchanged); the oracle **16.66** (unchanged).
The unchanged figures are the non-model strategies, which is exactly the expected signature of drift in
`compose` (god-file deletion, `fdr_avg` mean-features work — `docs/model-redesign-changelog.md`) rather
than a harness change. `model_mean` and `model_mean_x_pplay` are now identical on the full pool: inside
the availability gate `p_play` is near 1 and rarely moves the argmax.

## Failure points acknowledged

- **Top-N ownership is a proxy for a squad, not a squad.** A real manager's 15 are correlated with
  ownership but not identical, and their captaincy set is further constrained by who starts. A top-10
  ownership pool is a *popularity* pool, not *your* pool.
- **Block bootstrap on 35 GWs**, blocks of 4 — same caveat as all prior captaincy work. The paired
  design removes the shared GW variance, which is why any CI here excludes zero at all.
- **hit@1 binomial tests are unadjusted for multiplicity** (5 strategies × 4 pools = 20 tests). The
  headline results survive Bonferroni at α=0.05 (threshold 0.0025): `base_season` at top-50/20/10
  (p=0.0006/0.0003/0.0004), `p_haul` at top-10 (0.0004), `p90` at top-10 (0.0017). The middle band
  (`p_haul` top-50 p=0.0051, `e_points` top-10 p=0.0063) and everything above it do **not**. Read the
  surviving rows as solid and the rest as suggestive.
- **The chance baseline `mean(1/n)`** treats every candidate as equally likely to be the oracle, which
  is conservative for a pool deliberately selected to contain good players.
- **No per-position strategy claim is licensed.** The oracle mix shifts sharply toward FWD in
  restricted pools, but no strategy was evaluated per position — that remains untested, and is the
  most obvious next question this document raises rather than answers.
