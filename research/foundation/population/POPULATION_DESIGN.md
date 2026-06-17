# Population layer — design and intent

**Status:** intent doc for the informative `population/` layer
**Produced:** 2026-06-16
**Class:** read-only informative artifact (no *new* gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose

`population/` is the one foundation layer with a **prescriptive** purpose. Every
other layer (structure/, temporal/, fixture/) imposes a `minutes > 0`
participation filter and explicitly **defers the 60-minute performance-boundary
question to here**. This layer answers it: it describes the minutes landscape,
characterises the 60-minute mark, and measures whether the choice of population
scope actually changes analytical conclusions — then **restates** (does not
re-originate) the prescription that downstream should analyse on the
qualified-start population (`minutes >= 60`).

The layer stays **informative**: it does not mint a new gate. Its guiding
questions are phrased as **directives** (Determine / Establish / Quantify /
Prescribe) to make the prescriptive purpose explicit while keeping the artifacts
verdict-free.

## 2. Notebooks

| Notebook | Role | Question class |
|---|---|---|
| `minutes_distribution.ipynb` | Describe the minutes / rotation landscape by position | descriptive |
| `population_boundary.ipynb` | Characterise the 60-minute mark — is it a regime boundary? | descriptive |
| `scope_sensitivity.ipynb` | Measure whether re-scoping the population changes signal→target association | descriptive readout of association deltas |

## 3. Directive questions (the prescriptive framing)

**`minutes_distribution.ipynb`**
- Determine how minutes distribute by position — establish who plays full matches vs who is rotated/subbed.
- Establish each position's start rate, given the player featured.
- Quantify each position's secure-minutes (60+) share vs its cameo/partial share.

**`population_boundary.ipynb`**
- Determine whether mean scoring lifts at/after 60 minutes or ramps smoothly — is 60 a regime boundary or an arbitrary cut?
- Establish what a 60-minute filter would include vs discard (blank-rate + scoring by minutes band).
- State, with evidence, whether 60 is a defensible population boundary — restating the settled prescription, not originating a new gate.

**`scope_sensitivity.ipynb`**
- Determine whether re-scoping `minutes > 0` → `minutes >= 60` changes the signal→target association (delta-rho per signal-position).
- Establish which (signal, position) pairs are scope-robust vs scope-sensitive.
- Prescribe which population scope downstream should analyse on — and explain why an earlier "nothing changes" reading and this "this changes a lot" reading can both be correct.

## 4. Shared method

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic).
- **Base population:** `minutes > 0` participation (the player featured), **not** a
  performance gate — the 60-minute mark is the *object of study* here, not a
  pre-imposed filter. `scope_sensitivity` is the exception: it keeps the full
  minutes axis and derives both scopes (`>= 60` and `> 0`) internally.
- **Boundary under test:** `minutes >= 60` — the FPL scoring regime break (clean-sheet
  eligibility, the second appearance point, full BPS baseline).
- **DGW:** distributions pool SGW + DGW and flag the confound; per-fixture
  normalisation is the `fixture/` layer's job.

## 5. The scope-sensitivity method and its key finding

`scope_sensitivity.ipynb` orchestrates the dedicated, tested module
`research/foundation/population/robustness.py` (`compute_dual_scope_rho`,
`classify_population_robustness`) plus the shared shape kernels
(`select_bucketing_scheme` → `bin_analysis` → `classify_geometry`) for per-scope
geometry. Output is a **descriptive** robustness readout — point-estimate rho
shifts and a `{stable, scope_sensitive, untested}` label per pair — with no gate.

**Key finding (full season, raw per-GW mart signals).** The 60-minute cutoff is
**not neutral** for raw single-game stats: 43/84 testable pairs are
`scope_sensitive` (mean |shift| 0.12, max 0.53). The movers are the
**minutes-accumulating counts** — `starts`, defensive-action counts
(`defensive_contribution`, `recoveries`, `clearances_blocks_interceptions`,
`tackles`), `goals_conceded`, and per-match ICT totals (`creativity`, `xa`,
`xgi`). Raw counts pile up with minutes, so the participation population
(`minutes > 0`) inflates rho via a **minutes confound** that the 60+ scope
removes. Sparse / rate-like signals (`goals_scored`, `assists`, `bonus`, `saves`,
`penalties_saved`) barely move.

**Reconciliation (plain terms).** An earlier robustness check read "nothing
changes across the boundary." That was on the **smoothed rolling-average form
signals** the scorer actually uses (a player's average over recent games), which
do not carry a per-week minutes effect. This notebook reads the **raw
single-game stats**, which do. Both are correct on different inputs. The finding
*strengthens* the `minutes >= 60` prescription: for raw stats the cutoff removes
a "they just played more" illusion that would otherwise make minutes-driven
signals look more predictive than they are.

## 6. Out of scope

- **POPTHRESH-01** (`docs/studies/popthresh-01-design.md`) — the separate
  design-locked study of whether 60 is the *optimal* threshold vs T30/T45/T75/T90.
  Referenced as the home for the optimality question; not executed here.
- **Causal claims.** "An extra 30 minutes causes +X points" is causal (Pearl rung
  2) and deliberately out of scope — exposure is confounded with player quality.

## 7. Supporting module

`research/foundation/population/robustness.py` — relocated from the retired
`foundation/scope/` (its sibling `eda_04` was deleted). Tested by
`tests/test_signals_population.py`. Vocabulary `{stable, scope_sensitive,
untested}`; thresholds (`rho_shift < 0.10` stable, `<= 0.25` scope_sensitive) are
operational heuristics, not significance tests.
