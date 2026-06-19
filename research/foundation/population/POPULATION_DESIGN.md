# Population layer — design and intent

**Status:** intent doc for the informative `population/` layer
**Produced:** 2026-06-16 (updated 2026-06-17)
**Class:** read-only informative artifact (no *new* gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose and where we sit on the analytics maturity model

`population/` characterises **minutes — playing time / exposure — as an
analytical axis**: how the target Y (`total_points`) and each signal X sit
across the minutes axis and its 60-minute bands.

Every piece of analysis is placed on **Gartner's analytics maturity model** —
four ascending tiers, each answering a harder question:

| Tier | Question | Example on the minutes axis |
|---|---|---|
| **Descriptive** | *What happened?* | Scoring is higher in the 60+ bands than in cameo bands |
| **Diagnostic** | *Why did it happen?* | Is that lift driven by minutes, or confounded by player quality? |
| **Predictive** | *What will happen?* | Will this player clear 60' next week? |
| **Prescriptive** | *What should I do?* | Hold / transfer / captain this asset |

**This entire layer sits in the Descriptive tier.** It describes what the
minutes landscape looks like and how Y and X distribute across it. It does not
explain *why* (Diagnostic), forecast (Predictive), or recommend (Prescriptive).

One distinction that is **not** a move up the model: *univariate shape* (one
column on its own) vs *relational description* (a column read against the
minutes axis). Both are Descriptive. Characterising a column in isolation —
does a signal fire, does it move, what kind is it — is the `structure/` layer's
job. `population/` is the **relational** side of Descriptive: it relates Y and
X *to* the minutes axis. Minutes' own univariate shape appears here only as
**axis setup** — enough to show the distribution's shape (a full-match spike at 90 over a cameo/partial tail) and to justify
where the 60-minute band edge sits — never as a deliverable.

Why 60 recurs: FPL's scoring rules change at 60 minutes — clean-sheet
eligibility, the second appearance point, and the BPS baseline all switch
there. So 60 is a natural line on the minutes axis. That is a property of the
game's rules — not a gate, decision, or threshold this layer sets.

Guiding questions are phrased as directives (Determine / Establish / Quantify)
as a style choice. Anything that *explains* the description — confounding,
minutes-adjustment, significance — is the **Diagnostic** tier and is deferred
(§5). Forecasting (Predictive) and squad decisions (Prescriptive) are higher
tiers owned by other layers.

## 2. Notebooks

All four are Descriptive-tier. Three are relational (the layer's actual
purpose); `minutes_distribution` is the univariate axis-setup that the other
three build on.

| Notebook | Role | Within Descriptive |
|---|---|---|
| `minutes_distribution.ipynb` | Establish the minutes axis — spike-and-tail shape + where the band edges sit | univariate (axis setup) |
| `points_by_minutes_band.ipynb` | How Y sits across minutes-bands (bands × Y) | relational |
| `signals_by_minutes_band.ipynb` | How each signal X sits across minutes-bands (bands × X) | relational |
| `association_by_minutes_band.ipynb` | How the signal→points rank-association (rho) varies across minutes-bands — EDA, visualised | relational (association readout) |

## 3. Directive questions

**`minutes_distribution.ipynb`** *(axis setup — establishes the minutes axis the relational notebooks read against)*
- Determine how minutes distribute by position — establish the shape (a full-match spike at 90 over a cameo/partial tail, not a clean two-hump distribution).
- Quantify each position's secure-minutes (60+) share, justifying where the 60-minute band edge sits.

**`points_by_minutes_band.ipynb`**
- Determine whether mean scoring lifts at/after 60 minutes or ramps smoothly — is 60 a regime boundary or an arbitrary cut?
- Establish what a 60-minute filter would include vs discard (blank-rate + scoring by minutes band).
- Describe whether scoring steps at 60 (a property of the scoring rules) or ramps smoothly — purely the descriptive picture, nothing decided here.

**`signals_by_minutes_band.ipynb`**
- Determine how each signal's typical level sits across minutes-bands — does it rise with minutes on the pitch or stay flat?
- Establish which signals move most from cameo to full-game appearances and which barely move.

**`association_by_minutes_band.ipynb`** *(EDA — visualisation + understanding, not classification)*
- Determine, per (signal, position), how the Spearman rho between the signal and points varies across the minutes-bands (`1-29 / 30-59 / 60+`).
- Establish which signals track points in every band (event-driven, minutes-independent) versus only at 60+ (accumulation/defensive, minutes-dependent).
- *(No classification/verdict here; minutes-adjusted explanation — partial rho — is deferred, §5.)*

## 4. Shared method

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic).
- **Base population:** `minutes > 0` participation (the player featured), **not** a
  performance gate — the 60-minute mark is the *object of study* here, not a
  pre-imposed filter. Double-gameweeks are **excluded for now** (`is_dgw == False`;
  see DGW bullet). `association_by_minutes_band` slices by the three minutes-bands
  (`1-29 / 30-59 / 60+`) within the same (DGW-excluded) population.
- **Minutes-bands** (`signals_by_minutes_band`, `points_by_minutes_band`): `1-29 /
  30-59 / 60+` — collapsed at 60 because FPL's scoring rules do not distinguish
  60-89 from 90 (same appearance / clean-sheet regime), so `60+` is the
  rule-aligned band. `signals_by_minutes_band` plays them via
  `compute_signal_block_distributions` with `gw_column="minutes"` (the kernel bins
  by whatever column it is given).
- **DGW:** **excluded for now** (`is_dgw == False`) — this drops the
  fixture-doubling confound (the ~180-minute rows) cleanly rather than pooling and
  flagging it. Per-fixture DGW treatment is the `fixture/` layer's job.
- **Signal universe** (`signals_by_minutes_band`, `association_by_minutes_band`): raw
  per-GW numeric signals, excluding `starts` (a minutes proxy; deferred axis) and
  the **exact composites** `ict_index` (= influence+creativity+threat) and `xgi`
  (= xg+xa) — these are perfect functions of signals we keep, so dropping them
  loses no information while avoiding double-counting. `defensive_contribution`
  and its parts (CBI / tackles / recoveries) are **all kept** — DC is not an exact
  sum (r ≈ 0.81), so each carries independent signal.

## 5. Deferred — the Diagnostic-tier follow-up (not built)

`association_by_minutes_band.ipynb` *describes* (as EDA) how the signal→points rank-association
varies **across minutes-bands**: event-driven signals (`goals_scored`, `assists`,
`bps`, `bonus`) track points in every band (minutes-independent), while
accumulation/defensive signals (`defensive_contribution`, CBI, tackles,
`clean_sheets`) only relate to points at 60+ (minutes-dependent).
`signals_by_minutes_band.ipynb` separately *describes* (as EDA) that those same accumulating
signals sit higher in higher-minute bands. (Signal-universe exclusions — `starts`,
exact composites `ict_index` / `xgi` — are in §4.)

**It deliberately stops at description.** *Explaining* the shift — whether minutes
drives it, what the association looks like once minutes is adjusted for — is the
Diagnostic tier, not concluded in this layer. Recorded
here so a later phase can pick it up, with the method options and the fact that the
tooling already exists:
- minutes-adjusted association (partial Spearman controlling for minutes) —
  `research/kernels/inferential/resampling.py` (`partial_spearman`,
  `bootstrap_partial_rho`);
- per-90 normalisation of counts;
- formal conditioning / heterogeneity *testing* of the within-band association
  (the *descriptive* within-band rho is now shown in `association_by_minutes_band.ipynb`) —
  `research/kernels/diagnostic/conditioning.py` (`compute_conditional_rho`,
  `classify_heterogeneity`).

**No causal claims.** "An extra 30 minutes causes +X points" is causal (Pearl
rung 2) and is out of scope for the whole layer — exposure is confounded with
player quality; minutes-adjustment yields an *association*, not causation.

## 6. Supporting modules

No supporting modules remain in `population/`. `robustness.py`
(`compute_dual_scope_rho`, `classify_population_robustness`) was removed after the
EDA reframe of `association_by_minutes_band.ipynb` made it unused; its test file
`tests/test_signals_population.py` was removed with it.
