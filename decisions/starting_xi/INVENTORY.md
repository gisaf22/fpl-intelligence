# Starting XI and Bench Order — capability inventory

**Status:** Phase 1 findings. Read-only pass — no code was written, moved, or refactored.
**Governs nothing, and recommends nothing.** `DECISION.md` states what is decided; `METRIC.md`
governs the harness; `DESIGN.md` states how it is built and what is reused. This document answers
one question only — **what data and capabilities exist in the repository today** — and states
facts. It carries no verdicts, no reuse labels, no proposals, and no judgement about design fit.

**Method.** Searched by capability, not by filename, across `dal/ domain/ model/ serve/
operational/ research/ tests/ archive/ examples/` plus notebooks, staging contracts, and docs.
Data-side claims were verified against the live mart (`~/.fpl/fpl.mart.parquet`, 31,958 rows,
841 players × GW1–38) rather than inferred. Targeted tests were executed (89 passed) rather
than assumed from the presence of a test file. Where a claim could not be verified it is
listed in §3, not softened into a finding.

---

## 1. Summary table

| # | Capability | Exists? | Where |
|---|---|---|---|
| 1 | As-of player scoring (PPG / points-to-date) | Yes | `model/eval/baselines.py:58` |
| 2 | Position / club / budget constraint checking | No code; the constants exist upstream | `dal/staging/contracts/element_types.yaml` |
| 3 | Auto-substitution | No | — |
| 4 | Best-legal-XI / constrained selection | No | — |
| 5 | Minutes, NULL-vs-0, pre-registration prefix | Data yes; one uncalled, untested helper | `dal/fct/validation/completeness.py:32` |
| 6 | `p_play` | Yes, with three population cuts | `model/terms/p_play/`, `model/predictions.py:23` |
| 7 | Per-gameweek price | Yes | `purchase_price` on the mart |
| 8 | Seeded sampling | Convention yes; no squad sampler | `research/kernels/inferential/resampling.py:20` |
| 9 | Bootstrap + result-writing convention | Yes, and duplicated | `research/kernels/inferential/resampling.py:224` |
| 10 | Fixture / gameweek-block structure | Yes | mart columns; `research/families/*/validate/study.py` |

Three of the ten have no implementation anywhere in the repository: legality checking, the
counterfactual best XI, and auto-substitution. Nothing in the repository selects a constrained
squad, and that exclusion is recorded in three places (`docs/system-purpose.md:81`,
`docs/architecture/intelligence-layer.md:162`, ADR-012 §4).

Three of the seven that do exist carry a population cut written into the function itself:
`build_baseline_features` (`minutes > 0` and `~is_dgw`, §2.1), `PlayModel.population` (`~is_dgw`
and `minutes.notna()`, §2.6), and the walk-forward loop (`gw > WARMUP_GW`, §2.6). `METRIC.md` §6
defines a different population from all three.

---

## 2. Findings

### 2.1 As-of player scoring

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

**It carries no population of its own.** Its docstring states that its meaning follows the rows
passed, and names both the canonical (`minutes > 0`, DGW-excluded) and blanks-included variants.
The statistic it returns is therefore determined by the frame the caller supplies.

**Its wrapper does carry one.** `build_baseline_features` (same module, line 31) computes the same
statistic behind `mart[(mart["minutes"] > 0) & (~mart["is_dgw"])]`. That filter drops rows for a
player with no fixture; `METRIC.md` §6 keeps such a player selectable at 0 points.

**`points_roll3`.** There is **no `points_roll3` on the governed mart** — the
feat layer excludes `total_points` from `_ROLL_COLS` by lens decision
(`dal/feat/feat_player_gameweek.py:16–22`, "removed by lens evaluation (evaluation_circularity
or G2-FAIL)"). Verified: the mart's 64 columns contain no `points_roll*`. The one helper in the
repository that materialises a rolling window of an arbitrary mart column is
`model/features/build.py:37 add_lagged_rolls`, guarded by the `assert_lag_safe` property
(`build.py:190`: a strictly-prior feature must be NaN on each player's first appearance).

**Two `min_periods` conventions coexist in the codebase.** `build_baseline_features` computes its
rolling points columns inline at `model/eval/baselines.py:53` with `min_periods=k`, so a window's
warmup rows are **NaN**. `add_lagged_rolls` (`model/features/build.py:37`) and every `_lag_roll`
use `min_periods=1`, so warmup rows are **partial-window means**. The two yield different values
over the warmup rows of any window. The `base_roll{k}` expression is an expression inside
`build_baseline_features`, not a separately callable helper.

**Importing `add_lagged_rolls` brings in `model.features`, whose fan-out is two leaf modules.**
`model/features/__init__.py` imports `build` and `spec`; `build` imports only `model.features.spec`
plus `pandas`, and `spec` imports nothing project-internal.

### 2.2 Position, club, and budget constraints

**No implementation exists.** No module validates 2/5/5/3, max-3-per-club, or a budget cap.
`domain/fpl_scoring.py` (328 lines) is scoring rules only — no squad constants. No optimisation
dependency is declared in `pyproject.toml` (no `pulp`, `cvxpy`, `ortools`, `scipy.optimize`).

This exclusion is recorded three times: `docs/system-purpose.md:81` ("constrained squad
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

`squad_select` is `METRIC.md` §2's 2/5/5/3; `squad_min_play`/`squad_max_play` are the per-position
XI bounds, including the `≥3 DEF` minimum. **These never reach the mart** — they exist only in the
staging contract and the staged frame, readable via `dal/staging/stg_entities.py:73
get_staged_element_types(db_path)`, which takes a database path and returns a DataFrame.

**Where such constants live today, and what constrains that location.** `domain/` holds sourced
FPL rule constants — `domain/fpl_scoring.py`, annotated VERIFIED/UNVERIFIED per constant. There is
**no `domain/fpl_squad.py`**; the directory contains `decision.py`, `fpl_scoring.py`,
`fpl_signals.py`, `registry_signals.py`, `signal_layers.py` and `registry/`. `.importlinter`'s
`no_domain_to_anything` contract forbids `domain` importing `dal`, `research`, `model` or `serve`.
Separately, the feat layer asserts that its derived columns exactly equal `_GOVERNED_ROLLING_COLS`
and raises `RuntimeError` otherwise (`dal/feat/feat_player_gameweek.py:124`), so a new mart column
cannot be added without that set changing.

**Club and budget inputs are on the mart and were verified.** 20 teams; `purchase_price`
non-null on every row. Cheapest legal 2/5/5/3 at GW1 = **64.0** against a 100.0 cap.

**One finding, since resolved: `team_id` is not stable.** 27 of 841 players carry more than one
`team_id` across the season, so max-3-per-club is a per-gameweek predicate while `METRIC.md` §2
builds squads once and holds them, so a squad legal at build time can become illegal later in the
season. Raised as §3.2; `METRIC.md` §2 now assesses all four feasibility conditions once at GW2 and
never re-checks them.

### 2.3 Auto-substitution

Nothing implements it, anywhere — source, tests, notebooks, `archive/`, or scripts. The textual
matches for "bench" and "substitute" are unrelated: `tests/fixtures/create_test_db.py:44`
(scenario SC-6, a player who *came off the bench* — a data fixture, not autosub logic) and
`model/assemble/synth01_*.yaml` ("redundancy substitute", a SYNTH-01 signal verdict).

`METRIC.md` §4 defines three mechanics of the rule: the GK slot is a separate process from the
three outfield slots; a skipped player stays eligible for the next substitution in the same
gameweek; the trigger is strictly 0 minutes. No code in the repository reads or applies any of
the three.

The two states the 0-minute trigger distinguishes are separately present on the mart:
**17,977 rows carry `minutes == 0`** (played no part) and are structurally distinct from the
2,620 NULL rows. See 2.5.

### 2.4 Best-legal-XI / constrained selection

No selection or optimisation routine exists over a squad, and no solver dependency is declared.

**The size of the search space, verified.** Under `squad_min_play`/`squad_max_play` there are exactly
**8 legal formations** (1 GK; DEF 3–5, MID 2–5, FWD 1–3, summing to 11):

```
(1,3,4,3) (1,3,5,2) (1,4,3,3) (1,4,4,2) (1,4,5,1) (1,5,2,3) (1,5,3,2) (1,5,4,1)
```

A best legal XI is therefore determined by sorting each position's realised points descending and
taking the maximum over 8 prefix-sum combinations; the runner-up over the same enumeration is the
second-best XI `METRIC.md` §3's closeness gap uses.

**A name collision.** `model/eval/decision/metrics.py:20` defines
`regret(actual_best_points, picked_points)`. It is **not** the metric's regret: it is
best-scoring-player-in-the-league minus your-single-pick, at per-player top-1 grain
(`backtest.py:72`, `best = outcomes.loc[outcomes["total_points"].idxmax()]` over the whole
gameweek). `METRIC.md` §1 is best-legal-XI minus chosen-XI, at squad-week grain, within one
15-man squad. The name is shared; the quantity is not.

### 2.5 Minutes, NULL semantics, and the pre-registration prefix

**The prefix is a DAL construction.**
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

`METRIC.md` §6's "approximately 84%" is correct to the decimal. `is_bgw` marks the union of prefix
and blank; `minutes == 0` is a separate, well-populated state.

**The one function that computes a first-appearance gameweek.**
`dal/fct/validation/completeness.py:32 summarise_population_coverage` returns
`first_appearances`, a `player_id → first non-null GW` Series. Four properties of it:

1. It keys on `starts`, not `minutes`. `METRIC.md` §6 specifies minutes.
2. It returns a dict of EDA summary statistics, not a per-row boolean.
3. **It is never called.** Grep across the repo: zero production callers.
4. **It has no tests.** Grep: zero test references. (`tests/test_validation_modules.py` covers
   `validate_row_completeness`, its neighbour in the same file — not this function.)

`METRIC.md` §6's own rule — a NULL row is prefix iff no non-null row exists earlier in the season
for that player — reproduces the 84.4% figure in the table above when evaluated directly.

**`is_warmup_gw` is not a registration flag.**
`dal/feat/feat_player_gameweek.py:121` computes it as `gw == min(gw)` per player. On a cartesian
spine every player's minimum gameweek is GW1, so `is_warmup_gw` is True at GW1 for all 841
players regardless of when they actually registered. It correctly guards rolling-window warmup
— which is its documented purpose, and how `serve/captain.py:35`, `serve/value.py:41` and
`serve/transfers.py:39` use it — but it identifies no late joiners whatsoever.

### 2.6 `p_play`

**Implementation.** `model/terms/p_play/p_play.py` — `PlayModel`, a per-position logistic of the
derived target `played = 1{minutes > 0}`, fit at all four positions (GK included, deliberately:
unlike the p60 hurdle, appearance is a genuine starters-vs-backups split for keepers). Features
are `minutes_roll3`, `minutes_roll5` (from the mart) and `starts_roll3` (built lag-safe in
`population`). Pool declared at `model/terms/p_play/spec.py`.

**The fit loop, read directly rather than taken from the docstring.**
`model/terms/_binary_component.py:144–145`:

```python
for t in sorted(g for g in sdf["gw"].unique() if g > WARMUP_GW):
    prior, test = sdf[sdf["gw"] < t], sdf[sdf["gw"] == t]
```

Train on `gw < t`, predict `gw == t`, expanding, per position. The model is re-estimated at each
gameweek from strictly prior rows, not fit once on the season and applied backwards.

**What `_binary_component.py:144` is.** It is the walk-forward loop of the **shared base class**
`BinaryPerPositionComponent`, not `p_play`'s own implementation. Three terms inherit it —
`model/terms/p_play/p_play.py:40`, `model/terms/minutes/minutes.py:31` and
`model/terms/defensive_contribution/defensive_contribution.py:34`. `p_play`'s own module declares
only its target, pool and term (`p_play.py:40` `PlayModel`, `:83` `PlayTerm`).

**`p_play`'s transitive import reach into `model/`.** Measured by importing
`model.terms.p_play.p_play` in a clean interpreter: `sys.modules` then holds `model.terms._base`,
`model.terms._binary_component`, `model.terms.p_play.spec`, `model.features.spec`,
`model.features.build`, and — because `model/eval/__init__.py` imports eagerly (§2.11) — the whole
of `model.eval`: `baselines`, `metrics`, `population`, `scorer`, `walkforward`. Plus `statsmodels`
and `pandas`. Nothing from `research/` or `serve/`. `model.eval.metrics` and
`model.eval.walkforward` are reached directly from `model/terms/_binary_component.py:23-24`.

**The fields `METRIC.md` §6 forbids are not on the mart.** `p_play` derives entirely from lagged
`minutes` and `starts`. `status` and `chance_of_playing_*` are staged in the `players` table
(`dal/staging/contracts/players.yaml`) and **do not reach the mart** — confirmed against the mart's
full 64-column list. They are therefore unavailable to any mart consumer.

**Tests.** `model/terms/p_play/test_p_play.py`, 8 tests — contract conformance, population
semantics, blank-row scoring, the nailed-above-rotation ranking, and determinism. Ran: pass.

**A `p_play` column is emitted without calling `PlayModel` directly.**
`model/predictions.py:23 assemble_forecast(keep_all=True)` (the default) emits `p_play` per
`(player_id, gw)`, alongside `e_points_uncond`. `operational/recommend.py:61
enrich_with_forecast` merges that output onto the mart.

**Three population cuts and one cost property, all carried by the term itself:**

1. **DGW rows are excluded.** `PlayModel.population` filters `~mart["is_dgw"]` (line 78).
   `METRIC.md` does not exclude double gameweeks; those rows return NaN `p_play`.
2. **No-fixture rows are excluded** (`minutes.notna()`). `METRIC.md` §6 keeps such a player legal
   at 0 points, so those rows carry no `p_play` value.
3. **`WARMUP_GW = 3` means predictions begin at GW4** (`model/eval/walkforward.py:58`), while
   `METRIC.md` §6 fixes scope at GW2–38. GW2 and GW3 have no `p_play`. `WARMUP_GW` is shared by
   every term via `_binary_component` and `_poisson_component`, so its value is not local to
   `p_play`. See §3.3.
4. **Cost.** The fit re-estimates per position per gameweek.

### 2.7 Per-gameweek price

`purchase_price` is a first-class mart column: `float`, `nullable=False`, `Check.ge(0)`,
enforced fail-closed by `dal/mart/mart_schema.py:74` and described there as
"market price (per-GW; consumer-critical)".

**Verified per-gameweek, not a snapshot:** 600 of 841 players carry more than one distinct price
across the season; range 3.7–15.1; zero nulls. Source is `player_histories.value ÷ 10`
(`dal/staging/contracts/player_histories.yaml:164`), aggregated `first` per `(player_id, gw)`
under the semantic `invariant_per_gw` — "FPL uses one price per GW deadline"
(`dal/fct/fct_contracts.py`).

`players.now_cost` is the static snapshot and is explicitly annotated as such in the staging
contract ("NOT per-gameweek"). It does not reach the mart.

**Prefix rows carry a non-null price** — verified, 2,211 of 2,211.
It arrives via the *forward* fallback in `_apply_bgw_defaults` (step 2,
`dal/fct/fct_player_gameweek.py`), so a not-yet-registered player's GW1 price is his eventual
debut price — a value from later in the season. A prefix row therefore fails no null check on
price; nothing about the price column distinguishes a prefix row from a real one.

### 2.8 Seeded sampling

**The RNG convention is uniform across the repository.** Every RNG in the repository is
`np.random.default_rng(seed)` — `research/kernels/inferential/resampling.py` (5 sites),
`diagnostic/panel.py:313`, `inferential/variance_components.py:136,226`, `monotonicity.py:44`,
`model/simulate.py:166`. No `np.random.seed`, no global state.

Seed constants are centralised at `research/kernels/inferential/resampling.py:20–22`
(`N_BOOTSTRAP = 1000`, `BOOTSTRAP_SEED = 0`, `CI_LEVEL = 0.95`), "so all studies quote comparable
intervals". A second convention exists: the four family studies use a local `BOOTSTRAP_SEED = 42`
(`research/families/*/validate/study.py`). Each is internally consistent; the two differ in seed
value, so which one a caller gets depends on which module it imports from.

Determinism is tested as a property, not assumed:
`tests/test_kernels_inferential_resampling.py:20,115`, `model/terms/p_play/test_p_play.py:137`,
and the whole of `tests/stabilization/test_wave3_determinism.py`.

`model/simulate.py:158 iter_sample_blocks` is a batched seeded generator; it samples points, not
squads.

**No manager squad, picks, or bench-order history exists anywhere in the repository.** The mart
carries no picks, bench, squad, or manager/entry column; no module reads one; `bench_order` appears
in no code path. The mart's `starts` column is not that record — it marks that a player started for
their club, not that a manager started them in an FPL XI. There is therefore no observed squad to
replay a selection against.

**Nothing in the repository samples a constrained combinatorial object.** `METRIC.md` §2 requires uniform
sampling over the feasible set — budget, 2/5/5/3, and ≤3-per-club simultaneously. Whether
per-position draws with rejection are uniform over that set **depends on what is rejected**:
discarding the whole 15 and redrawing independently conditions a uniform draw over the
position-quota set on membership in the feasible set, which is uniform over the feasible set;
redrawing only the offending position while holding the rest is not. No implementation of either
form exists in the repository.

> **Corrected 2026-08-20.** As published, this paragraph stated flatly that "independent
> per-position draws with rejection are *not* uniform over that set". That is true of partial
> rejection and false of whole-draw rejection; the distinction was identified in `DESIGN.md` §2.4
> and the claim is narrowed above rather than left standing.

### 2.9 Bootstrap, resampling, and result conventions

**Gameweek resampling.**
`research/kernels/inferential/resampling.py:224 block_bootstrap_ci(values, block=4, n=1000,
ci_level=0.95, seed=0)` is a moving-block bootstrap of the mean of a per-gameweek series,
motivated in its docstring exactly as `METRIC.md` §5 motivates it ("consecutive gameweeks autocorrelate").
This is `METRIC.md` §5's "resample gameweeks, holding squads fixed". Tested and deterministic.

**There are two `block_bootstrap_ci` functions, and they return different numbers.**

| | `research/kernels/inferential/resampling.py:224` | `model/eval/metrics.py:79` |
|---|---|---|
| `n` resamples | **1000** | **3000** |
| Rounding | 4 dp (`_percentile_ci`) | none |
| block, seed, ci_level | 4, 0, 0.95 | 4, 0, 0.95 (block from the named `BLOCK_GWS`, `metrics.py:18`) |
| Algorithm | moving-block mean | identical |
| Used by | `model/eval/decision/backtest.py:107,168` | `model/eval/walkforward.py:165`, `model/eval/captaincy_backtest.py:106`, 3 `model/terms/test_*_significance.py`, re-exported from `model/eval/__init__.py:10` |

Same name, same signature shape, same algorithm, different resample count — so the same input
yields two different intervals depending on which module the caller imported.

**The `model/eval` implementation's outputs are published.** Its six call sites include
`model/eval/walkforward.py:165` and `model/eval/captaincy_backtest.py:106`, where `_ci3`
(`captaincy_backtest.py:103`) rounds its endpoints to **3dp**, its docstring stating this
"preserves the prior displayed precision now that the raw helper returns unrounded floats".
`docs/audits/phase1-audit.md` §4 (line 189) is headed "Reproduction anchors (must still reproduce
to 4dp after any change)", and five `docs/studies/results/predictive-phase5-*.md` files carry
frozen captaincy intervals.

**Cluster resampling.**
`METRIC.md` §5 forbids resampling squad-weeks as independent draws. A cluster resampler —
resample clusters, take all of a drawn cluster's rows — exists at
`research/kernels/inferential/resampling.py:252 cluster_bootstrap_minutes_adjusted_rho`, which
resamples *players* and states in its docstring that "a row bootstrap understates the
uncertainty". It is hard-wired to the rho / partial-rho statistic. **There is no generic
cluster-bootstrap-of-a-mean in the repository.**

**Result-writing convention: it exists, and it is plural.**

| Surface | Purpose |
|---|---|
| `research/families/*/validate/evidence.yaml` + `annotations.yaml` | Durable verdict-of-record; the governance handoff (CONTEXT.md §4). Frozen by `tests/test_evidence_verdict_freeze.py` |
| `outputs/` | Run artefacts — `minstab_01_detail.csv`, `phase9_backtest_results.yaml`, `operational-baseline.md` |
| `outputs/decisions/gw{N}/{slug}.csv` + `recommendations.md` | Weekly recommendations (`operational/recommend.py:39`) |
| `research/runs/` | Git-ignored run outputs |
| `docs/studies/results/*.md` | Human-readable frozen results |

None of the five is a convention for "a harness result read back programmatically". The
`evidence.yaml` + freeze-test pattern is the only one of the five whose values a test pins, so
that a later run which moves them fails.

### 2.10 Fixture and gameweek-block structure

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
"LENS-FORM must define its own three-block structure — this is not derivable from EDA-5." The
divergence is recorded rather than incidental.

*Second, a stale table.* `research/families/form/LENS_DESIGN.md:106` still shows late = "GW
27-33"; the §6 amendment in the same file corrects it to GW 27-38. Verified that all four family
implementations agree on `(3,12) / (13,26) / (27,38)` — `form`, `fixture`, `availability`,
`market`. The code is consistent; that one documentation table is not.

**Every block scheme in the repository starts at GW3 or later.** `METRIC.md` §6 fixes scope at
GW2–38, so no existing scheme covers GW2.

**"Block" names two different things in code.** A *season phase*
(`BLOCK_ORDER = ["early", "mid", "late"]`, `research/kernels/descriptive/binning.py:24`) and
*4 consecutive gameweeks resampled together for autocorrelation* (`block=4` in
`block_bootstrap_ci`).

### 2.11 Package boundaries, `__init__.py` fan-out, and the pytest import surface

*Recorded 2026-08-20, after the main pass, from facts established while designing.*

**`decisions/starting_xi/` is not a Python package today.** The directory holds four markdown files
(`DECISION.md`, `DESIGN.md`, `INVENTORY.md`, `METRIC.md`), no Python, and no `__init__.py`. Nothing
in the tree imports from it. (It held three markdown files when `DESIGN.md` §3.1 recorded this;
`DESIGN.md` itself is the fourth.)

**A package `__init__.py` in this repository can carry a large transitive fan-out.**
`model/eval/baselines.py` imports only `pandas`, but importing it executes
`model/eval/__init__.py`, which eagerly imports `baselines`, `metrics`, `population`, `scorer` and
`walkforward`. That fan-out stays inside `model.eval` and reaches no forecast component. The
`model/eval/` modules that do reach `model.compose` / `model.simulate` are `calibration.py`,
`captaincy_backtest.py` and `scoring_conformance.py` directly, plus `captaincy_diagnostics.py`
transitively via `captaincy_backtest`; none of the four is named in `model/eval/__init__.py`.

**The import-graph constraints on where such a package could sit.** `.importlinter` declares
`root_packages = dal, domain, research, model, serve` and forbids `serve → model`,
`serve → research`, `research → model`, and `domain → {dal, research, model, serve}`.
`operational/` is not a root package and so is not covered by any contract.
`decisions/README.md:22` records that ADR-012 §4 restricts the `DecisionSpec` family to per-player
ranking and excludes the squad family, and `decisions/README.md:29` names `starting_xi/` as that
family.

**Import-linter does not see parent-package `__init__.py` execution.** It analyses the static
import graph, in which a module importing a sibling submodule is not an edge to the parent
package's own imports — even though Python executes the parent's `__init__.py` at runtime.

**`pyproject.toml:34` sets `testpaths = ["tests", "model"]`.** A pytest session therefore imports
`model` — and, through it, `statsmodels` — before any test outside those paths runs. An in-process
`sys.modules` assertion about which packages a module pulls in cannot distinguish the module under
test from what the session already imported; establishing that requires a subprocess.

### 2.12 Position vocabulary

Three position columns reach the mart, verified against the live parquet's 64 columns:

| Column | Values |
|---|---|
| `position` | GK, DEF, MID, FWD |
| `position_label` | GKP, DEF, MID, FWD |
| `position_code` | 1, 2, 3, 4 |

`position` and `position_label` differ only at goalkeeper. `position_label` is the canonical name
declared in `dal/staging/contracts/element_types.yaml:15` and is a required spine column in
`serve/input_contracts.py:24`; `serve/decision_engine.py:62` ranks by it, and the research
families key on it. `model/terms/_binary_component.py` fits per `position`.
`tests/test_evidence_record.py:84–95` tests GKP→GK normalisation on the way into `evidence.yaml`
as intended behaviour.

---

## 3. Could not determine

Questions this pass could not answer from the repository, and what has since answered them.
§3.2 and §3.5 were answered by `METRIC.md` §2, which assesses all four feasibility conditions once
at the build gameweek (GW2) and never re-checks them. §3.1 was answered by `METRIC.md` §3. §3.7
was answered by running it; see below. §3.3, §3.4 and §3.6 remain unanswered.

**3.1 — The "as-of PPG" denominator. Answered.** `expanding_prior_mean` computes a per-gameweek
or a per-appearance mean depending on the frame passed (§2.1), and the repository does not fix
which. `METRIC.md` §3 now specifies gameweeks elapsed, with blanked and no-fixture weeks counted
at 0 and pre-registration weeks excluded, extended to the 3-gameweek baseline.

**3.2 — When max-3-per-club binds.** 27 of 841 players change `team_id` mid-season (verified,
§2.2). §2 builds squads once and holds them all season, so a squad legal at construction can
become illegal later. Whether legality is evaluated at build time only was not stated in the
repository. `METRIC.md` §2 now states it.

**3.3 — `p_play` over GW2–GW3.** `METRIC.md` §6 fixes scope at GW2–38; `WARMUP_GW = 3` means `p_play` exists
only from GW4 (§2.6). Two gameweeks of that baseline's window are unavailable. `WARMUP_GW` is
global to every term (§2.6), and no per-term override exists in the code.

**3.4 — Whether `p_play`'s DGW exclusion matters.** `PlayModel.population` drops `is_dgw` rows,
which the metric does not. How many squad-weeks would contain a DGW player is not measurable
without a squad set, and no squad set exists yet.

**3.5 — Whether the budget cap binds only at build time.** Prices move weekly for 600 of 841
players (§2.7). `METRIC.md` §2 imposes the cap on a squad "built once"; the repository does not
determine whether the cap is re-evaluated later.

**3.6 — The prior "`dal/` canonical vs `domain` split, physical move to `fpl-ingest` deferred".**
I could not find this recorded anywhere in the repository. `fpl-ingest` appears in exactly three
places — `CONTEXT.md:8`, `CONTEXT.md:91`, `docs/architecture/layer-boundaries.md:13` — all
describing it only as the external producer of `~/.fpl/fpl.db`. No migration plan, no deferral
record, no ADR. What I *can* evidence is an observable scatter of canonical FPL reference
knowledge across `domain/fpl_scoring.py`, `dal/staging/contracts/*.yaml`, and
`dal/mart/mart_analytical.py:34`, with the position vocabulary independently redeclared at
`dal/mart/mart_schema.py:41`, `domain/registry/schema.py:137`, `model/eval/walkforward.py:58`,
and `model/forecast/count_models.py:37`. Whether the described split was ever recorded remains
undetermined.

**3.7 — Whether `operational/backtest.py` has ever run against the real mart. Answered by
running it — it cannot.** Originally a code-path inference; it has since been executed.

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

The same guard covers every registered decision — captain, value and transfers all route through
`backtest.py:59` and `:137` — so the decision-backtest path does not run against the governed mart
for any of them. Its test coverage runs on fixtures that supply the missing column
(`tests/test_decision_backtest.py:32`, `tests/test_operational_backtest.py:28`).

**The guard's error message names a source that reproduces the failure.** It instructs the caller
to source features from `dal.pipeline.load().mart`, which is what the failing call did.
`assert_no_future_leakage` requires a column the governed mart excludes (§2.1); the guard's
required-column set and the mart contract differ.

---

## 4. What this pass did not do

No code was written, no files moved, no refactor performed. Nothing in this document proposes a
change, recommends one, or assesses whether an existing component suits the harness. What is built,
what is reused, and what is rebuilt are decided in `DESIGN.md`.
