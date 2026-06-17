# Population layer — design and intent

**Status:** intent doc for the informative `population/` layer
**Produced:** 2026-06-16 (updated 2026-06-17)
**Class:** read-only informative artifact (no *new* gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose and where we are on the ladder

`population/` characterises **minutes — playing time / exposure — as an
analytical axis**: it describes the minutes landscape, and how the target Y
(`total_points`) and each signal X sit across minutes-bands.

Why minutes gets its own layer, and why the 60-minute mark recurs: FPL's scoring
rules have a structural change at 60 minutes — clean-sheet eligibility, the second
appearance point, and the BPS baseline all switch there. So 60 is a natural line
to look at on the minutes axis. That is a property of the game's rules — not a
gate, decision, or threshold this layer sets.

This layer is on the **descriptive rung**: it describes the data and nothing else
— it does not decide, gate, or recommend a population. Guiding questions are
phrased as directives (Determine / Establish / Quantify) as a style choice.
Anything that *explains* the description — confounding, minutes-adjustment,
significance — is a **later rung** (diagnostic or inferential) and is deferred
(§5).

## 2. Notebooks

| Notebook | Role | Rung |
|---|---|---|
| `minutes_distribution.ipynb` | Describe the minutes / rotation landscape by position | descriptive |
| `population_boundary.ipynb` | Characterise the 60-minute mark (bands × Y) | descriptive |
| `signal_minutes.ipynb` | Describe each signal's level across minutes-bands (bands × X) | descriptive |
| `scope_sensitivity.ipynb` | Describe whether the population definition changes the signal→points association | descriptive (association readout) |

## 3. Directive questions

**`minutes_distribution.ipynb`**
- Determine how minutes distribute by position — who plays full matches vs who is rotated/subbed.
- Establish each position's start rate, given the player featured.
- Quantify each position's secure-minutes (60+) share vs its cameo/partial share.

**`population_boundary.ipynb`**
- Determine whether mean scoring lifts at/after 60 minutes or ramps smoothly — is 60 a regime boundary or an arbitrary cut?
- Establish what a 60-minute filter would include vs discard (blank-rate + scoring by minutes band).
- Describe whether scoring steps at 60 (a property of the scoring rules) or ramps smoothly — purely the descriptive picture, nothing decided here.

**`signal_minutes.ipynb`**
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
- **Minutes-bands** (`signal_minutes`, `population_boundary`): `1-29 / 30-59 /
  60-89 / 90+` — played by `compute_signal_block_distributions` with
  `gw_column="minutes"` (the kernel bins by whatever column it is given).
- **DGW:** distributions pool SGW + DGW and flag the confound; DGW full-plays land
  in the `90+` band (~180 min, doubled counts). Per-fixture normalisation is the
  `fixture/` layer's job.

## 5. Deferred — the later-rung follow-up (not built)

`scope_sensitivity.ipynb` *describes* that the signal→points association shifts
across the two population definitions for many raw single-game stats (43/84
testable pairs shift, up to 0.53; movers are the per-match accumulating stats —
`starts`, defensive counts, ICT totals; sparse/rate-like stats barely move).
`signal_minutes.ipynb` separately *describes* that those same accumulating stats
sit higher in higher-minute bands.

**It deliberately stops at description.** *Explaining* the shift — whether minutes
drives it, what the association looks like once minutes is adjusted for — is a
later rung (diagnostic or inferential, TBD), not concluded in this layer. Recorded
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
