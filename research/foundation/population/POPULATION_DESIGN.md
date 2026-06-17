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
**axis setup** — enough to show the distribution is bimodal and to justify
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
| `minutes_distribution.ipynb` | Establish the minutes axis — bimodal shape + where the band edges sit | univariate (axis setup) |
| `points_by_minutes_band.ipynb` | How Y sits across minutes-bands (bands × Y) | relational |
| `signals_by_minutes_band.ipynb` | How each signal X sits across minutes-bands (bands × X) | relational |
| `scope_sensitivity.ipynb` | Whether the population definition shifts the signal→points association | relational (association readout) |

## 3. Directive questions

**`minutes_distribution.ipynb`** *(axis setup — establishes the minutes axis the relational notebooks read against)*
- Determine how minutes distribute by position — establish that the distribution is bimodal (full-match mass vs cameo/partial mass).
- Quantify each position's secure-minutes (60+) share, justifying where the 60-minute band edge sits.

**`points_by_minutes_band.ipynb`**
- Determine whether mean scoring lifts at/after 60 minutes or ramps smoothly — is 60 a regime boundary or an arbitrary cut?
- Establish what a 60-minute filter would include vs discard (blank-rate + scoring by minutes band).
- Describe whether scoring steps at 60 (a property of the scoring rules) or ramps smoothly — purely the descriptive picture, nothing decided here.

**`signals_by_minutes_band.ipynb`**
- Determine how each signal's typical level sits across minutes-bands — does it rise with minutes on the pitch or stay flat?
- Establish which signals move most from cameo to full-game appearances and which barely move.

**`scope_sensitivity.ipynb`**
- Determine whether re-scoping `minutes > 0` → `minutes >= 60` changes each signal's rank-correlation with points (a per-position shift).
- Establish which (signal, position) pairs are unaffected by the cutoff and which shift a lot.
- *(Explaining the shift is deferred — §5.)*

## 4. Shared method

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic).
- **Base population:** `minutes > 0` participation (the player featured), **not** a
  performance gate — the 60-minute mark is the *object of study* here, not a
  pre-imposed filter. `scope_sensitivity` derives both scopes (`>= 60` and `> 0`)
  internally from the full minutes axis.
- **Minutes-bands** (`signals_by_minutes_band`, `points_by_minutes_band`): `1-29 / 30-59 /
  60-89 / 90+` — played by `compute_signal_block_distributions` with
  `gw_column="minutes"` (the kernel bins by whatever column it is given).
- **DGW:** distributions pool SGW + DGW and flag the confound; DGW full-plays land
  in the `90+` band (~180 min, doubled counts). Per-fixture normalisation is the
  `fixture/` layer's job.

## 5. Deferred — the Diagnostic-tier follow-up (not built)

`scope_sensitivity.ipynb` *describes* that the signal→points association shifts
across the two population definitions for many raw single-game stats (43/84
testable pairs shift, up to 0.53; movers are the per-match accumulating stats —
`starts`, defensive counts, ICT totals; sparse/rate-like stats barely move).
`signals_by_minutes_band.ipynb` separately *describes* that those same accumulating stats
sit higher in higher-minute bands.

**It deliberately stops at description.** *Explaining* the shift — whether minutes
drives it, what the association looks like once minutes is adjusted for — is the
Diagnostic tier, not concluded in this layer. Recorded
here so a later phase can pick it up, with the method options and the fact that the
tooling already exists:
- minutes-adjusted association (partial Spearman controlling for minutes) —
  `research/kernels/inferential/resampling.py` (`partial_spearman`,
  `bootstrap_partial_rho`);
- per-90 normalisation of counts;
- association within minutes-bands —
  `research/kernels/diagnostic/conditioning.py` (`compute_conditional_rho`,
  `classify_heterogeneity`).

**No causal claims.** "An extra 30 minutes causes +X points" is causal (Pearl
rung 2) and is out of scope for the whole layer — exposure is confounded with
player quality; minutes-adjustment yields an *association*, not causation.

## 6. Supporting module

`research/foundation/population/robustness.py` — relocated from the retired
`foundation/scope/` (its sibling `eda_04` was deleted). Tested by
`tests/test_signals_population.py`. Backs `scope_sensitivity.ipynb`
(`compute_dual_scope_rho`, `classify_population_robustness`). Vocabulary
`{stable, scope_sensitive, untested}`; thresholds are operational heuristics, not
significance tests.
