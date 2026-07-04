# Diagnostic layer — design and intent

**Status:** intent doc for the informative `diagnostic/` layer
**Produced:** 2026-06-22
**Class:** read-only informative artifact (no gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose and where we sit on the analytics maturity model

`diagnostic/` is the **"why"** layer. Where `foundation/` described *what* the
position × minutes × signal landscape looks like (Descriptive), this layer asks *why the
observed associations look the way they do* — by **decomposing and attributing** them, not
by explaining their cause.

| Tier | Question | This layer |
|---|---|---|
| **Descriptive** | *What happened?* | `foundation/` (done) |
| **Diagnostic** | *Why did it happen?* | **here** |
| **Predictive** | *What will happen?* | `families/` (validate) |
| **Prescriptive** | *What should I do?* | `model/` + `serve/` |

It sits between `foundation/` and `families/` in the research pipeline:

```
kernels → foundation (what) → diagnostic (why) → families (validate) → findings → registry → model → serve
```

**Two non-negotiable boundaries** (`docs/foundations/statistical-framework.md` §1, ADR-008):

1. **Statistical Rung 2 (Diagnostic), association-only — two different ladders.** This layer sits at
   **Rung 2 (Diagnostic) on the project's five-rung statistical ladder** — it enriches the *structure*
   of an association already observed in the season at hand — while staying on **Pearl rung 1
   (association)** on the (orthogonal) causal ladder: it climbs the *analytical* ladder without
   climbing the *causal* one. (Unqualified "Rung N" below = the statistical ladder; "Pearl rung N" =
   the causal one.) "An extra 30 minutes *causes* +X points" is causal (Pearl rung 2) and is
   out of scope. Where a notebook claims a pattern is real *beyond sampling noise*, it must
   carry a bootstrap CI (Rung 3 machinery) — it does not get that claim for free.
2. **No predictive language.** "Predicts", "forecasts next week", "expected next GW" belong to
   the `families/` validate stage (lagged design + inference + the three gates). Any question with a
   week-to-week lag (form persistence, post-spike reversion) is a *predictive* claim by construction
   and therefore lives in `families/`, **not** here — the earlier attempt to keep them as
   "serial dependence within the season" (ex-Q4/Q5) is retired; see §2.

This layer produces **no governance verdict**. Like `foundation/`, it is informative EDA: its
outputs characterise structure so a later predictive/governance stage can act on it.

**Notebooks render for humans, never for the model.** A diagnostic notebook's only output is what a
reader sees — tables, plots, prose. It **never emits a structured finding into the
`findings → registry → model` path**, and the model never reads a notebook artifact to route a
signal. The pipeline arrow above is one-directional and production-fed: a diagnostic read becomes
model-consumable *only* by being re-derived in a `families/` validate study (lagged design +
inference + gates) and, if it earns persistence, recorded as a separate DAL decision (§5.2). Any
"emit the verdict so the model can route on it" step is therefore out of scope **for every diagnostic
question**, not just deferred — it would smuggle an un-validated, single-season notebook estimate into
the model path, the exact failure §5.2 forbids.

## 2. Questions

> **Revision (2026-06-25) — Rung-2 question redesign.** The original four-notebook set was superseded
> by a five-question set (Q1, Q1b, Q2, Q3, Q4, Q5). Each question carries **one estimand and one
> manager-read**, anchored to `total_points` where possible, with an explicit null. Per-question data
> and method rationale are in §3.
>
> **Revision (2026-07-03) — layer closed at Q1/Q1b/Q2.** The diagnostic layer is now scoped to the
> three association-structure questions below. The rest are resolved as follows:
> - **Q3 (tail vs body) — dropped.** Off the critical path: it characterises a surviving signal
>   (captaincy texture) but gates nothing downstream, and abstains for thin-haul positions (FWD/GK).
>   The tail idea is revived only *inside* a haul-probability model, if one is built.
> - **Q4 (form persistence) + Q5 (post-spike reversion) — relocated to `families/`.** Both carry a
>   week-to-week lag, which makes them *predictive* claims (Rung 4) outside this layer's
>   association-only boundary. They belong in the `form` family, done with lagged design + gates. The
>   `serial.py` kernel (`within_player_autocorr`, `post_event_outcome_rate`) is **retained** as the
>   reusable primitive that the families study will call — no diagnostic `serial.py` extension will be built.
>
> **Progress.** Q1, Q1b, Q2 complete (executed, player-clustered CIs, CI-gated verdicts). Q2 adds a
> paired minutes-shrinkage CI + FDR + players-per-band guard; result: discard `recoveries`(DEF) and
> `tackles`(FWD) as minutes proxies, `defensive_contribution` is a vetted regime trap, the rest carry
> information beyond minutes. **Layer closed.**

Each read completes a deferred `§5` thread from a foundation design doc and/or a named gap in the
statistical framework, and sorts a signal into one slot of a manager's triage — **own / discard**.

| # | Question | Manager use | Owns |
|---|---|---|---|
| Q1 | Before any signal, how much of weekly `total_points` variation sits *between* players vs *within* a player? | descriptive **preamble** Q1b reads against | the points between/within partition |
| Q1b | Given a signal links to points, is that link *identity*-driven or *state*-driven? | **own** vs **time** | the per-signal identity-vs-state split |
| Q2 | Does a signal still track points once playing time is held equal? | **discard** (minutes proxy) | the minutes-confound adjustment |
| ~~Q3~~ | ~~tail vs body~~ — **dropped** (off critical path) | — | folds into a haul-probability model if built |
| ~~Q4~~ | ~~form persistence~~ — **relocated → `families/form`** | **time** | lagged/predictive; reuses `serial.py` |
| ~~Q5~~ | ~~post-spike reversion~~ — **relocated → `families/`** | **fade** | lagged/predictive |

Q1 is a **points-only descriptive preamble** — a single between/within partition with no signals in it —
that Q1b reads against: where a position shows little within-player movement this season, there is little
within-player variation for a signal to track. It describes the observed spread; it does not estimate
durable player quality or set a hard bound on what is findable.
The temporal complement to Q1b — whether within-player state, once shown to *exist*, also *persists*
(ex-Q4) or *reverts* after a spike (ex-Q5) — is a lagged/predictive question and now lives in
`families/`, not here. Q1b establishes existence; persistence and prediction are a `families/form`
concern, done with lagged design and gates.

## 3. Directive questions

Each question states its **data**, its **method (and, plainly, why)**, and the **manager-read** it
produces. Shared conventions (GW range, `minutes > 0`, per-position, DGW excluded) are in §4.

**Q1 — Between-player vs within-player variation in points (descriptive preamble)** *(points_variance_ceiling)*
- **Data:** per position — every player's weekly `total_points` (≥ 10 games); **no signals**.
- **Method (why):** partition the observed variance of `total_points` into a **between-player** part
  (players differ in level — identity) and a **within-player** part (one player swings week to week —
  state) via `descriptive.variance_components.decompose_variance`. This is a one-time, layer-level
  framing: it describes how much week-to-week movement was observed for a signal to track. A
  near-all-between position (e.g. GK) shows little within-player movement — so Q1b should mostly
  abstain there. Descriptive only: it does not estimate true player quality, and within-player
  movement still includes playing-time embedded in `total_points`.
- **Manager-read:** none per-signal — it is the descriptive split Q1b reads against. A high within
  share means more week-to-week movement was observed; a low one means points were driven mostly by
  stable between-player level differences.

**Q1b — Is a signal's link identity or state?** *(identity_vs_state)*
- **Data:** per (signal, position) — every player's weekly rows; the signal + `total_points`, grouped by player.
- **Method (why):** split the signal→points rank association into a **between-player** part (compare
  players' season averages) and a **within-player** part (compare each player's weeks to their own
  average) via `panel.split_between_within_player_rho`; summarise as `panel_class`. A pooled
  correlation blends "good players score more" (identity) with "players score more in their good
  weeks" (state); the split is the only way to tell a manager which one they're seeing.
- **Manager-read:** identity-dominant → **own** (re-ranks players you already know); state-sensitive
  → **time** (worth acting on a player's current run).
- **Estimand (committed, Phase 2).** For a given (signal, position) and target `total_points`, Q1b
  estimates **which of two within-season rank associations is larger**: the *between-player*
  association `rho_between` (Spearman of players' season-mean signal vs season-mean points) or the
  *within-player* association `rho_within` (Spearman of each player's demeaned signal vs demeaned
  points). The estimand is the **sign and magnitude of the dominance contrast
  `|rho_between| − |rho_within|`**, carried with player-clustered bootstrap uncertainty — **not** the
  ratio `within_share`, and **not** a variance decomposition. In plain terms: *does this signal's link
  to points run mostly through stable differences between players (identity → own) or through a
  player's week-to-week movement around his own baseline (state → time)?*

  This is deliberately a **dominance** question, not an **existence** one. A signal may carry real
  structure on *both* axes (both CIs exclude zero) yet be decisively between-dominant; the
  manager-read turns on which axis **dominates**, not on which merely **exists**. Existence is
  recorded but does not decide the class.

  The quantity is **descriptive and association-only**, scoped to a single season, per position, on
  `minutes > 0` participation, DGW excluded, players below the appearance floor dropped. It makes
  **no** causal, predictive, or cross-season claim, and is **not** an estimate of durable player
  quality or of a variance share. The repeated-measures biases catalogued for this panel (mean
  attenuation on thin players, playing-time embedded in the target, survivor selection) bound its
  precision and are why it carries clustered CIs and honest abstention rather than a bare point
  verdict. `panel_class` is the **label of this dominance contrast** — `identity_dominant` /
  `state_sensitive` / `mixed` when the contrast is decided by its own CI, and `undecomposable` /
  `indeterminate` / `insufficient_support` when it is not. Because governance consumes this label, it
  must denote **measured dominance of the named axis**.
- **Correctness — resolved.** The v1 `within_share = |rho_within|/|rho_pooled|` classifier was
  structurally biased (pooled ≈ within by row count, so `rho_between` never entered). A Phase-1
  disagreement test on the 2025-26 mart confirmed it empirically at maximal severity: `within_share`
  labelled 29/29 FDR-significant cells `state_sensitive` while `|rho_between| > |rho_within|` held on
  28/29 — 97% disagreement with the dominance estimand, i.e. the old verdicts were **systematically
  inverted**. This is now **fixed**: `panel_class` is re-derived from the CI on the dominance contrast
  (below), `within_share` is demoted to a descriptive column, and the Kendall cross-check reads the
  new point dominance. The classifier axis of Q1b is **closed**; the one remaining thread is the
  registry population/golden-registry regeneration (deferred, see the *Classifier* note below).
- **Classifier (implemented).** `panel_class` is derived from the dominance
  contrast, first match wins:

  | Priority | Condition | Label |
  |---|---|---|
  | 1 | below sample floors | `insufficient_support` → collapses to `indeterminate` at the registry |
  | 2 | pooled ρ CI includes 0 | `undecomposable` → collapses to `indeterminate` at the registry |
  | 3 | dominance CI wholly > 0 | `identity_dominant` |
  | 4 | dominance CI wholly < 0 | `state_sensitive` |
  | 5 | dominance CI crosses 0 **and** both axis CIs exclude 0 | `mixed` |
  | 6 | dominance CI crosses 0 **and** an axis CI includes 0 | `indeterminate` |

  Directional classes (3/4) come from the paired difference-CI in `bootstrap_panel_decomposition`;
  the tied region (5/6) is split by axis existence. The **point** `split_between_within_player_rho`
  emits only the *sign* of `dominance` (no CI, no abstention) — a direction indicator for the
  notebook's Kendall cross-check. The registry (`research/registry/sections.py`) now consumes the
  **bootstrap** (CI-gated) class, collapsing the two kernel-internal abstentions to `indeterminate`
  so only the four `PANEL_CLASS_VALUES` persist (no schema migration). Governance code is unchanged —
  only the label *values* flowing in change: ~22 of 29 decided cells move `state_sensitive →
  identity_dominant`, i.e. from `continuous_monotonic` (useful) to `weak_association`
  (`assign_association_class`) — the corrected, framework-consistent (Gap 8) routing.
  **Edges pinned:** opposite-sign axes (Simpson) are out of scope here (Q2/conditioning owns
  sign-heterogeneity). The registry decomposition sets `panel_n_bootstrap = 1000` (removes the
  Monte-Carlo class jitter that flips ~1 borderline cell across seeds at 200; `rho` is a
  deterministic point estimate so this does not shift `rho_*` and golden parity holds).
  **Deferred:** aligning the population to the estimand (`min_appearances = 10`, on top of the
  registry's existing `minutes ≥ 60` filter) shifts the persisted `rho` evidence and so requires
  regenerating the golden registry (`research/findings/records/eda_03_joint_registry.csv`) — and
  that must go through the real build pipeline, not a raw rewrite, because the registry contract
  forbids null booleans (`tail_sensitive` = None must be coerced on save). Tracked as its own task.

**Q2 — Just minutes?** *(minutes_adjusted_association)*
- **Data:** per (signal, position) — signal + `total_points` + `minutes`.
- **Method (why):** the signal→points association **after partialling out minutes** (`partial_spearman`)
  with a bootstrap CI (`bootstrap_partial_rho`), against the raw association; plus whether it holds
  across minutes bands (`compute_conditional_rho` / `classify_heterogeneity`). Minutes inflate every
  counting stat *and* points together, so the raw link is partly "nailed-on starters do more of
  everything" — holding minutes equal asks whether the signal still separates two equally-played
  players. The bootstrap error-bars the survivor; the band check catches a signal that reverses sign
  inside a band (a trap).
- **Manager-read:** collapses toward 0 → **discard** (a playing-time proxy); survives → real information.

**Q3 — Boom-bust or steady? — DROPPED (2026-07-03).**
Off the critical path: it characterises a signal that already survived Q1b/Q2 (captaincy texture) but
gates nothing downstream, and it abstains for thin-haul positions (FWD/GK) where boom-bust matters
most. The tail-vs-body idea is revived only *inside* a haul-probability model, if one is built. (The
registry `haul` decomposition section is unaffected — that is separate production machinery, not this
notebook.)

**Q4 — Does form stick? / Q5 — Hold or fade after a spike? — RELOCATED to `families/` (2026-07-03).**
Both correlate a value at week *t* with an outcome at week *t+1*; a week-to-week lag is a *predictive*
claim (Rung 4) and sits outside this layer's association-only boundary. The earlier attempt to keep
them here as "serial dependence within the season" is retired. They belong in the `form` family, done
with lagged design + inference + gates, where `total_points` form (Q5) is admissible and prediction is
legitimate. The `serial.py` kernel (`within_player_autocorr`, `post_event_outcome_rate`) is retained
as the reusable primitive that study will call; no diagnostic `serial.py` extension will be built.
Q1b already answers the diagnostic half — whether within-player *state exists*; persistence and
reversion are the predictive half.

## 4. Shared method

Inherited from the informative-EDA conventions established in `foundation/`:

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic from the mart).
- **Base population:** `minutes > 0` participation (the player featured), **not** a performance
  gate. The minutes confound is examined explicitly in Q2, not pre-filtered here.

  > **Diagnostic vs registry population — deliberately different, do not "fix" by aligning them.**
  > These notebooks describe structure on the broad participation population (`minutes > 0`, whole
  > season) — the exploratory read. The **registry** (governance evidence) instead builds on the
  > scoring-homogeneous population **`minutes >= 60`** (`research/registry/population_builder.py`,
  > `CLEAN_SHEET_MIN_MINUTES`): below 60, `total_points` has a *different* generating process
  > (appearance / clean-sheet / BPS baselines all break at 60), so the registry pools one regime.
  > Consequently a signal's `panel_class` **can differ between the notebook and the registry by
  > construction** — the registry build is authoritative for governance; the notebook is the
  > broader exploratory view. This is a purpose difference, not an inconsistency to reconcile.
  > (The registry's historical GW6–33 span is *not* a governance window — the upper bound is the
  > `data_cutoff_gw` snapshot at build time and the lower bound is only a parity-test fixture
  > filter; a live full-season build has no lower trim.)
- **Positions:** GK / DEF / MID / FWD; every read is **per-position** (never pooled across
  positions — structural point differences make pooled statistics uninterpretable).
- **DGW:** excluded (`is_dgw == False`) on the same grounds as `foundation/` — fixture doubling
  is a confound this layer does not treat (it is deferred with the fixture block, §5).
- **Signal classes:** drawn from `domain/signal_layers.py` via
  `research/kernels/descriptive/relevance.py` — **never hardcoded**. Tautological / formula-input
  signals never appear on the association side (the same-GW relationship would measure the
  scoring formula, not player quality); the leading-indicator set, with exact composites
  (`xgi`, `ict_index`) dropped in favour of their parts, is the association universe.
- **Lag axis (Q4 / Q5 only):** within-player pairing is by **gameweek number** — a row
  at gw `t` pairs with the same player's row at `t + lag` only when both exist, so a missed
  gameweek never produces a spurious "consecutive" pair. The lag is a **transient measurement**,
  not a persisted feature (see §5).
- **Uncertainty / not overstating:** a bare median or rho is a within-data description; any claim
  that an association generalises beyond the sample carries a bootstrap CI. When many signals are
  screened at once, p-values are FDR-adjusted (`benjamini_hochberg`). Every cell reports its `n`;
  thin positions (FWD, GK) yield wide CIs and are flagged, not hidden.
- **Visualisation:** matplotlib only (no seaborn); per-position facets; ≤ 4–6 panels; the
  foundation palettes (`GK #9467bd · DEF #1f77b4 · MID #2ca02c · FWD #d62728`; minutes bands
  light→dark blue); diverging `RdBu_r` centred at 0 for correlation heatmaps; dense facet grids
  are avoided (rejected in foundation history).

## 5. Deferred — three triggered follow-ups (not built)

This layer deliberately stops at diagnostic structure. Three threads are recorded for later
stages, each with an explicit trigger so the design stays open by construction:

1. **Predictive generalisation → `families/`.** Any structure found here (a surviving
   minutes-adjusted association, a state-sensitive `panel_class`, serial dependence) becomes a
   *predictive* claim only through a `families/` validate study: lagged design, bootstrap
   inference, and the three qualification gates. Diagnostic structure is the input, not the
   verdict.
2. **Persisted DAL features → a DAL decision.** Diagnostic intermediates (minutes-residualised
   rho, per-90 rescaling, the within-player lag) are **transient measurements**, never written
   back to the mart. A signal is promoted to a persisted `dal/feat/` feature only once a
   *validated* finding earns it — recorded as a separate DAL decision, not smuggled into a
   notebook.
3. **The entire fixture-diagnostic block → gated behind a team-strength model.** Fixture
   difficulty, double-gameweek doubling, and home/away are **out of scope this rung**. `fdr_avg`
   is FPL's static, semi-subjective rating, not an empirical team-strength measure, and we will
   not condition diagnostics on an instrument we distrust; the doubling/venue reads are
   small-n and schedule-entangled. The prerequisite is an **empirical team-strength model
   (attack/defence ratings)** — a later inferential-rung workstream. Until it exists, the
   descriptive `foundation/fixture/` notebooks are the last word on fixtures.

**No causal claims.** Minutes-adjustment, between/within decomposition, and serial dependence
all yield *associations*, not causation; exposure is confounded with player quality. Higher
Pearl rungs are gated, not foreclosed (ADR-008) — a future redesign may justify them.

## 6. Supporting modules

All statistical logic lives in the shared kernel package; the notebooks compose kernels and
plot, they do not reimplement statistics.

| Need | Kernel |
|---|---|
| Signal-class / liveness map | `research/kernels/descriptive/relevance.py` |
| Target variance between/within | `research/kernels/descriptive/variance_components.py::decompose_variance` |
| Signal rho between/within + `panel_class` | `research/kernels/diagnostic/panel.py::split_between_within_player_rho` |
| Minutes-adjusted (partial) rho + CI | `research/kernels/inferential/resampling.py::partial_spearman`, `bootstrap_partial_rho` |
| Heterogeneity / sign-flip across strata | `research/kernels/diagnostic/conditioning.py::compute_conditional_rho`, `classify_heterogeneity` |
| Tail / haul dependence | `research/kernels/diagnostic/tail.py::measure_tail_event_dependence` |
| Form persistence (Q4) — detrended, multi-lag, vs null | `research/kernels/diagnostic/serial.py::within_player_autocorr` **(extend: per-player detrend + lag sweep + noise null)** |
| Post-spike reversion (Q5) | `research/kernels/diagnostic/serial.py::transition_rate` (position-relative spike; read as regression to the mean) |
| Position-relative event line (Q3, Q5) | per-position p95 of `total_points` — replaces the league-wide `HAUL_THRESHOLD_PTS` cut for these reads |
| Multiple-comparison control | `research/kernels/hypothesis/multiplicity.py::benjamini_hochberg` |

`serial.py` exists (autocorr + transition rate, tested); **Q4 requires extending it** with per-player
detrending, a lag-1..k sweep, and a no-persistence null. Everything else is reused and already tested.
