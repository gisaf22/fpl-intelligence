# PROJECT — what was investigated, what was found, where it stands

**Type:** research record · **Written:** 2026-08-16 · **Branch:** `predictive-cleanup-and-redesign-spec`
(HEAD `ae90398`, plus uncommitted Phase-5 captaincy work).

This is a record, not a plan. Every number below was read out of the artifact named beside it, or
recomputed against the mart. Where something could not be verified it says so.

---

## 1. The question

The project set out to find out what, if anything, about a Fantasy Premier League player in gameweek
*N* carries usable information about what happens in gameweek *N+1* — over one season, 2025-26,
GW 1–38. The unit of analysis is the player-gameweek. The decisions in view are the ones an FPL
manager actually makes: who to captain, who to buy, who to sell. The programme was deliberately built
bottom-up: describe the population first, then measure per-feature association under a pre-registered
gate, then compose the surviving features, then — separately — build a probabilistic points model and
test whether either output improves a decision against a naive benchmark.

Two commitments shaped everything. First, **ranking, not point prediction**: squads fill under
position quotas, so the metric is within-position Spearman rank correlation (ADR-001) and there is no
pooled cross-position number. Second, **pre-registration and honest nulls**: every study locked its
population, window, gates and thresholds before running (`LENS_DESIGN.md` §15 "design lock"), and a
refuted hypothesis is recorded as a result rather than quietly dropped. A large fraction of what
follows is nulls, and that is the substance of the record, not a preamble to it.

---

## 2. Vocabulary

| Term used here | Meaning | Where the codebase disagrees |
|---|---|---|
| **feature / signal** | One measurable column at the player-GW grain (`xgi_roll3`, `transfers_in`). | `research/` calls these *signals*; `model/features/spec.py` calls the same things `FeatureSpec` — *features*. Both names are live. |
| **feature group** | The four thematic bundles: form, availability, market, fixture. | Called a **family** in the directory tree (`research/families/`) and a **lens** in every design doc and in code (`LENS_DESIGN.md`, `lens: form` in `evidence.yaml`, `LENS-FORM-*` run dirs). Three names, one concept. |
| **association** | Spearman rho between a feature at GW *N* and an outcome, with a bootstrap CI. Rung 1 of Pearl's ladder throughout — no causal claim is made anywhere (ADR-008). | — |
| **outcome** | The scored target. Three distinct ones are in use: `total_points_next_gw` (lag-1, form/market), `played_next_gw` (lag-1, availability), `total_points` (same-GW, fixture and the characterization layer). | The fixture lens's same-GW target is deliberate and documented (`fixture/validate/study.py:1-9`); it is *not* comparable to the lag-1 studies. |
| **characterization** | Describing a feature's shape: bin geometry, monotonicity, between/within panel split, haul sensitivity. Produces `association_class` and `promotion_class`. | — |
| **qualification** | Deciding pass/fail under the three lens gates: G1 CI excludes zero → G2 quintile decision-relevance → G3 block stability. Produces `lens_status`. | — |
| **verdict** | The recorded decision about a feature. | **Five parallel vocabularies exist for this one idea.** `lens_status` ∈ {informative, uninformative, unstable} in `classification_summary.csv`; `decision_class` ∈ {informative, uninformative} in `evidence.yaml`; `lifecycle_state` ∈ {approved, excluded, not_applicable} and `downstream_status` ∈ {approved, blocked} in `annotations.yaml`; `association_class` and `promotion_class` and a third `downstream_status` ∈ {eligible, caveated, blocked} in the characterization registry; `decision` ∈ {APPROVED-PRIMARY, APPROVED-SECONDARY, EXCLUDED-REDUNDANT, FWD-SINGLE-SIGNAL} in `synth01_decisions.yaml`. ADR-009 §Context calls two of these "complementary, not competing" and never reconciles the rest. |

One further collision: **"FDR"** means *Fixture Difficulty Rating* in `fdr_avg` and
`_fdr_moderation_check`, and *False Discovery Rate* in the captaincy documents' BH-FDR corrections.
Both appear in this repository, in files that cite each other.

---

## 3. What was built

**Population / DAL** — `dal/pipeline.py::run`/`::load`. Staging → intermediate → fct → feat → mart,
with a fail-closed `MART_SCHEMA` and a validation layer. Produces one deterministic
`(player_id, gw)` mart: **31,958 rows, 64 columns, GW 1–38**, cached as parquet with a manifest.
Every other layer reads it and nothing else. *Complete and in use.*

**Characterization** — `research/registry/` (`sections.py`, `assembler.py`, `build.py`) over
`research/kernels/{descriptive,diagnostic,inferential}`. For each of 26 raw signals × 4 positions it
computes an adaptive binning geometry, a bootstrapped between/within panel decomposition, temporal
stability, and haul-tail dependence. The committed output is
`research/findings/records/eda_03_joint_registry.csv` — **104 signal-position rows** with 38 columns.
*Built, never run in its current form:* `research/registry/build.py` reads that CSV as its source and
writes to `research/findings/registry_builds/`, which does not exist; `model/governance/promote.py`
publishes to `outputs/registry/`, which was deleted at `ae90398` because "its only consumer is gone."

**Qualification — the four lens studies** — `research/families/{form,market,availability,fixture}/validate/study.py`,
each locked by a `LENS_DESIGN.md` dated 2026-05-22 and amended once (ADR-010, extending the window to
GW 38). Population `minutes >= 60`; three GW blocks early 3–12 / mid 13–26 / late 27–38; Spearman with
2,000 bootstrap resamples, seed 42. Three gates in sequence: G1 CI excludes zero, G2 quintile
decision-relevance (|Q5−Q1| ≥ 1.0 point *and* monotonic), G3 ≥2 of 3 blocks. Committed outputs are
`evidence.yaml` (machine) and `annotations.yaml` (hand-authored judgment). *Complete and reproducible:*
re-running the studies on 2026-08-16 reproduced the June rho values exactly — `xgi_roll3@DEF` 0.1234,
`xgi_roll5@DEF` 0.1105 — and `ae90398` records the same check as "fixture 10/10, form 20/20, market
12/12 rho cells reproduce."

**Selection — SYNTH-01** — `model/assemble/composition_study.py` → `synth01_recommendations.yaml`,
ratified into `synth01_decisions.yaml`. Takes the qualified features, computes partial Spearman with
bootstrap CI for each one controlling for the others *in the same position × lens group*, and assigns
composition weights under an equal-weight-unless-it-buys-0.02-rho rule (ADR-002). **14 decisions: 10
approved, 3 excluded-redundant, 1 FWD single-signal.** *Superseded* by ADR-011 for ranking; the study
code and both YAMLs remain, with no consumer on the live path.

**The forecast model** — `model/terms/` (8 term models) → `model/compose.py` → `model/simulate.py` →
`model/predictions.py::assemble_forecast`. Each term is a separately gated, walk-forward-fit model over
a declared lag-safe `FeaturePool`; `team_goals_against` is joint (clean sheet and the conceded penalty
are one Poisson draw); `bonus` is fit last on the assembled returns; `p_play` sits out front as the
unconditional factor. The simulator draws components through the real FPL scoring rules and emits
`p10/p50/p90/p_haul`. *Complete and in use.*

**The decision runtime** — `domain/decision.py::DecisionSpec` + `serve/decision_engine.py::run_decision`,
with three specs: `serve/captain.py` (rank by `p_haul`, tie-break `p90`), `serve/value.py`
(`e_points_uncond / purchase_price`), `serve/transfers.py` (`e_points_uncond`). The composition root
is `operational/recommend.py::main --target-gw`, the only place `dal`, `model` and `serve` meet; the
evaluation harness is `model/eval/decision/` with `serve`'s rankers injected as `pick_fn`. *Complete;
no evidence of a persisted run.*

---

## 4. What was found

### Which features carry usable information, and where

Across the four lens studies, **14 of the 54 (signal × position) cells that reached a gate qualify as
informative**. (The four `annotations.yaml` files carry 64 cells; 10 never reached a gate — `xgi_roll3`,
`xgi_roll5`, `goals_scored_roll3` and `minutes_roll3` at GK, and `transfers_balance` at all four
positions, all blocked upstream in EDA.) Pooled rho, with 95% bootstrap CI, read from the
`evidence.yaml` files:

| feature | position | rho | CI | blocks | verdict |
|---|---|---|---|---|---|
| `transfers_in` | DEF | **0.192** | [0.156, 0.229] | 3/3 | informative |
| `transfers_in` | MID | **0.184** | [0.147, 0.219] | 3/3 | informative |
| `ownership_count` | MID | 0.162 | [0.124, 0.195] | 3/3 | informative |
| `fdr_avg` | GK | −0.162 | [−0.235, −0.092] | 2/3 | informative |
| `fdr_avg` | MID | −0.158 | [−0.192, −0.124] | 3/3 | informative |
| `xgi_roll5` | MID | 0.158 | [0.120, 0.196] | 3/3 | informative |
| `ownership_count` | DEF | 0.145 | [0.109, 0.180] | 3/3 | informative |
| `xgi_roll3` | MID | 0.146 | [0.108, 0.184] | 3/3 | informative |
| `xgi_roll3` | DEF | 0.123 | [0.086, 0.160] | 3/3 | informative |
| `purchase_price` | DEF | 0.113 | [0.075, 0.150] | 2/3 | informative |
| `minutes_roll3` | MID | 0.227* | [0.191, 0.263] | 3/3 | informative |
| `minutes_roll5` | MID | 0.224* | [0.187, 0.259] | 3/3 | informative |
| `minutes_roll8` | MID | 0.218* | [0.182, 0.254] | 3/3 | informative |
| `minutes_roll5` | FWD | 0.207* | [0.129, 0.278] | 2/3 | informative |

\* availability rows score `played_next_gw`, a different and easier target — not comparable to the
points rows above. The two `fdr_avg` rows score `total_points` in the *same* gameweek (the fixture is
known before kickoff, so no lag is needed); every other points row scores `total_points_next_gw`.

The headline is the ceiling: **nothing exceeds rho ≈ 0.19 against next-GW points.** The strongest
feature found anywhere is `transfers_in` — crowd transfer demand — and it explains a rank association
of about 0.19 at DEF. Form (`xgi_roll5@MID`, 0.158) does not clear its own naive baseline
(`points_roll5@MID`, 0.153–0.158); the `annotations.yaml` entry records it as "borderline below."
Everything the lens layer found sits in a narrow band between 0.11 and 0.19, and the diagnostic layer
puts the reason plainly: roughly 88% of weekly points variance is within-player noise
(`predictive-phase1-icc-shrinkage.md`: ICC 0.056 DEF / 0.101 MID / 0.097 FWD / 0.000 GK).

Two structural readings from the characterization layer are worth more than the rho values. First,
`transfers_in`'s association is almost entirely *between* players, not within them: `within_share`
0.024 at DEF and 0.043 at MID, classed `identity_dominant`
(`eda_03_joint_registry.csv`). It ranks players by who they are, not by how their week is going.
Second, the only features the characterization layer classes `continuous_monotonic` are
contemporaneous components of the target itself — `goals_scored`, `assists`, `bonus`, `bps`,
`goals_conceded` — measured against a same-GW outcome. They are descriptive, not predictive, and
nothing downstream treats them otherwise.

### The nulls

**FIXTURE-GW is now a mixed result, not a clean null.** Under the corrected ordinal binning
(`CHARACTERIZE_DESIGN.md` §2, implemented and re-run 2026-08-16), `fdr_avg` is `informative` at GK
(−0.162 [−0.235, −0.092], 2/3 blocks) and MID (−0.158 [−0.192, −0.124], 3/3 blocks). DEF is unchanged
at `uninformative`: the ordinal profile still reverses at bins 1→2, so it still fails Gate 2
(`monotonic=False`) — a binning fix does not rescue it (§5). FWD also stays `uninformative`, but the
reason moved: its ordinal profile is monotonic, so it now clears Gate 2, and instead fails Gate 3 on
temporal block stability (1/3 blocks, rho −0.113 [−0.182, −0.043]). So of the four fixture cells, two
now qualify, one fails on the same axis as before (Gate 2, DEF), and one fails on a different axis than
before (Gate 3, FWD). §5 below has the before/after detail.

**GK has exactly one qualifying cell, and it is a fixture property.** Since the 2026-08-16 binning fix,
`fdr_avg@GK` (−0.162, 2/3 blocks) is the single GK cell that qualifies anywhere in the qualification
layer — and it describes the opponent, not the keeper. Every GK cell that scores a *player* attribute
still fails: `transfers_in@GK` 0.145, 2/3 blocks, uninformative; `minutes_roll3@GK` 0.153
against *availability* — Q5−Q1 = 0.080, uninformative; `points_roll3@GK` 0.091, uninformative. This
corroborates independently at every layer: Phase-0 baselines put the best GK ranker at Spearman **0.06,
approximately chance**; Phase 1 measures ICC(GK) = **0.000** with LRT p = 0.50 — no durable
between-keeper level at all; Phase 4 is the only place GK loses to climatology on CRPS (1.419 vs
1.347). Keeper points are a team and fixture property, not a player property. The one place the stack
recovers GK signal is the team-goals-against layer, which lifts GK clean-sheet ranking from 0.037 to
**0.159** (`predictive-phase3-points-model.md` Part 3.1) — by modelling the team, not the keeper.

**FWD is nearly so.** Exactly one FWD cell qualifies in the entire qualification layer:
`minutes_roll5@FWD` against availability (rho 0.207, 2/3 blocks). Every FWD points cell fails —
`xgi_roll3@FWD` 0.100 fails G2 (non-monotonic), `transfers_in@FWD` 0.118 fails on 1/3 blocks,
`fdr_avg@FWD` −0.113 now clears G2 under ordinal binning (−1.815, strictly monotonic) and fails G3
instead, on 1/3 blocks — only the mid window excludes zero. `purchase_price@FWD` is carried into SYNTH-01 as a
`FWD-SINGLE-SIGNAL` with its own caveat recorded in the decision note: "G3-WEAK: 2/3 temporal blocks."
The recurring explanation in the annotations is haul concentration: forwards' points arrive in bursts,
and a rolling mean over burst events cannot produce monotonic quintile separation.

**`goals_scored_roll3` is uninformative everywhere it was tested.** DEF rho 0.031 with the CI crossing
zero [−0.008, 0.071]; MID 0.069 and FWD 0.097 with CIs excluding zero but pre-fix Q5−Q1 of 0.30 and
0.95. (`goals_scored_roll3` now classifies as `discrete` under the post-`68b6246` bucketing logic, so
Gate 2 auto-fails via the `None` branch rather than computing a quintile gap; the gaps quoted here are
from the superseded rank-tie-break cut and are not reproducible under current code, though the verdict
is the same either way. `form/validate/annotations.yaml` records different historical values for the
same two cells — 0.38 and 0.79 — so the two committed sources disagree on the pre-fix number; neither
is authoritative and there is no live code path to re-derive it.) Past
goals do not predict future goals well enough to rank on. The model layer measured the same thing
directly and preferred the process stat: forecasting next-GW `goals_scored`, lagged xG beats lagged
goals at every position (DEF +0.026, MID +0.043, FWD +0.013 — `predictive-phase2-component-model.md`).

**`was_home` carries almost nothing.** GK 0.063 and FWD 0.032 with CIs crossing zero; DEF 0.083 and
MID 0.051 with CIs excluding zero but pre-fix Q5−Q1 of −0.052 and 0.088 — that is, five to nine
*hundredths* of a point separating home from away. (Since Amendment B, `was_home` is recognised as
binary, routes to the `discrete` scheme and gets no quintile split at all; the gaps quoted here are
from the superseded rank-tie-break cut, and the verdict is the same either way.) All four cells
uninformative. The model layer found the same
and then found the placement finding was wrong too: Phase 2.1 hard-coded venue into the clean-sheet
model only, and Phase 2.2's tuned elastic net kept `was_home` most consistently for *assists*
(selection frequency 1.000) with coefficients of 0.02–0.06 everywhere. Small, real, and not defensive-only.

### The captaincy verdict

Captaincy was attacked three times, each time against a different explanation for the previous null.
All three agree, and the two most recent are uncommitted work.

1. **Full-pool divergence** (`predictive-phase5-captaincy-diagnostic-rerun.md`). When a model strategy
   picks a different captain than `base_season`, does it win? `e_points` 0.440 [0.280, 0.560];
   `p90` 0.385 [0.269, 0.462]; `p_haul` 0.385 [0.231, 0.500]. Every point estimate at or below 0.5,
   every CI includes or sits below it, every mean-delta CI contains zero.
2. **Walk-forward discrimination** (same document). The one measurement that had looked like real
   signal — oracle-captain AUC 0.626 against a permutation floor of 0.577 — was fit with
   leave-one-GW-out CV, training on gameweeks after the test week. Refit strictly chronologically it
   reads **0.561 against a floor of 0.578**: below the floor. This costs only one gameweek and 217 of
   7,528 rows, so it is not a power artifact; the 0.065 drop is what the peek at the future was worth.
3. **Restricted pools, pooled and per position** (`-realistic-pool.md`, `-by-position.md`). The
   objection that all prior tests scored a 219-candidate universe no manager faces is *correct*: inside
   a top-10 ownership pool there is 5.63 pts/GW of headroom, and the oracle is genuinely identifiable —
   `base_season` and `p_haul` each land the exact best captain in **11 of 35 GWs against a 3.5-GW chance
   expectation** (p = 0.0004). The decision even changes character, flipping from MID-dominated
   (oracle MID 15/35 on the full pool) to FWD-dominated (FWD 15/35 at top-20). None of it converts.
   Every paired delta CI against `base_season` includes zero in every pool; at top-20 `model_mean`
   (−1.46 [−2.83, −0.57]) and `ceiling_p90` (−1.34 [−2.66, −0.51]) are *significantly worse*. Cut per
   position, **0 of 36 comparisons reach significance** — minimum bootstrap p = 0.072, where under a
   pure null one would expect about 1.8 nominally significant cells. The pre-registered hypothesis
   (`ceiling_phaul` wins at FWD, loses at DEF) is refuted with the wrong sign on both halves: FWD
   +0.36 / −0.29 / −0.06 across the three pools, and the largest positive delta in the whole grid is
   **+1.14 at DEF top-50**, exactly where it was predicted to fail.

**`base_season` — a player's expanding season mean — extracts essentially all of the available
captaincy signal, and the model adds nothing on top of it at any position, in any pool.** The residual
headroom is haul-timing variance. Per its own pre-registered null-handling rule, the by-position
document closes captaincy.

Note that this sits alongside a model that is genuinely good at what it was gated on. The full points
model beats both `base_season` and the Phase-2.1 component model at every position on point estimates
(GK 0.154, DEF 0.263, MID 0.391, FWD 0.398), with DEF and MID separable by non-overlapping CIs. Haul
and return probabilities pass calibration after one isotonic pass (ECE ≤ 0.0052 against a
pre-registered ≤ 0.02). Ranking skill and calibration were both achieved; neither converted into a
captaincy edge. That gap is the most important thing the evaluation layer established.

### The SYNTH-01 redundancy structure

Composition found that the qualified features are largely substitutes for one another.

- **Form is a one-signal group.** At DEF, `xgi_roll3` holds (partial rho 0.048 [0.009, 0.087]) and
  `xgi_roll5` collapses to 0.018 [−0.020, 0.056] — below the 0.02 materiality threshold, absorbed. At
  MID the roles invert exactly: `xgi_roll5` holds (0.062 [0.025, 0.099]) and `xgi_roll3` collapses to
  0.013 [−0.026, 0.049]. The two windows carry the same information; which one survives is
  position-dependent and, at these interval widths, close to arbitrary.
- **Market redundancy is asymmetric.** At DEF, `ownership_count` is absorbed entirely by
  `transfers_in` + `purchase_price` (partial rho **−0.012** [−0.047, 0.024]) — the decision note
  records this as confirming a HIGH REDUNDANCY SUBSTITUTE pair predicted in `synth01_candidates.yaml`.
  At MID it survives (0.031), but with a CI that crosses zero, [−0.007, 0.067].
- **Availability windows overlap almost completely.** At MID, `minutes_roll3` (0.046) and
  `minutes_roll8` (0.043) are retained at equal weight and `minutes_roll5` is absorbed by both (0.015).
  All three measure the same thing over different horizons.
- **Every retained group preferred equal weights.** Not one group cleared the ADR-002 rule that
  evidence-derived weights must buy ≥ 0.02 rho over equal weighting. The "weights" in
  `synth01_decisions.yaml` are all 1.0 or 0.5.

**Market-vs-form independence was never tested.** `market/LENS_DESIGN.md` §1 states the study question
as: *"Do they carry independent information beyond form signals, or do they simply reflect crowd
consensus about form?"* Nothing measures this. The lens study computes bivariate rho only —
`market/validate/study.py` contains no partial correlation and no form control. SYNTH-01, which does
compute partial rho, is structured as `GROUPS` keyed on `position × lens`
(`composition_study.py:67-107`), so it controls for other market features and never for a form one.
The question the market lens was designed around remains open, and `transfers_in`'s
`identity_dominant` panel class (within-share 0.024 at DEF) is at least consistent with the
crowd-consensus reading.

---

## 5. Known caveats in this work

**Two features carry composition weight against their own study's verdict.** `minutes_roll8@DEF` is
`APPROVED-PRIMARY` at weight 1.0 in `synth01_decisions.yaml`, the sole retained signal in the DEF ×
avail group. Its `annotations.yaml` entry records `G2-PASS: monotonic Q5-Q1` and `G3-PASS: 3/3 blocks`.
The machine disagrees: `availability/validate/evidence.yaml` gives it `decision_class:
uninformative`, and `classification_summary.csv` states the reason — *"CI excludes zero but fails
decision relevance (Q5-Q1=0.250, monotonic=False)"*. The annotation asserts the exact gate outcome the
study computed the opposite of. `xgi_roll5@DEF` is the same shape with an additional wrinkle: its
annotation records `G2-PASS`, its evidence records `uninformative` (*"Q5-Q1=0.96, monotonic=True"* —
monotonic, but the gap is below the pre-registered 1.0 threshold), and `synth01_decisions.yaml`
contradicts *itself* about it — the decision record says `APPROVED-SECONDARY` with
`composition_weight: 0.5` while the `group_summary` for the same group lists it under `excluded` with
`xgi_roll3` at weight 1.0. Its effective weight is 0.5 or 0.0 depending on which half of one generated
file you read.

**The FIXTURE null was partly a binning artifact — fixed 2026-08-16, and no longer a caveat.**
`fdr_avg` takes exactly **7 distinct values** on the
mart (1.0, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0), and at DEF **1,684 of 2,837 rows — 59% — sit at exactly
3.0**. The lens used to cut quintiles with `pd.qcut(series.rank(method="first"), 5)`
(`research/kernels/hypothesis/stratification.py`), and `method="first"` breaks ties by row
order. The consequence, on the pre-fix cut:

| | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| **DEF** composition | 1.0×143, 2.0×344, 2.5×14, 3.0×67 | **3.0 × 567** | **3.0 × 567** | 3.0×483, 3.5×16, 4.0×68 | 4.0×422, 5.0×146 |
| **DEF** mean points | 4.880 | 3.631 | **3.970** | 3.347 | 2.836 |
| **MID** composition | 1.0×157, 2.0×366, 2.5×16, 3.0×73 | **3.0 × 612** | **3.0 × 611** | 3.0×530, 3.5×17, 4.0×65 | 4.0×461, 5.0×151 |
| **MID** mean points | 4.729 | 4.088 | **4.326** | 3.650 | 3.309 |

Q2 and Q3 were 100% `fdr_avg == 3.0` at both positions. They are the same fixtures, split by row order.
Their means differ by 0.34 (DEF) and 0.24 (MID) from that alone — and that difference *was* the single
reversal that set `is_monotonic=False` and failed the gate.

**The fix.** Gate 2's quintile cut now consumes the ordinal bin scheme characterization already selects
for FDR signals — `research/kernels/descriptive/binning.py::select_bucketing_scheme`, one bin per FDR
value on `FDR_ORDINAL_BINS` — instead of cutting its own. The design decision is
`research/registry/CHARACTERIZE_DESIGN.md` §2 ("qualification's binning is replaced by
characterization's, not run beside it"); the lens-side amendment is
`research/families/fixture/LENS_DESIGN.md` Amendment B (2026-08-16), which also records that `was_home`
and `fixture_count` are binary on the mart, route to the `discrete` scheme, and are now reported as not
decision-relevance-testable rather than forced into a manufactured 5-way split — neither one's
`decision_class` changes. The fixture lens was re-run on the corrected cut
(`LENS-FIXTURE-GW-20260816_220229`), and `fixture/validate/evidence.yaml` now carries that run.

The Gate 2 profiles on the ordinal cut, and what each position's outcome became:

| | 1 | 2 | 3 | 4 | 5 | gap | Gate 2 | outcome |
|---|---|---|---|---|---|---|---|---|
| **MID** | 4.879 (157) | 4.618 (382) | 4.075 (1843) | 3.458 (526) | 2.901 (151) | −1.978 | pass, strictly monotonic | uninformative → **informative** (3/3 blocks) |
| **GK** | 4.200 (35) | 4.156 (90) | 3.388 (425) | 2.984 (122) | 2.057 (35) | −2.143 | pass, strictly monotonic | uninformative → **informative** (2/3 blocks) |
| **FWD** | 5.222 (36) | 4.606 (99) | 4.221 (443) | 3.491 (116) | 3.407 (27) | −1.815 | pass, strictly monotonic | uninformative → **uninformative**, but now at Gate 3 (1/3 blocks) |
| **DEF** | 4.713 (143) | 4.818 (358) | 3.737 (1700) | 3.210 (490) | 1.822 (146) | −2.891 | **fail**, one reversal at bins 1→2 | uninformative → uninformative, unchanged |

Before the fix, all four cells failed Gate 2 with `monotonic=False` (Q5−Q1 of −1.366 GK, −2.044 DEF,
−1.420 MID, −1.183 FWD). After it, three of four clear Gate 2 and two qualify outright. This also ends
the contradiction between `eda_03_joint_registry.csv` (`fdr_avg@MID` → `monotonic_negative`,
`q1_q5_mean_gap = −1.868`) and the fixture lens, which used to say `monotonic=False` for the same cell
against the same target.

**What remains true and is still a caveat.** DEF is not rescued: its ordinal profile has its own
reversal (bins 1→2, +0.105, on 143 and 358 rows), so a binning fix was not an outcome fix. And MID
passes flagged — `eda_03_joint_registry.csv` gives it `monotonicity_confidence = 0.675`, below the
schema's `MONO_CONF_HIGH` of 0.80 — so the more robust of the two new qualifications (3/3 blocks)
still carries a low-confidence monotonicity flag. Separately, `composition_study._fdr_moderation_check` still builds its FDR quartiles with the old
`rank(method="first")` tie-break; `CHARACTERIZE_DESIGN.md` §2 limit 3 records that defect as out of
scope for that document, and it is not fixed (see §7).

**Two evidence files were labelled with the wrong target — fixed 2026-08-16, label only.**
`form/validate/evidence.yaml:2` and `market/validate/evidence.yaml:2` both used to read
`target: total_points`. The studies that wrote them set
`TARGET = "total_points_next_gw"` (`form/validate/study.py:33`, `market/validate/study.py:31`), and the
corresponding `run_metadata.json` and `correlation_results.csv` from the reproducing 2026-08-16 rerun
both record `total_points_next_gw`. The numbers were lag-1; the label beside them said same-GW. Both
labels now read `total_points_next_gw`; no rho, CI or block count was touched, since none of them was
wrong. **The same mislabel is still on disk in `form/validate/annotations.yaml:2` and
`market/validate/annotations.yaml:2`**, which were not part of this fix.

**The forecast model does not consume the qualification layer's outputs.** No file under
`model/terms/`, `model/features/`, `model/forecast/`, `model/compose.py`, `model/simulate.py` or
`model/predictions.py` reads `evidence.yaml`, `annotations.yaml` or `synth01_decisions.yaml`. The link
is prose: each `FeatureSpec` carries a `prior=` string ("families §3: opponent strength", "phase2
design check"), documented in `model/features/spec.py` as "provenance from discovery, *non-authoritative*."
The concrete consequence is that **`transfers_in` — the strongest feature the qualification layer
found, at both DEF and MID — is not a model input.** Neither is `ownership_count` or `purchase_price`.
No market feature appears in any term's pool. `purchase_price` enters the system exactly once, as the
denominator in `serve/value.py`. Whether that omission costs anything was never measured; the two
layers were built against different targets and never joined.

**`sections.py` computes confidence intervals and discards them before writing.**
`research/kernels/diagnostic/panel.py` runs a 1,000-resample bootstrap and returns `rho_pooled_ci`,
`rho_between_ci`, `rho_within_ci`, `within_share_ci` and `dominance_ci`.
`sections.py:310-322` spreads all of them into each decomposition row. `assembler.py:27-38` then
selects `DECOMPOSITION_COLUMNS`, which lists the point estimates and omits every `*_ci`. The bootstrap
runs, the intervals are computed, and the persisted registry carries `rho_between = 0.024` with no
indication of how precisely it is known. The same is true of `q1_q5_mean_gap` in the geometry section —
the panel decomposition is the only place uncertainty is quantified, and it is the place it is dropped.

**Everything rests on one season.** Every study in this repository says so; it is repeated here because
it bounds every number above. 35–38 gameweeks, ~3,000 rows per position. "Closed" in the captaincy
documents means closed on this evidence at this sample.

---

## 6. Where each thread stops, and why

**DAL** — *terminal, in use.* Serves every layer. No open question.

**Characterization (`research/registry/`)** — *built, never run; its consumer removed.* The code
computes relationship sections and assembles a registry; `model/governance/promote.py` publishes to
`outputs/registry/`. Commit `ae90398` deleted `outputs/registry/gw36/` with the note "the promoted
artifact; its only consumer is gone," having already deleted `domain/registry/{verdict,governance_lookup,governance_types}.py`
(`governance_lookup` "hard-raised FileNotFoundError on the removed `evaluation_metadata.yaml` and had
zero production importers") and the whole of `serve/scoring/` and `serve/reporting/`, which were the
runtime surfaces that read it. The build machinery and `research/findings/records/eda_03_joint_registry.csv`
were kept deliberately; the pipeline from that CSV to a published registry has no output on disk and no
reader if it did.

**The four lens studies** — *complete.* Locked design, executed, reproducible, evidence committed. Each
is superseded as a *ranking input* by ADR-011 but stands as measurement. `research/runs/` is gitignored,
so run CSVs are local only; `evidence.yaml` is the durable artifact.

**SYNTH-01** — *superseded by ADR-011* (`docs/decisions/011-model-forecast-supersedes-composites.md`,
2026-08-01). The composites it weighted were replaced by the model forecast in
`serve/{captain,value,transfers}.py`; `serve/weight_registry.{yaml,py}` and `serve/provenance.py` were
deleted. `composition_study.py` and both YAMLs remain, importable and tested, with no consumer.

**The `fdr_moderation_check`** — *measured, never implemented.* `synth01_decisions.yaml:13-41` records
`material: true`, `n_material_groups: 3` of 3 checked, verdict "MATERIAL — flag for Phase 8 moderator
implementation", with `fraction_rank_changed: 1.0` in all three groups — the rank ordering of retained
signals changed in *every* adjacent FDR-quartile comparison, at DEF × points, MID × points and MID ×
availability alike. No moderator was ever built. The only implementation of the word anywhere is
`archive/monitor/phase9_backtest.py::fdr_moderation_check`, which is archived and superseded. The
decision slug `docs/decisions/set-synth-weights.md` records it as "deferred despite a MATERIAL (>15%)
rank-order effect, with binary-DGW as the current proxy" and says both open halves are "closed in Phase
7 (see ADR-006 for the FDR decision)" — **ADR-006 was never written**; `docs/decisions/README.md:21`
lists 006 and 007 as reserved. The strongest recorded evidence that the composition is
context-dependent points at a document that does not exist.

**Phase-9 operational monitor** — *superseded, archived, terminal.* `archive/monitor/phase9_backtest.py`.
It validated SYNTH-01's compositions; ADR-011 removed the thing it validated. Its published output
`outputs/operational-baseline.md` still cites a source path (`studies/operational/phase9_backtest.py`)
that has not resolved since the `studies/` → `research/` migration.

**The predictive layer, Phases 0–4** — *complete, frozen, in use.* Phase 0 set per-position baselines
(GK 0.06 / DEF 0.167 / MID 0.311 / FWD 0.334). Phase 1 shipped ICC inference and recorded EB shrinkage
as a null. Phase 2 closed A-F1 with a tuned elastic net that clears both gates only at DEF. Phase 3
built and gated all eight terms and the simulator. Phase 4 passed the probability gate after one
isotonic recalibration and recorded the per-position interval-dispersion residual, later reclassified
as intrinsic atomicity rather than under-dispersion (`model-redesign-changelog.md` §Open items).
Three further hypotheses were pre-registered and refuted: correlated component draws, parameter-uncertainty
propagation, and a mechanistic within-fixture bonus allocator.

**Phase 5 — captaincy** — *closed on this evidence, and uncommitted.* Three of the five result
documents are untracked and the code they were run against is a dirty working tree:
`predictive-phase5-captaincy-{realistic-pool,diagnostic-rerun,by-position}.md` are `??` in git status;
`model/eval/{captaincy_backtest,captaincy_diagnostics,metrics}.py` are `M`. The documents state their
own drift honestly — full-pool `model_mean` now reads 6.14 against the frozen doc's 4.89, and the
frozen Q3 numbers do not reproduce — and attribute it to `compose` moving under the god-file deletion
and the `fdr_avg` mean-features work, verified by re-running pre-edit logic on the current panel. They
are not linked from `docs/predictive-layer-plan.md`, whose status dashboard was last updated
2026-07-10 and still points at "Door 2 (multi-season data)". The by-position document's pre-registered
rule proposes no further captaincy tests.

**`operational/recommend.py`** — *built, no evidence of a persisted run.* The composition root exists
and its call chain is complete: `dal.pipeline.load` → `assemble_forecast` → merge on `(player_id, gw)`
→ `run_decision` over CAPTAIN/VALUE/TRANSFERS. Its intended output directory `outputs/decisions/gw{N}/`
does not exist in the tree; `outputs/` contains only `minstab_01_detail.csv`,
`operational-baseline.md` and `phase9_backtest_results.yaml`, and `outputs/*` is gitignored. So there
is no artifact evidence either way, and this cannot be resolved from the repository. ADR-012 §Context
records the same absence for its predecessor: *"`outputs/` has never contained a decision
recommendation."* `operational/backtest.py` returns an in-memory `BacktestResult` and persists nothing.

**ADR-012** — *shipped past its own status line.* The ADR is marked "Proposed" with Phase 4 "in
scoping"; Phase 4 shipped at `c475873` (`model/eval/decision/{spec,backtest,baselines,metrics}.py`
exists, `tests/helpers/` is empty but for `__init__.py`).

**`docs/workflow-map.md`** — *stale by one commit.* Dated 2026-08-15 and untracked, it documents
Workflow G (`serve/scoring` CLI) and Workflow H (`serve/reporting` CLI) as live-but-disconnected. Both
directories were deleted the next day at `ae90398`; only `__pycache__` remains on disk. Its Workflows
A–F remain accurate.

---

## 7. Map

The stages below are the ones the work actually fell into, named against CRISP-DM. The order is the
order evidence moves in, not the order things were built — Selection predates the forecast model by a
month, and the forecast model does not consume it. Each row records what the stage answers, what it
produced, where it stands, and any collision it currently carries. The collisions are §4 and §5 stated
positionally; nothing here is new evidence.

| CRISP-DM phase | Stage | Question it answers | Main artifacts | Status | Known collision |
|---|---|---|---|---|---|
| **Business Understanding** | Decision Framework | What FPL decision is this informing? | — | separate thread, in progress; not detailed in this record | — |
| **Data Understanding** | Population + Foundation ("EDA") | What exists, what shape is it, what is alive where? | `dal/pipeline.py::run`/`::load` → mart (31,958 × 64, GW 1–38); `research/foundation/{composition,exposure,fixture,temporal}/*` (14 notebooks + 4 `*_DESIGN.md`); `research/diagnostic/*` (3 notebooks + `DIAGNOSTIC_DESIGN.md`) | DAL terminal and in use; the 17 notebooks terminal and render-only **by design** — they emit no findings and have no importer | none |
| **Data Preparation** | Characterization | What is the shape of this relationship, and what geometry should it be tested on? | `research/registry/sections.py`, `assembler.py`, `build.py` over `research/kernels/{descriptive,diagnostic,inferential}`; artifact `research/findings/records/eda_03_joint_registry.csv` (104 signal-position rows × 38 cols) | built, never run in its present form (`build.py` writes to `research/findings/registry_builds/`, absent); publication step deleted at `ae90398`. Now governed by `research/registry/CHARACTERIZE_DESIGN.md` (2026-08-16) — the design lock it had lacked **Resolved 2026-08-16.** The `fdr_avg` binning contradiction (`eda_03_joint_registry.csv` → `monotonic_negative`, gap −1.868, against the fixture lens's `monotonic=False`) is closed in the direction `CHARACTERIZE_DESIGN.md` §3 specified: qualification's Gate 2 now *consumes* characterization's bin scheme via `binning.py::select_bucketing_scheme` rather than cutting its own, per `research/families/fixture/LENS_DESIGN.md` Amendment B, and the lens was re-run. Both artifacts now agree. **One related defect is not closed:** `composition_study._fdr_moderation_check` still cuts FDR quartiles with the old `rank(method="first")` tie-break (`CHARACTERIZE_DESIGN.md` §2 limit 3 records it as out of that document's scope). Its 2026-08-16 output still reads MATERIAL — `synth01_recommendations.yaml` gives `fraction_rank_changed` 1.0 (DEF × points), 1.0 (MID × points), 0.75 (MID × availability), 3 of 3 groups material — so that finding is unaffected by the binning fix |
| *(pre-registration step, unnamed in CRISP-DM)* | Exploration | What does a rough first look suggest, before committing to a locked design? | `research/families/form/explore/{rolling_xgi_study,minutes_stability_study,feature_lift}.py` | complete; superseded by the locked lens studies that followed | No verdict collision, but the result docs are **split and desynced from re-runs on different data**. `rolling-xgi-horizon-study-results.md` was executed on a *synthetic* seed-42 dataset and `rolling-xgi-real-validation.md` re-ran it on the **2024-25** season — neither is 2025-26, and the study sits at lifecycle `candidate` with its stability criterion unmet. `minutes_stability_study` carries a design doc, a results doc and a gitignored detail CSV (`outputs/minstab_01_detail.csv`). `feature_lift.py` has **no result doc at all** |
| **Modeling: bivariate** | Qualification ("Associations") | Does this one signal move with the target, under a pre-registered gate? | the four `research/families/*/validate/study.py` + `LENS_DESIGN.md`; per-lens `evidence.yaml` (machine) + `annotations.yaml` (judgment); run CSVs in gitignored `research/runs/` | complete and reproducible — the 2026-08-16 rerun reproduced the June rho values exactly | **One left, in committed files.** (a) *Fixed 2026-08-16:* `form/validate/evidence.yaml:2` and `market/validate/evidence.yaml:2` read `target: total_points` while the studies that wrote them set `total_points_next_gw`; both labels now read `total_points_next_gw` (label only — no numeric value was affected). The same wrong label survives in the two matching `annotations.yaml` files. (b) *Open:* `minutes_roll8@DEF` and `xgi_roll5@DEF` annotations assert `G2-PASS` against their own evidence files' G2-FAIL (`Q5-Q1=0.250, monotonic=False`; `Q5-Q1=0.96` below the 1.0 threshold) |
| **Modeling: multivariate** | Selection ("Does this relate to what's already known?") | Controlling for the other qualified signals, does this one still add anything? | `model/assemble/composition_study.py` → `synth01_recommendations.yaml` → `synth01_decisions.yaml` (14 decisions: 10 approved, 3 excluded-redundant, 1 FWD single-signal) | superseded **for ranking** by ADR-011; `composition_study.py` and both YAMLs remain, importable and tested, with no live consumer. Retargeting it to feed the forecast model's `FeaturePool` (closing the `transfers_in`-not-a-model-input gap) is a proposed reconciliation, not yet implemented | **`synth01_decisions.yaml` contradicts itself on `xgi_roll5@DEF`**: `APPROVED-SECONDARY` at `composition_weight: 0.5` in the decision record, listed under `excluded` in the `group_summary` for the same group in the same generated file. Separately, **the market lens's own stated question — do market signals carry information independent of *form*? — was never computed anywhere in this stage**: `GROUPS` is keyed `position × lens`, so partial rho controls only for other market signals |
| **Modeling: generative** | Forecast model | Can we generate a calibrated score distribution from raw process stats? | `model/terms/` (8 terms) → `model/compose.py` → `model/simulate.py` → `model/predictions.py::assemble_forecast`; frozen records in `docs/studies/results/predictive-phase*.md` | terminal, in use, healthy — beats `base_season` at every position, calibrated after one isotonic pass | No material internal collision. But **it does not consume Qualification or Selection output**: no file under `model/terms/`, `model/features/`, `model/forecast/`, `compose.py`, `simulate.py` or `predictions.py` reads `evidence.yaml`, `annotations.yaml` or `synth01_decisions.yaml`. The link is prose — `model/features/spec.py`'s `prior=` strings, documented there as *non-authoritative*. This is a proposed integration gap for future reconciliation to close; no code currently bridges it |
| **Evaluation** | Decision evaluation | Does it beat a naive heuristic for a decision a manager actually makes? | captaincy: `model/eval/captaincy_{backtest,diagnostics}.py` + five `predictive-phase5-captaincy-*.md`; general harness: `model/eval/decision/{spec,backtest,baselines,metrics}.py` | captaincy **closed on this evidence** — three independent lines (full-pool divergence, chronological walk-forward AUC, restricted pools pooled and per position) agree; three of its five result docs untracked and its code a dirty tree | **Asymmetric evidentiary standard.** Captaincy was attacked three times and documented to the point of overturning its own earlier positive result. Transfers and value carry head-to-head numbers (`+1.73` cumulative, GW6-35, 3-GW hold) that exist **only in module docstrings** — `serve/transfers.py`, `serve/value.py` — with no frozen result doc, no committed panel and no reproduction path. Flagged as a gap |
| **Deployment** | Operational | Does it run end to end and produce something actionable? | `operational/recommend.py::main --target-gw` (the one place `dal`, `model` and `serve` meet), `operational/backtest.py`, `serve/decision_engine.py` + `domain/decision.py` + the three specs | complete and runnable; whether it has ever been run is **unresolvable from the repository** — `outputs/*` is gitignored and `outputs/decisions/gw{N}/` is absent | Not a gap to fix: the absence of evidence is a consequence of the gitignore policy, by design. ADR-012 §Context records the same absence for the predecessor surface |

Two things sit outside the ladder. `model/governance/promote.py` (registry promotion → `outputs/registry/`)
is **deleted**, along with the runtime surfaces that read it. `archive/monitor/phase9_backtest.py`
(the Phase-9 operational monitor, which validated SYNTH-01's compositions) is **superseded, archived and
terminal** — ADR-011 removed the thing it validated — and its published output
`outputs/operational-baseline.md` still cites a source path that has not resolved since the
`studies/` → `research/` migration.

Layer order is enforced by six `import-linter` contracts: `domain` imports nothing project-internal;
`research` imports nothing downstream; `serve` imports neither `research` nor `model`; `model` imports
no research analysis or findings (kernels exempt); `dal` imports no system layer; diagnostic research
imports no predictive research.

**On the verdict vocabularies.** §2 records five parallel ones for a single idea: `lens_status`
(informative / uninformative / unstable) in `classification_summary.csv`; `decision_class`
(informative / uninformative) in `evidence.yaml`; `lifecycle_state` (approved / excluded /
not_applicable) with `downstream_status` (approved / blocked) in `annotations.yaml`;
`association_class` + `promotion_class` + a *third* `downstream_status` (eligible / caveated / blocked)
in the characterization registry; and `decision` (APPROVED-PRIMARY / APPROVED-SECONDARY /
EXCLUDED-REDUNDANT / FWD-SINGLE-SIGNAL) in `synth01_decisions.yaml`. ADR-009 §Context calls two of them
"complementary, not competing" and never reconciles the rest. The design intent going forward is to
collapse all five onto the single ladder the table above describes — **association → characterization →
qualification → verdict** — retiring `lifecycle_state`, `downstream_status` and `promotion_class` as
separate concepts unless a specific consumer is identified that needs one of them; at present none is,
since the runtime surfaces that read `promotion_class` and the operational `downstream_status` were
deleted at `ae90398`. This is scoped as a future reconciliation task. It is **not** done in this edit,
and every vocabulary named above is still live on disk.
