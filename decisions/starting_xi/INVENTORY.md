# Starting XI and Bench Order — capability inventory

**Status:** Phase 1 findings. Read-only pass — no code was written, moved, or refactored.
**Governs nothing.** `DECISION.md` states what is decided; `METRIC.md` governs the harness.
This document reports what the repository already contains, measured against `METRIC.md` §6.

**Method.** Searched by capability, not by filename, across `dal/ domain/ model/ serve/
operational/ research/ tests/ archive/ examples/` plus notebooks, staging contracts, and docs.
Data-side claims were verified against the live mart (`~/.fpl/fpl.mart.parquet`, 31,958 rows,
841 players × GW1–38) rather than inferred. Targeted tests were executed (89 passed) rather
than assumed from the presence of a test file. Where a claim could not be verified it is
listed in §5, not softened into a finding.

---

## 1. Summary table

| # | Capability | Verdict | Where |
|---|---|---|---|
| 1 | As-of player scoring (PPG / points-to-date) | **REUSE AS-IS** | `model/eval/baselines.py:58` |
| 2 | Position / club / budget constraint checking | **ABSENT** (code) — data present | `dal/staging/contracts/element_types.yaml` |
| 3 | Auto-substitution | **ABSENT** | — |
| 4 | Best-legal-XI / constrained selection | **ABSENT** | — |
| 5 | Minutes, NULL-vs-0, pre-registration prefix | **REUSE WITH CHANGE** | `dal/fct/validation/completeness.py:32` |
| 6 | `p_play` | **REUSE WITH CHANGE** | `model/terms/p_play/`, `model/predictions.py:23` |
| 7 | Per-gameweek price | **REUSE AS-IS** | `purchase_price` on the mart |
| 8 | Seeded sampling | **REUSE AS-IS** (convention) / **ABSENT** (squad sampler) | `research/kernels/inferential/resampling.py:20` |
| 9 | Bootstrap + result-writing convention | **REUSE WITH CHANGE** — and one live duplication | `research/kernels/inferential/resampling.py:224` |
| 10 | Fixture / gameweek-block structure | **REUSE WITH CHANGE** | mart columns; `research/families/*/validate/study.py` |

Three of ten are absent, and they are the three the metric is built on: legality, the
counterfactual XI, and auto-substitution. Nothing in the repository has ever selected a
constrained squad — that exclusion is deliberate and documented in three places
(`docs/system-purpose.md:81`, `docs/architecture/intelligence-layer.md:162`, ADR-012 §4).

The reusable half is real and better than expected: as-of scoring, price, availability
probability, and the resampling machinery all exist, are tested, and are lag-safe by
construction. The risk in this slice is not rebuilding what exists — it is **adopting an
existing population filter along with the function that carries it**. Every reusable
component below ships with a population cut (`minutes > 0`, `~is_dgw`, `gw > WARMUP_GW`)
that `METRIC.md` §6 does not authorise.

---

## 2. Findings

### 2.1 As-of player scoring — REUSE AS-IS

**Implementation.** `model/eval/baselines.py:58` `expanding_prior_mean(mart) -> Series`:

```python
mart.groupby("player_id")["total_points"].transform(lambda s: s.shift(1).expanding().mean())
```

`shift(1)` before `expanding()` excludes the current gameweek; `groupby.transform` prevents
the window crossing a player boundary. This is a correct as-of construction.

**Call sites (4).** `model/compose.py:225`, `model/forecast/level_estimators.py:80`
(`lvl_mean`), `model/forecast/shrinkage.py:87`, `model/eval/baselines.py:54` (`base_season`).
Its docstring names it "the single source of the expanding-prior-mean stat" and explains that
the four are numerically equal *because* they share it.

**Tests.** `tests/test_model_eval_components.py:44` (equals the inline lambda),
`tests/test_model_forecast_level_estimators.py:52` (`lvl_mean` identity),
`tests/test_model_eval_baselines.py:35` (leakage-safe on a player's first appearance). Ran: pass.

**Why it is usable as-is.** It is deliberately population-agnostic — the docstring states that
its meaning follows the rows passed, and names both the canonical (`minutes > 0`, DGW-excluded)
and blanks-included variants. The harness supplies its own population and gets the matching
statistic. No modification needed.

**What must not be reused with it.** `build_baseline_features` (same module, line 31) wraps the
same statistic behind `mart[(mart["minutes"] > 0) & (~mart["is_dgw"])]`. That filter is correct
for forecast benchmarking and wrong here: `METRIC.md` §6 requires a no-fixture player to remain
selectable and score 0. Take `expanding_prior_mean`, not `build_baseline_features`.

**A related absence worth stating.** There is **no `points_roll3` on the governed mart** — the
feat layer excludes `total_points` from `_ROLL_COLS` by lens decision
(`dal/feat/feat_player_gameweek.py:16–22`, "removed by lens evaluation (evaluation_circularity
or G2-FAIL)"). Verified: the mart's 64 columns contain no `points_roll*`. If the harness wants a
rolling points window rather than an expanding one, `model/features/build.py:37
add_lagged_rolls` materialises it lag-safely, guarded by the `assert_lag_safe` property
(`build.py:190`: a strictly-prior feature must be NaN on each player's first appearance).

### 2.2 Position, club, and budget constraints — ABSENT in code, present in data

**No implementation exists.** No module validates 2/5/5/3, max-3-per-club, or a budget cap.
`domain/fpl_scoring.py` (328 lines) is scoring rules only — no squad constants. No optimisation
dependency is declared in `pyproject.toml` (no `pulp`, `cvxpy`, `ortools`, `scipy.optimize`).

This is by design, recorded three times: `docs/system-purpose.md:81` ("constrained squad
selection is a separate problem"), `docs/architecture/intelligence-layer.md:162` (a stated
non-goal), and ADR-012 §4, which reserves the squad family for its own abstraction.
`decisions/README.md` identifies `starting_xi/` as that family.

**The constants do exist, upstream.** `dal/staging/contracts/element_types.yaml` maps FPL's own
declaration — `squad_select`, `squad_min_play`, `squad_max_play` — staged by
`dal/staging/stg_entities.py:73`. Values (from `tests/fixtures/create_test_db.py:248`):

| Position | `squad_select` | `squad_min_play` | `squad_max_play` |
|---|---|---|---|
| GK | 2 | 1 | 1 |
| DEF | 5 | 3 | 5 |
| MID | 5 | 2 | 5 |
| FWD | 3 | 1 | 3 |

`squad_select` is `METRIC.md` §2's 2/5/5/3. `squad_min_play`/`squad_max_play` are the XI
legality rule of §1 — and they confirm §3's "`≥3 DEF` formation minimum" against the source
rather than against a recollection. **These never reach the mart**, so the harness cannot read
them today. See migration **M2**.

**Club and budget inputs are on the mart and were verified.** 20 teams; `purchase_price`
non-null on every row. Cheapest legal 2/5/5/3 at GW1 = **64.0** against a 100.0 cap, so §2's
feasible set is large and uniform sampling is not near-degenerate.

**One finding the metric does not currently account for: `team_id` is not stable.** 27 of 841
players carry more than one `team_id` across the season. Max-3-per-club is therefore a per-gameweek
predicate, while §2 builds squads once and holds them. A squad legal at build time can become
illegal in week 30. Listed in §5.

### 2.3 Auto-substitution — ABSENT

Nothing implements it, anywhere — source, tests, notebooks, `archive/`, or scripts. The textual
matches for "bench" and "substitute" are unrelated: `tests/fixtures/create_test_db.py:44`
(scenario SC-6, a player who *came off the bench* — a data fixture, not autosub logic) and
`model/assemble/synth01_*.yaml` ("redundancy substitute", a SYNTH-01 signal verdict).

`METRIC.md` §4 fixes three mechanics that nothing in the repo respects because nothing in the
repo touches them: the GK slot is a separate process from the three outfield slots; a skipped
player stays eligible for the next substitution in the same gameweek; the trigger is strictly
0 minutes. All three must be built.

The 0-minute trigger is at least cleanly expressible in this data: **17,977 rows carry
`minutes == 0`** (played no part) and are structurally distinct from the 2,620 NULL rows. See 2.5.

### 2.4 Best-legal-XI / constrained selection — ABSENT, but not hard

No selection or optimisation routine exists over a squad. There is also no solver dependency to
build on — and none is needed.

**Verified: the search is trivial.** Under `squad_min_play`/`squad_max_play` there are exactly
**8 legal formations** (1 GK; DEF 3–5, MID 2–5, FWD 1–3, summing to 11):

```
(1,3,4,3) (1,3,5,2) (1,4,3,3) (1,4,4,2) (1,4,5,1) (1,5,2,3) (1,5,3,2) (1,5,4,1)
```

Best legal XI = sort each position's realised points descending, then take the max over 8
prefix-sum combinations. No combinatorics, no solver, no new dependency. The same routine
computes §3's second-best XI for the closeness gap by taking the runner-up over the same
enumeration.

**A name collision to avoid.** `model/eval/decision/metrics.py:20` defines
`regret(actual_best_points, picked_points)`. It is **not** the metric's regret: it is
best-scoring-player-in-the-league minus your-single-pick, at per-player top-1 grain
(`backtest.py:72`, `best = outcomes.loc[outcomes["total_points"].idxmax()]` over the whole
gameweek). `METRIC.md` §1 is best-legal-XI minus chosen-XI, at squad-week grain, within one
15-man squad. The word transfers; the code does not. **REBUILD**, and do not import the
existing symbol into the harness under the same name.

### 2.5 Minutes, NULL semantics, and the pre-registration prefix — REUSE WITH CHANGE

**The prefix is a DAL construction, and understanding that is the finding.**
`dal/fct/fct_player_gameweek.py` builds the spine as a **full cartesian product** of
`player_universe × gw_range` (`_build_full_spine`, line 105). Verified exactly: 841 players ×
38 gameweeks = 31,958 rows. A player who debuts in GW20 therefore *has* rows for GW1–19,
synthesised as BGW with NULL performance. That is the origin of `METRIC.md` §6's prefix.

**Verified against the live mart:**

| Quantity | Value |
|---|---|
| NULL-`minutes` rows | 2,620 (8.2% of all rows) |
| — pre-registration prefix (no earlier non-null row) | 2,211 — **84.4%** |
| — genuine no-fixture blank | 409 — 15.6% |
| Players with no non-null row at all | 0 |
| `minutes == 0` rows (featured in no minutes) | 17,977 |
| `is_bgw` ⟺ `minutes` is NULL | exact, both directions |

`METRIC.md` §6's "approximately 84%" is correct to the decimal. The NULL-vs-0 distinction §6
depends on is cleanly present: `is_bgw` marks the union of prefix and blank, and `minutes == 0`
is a separate, well-populated state.

**The prefix predicate exists but is not usable as-is.**
`dal/fct/validation/completeness.py:32 summarise_population_coverage` returns
`first_appearances` — a `player_id → first non-null GW` Series, which is exactly the test §6
specifies. Four problems:

1. It keys on `starts`, not `minutes`. §6 specifies minutes.
2. It returns a dict of EDA summary statistics, not a per-row boolean the harness can filter on.
3. **It is never called.** Grep across the repo: zero production callers.
4. **It has no tests.** Grep: zero test references. (`tests/test_validation_modules.py` covers
   `validate_row_completeness`, its neighbour in the same file — not this function.)

Classifying it REUSE AS-IS on the strength of living in a validated DAL module would be the
error this phase exists to prevent. It is an untested, uncalled EDA helper whose *idea* is
right. **REUSE WITH CHANGE** — see **M3**.

**`is_warmup_gw` is not a registration flag and must not be used as one.**
`dal/feat/feat_player_gameweek.py:121` computes it as `gw == min(gw)` per player. On a cartesian
spine every player's minimum gameweek is GW1, so `is_warmup_gw` is True at GW1 for all 841
players regardless of when they actually registered. It correctly guards rolling-window warmup
— which is its documented purpose, and how `serve/captain.py:35`, `serve/value.py:41` and
`serve/transfers.py:39` use it — but it identifies no late joiners whatsoever.

### 2.6 `p_play` — REUSE WITH CHANGE

**Implementation.** `model/terms/p_play/p_play.py` — `PlayModel`, a per-position logistic of the
derived target `played = 1{minutes > 0}`, fit at all four positions (GK included, deliberately:
unlike the p60 hurdle, appearance is a genuine starters-vs-backups split for keepers). Features
are `minutes_roll3`, `minutes_roll5` (from the mart) and `starts_roll3` (built lag-safe in
`population`). Pool declared at `model/terms/p_play/spec.py`.

**As-of correctness — verified by reading the fit loop, not the docstring.**
`model/terms/_binary_component.py:144–145`:

```python
for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
    prior, test = sdf[sdf["gw"] < t], sdf[sdf["gw"] == t]
```

Train on `gw < t`, predict `gw == t`, expanding, per position. This is a correct walk-forward
fit — the model itself is re-estimated as-of, not fit once on the season and applied backwards.

**`METRIC.md` §6's forbidden-field rule is satisfied.** `p_play` derives entirely from lagged
`minutes` and `starts`. `status` and `chance_of_playing_*` are staged in the `players` table
(`dal/staging/contracts/players.yaml`) but **do not reach the mart** — confirmed against the
mart's full 64-column list. The post-season-snapshot leak §6 prohibits is structurally
unavailable to any mart consumer, which is a stronger guarantee than a convention.

**Tests.** `model/terms/p_play/test_p_play.py`, 8 tests — contract conformance, population
semantics, blank-row scoring, the nailed-above-rotation ranking, and determinism. Ran: pass.

**Cheapest access route.** Not `PlayModel` directly — `model/predictions.py:23
assemble_forecast(keep_all=True)` (the default) already emits a `p_play` column per
`(player_id, gw)`, alongside `e_points_uncond`. `operational/recommend.py:61 enrich_with_forecast` is the existing pattern for merging it onto the mart.

**Four changes the harness must make or absorb:**

1. **DGW rows are excluded.** `PlayModel.population` filters `~mart["is_dgw"]` (line 78).
   `METRIC.md` does not exclude double gameweeks; those rows return NaN `p_play`.
2. **No-fixture rows are excluded** (`minutes.notna()`). Correct for training — a no-fixture row
   is not an appearance decision — but §6 keeps such a player legal at 0 points, so the harness
   must supply its own value. `p_play = 0` is the natural reading; it is a harness decision, not
   a defect in the term.
3. **`WARMUP_GW = 3` means predictions begin at GW4** (`model/eval/walkforward.py:58`).
   `METRIC.md` §6 fixes scope at GW2–38. GW2 and GW3 have no `p_play` — a two-gameweek hole in
   the primary naive baseline of §5. **Do not lower `WARMUP_GW` globally**: it is shared by every
   term via `_binary_component` and `_poisson_component`, and moving it would change every
   published term number. See §5.3.
4. **Cost.** The fit refits per position per gameweek. Compute it once for the season and cache;
   never call it inside a per-squad loop.

### 2.7 Per-gameweek price — REUSE AS-IS

`purchase_price` is a first-class mart column: `float`, `nullable=False`, `Check.ge(0)`,
enforced fail-closed by `dal/mart/mart_schema.py:74` and described there as
"market price (per-GW; consumer-critical)".

**Verified per-gameweek, not a snapshot:** 600 of 841 players carry more than one distinct price
across the season; range 3.7–15.1; zero nulls. Source is `player_histories.value ÷ 10`
(`dal/staging/contracts/player_histories.yaml:164`), aggregated `first` per `(player_id, gw)`
under the semantic `invariant_per_gw` — "FPL uses one price per GW deadline"
(`dal/fct/fct_contracts.py`).

`players.now_cost` is the static snapshot and is explicitly annotated as such in the staging
contract ("NOT per-gameweek"). It does not reach the mart. The two were previously collapsed
under one name; that is already resolved.

**One trap worth naming.** Prefix rows carry a **non-null price** — verified, 2,211 of 2,211.
It arrives via the *forward* fallback in `_apply_bgw_defaults` (step 2,
`dal/fct/fct_player_gameweek.py`), so a not-yet-registered player's GW1 price is his eventual
debut price: future information. This is harmless **only** while the harness excludes prefix
rows from squad construction, which §6 requires anyway. The practical consequence is that a bug
in prefix exclusion will not crash on a missing price — it will silently build a squad
containing a phantom player at a leaked valuation. Prefix exclusion must be asserted, not assumed.

### 2.8 Seeded sampling — REUSE AS-IS (convention) / ABSENT (squad sampler)

**The convention is uniform and worth adopting unchanged.** Every RNG in the repository is
`np.random.default_rng(seed)` — `research/kernels/inferential/resampling.py` (5 sites),
`diagnostic/panel.py:313`, `inferential/variance_components.py:136,226`, `monotonicity.py:44`,
`model/simulate.py:166`. No `np.random.seed`, no global state.

Seed constants are centralised at `research/kernels/inferential/resampling.py:20–22`
(`N_BOOTSTRAP = 1000`, `BOOTSTRAP_SEED = 0`, `CI_LEVEL = 0.95`), "so all studies quote comparable
intervals". A second convention exists: the four family studies use a local `BOOTSTRAP_SEED = 42`
(`research/families/*/validate/study.py`). Both are internally consistent; the harness should
pick one explicitly rather than inherit whichever it imports first.

Determinism is tested as a property, not assumed:
`tests/test_kernels_inferential_resampling.py:20,115`, `model/terms/p_play/test_p_play.py:137`,
and the whole of `tests/stabilization/test_wave3_determinism.py`.

`model/simulate.py:158 iter_sample_blocks` is a good batched-seeded-generator pattern to imitate
for squad draws, but it samples points, not squads — not directly reusable.

**ABSENT: nothing samples a constrained combinatorial object.** `METRIC.md` §2 requires uniform
sampling over the feasible set — budget, 2/5/5/3, and ≤3-per-club simultaneously. Independent
per-position draws with rejection are *not* uniform over that set, and §2 identifies
independence-from-the-ranker as the load-bearing property of the whole design. This is the
single hardest thing to build in the slice and there is no prior art here to start from.

### 2.9 Bootstrap, resampling, and result conventions — REUSE WITH CHANGE

**Gameweek resampling: REUSE AS-IS.**
`research/kernels/inferential/resampling.py:224 block_bootstrap_ci(values, block=4, n=1000,
ci_level=0.95, seed=0)` is a moving-block bootstrap of the mean of a per-gameweek series,
motivated in its docstring exactly as §5 motivates it ("consecutive gameweeks autocorrelate").
This is `METRIC.md` §5's "resample gameweeks, holding squads fixed". Tested and deterministic.

**⚠ There are two `block_bootstrap_ci` functions, and they return different numbers.**

| | `research/kernels/inferential/resampling.py:224` | `model/eval/metrics.py:79` |
|---|---|---|
| `n` resamples | **1000** | **3000** |
| Rounding | 4 dp (`_percentile_ci`) | none |
| block, seed, ci_level | 4, 0, 0.95 | 4, 0, 0.95 |
| Algorithm | moving-block mean | identical |
| Used by | `model/eval/decision/backtest.py:107,168` | `model/eval/walkforward.py:165`, `model/eval/captaincy_backtest.py:106`, 3 `model/terms/test_*_significance.py`, re-exported from `model/eval/__init__.py:10` |

Same name, same signature shape, same algorithm, different resample count — so the same input
yields two different intervals depending on which module the caller imported. `METRIC.md` §5
requires two named intervals and a significance verdict that turns on whether one excludes zero.
This is a live hazard for the harness, not a stylistic duplication. Handling in **M1** — and the
recommendation there is *not* to unify, for a reason worth reading.

**Squad resampling: REBUILD, with a pattern to copy.**
`METRIC.md` §5 forbids resampling squad-weeks as independent draws. The correct structure —
resample clusters, take all of a drawn cluster's rows — already exists at
`research/kernels/inferential/resampling.py:252 cluster_bootstrap_minutes_adjusted_rho`, which
resamples *players* and is explicit that "a row bootstrap understates the uncertainty". But it is
hard-wired to the rho / partial-rho statistic. **There is no generic cluster-bootstrap-of-a-mean.**
Building one (~25 lines, patterned on the existing function) is the honest route; reaching for
`block_bootstrap_ci` on a flattened squad-week series is precisely the error §5 names.

**Result-writing convention: it exists, and it is plural.**

| Surface | Purpose |
|---|---|
| `research/families/*/validate/evidence.yaml` + `annotations.yaml` | Durable verdict-of-record; the governance handoff (CONTEXT.md §4). Frozen by `tests/test_evidence_verdict_freeze.py` |
| `outputs/` | Run artefacts — `minstab_01_detail.csv`, `phase9_backtest_results.yaml`, `operational-baseline.md` |
| `outputs/decisions/gw{N}/{slug}.csv` + `recommendations.md` | Weekly recommendations (`operational/recommend.py:39`) |
| `research/runs/` | Git-ignored run outputs |
| `docs/studies/results/*.md` | Human-readable frozen results |

No single convention covers "a harness result read back programmatically". The closest match to
§5's pre-registered criterion is the **`evidence.yaml` + freeze-test** pattern: a machine-readable
verdict whose values a test pins, so a later run that moves them fails loudly. That is the one
worth copying, and it is what makes §5's "fixed **before** the first run and **not** revised in
response to results" enforceable rather than aspirational.

### 2.10 Fixture and gameweek-block structure — REUSE WITH CHANGE

**On the mart:** `gw` (1–38), `is_bgw`, `is_dgw`, `fixture_context ∈ {BGW, SGW, DGW}`,
`fixture_count`, `fdr_avg`, `was_home` (NULL on DGW by contract). Fixture identity is
deliberately *not* on the mart — a DGW row spans two fixtures, so the key is ambiguous. Two
sanctioned accessors restore it for single-fixture rows: `dal/pipeline.py:load_fixture_map`
→ `(player_id, gw, fixture_id)` and `load_opponent_map` → `(player_id, gw, opponent_team_id)`.
Both exclude DGW rows by construction.

**The GW-block scheme mismatch — encountered, and it is two things, not one.**

*First, the documented one.* `research/findings/FINDINGS.md:264`: "The EDA two-block structure
(GW 1-17 / GW 18-38) is **not** the same as the LENS-FORM three-block structure (early GW 3-12 /
mid GW 13-26 / late GW 27-38)." Gate `G-EDA5-01` records this as a deliberate non-derivation:
"LENS-FORM must define its own three-block structure — this is not derivable from EDA-5." So it
is a known, reasoned divergence, not a defect.

*Second, a stale table.* `research/families/form/LENS_DESIGN.md:106` still shows late = "GW
27-33"; the §6 amendment in the same file corrects it to GW 27-38. Verified that all four family
implementations agree on `(3,12) / (13,26) / (27,38)` — `form`, `fixture`, `availability`,
`market`. The code is consistent; one documentation table is not. Logged as **M6**, not proposed
as urgent.

**Why none of this is directly reusable.** Every block scheme in the repo starts at GW3 or later;
`METRIC.md` §6 fixes scope at GW2–38. The research strata cannot be adopted as the harness's
reporting blocks without redefining the early block, and there is no reason to — §3's conditioning
is on closeness, not on season phase.

**One naming hazard.** "Block" means two unrelated things in code the harness will import side by
side: a *season phase* (`BLOCK_ORDER = ["early", "mid", "late"]`,
`research/kernels/descriptive/binning.py:24`) and *4 consecutive gameweeks resampled together for
autocorrelation* (`block=4` in `block_bootstrap_ci`). Worth a naming decision in the harness
rather than a debugging session later.

---

## 3. Capabilities

Per `CLAUDE.md` and `docs/architecture/platform-capabilities.md` — assessed for the **proposed
migrations in §4**, which is the only part of this document that changes anything.

| Capability | Status | Notes |
|---|---|---|
| Determinism | ✓ | M2/M3 add pure functions of their inputs; M1 deliberately declines a change that would alter published numbers. The RNG convention adopted (`default_rng(seed)`, §2.8) is already property-tested. |
| Observability | ~ | M4 makes the harness's home explicit and import-linter-visible. Run-level observability (manifest, per-gameweek status) is a harness design concern, deferred to Phase 2 — this pass proposes no runtime. |
| Contracts | ✓ | M2's constants get a test asserting they equal `get_staged_element_types()` on the fixture DB, so they cannot drift from FPL's own declaration. M4 adds an explicit import contract rather than relying on convention. |
| Lineage | ✓ | M2 sources the quota from the staging contract that already carries it, so the constants trace to `element_types` rather than to a hardcode. §2 records the provenance of every reused component. |
| Idempotency | ✓ | All proposed changes are additive and re-runnable; none rewrites existing data or artefacts. M1 moves nothing. |
| Testability | ✓ | M3 replaces an untested helper with a tested predicate — the main testability gain. M2 is a constants file plus a drift test. Every reuse claim in §2 is backed by a test that was executed, not merely located. |
| Operability | ~ | M4 requires `pyproject.toml` + `.importlinter` edits that a contributor must not miss; mitigated by import-linter failing closed in CI once added. No operational runtime is proposed yet. |
| Evolvability | ✓ | M2 in `domain/` (the shared leaf that imports nothing project-internal) means a second squad-family decision reuses the quota constants without a new dependency edge. M1's declined unification is recorded with its cost so it can be revisited deliberately. |

---

## 4. Migration proposal

Ordered. Each states what breaks, what needs re-testing, and how many call sites move.
**Unblocking** = the harness cannot be built correctly without it. **Desirable** = real, but not
a dependency of this slice.

The repository has been audited three times for dead weight and found to have little. Nothing
below is proposed on tidiness grounds; the two candidates that would have been (M1's unification
and M5's vocabulary merge) are **argued down** rather than up.

### M1 — Pin the bootstrap fork; do **not** unify it. *(UNBLOCKING — as a decision, not a change)*

The obvious move is to delete one of the two `block_bootstrap_ci` implementations (§2.9) and
repoint callers. **That would be wrong here, and the cost is why.**

Unifying on the kernels version changes `n` from 3000 to 1000 and adds 4-dp rounding for six
call sites: `model/eval/walkforward.py:165`, `model/eval/captaincy_backtest.py:106`,
`model/eval/__init__.py:10` (re-export), and three `model/terms/test_*_significance.py`
significance tests. Those CIs are **published**. `model/eval/captaincy_backtest.py:104` states
its rounding "preserves the prior"; `docs/audits/phase1-audit.md` §4 lists reproduction anchors
that "must still reproduce to 4dp after any change"; `docs/studies/results/predictive-phase5-*.md`
carry frozen captaincy intervals. Unification is a re-baselining exercise, and it would be
performed to serve a slice that does not need it.

- **Proposal:** the harness imports `research.kernels.inferential.resampling.block_bootstrap_ci`
  explicitly and by full path, never the `model.eval` re-export. This document is the record of
  why. Real unification is a separate decision with a stated re-baselining cost.
- **Breaks:** nothing.
- **Re-testing:** none.
- **Call sites moved:** **0.**

### M2 — Squad quota and formation constants into `domain/` *(UNBLOCKING)*

`squad_select` / `squad_min_play` / `squad_max_play` exist only in the staging contract and the
staged frame; they never reach the mart, so the harness cannot read them (§2.2).

- **Proposal:** a new `domain/fpl_squad.py` carrying the quota, the per-position XI min/max, and
  the 8 legal formations, annotated VERIFIED/UNVERIFIED in the established style of
  `domain/fpl_scoring.py`. `domain/` is the shared leaf — `.importlinter no_domain_to_anything`
  forbids it importing anything project-internal — and it already holds exactly this class of
  sourced FPL rule constant.
- **Anti-drift:** one test asserting the constants equal `get_staged_element_types()` on
  `tests/fixtures/test.db`. Without it this is a hardcode wearing a domain module's clothes.
- **Rejected alternative — plumb `element_types` to the mart.** Wrong grain: these are 4 rows of
  per-position constants, not `(player_id, gw)` facts. Adding them as columns would also trip the
  `_produced != _GOVERNED_ROLLING_COLS` governance assertion at
  `dal/feat/feat_player_gameweek.py:124`.
- **Rejected alternative — hardcode inside `starting_xi/`.** Re-declares what the source already
  declares, and forfeits the drift test.
- **Breaks:** nothing.
- **Re-testing:** the new file's own test.
- **Call sites moved:** **0** (new file, ~40 lines).

### M3 — A tested pre-registration predicate *(UNBLOCKING)*

§2.5: the primitive exists in `dal/fct/validation/completeness.py:32` but is keyed on `starts`,
returns an EDA dict, is called by nothing, and is tested by nothing.

- **Proposal:** a per-row boolean predicate keyed on `minutes`, implementing §6's rule directly —
  a NULL row is prefix iff no non-null row exists earlier in the season for that player. It
  belongs in `dal/`: the cartesian spine is a DAL construction, so the DAL should be able to
  label its own artefact. ~15 lines plus tests.
- **Verification already done:** the rule reproduces §6's figure exactly — 84.4% of NULL rows are
  prefix — so the predicate can be tested against a known number rather than against itself.
- **On the existing function:** `summarise_population_coverage` is dead by grep (zero callers,
  zero tests). Given the repo's audit history I am **flagging, not proposing deletion** — that is
  a separate call with its own evidence.
- **Breaks:** nothing.
- **Re-testing:** new tests only.
- **Call sites moved:** **0** (nothing calls the current function).

### M4 — Make `decisions/starting_xi/` an importable package with an import contract *(UNBLOCKING)*

The harness has **no legal home today**. `.importlinter` forbids `serve → model` and
`serve → research`; the harness needs `p_play` (model) and the resampling kernels (research), so
it cannot live in `serve/`. `research → model` is forbidden, so it cannot live in `research/`.
`operational/` is the composition root and sits outside import-linter's `root_packages`
altogether. `model/eval/decision/` is the nearest legal home, but ADR-012 §4 and
`decisions/README.md` both place the squad family outside `DecisionSpec`.

- **Proposal:** make `decisions/starting_xi/` a package; add it to `.importlinter` `root_packages`
  with a contract permitting `domain`, `dal`, `model.terms`, `research.kernels`, and forbidding
  anything from importing it except `operational`.
- **Breaks:** nothing.
- **Re-testing:** import-linter run (already in CI per `CLAUDE.md`).
- **Call sites moved:** **0.** Two files edited (`pyproject.toml`, `.importlinter`).

### M5 — `position` vs `position_label`: normalise at the harness boundary, do **not** unify *(DESIRABLE — argued down)*

The mart carries both. Verified: `position` ∈ {GK, DEF, MID, FWD}; `position_label` ∈ {GKP, DEF,
MID, FWD} — they differ only at goalkeeper. `serve/` ranks on `position_label`
(`decision_engine.py:62`), `model/` fits on `position` (`_binary_component.py:144`), and the
research families key on `position_label`.

Unifying would touch `serve/input_contracts.py` `_REQUIRED_SPINE_COLS`, every serve
`DecisionSpec.output_cols`, the family `evidence.yaml` keys, and
`tests/test_evidence_record.py:84–95`, which explicitly tests GKP→GK normalisation as intended
behaviour. That is a large, risky sweep serving no requirement of this slice.

- **Proposal:** the harness normalises to one vocabulary at its own boundary and documents which.
- **Breaks:** nothing.
- **Call sites moved:** **0.**

### M6 — Stale block table in `LENS_DESIGN.md` *(DESIRABLE — noted, not urgent)*

`research/families/form/LENS_DESIGN.md:106` shows late = GW 27-33; the §6 amendment below it and
all four implementations say GW 27-38 (§2.10). A one-line documentation correction. Recorded
because it was found while checking capability 10 — not because this slice needs it.

---

## 5. Could not determine

Listed because a wrong REUSE AS-IS costs more than an honest gap. Items 1, 2 and 5 are one-line
clarifications to `METRIC.md`; items 3, 4 and 7 are measurements; item 6 is a question for the user.

**Status since publication.** §5.2 and §5.5 are **closed** by `METRIC.md` §2, which now assesses all
four feasibility conditions once at the build gameweek (GW2) and never re-checks them. §5.7 is
**closed by measurement** — it was run; see below. The rest remain open.

**5.1 — The "as-of PPG" denominator.** §3 defines closeness in "as-of PPG" and §5 names
"PPG-to-date" as a floor ranker, but neither fixes whether the denominator is *gameweeks elapsed*
or *appearances made*. `expanding_prior_mean` computes either, depending on the frame passed
(§2.1), so this is not a code question — but the two produce different closeness gaps, a different
exclusion count under §3's zero-gap rule, and a different naive baseline. **Settled by:** one line
in `METRIC.md` §3.

**5.2 — When max-3-per-club binds.** 27 of 841 players change `team_id` mid-season (verified,
§2.2). §2 builds squads once and holds them all season, so a squad legal at construction can
become illegal later. **Settled by:** one line in `METRIC.md` §2 stating whether legality is
evaluated at build time only.

**5.3 — `p_play` over GW2–GW3.** §6 fixes scope at GW2–38; `WARMUP_GW = 3` means `p_play` exists
only from GW4 (§2.6). Two gameweeks of the primary naive baseline are unavailable. **Settled by:**
either §5 accepting a reduced window for that ranker and reporting it, or a per-term warmup
override — **not** by changing the global `WARMUP_GW`, which would move every published term
number.

**5.4 — Whether `p_play`'s DGW exclusion matters.** `PlayModel.population` drops `is_dgw` rows,
which the metric does not. Whether this is material depends on how many squad-weeks contain a
DGW player — a harness output, not a document question. **Settled by:** measuring it on the first
run, in the same spirit as §4's live-event count.

**5.5 — Whether the budget cap binds only at build time.** Prices move weekly for 600 of 841
players (§2.7). §2 imposes the cap on a squad "built once". Presumably build-time only.
**Settled by:** one line in `METRIC.md` §2.

**5.6 — The prior "`dal/` canonical vs `domain` split, physical move to `fpl-ingest` deferred".**
I could not find this recorded anywhere in the repository. `fpl-ingest` appears in exactly three
places — `CONTEXT.md:8`, `CONTEXT.md:91`, `docs/architecture/layer-boundaries.md:13` — all
describing it only as the external producer of `~/.fpl/fpl.db`. No migration plan, no deferral
record, no ADR. What I *can* evidence is an observable scatter of canonical FPL reference
knowledge across `domain/fpl_scoring.py`, `dal/staging/contracts/*.yaml`, and
`dal/mart/mart_analytical.py:34`, with the position vocabulary independently redeclared at
`dal/mart/mart_schema.py:41`, `domain/registry/schema.py:137`, `model/eval/walkforward.py:58`,
and `model/forecast/count_models.py:37`. Of that scatter, **only the squad quota actually blocks
this slice**, and M2 addresses it without touching the rest. **Settled by:** the user pointing at
the document, or confirming it was a conversation rather than a commit.

**5.7 — Whether `operational/backtest.py` has ever run against the real mart. RESOLVED — it
cannot.** This was recorded as a code-path inference. It has since been **executed**, and the
inference was correct but understated.

Run 2026-08-18 against the live mart (`~/.fpl/fpl.mart.parquet`, 31,958 rows, GW1–38) along the
real operational path — `dal.pipeline.load()` → `operational.recommend.enrich_with_forecast` →
`operational.backtest.backtest_decision(CAPTAIN_EVAL, enriched, [10, 11, 12])`:

- `enrich_with_forecast` **succeeds** (~9 s), adding 12 forecast columns: `appearance`, `goals`,
  `e_points`, `base_season`, `p_play`, `e_points_uncond`, `sim_mean`, `sim_sd`, `p10`, `p50`,
  `p90`, `p_haul`.
- `points_roll3` is **absent** from the enriched frame — nothing on the operational path
  materialises it.
- `backtest_decision` **raises `ValueError` on the first evaluated gameweek**, at
  `model/eval/decision/backtest.py:59` → `research/kernels/evaluation.py:46`:

```
assert_no_future_leakage: missing rolling columns ['points_roll3'] for gw=10.
Features must come from dal.pipeline.load().mart to guarantee temporal integrity
(lag-1 rolling windows).
```

**The conclusion is stronger than the original flag.** It is not just that the driver has only been
exercised on synthetic frames: the decision-backtest path is **unrunnable against the governed mart
at all**, for every registered decision — captain, value and transfers route through the same guard
(`backtest.py:59` and `:137`). Its entire coverage rests on fixtures that fabricate the missing
column (`tests/test_decision_backtest.py:32`, `tests/test_operational_backtest.py:28`).

**A second finding fell out of the run.** The guard's remediation advice is itself wrong. It
instructs the caller to source features from `dal.pipeline.load().mart` — which is exactly what the
failing call did. Following the error message as written reproduces the failure. The cause is that
`assert_no_future_leakage` asserts the presence of a column the governed mart deliberately excludes
(§2.1), so the guard's required-column set and the mart contract have diverged. That is the same
governance question `METRIC.md` §5 routes for `points_roll3`, seen from the other end: whichever way
it is answered, one of the two has to move.

**Consequence for this slice.** The `starting_xi` harness must not adopt `assert_no_future_leakage`
as its leakage guard without resolving this first — it would import a guard that fails closed
against the very data the harness reads.

---

## 6. What this pass did not do

No code was written, no files moved, no refactor performed. Every migration in §4 is a proposal;
execution is a later phase and a separate decision. The two candidates most likely to be waved
through on appearance — the duplicate bootstrap (M1) and the position vocabulary (M5) — are
recommended **against** changing, with the cost of changing them stated so the recommendation can
be overturned deliberately rather than by default.
