# Exposure layer — design and intent

**Status:** intent doc for the informative `exposure/` layer
**Produced:** 2026-06-16 (updated 2026-06-19 — descriptive-layer redesign)
**Class:** read-only informative artifact (no *new* gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose and where we sit on the analytics maturity model

`exposure/` is the **cross-sectional** (between-player, across the whole
population) description of how the target Y (`total_points`) and each signal X
sit across the two stratifying axes — **position** (GK / DEF / MID / FWD) and
**minutes band** (`1-29 / 30-59 / 60+`) — plus how the leading-indicator
signals overlap with one another. It is the *relational* half of the
descriptive picture: it reads Y and X *against* those axes, where `composition/`
characterises each column in isolation.

Every piece of analysis is placed on **Gartner's analytics maturity model** —
four ascending tiers, each answering a harder question:

| Tier | Question | Example on the minutes axis |
|---|---|---|
| **Descriptive** | *What happened?* | Scoring is higher in the 60+ band than in cameo bands |
| **Diagnostic** | *Why did it happen?* | Is that lift driven by minutes, or confounded by player quality? |
| **Predictive** | *What will happen?* | Will this player clear 60' next week? |
| **Prescriptive** | *What should I do?* | Hold / transfer / captain this asset |

**This entire layer sits in the Descriptive tier.** It describes what the
position × minutes landscape looks like and how Y and X distribute across it. It
does not explain *why* (Diagnostic), forecast (Predictive), or recommend
(Prescriptive). It is also strictly **cross-sectional**: within-player /
longitudinal questions (form persistence, autocorrelation) belong to the
`temporal/` and diagnostic layers, not here.

Why 60 recurs: FPL's scoring rules change at 60 minutes — clean-sheet
eligibility, the second appearance point, and the BPS baseline all switch
there. So 60 is a natural line on the minutes axis. That is a property of the
game's rules — not a gate, decision, or threshold this layer sets.

Anything that *explains* the description — confounding, minutes-adjustment,
significance — is the **Diagnostic** tier and is deferred (§5).

## 2. Notebooks

Six Descriptive-tier notebooks. `minutes_distribution` sets up the minutes
axis; `target_by_band` and the three signal notebooks are relational reads
against the position × band grid; `signal_correlation` is the cross-sectional
X-vs-X overlap.

| Notebook | Question | Owns |
|---|---|---|
| `minutes_distribution.ipynb` | How do minutes distribute by position? Where does the band edge sit? | the minutes axis (univariate setup) |
| `target_by_band.ipynb` | What does scoring look like at each position × minutes band? | **the `total_points` distribution** (blank / effective-blank / return / haul rates) |
| `signal_levels_by_band.ipynb` | How does each signal's typical level sit across minutes bands? | signal level (median/IQR/p90) per band |
| `signal_presence_by_band.ipynb` | Which leading indicators are alive/testable within each band × position? | zero-mass / liveness per (leading indicator, position, band) |
| `signal_target_association.ipynb` | How does the signal→points rank-association (rho) vary across bands? | within-band rho EDA (leading indicators only) |
| `signal_correlation.ipynb` | How much do leading indicators overlap with each other, per position? | Spearman matrix among `leading_alive` pairs |

`target_by_band` **owns the Y distribution** for the whole foundation layer;
`composition/scoring_engine` owns the formula-component distributions and the
total_points *reconstruction*, but not Y's own distribution.

## 3. Directive questions

**`minutes_distribution.ipynb`** *(axis setup)*
- Determine how minutes distribute by position — establish the shape (a
  full-match spike at 90 over a cameo/partial tail, not a clean two-hump
  distribution).
- Quantify each position's secure-minutes (60+) share, justifying where the
  60-minute band edge sits.

**`target_by_band.ipynb`**
- Determine how `total_points` distributes at each (position, minutes band):
  blank (Y = 0), effective-blank (Y ≤ 2), return (≥ 4, ≥ 6, ≥ 8) and haul
  (> 10) rates.
- Establish whether scoring steps at 60 (a property of the scoring rules) or
  ramps smoothly — purely the descriptive picture, nothing decided here.

**`signal_levels_by_band.ipynb`**
- Determine how each signal's typical level sits across minutes bands — does it
  rise with minutes on the pitch or stay flat?
- Establish which signals move most from cameo to full-game appearances and
  which barely move.

**`signal_presence_by_band.ipynb`** *(leading indicators only)*
- Determine, per (leading indicator, position, band), whether the signal is
  *alive* (carries mass and variance) or a structural zero — i.e. which signals
  are even testable in that cell.
- Establish where liveness is minutes-gated (a signal that only switches on at
  60+) versus present in every band.

**`signal_target_association.ipynb`** *(EDA — leading indicators only; never formula inputs)*
- Determine, per (signal, position), how the Spearman rho between the signal and
  points varies across the minutes bands (`1-29 / 30-59 / 60+`).
- Establish which signals track points in every band (event-driven,
  minutes-independent) versus only at 60+ (accumulation/defensive,
  minutes-dependent).
- *(No classification/verdict here; minutes-adjusted explanation — partial rho —
  is deferred, §5.)*

**`signal_correlation.ipynb`**
- Determine, per position, how strongly the live leading indicators overlap with
  each other (Spearman matrix over `leading_alive` pairs).
- Establish which signals are near-redundant (high mutual rho) versus carrying
  independent information.

## 4. Shared method

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic).
- **Base population:** `minutes > 0` participation (the player featured), **not**
  a performance gate — the 60-minute mark is the *object of study* here, not a
  pre-imposed filter.
- **Minutes bands:** `1-29 / 30-59 / 60+` — collapsed at 60 because FPL's
  scoring rules do not distinguish 60-89 from 90 (same appearance / clean-sheet
  regime), so `60+` is the rule-aligned band.
- **Positions:** GK / DEF / MID / FWD; every relational read is per-position.
- **DGW:** **excluded** across all band notebooks (`is_dgw == False`) — this
  drops the fixture-doubling confound (the ~180-minute rows) cleanly rather than
  pooling and flagging it. Per-fixture DGW treatment is the `fixture/` layer's
  job.
- **Two signal classes** (derived from the domain sets — `domain/signal_layers.py`,
  never hardcoded):
  - **Formula inputs** = `layer_role ∈ TAUTOLOGICAL_LAYER_ROLES` (`goals_scored`,
    `assists`, `clean_sheets`, `bonus`, `bps`, `saves`, `penalties_saved`,
    `penalties_missed`, `own_goals`, `yellow_cards`, `red_cards`,
    `goals_conceded`). Valid for **distribution / frequency / decomposition**.
    **Not** valid for association with Y.
  - **Leading indicators** = `feature_candidate_eligible` signals *not* in the
    tautological set (`xg`, `xa`, `threat`, `influence`, `creativity`, `tackles`,
    `clearances_blocks_interceptions`, `recoveries`, `defensive_contribution`;
    plus composites `xgi`, `ict_index`). Valid for **association** and
    **X-vs-X correlation**.
- **The tautology rule (mandate #1):** a same-gameweek association between a
  formula-input signal and `total_points` is mechanically determined by the
  scoring formula — it measures the formula, not player quality. So
  `signal_target_association` and `signal_correlation` operate on **leading
  indicators only**; formula inputs never appear on the association/correlation
  side.
- **Signal universe for distribution & correlation:** drop `starts` (a minutes
  proxy, deferred axis) and the **exact composites** `ict_index`
  (= influence + creativity + threat) and `xgi` (= xg + xa) in favour of their
  parts — perfect functions of signals we keep, so dropping them loses no
  information while avoiding double-counting. `defensive_contribution` and its
  parts (CBI / tackles / recoveries) are **all kept** — DC is not an exact sum
  (r ≈ 0.81), so each carries independent signal.
- **Shared liveness logic:** the `(signal, position[, band])` "is this leading
  indicator alive?" determination is extracted into
  `research/kernels/descriptive/relevance.py`, which classifies each pair into
  `formula_input` / `formula_input_dead` / `leading_alive` / `structural_zero`
  from the mart + domain sets. `signal_presence_by_band` and `signal_correlation`
  (and `composition/signal_taxonomy`) call the kernel; none recompute the
  heuristic.

## 5. Deferred — the Diagnostic-tier follow-up (not built)

`signal_target_association.ipynb` *describes* (as EDA) how the leading-indicator
→ points rank-association varies **across minutes bands**: event-driven signals
track points in every band (minutes-independent), while accumulation/defensive
signals only relate to points at 60+ (minutes-dependent). `signal_levels_by_band`
separately *describes* that those same accumulating signals sit higher in
higher-minute bands.

**The layer deliberately stops at description.** *Explaining* the shift —
whether minutes drives it, what the association looks like once minutes is
adjusted for — is the Diagnostic tier, not concluded here. Recorded so a later
phase can pick it up, with the method options and the fact that the tooling
already exists:
- minutes-adjusted association (partial Spearman controlling for minutes) —
  `research/kernels/inferential/resampling.py` (`partial_spearman`,
  `bootstrap_partial_rho`);
- per-90 normalisation of counts;
- formal conditioning / heterogeneity *testing* of the within-band association —
  `research/kernels/diagnostic/conditioning.py` (`compute_conditional_rho`,
  `classify_heterogeneity`).

**No causal claims.** "An extra 30 minutes causes +X points" is causal (Pearl
rung 2) and is out of scope for the whole layer — exposure is confounded with
player quality; minutes-adjustment yields an *association*, not causation.

## 6. Supporting modules

No population-local modules remain. The one piece of shared logic — the
`(signal, position)` relevance/liveness map — lives in the descriptive kernel
package (`research/kernels/descriptive/relevance.py`, §4) so the three
notebooks that need it call one source. `robustness.py`
(`compute_dual_scope_rho`, `classify_population_robustness`) was removed after
the EDA reframe of the within-band association notebook made it unused; its test
file `tests/test_signals_population.py` was removed with it.
