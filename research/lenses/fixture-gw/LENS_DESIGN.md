# Study SC — Fixture Difficulty Distribution Against Returns

**Status:** ARCHIVED — pre-methodology run. Redesign required before rerun under locked methodology.  
**Lag convention:** same-GW — descriptive, not predictive  
**Depends on:** none

---

## Question

How did fixture difficulty distribute against returns across 
positions across the full 2025-26 season?

---

## Population

Players with a fixture in the signal GW who played (minutes > 0) 
in at least 2 of their last 3 available GWs. This filter is 
derived inline in the study script — consistent with SA's 
implementation and a proxy for the ADR-001 minutes certainty 
definition. It is not an exact implementation of ADR-001, which 
defines "started" as a stricter threshold; the proxy uses any 
minutes played as the activity signal.

DGW rows excluded — fixture_count == 1 (SGW rows only). In a DGW 
the dominant effect is opportunity volume, not fixture difficulty. 
DGW structure is a separate question. Excluding DGW rows keeps 
the fixture difficulty question clean and unambiguous.

Players without a fixture in the signal GW are excluded by 
construction — spine is fixture-driven, absent players have no row.

---

## Method

| Parameter | Value |
|---|---|
| GW range | 4–33 |
| Activity filter | minutes > 0 in >= 2 of last 3 available GWs — derived inline as rolling(3, min_periods=3).sum() >= 2 on a binary played flag (minutes > 0) |
| SGW filter | fixture_count == 1 — DGW rows excluded |
| Target variable | total_points at GW N (same-GW) |
| Correlation method | Spearman |
| Positions | GK, DEF, MID, FWD |
| FDR buckets | Easy (1–2), Medium (3), Hard (4–5) |
| NaN handling | Pairwise — n varies per signal and is reported |
| Uncertainty | Bootstrap 95% CI, 1000 resamples |
| Reported per result | rho, CI lower, CI upper, n |
| Reported per FDR bucket | E[points], P25, median, P75, P90, n |

No p-values. 2025-26 is the population. Bootstrap CIs test 
sensitivity to which player-GW records are included in the 
calculation. Signals where the bootstrap CI crosses zero are 
treated as uninformative — consistent with SA.

Same-GW design is intentional. Fixture difficulty is known 
before the GW and its effect is on that same GW. SC describes 
what happened, not what to predict.

---

## DAL functions called

- build_player_gameweek_spine()
- build_player_gameweek_state()
- get_opponent_context()

---

## Signals tested

Fixture context signals only. No player-side rolling windows — 
fixture difficulty is a point-in-time fact for each GW. 
Opponent-side rolling signals describe the opponent's recent 
defensive form, not the player's own history.

| Signal | Source field | Rationale |
|---|---|---|
| fixture_difficulty_avg | fixture_difficulty_avg | FPL FDR — primary fixture quality signal. Integer-valued on SGW rows. |
| opponent_goals_conceded_roll3 | opponent_goals_conceded_roll3 | Opponent defensive weakness, short window |
| opponent_goals_conceded_roll5 | opponent_goals_conceded_roll5 | Opponent defensive weakness, longer window |
| opponent_xgc_roll3 | opponent_xgc_roll3 | Opponent underlying defensive quality, short window |
| opponent_xgc_roll5 | opponent_xgc_roll5 | Opponent underlying defensive quality, longer window |
| is_home | home_count == 1 | Home fixture advantage — binary, clean on SGW rows |

fixture_count excluded — DGW structure is a separate question.
home_count and away_count excluded — replaced by is_home binary 
flag which is unambiguous on SGW rows (home_count == 1 → home, 
home_count == 0 → away).

---

## Pre-run decisions

- Activity filter derived inline — `minutes > 0` per GW is binarised
  as `_played`, then `rolling(3, min_periods=3).sum() >= 2` is applied
  per player. This matches SA's exact implementation. It is a proxy
  for the ADR-001 minutes certainty definition (which defines
  "started" more strictly); the proxy uses any minutes played as
  the activity signal.
- GW range 4–33 — GW 34 not yet ingested, no completed target GW
- DGW rows excluded — fixture_count == 1 filter applied before 
  any correlation or distribution calculation
- BGW handled by construction — spine is fixture-driven, players 
  without a fixture have no row
- Same-GW design intentional — fixture difficulty is known before 
  the GW, effect is on that same GW
- is_home derived as home_count == 1 — structurally guaranteed 
  binary on SGW rows, no new DAL field needed
- fixture_count excluded as signal — DGW structure is a separate 
  question, not a fixture difficulty signal
- home_count and away_count excluded as signals — replaced by 
  is_home binary which is unambiguous on SGW rows only
- FDR bucketing on integer-valued floats — fixture_difficulty_avg 
  is structurally integer-valued on SGW rows (e.g. 3.0). Bucket 
  assignment Easy (1–2), Medium (3), Hard (4–5) applied as integer 
  comparison. No non-integer means exist after DGW exclusion
- No magnitude threshold — signals where bootstrap CI crosses zero 
  are uninformative. All rhos reported regardless
- NaN handling is pairwise — n varies per signal and is reported
- NaN counts reported explicitly as data quality findings
- Distributions reported per FDR bucket per position — rho alone 
  is not actionable, distributions are directly usable in a brief
- Bootstrap CIs test sensitivity to which player-GW records are 
  included, not sampling error
- No roll window divergence rule — no player-side rolling windows 
  in this study. Opponent rolling signals (roll3/roll5) are both 
  reported; if they diverge in direction for the same 
  position-signal pair, flag as unstable — consistent with SA rule

---

## What this study describes

How fixture difficulty actually distributed against returns in 
2025-26 by position on single-gameweek fixtures. Not a prediction 
model. Not a generalisable finding. A description of what happened 
this season that is directly usable in a GW brief.

Example output: "DEF facing FDR 4–5 fixture at home: median X 
pts, P75 Y pts, P90 Z pts." That is actionable for transfer and 
captaincy decisions. A correlation coefficient alone is not.

Next season: run identical methodology on 2026-27. The delta is 
the drift measurement.

---

## Open questions

- fixture_difficulty_avg is the only informative standalone 
  signal — opponent rolling defensive signals and is_home do 
  not add information beyond FDR on SGW rows in 2025-26.
- FDR distributions show modest median differentiation — 
  fixture difficulty shifts the tail (P75, P90), not the median. 
  P75 and P90 values are the decision-relevant outputs for 
  captaincy and transfer decisions.
- is_home is uninformative as a standalone signal but may 
  matter as an interaction term in SD — flagged for SD design.
- MID shows least FDR differentiation across buckets — MID 
  returns may be less fixture-dependent than other positions.
- DGW structure is a separate unanswered question — excluded 
  from SC, not addressed here.
- opponent_xgc_roll3/5 uninformative as standalone signals — 
  not yet tested as interaction terms in SD. Retain as SD 
  signal candidates.
- Does fixture difficulty interact with player form signals? 
  (→ SD)

---

## Known gaps

**Missing signal — opponent attacking threat for GK/DEF**
SC tested opponent_xgc_roll3/5 — how many expected goals the 
opponent's defence concedes. That signal is relevant for 
attacking players (MID/FWD). For GK/DEF the relevant signal 
is opponent attacking xG — how many expected goals the 
opponent's attack generates. A GK facing a high-xG attack 
has a lower clean sheet probability regardless of overall FDR. 
This signal is not in the current DAL signal set and was not 
tested. FDR may be absorbing it as a composite or masking it. 
Cannot be determined from SC alone.

**Missing signal — clean sheet probability as explicit target**
SC used total_points as the target for all positions. For 
GK/DEF a cleaner target would isolate clean_sheet_points — 
separating the defensive return mechanism from appearance 
points and save bonuses. Not available as a separate target 
in the current study design. A position-split target 
structure would be needed.

**opponent_xgc vs opponent_xg distinction**
opponent_xgc_roll3/5 measures opponent defensive weakness — 
relevant for MID/FWD attacking returns. opponent_xg_roll3/5 
would measure opponent attacking threat — relevant for GK/DEF 
clean sheet probability. SC only tested the former. The latter 
requires a new field in get_opponent_context() before it can 
be tested. This is a DAL gap, not a study design gap.

---

## Outputs

| Output | Path |
|---|---|
| Correlations | research/studies/SC/results/spearman_correlations.json |
| Distributions | research/studies/SC/results/fdr_distributions.json |
| MLflow run | experiment: studies, run tag: study_id=SC |

---

## Signal status

| Signal | Position | rho | CI lower | CI upper | n | Notes |
|---|---|---|---|---|---|---|
| fixture_difficulty_avg | GK | -0.139 | -0.219 | -0.057 | 589 | informative |
| fixture_difficulty_avg | DEF | -0.119 | -0.154 | -0.082 | 3099 | informative |
| fixture_difficulty_avg | MID | -0.079 | -0.110 | -0.049 | 4262 | informative |
| fixture_difficulty_avg | FWD | -0.086 | -0.142 | -0.033 | 1090 | informative |
| opponent_goals_conceded_roll3 | all | — | — | — | — | uninformative — CI crosses zero |
| opponent_goals_conceded_roll5 | all | — | — | — | — | uninformative — CI crosses zero |
| opponent_xgc_roll3 | all | — | — | — | — | uninformative — CI crosses zero |
| opponent_xgc_roll5 | all | — | — | — | — | uninformative — CI crosses zero |
| is_home | all | — | — | — | — | uninformative — CI crosses zero |

---

## FDR distribution results

| Position | FDR bucket | is_home | E[points] | P25 | Median | P75 | P90 | n |
|---|---|---|---|---|---|---|---|---|
| GK | Easy | home | 3.660 | 2.0 | 3.0 | 6.0 | 7.0 | 106 |
| GK | Easy | away | 3.483 | 1.0 | 2.5 | 6.0 | 7.0 | 58 |
| GK | Medium | home | 3.099 | 1.0 | 2.0 | 3.0 | 7.0 | 162 |
| GK | Medium | away | 3.153 | 1.0 | 2.0 | 5.0 | 7.0 | 150 |
| GK | Hard | home | 2.815 | 1.5 | 2.0 | 3.0 | 6.4 | 27 |
| GK | Hard | away | 2.465 | 1.0 | 2.0 | 3.0 | 7.0 | 86 |
| DEF | Easy | home | 3.354 | 1.0 | 2.0 | 6.0 | 8.0 | 565 |
| DEF | Easy | away | 3.329 | 1.0 | 2.0 | 6.0 | 8.4 | 307 |
| DEF | Medium | home | 2.783 | 1.0 | 2.0 | 4.0 | 7.0 | 852 |
| DEF | Medium | away | 2.792 | 1.0 | 1.0 | 4.0 | 8.0 | 783 |
| DEF | Hard | home | 2.649 | 1.0 | 2.0 | 3.0 | 8.0 | 134 |
| DEF | Hard | away | 2.052 | 1.0 | 1.0 | 3.0 | 6.0 | 458 |
| MID | Easy | home | 3.049 | 1.0 | 2.0 | 4.0 | 8.0 | 782 |
| MID | Easy | away | 3.063 | 1.0 | 2.0 | 4.0 | 8.0 | 415 |
| MID | Medium | home | 2.783 | 1.0 | 2.0 | 4.0 | 7.0 | 1162 |
| MID | Medium | away | 2.643 | 1.0 | 2.0 | 3.0 | 6.0 | 1076 |
| MID | Hard | home | 2.192 | 1.0 | 2.0 | 2.75 | 4.0 | 198 |
| MID | Hard | away | 2.200 | 1.0 | 2.0 | 3.0 | 5.0 | 629 |
| FWD | Easy | home | 3.203 | 1.0 | 2.0 | 5.0 | 7.4 | 187 |
| FWD | Easy | away | 3.204 | 1.0 | 2.0 | 5.0 | 8.0 | 103 |
| FWD | Medium | home | 2.857 | 1.0 | 2.0 | 4.0 | 8.0 | 308 |
| FWD | Medium | away | 2.697 | 1.0 | 2.0 | 2.0 | 8.0 | 277 |
| FWD | Hard | home | 2.378 | 1.0 | 2.0 | 2.0 | 5.6 | 45 |
| FWD | Hard | away | 2.365 | 1.0 | 1.0 | 2.0 | 6.0 | 170 |

---

## What this unblocks

SD depends on SC fixture signals once rerun is complete. 
SA and SC together unblock SD.
