# Phase 3.0 — Tracks 0 & 2: rule verification + scoring diagnostics (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 3.0.
**Produced:** 2026-07-08 · population `minutes > 0`, DGW-excluded (canonical). These are
**contemporaneous, season-pooled associations** (diagnostic tier, Rung 2, association-only — *not*
lagged/predictive): they inform the points-composition *structure*, not a forecast. Bootstrap
percentile 95% CIs via `research.kernels.inferential.resampling`.

---

## Track 0 — rulebook verification (vs FPL bootstrap-static `game_config.scoring`)

**Confirmed against the API** (flip `UNVERIFIED`→`VERIFIED`): goals (GK 10 / DEF 6 / MID 5 / FWD 4),
clean sheets (4 / 4 / 1 / 0), assists +3, pen save +5, pen miss −2, yellow −1, red −3, own goal −2,
appearance long/short 2/1, **defensive contribution +2 for DEF/MID/FWD and 0 for GK**, **goals-conceded
coefficient −1 for GK/DEF and 0 for MID/FWD** (position applicability confirmed).

**Not exposed by the endpoint — remain "by-rule" (still to confirm from the rules page / empirical
reconstruction in `scoring_engine.ipynb`), do NOT mark VERIFIED:**
- the **÷2 divisor** on goals-conceded (`GOALS_CONCEDED_PER_PENALTY`),
- the **÷3 divisor** on saves (`GK_SAVES_PER_POINT`),
- the **DC action thresholds** (10 CBIT for DEF, 12 CBIRT for MID/FWD).

*Net: every point coefficient and its position applicability is now verified; three threshold/divisor
parameters are not in bootstrap-static and stay by-rule.*

---

## Track 2 — scoring diagnostics (D-A … D-D)

### D-A — does defensive contribution co-move with conceding / clean sheets? **NULL (after minutes adj.)**
| measure (DEF, n=3845) | rho | 95% CI |
|---|---|---|
| raw corr(DC, goals_conceded) | +0.236 | [+0.205, +0.267] |
| raw corr(DC, clean_sheet) | +0.161 | [+0.131, +0.189] |
| **partial(DC, goals_conceded \| minutes)** | **+0.051** | [+0.018, +0.086] |
| **partial(DC, clean_sheet \| minutes)** | **+0.003** | [−0.030, +0.036] |

The raw positive correlation with *both* targets was the tell of a **minutes confound** (DC accrues
with time on pitch; CS needs ≥60'; conceding accrues on pitch). Once minutes is partialled out, the
association collapses to ~0.05 (conceded) and ~0.00 (CS). **DC is effectively conditionally independent
of conceding/CS given minutes.** The earlier "team-under-siege" story is **not supported** — it was a
minutes artifact. **Modeling decision:** the simulator does **not** couple DC to the goals-against
layer; DC is its own component conditional on minutes. *(Retracts the pre-measurement claim that this
coupling "matters most".)*

### D-B — is bonus recoverable from modeled returns? **YES (proxy viable)**
corr(`bonus`, modeled `returns_pts`), per position:

| GK | DEF | MID | FWD |
|---|---|---|---|
| +0.503 [.455,.548] | +0.533 [.506,.560] | +0.546 [.521,.571] | **+0.777 [.743,.807]** |

Bonus is strongly, monotonically tied to modeled returns — overwhelmingly so for FWD (goals dominate
BPS), moderately (~0.53) for the rest, where the residual is the competitive / defensive-action part.
**Modeling decision:** a reduced-form `E[bonus | returns, minutes, position]` proxy is viable; the
un-recoverable competitive residual is documented (irreducible without a full 22-player match sim).

### D-C — does DC predict bonus *beyond* returns? **MODEST-REAL**
partial(DC, `bonus` | `returns_pts`): DEF +0.149 [+0.120,+0.177] · MID +0.098 [+0.072,+0.122].
DC carries bonus signal beyond returns (defensive actions feed BPS). **Modeling decision:** include DC
among the **bonus-proxy features** (not returns-only); it shares the DC input with the DC *points* term,
so treat their errors as correlated — no separate double-count as long as bonus is a proxy on inputs.

### D-D — is clean sheet the same event as zero goals conceded? **IDENTITY HOLDS**
DEF+GK, n=4592: **impossible states (CS=1 & GA>0): 0.00%**; `CS == 1{GA=0}` agreement **87.78%**.
CS is a strict subset of GA=0 (never violated); the ~12% gap is the **≥60' / on-pitch gate** (GA=0 but
CS not awarded for sub-60' or late subs). **Modeling decision:** derive CS (gated on ≥60') **and** the
conceded penalty from **one team-goals-against model** — independent CS + conceded models are
definitionally wrong (they permit the 0%-observed impossible states).

---

### Robustness — clustered bootstrap (2026-07-09)
The D-A/B/C intervals above are row bootstraps, but player-GW rows are clustered (repeated player;
shared team-fixture). Re-running with a **player-clustered** and a **team-fixture-clustered** bootstrap
(`cluster_bootstrap_minutes_adjusted_rho`) changes the intervals negligibly — e.g. D-A DC~conceded|min
row [+0.018,+0.086] vs player [+0.018,+0.083] vs team-fixture [+0.016,+0.085]; D-B FWD row [.743,.807]
vs player [.737,.811]. These are *contemporaneous within-GW* associations, so the pairwise residuals are
not autocorrelated enough within cluster to inflate variance at this n. **Verdicts and CI widths are
robust to clustering** — the row-bootstrap intervals stand.

## Consolidated verdicts → Phase 3.0 Track 3 design
| diagnostic | verdict | decision |
|---|---|---|
| D-A | null given minutes | DC = standalone component conditional on minutes; **no** GA coupling |
| D-B | strong (FWD esp.) | reduced-form bonus proxy on returns+minutes+position |
| D-C | modest-real | add DC to bonus-proxy features |
| D-D | identity holds | one team-GA model → CS (≥60' gate) + conceded jointly |

**Discipline note:** D-A is the case study — a plausible causal story ("siege") was asserted
pre-measurement, then **retracted by the data**. Honest-null is a valid, recorded outcome.
