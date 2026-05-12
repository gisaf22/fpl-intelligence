# Study SA — Performance Signal Association with Returns

**Status:** ARCHIVED — pre-methodology run. Redesign required before rerun under locked methodology.  
**Lag convention:** lag-1  
**Depends on:** none

---

## Question

Among the full 2025-26 population, which 3-GW and 5-GW rolling output 
signals at GW n are associated with total_points at GW n+1?

---

## Population

Players with a fixture in the signal GW who played (minutes > 0) in at 
least 2 of their last 3 available GWs. Consistent with the pinned minutes 
certainty definition (ADR-001). "Played" means any appearance — no minutes 
threshold beyond minutes > 0.

---

## Method

| Parameter | Value |
|---|---|
| GW range | 4–33 |
| Minutes filter | None |
| Target variable | total_points at GW N+1 |
| Correlation method | Spearman |
| Positions | GK, DEF, MID, FWD |
| NaN handling | Pairwise — maximum data per signal, n varies per signal and is reported |
| Uncertainty | Bootstrap 95% CI, 1000 resamples |
| Reported per result | rho, CI lower, CI upper, n |

No p-values. 2025-26 is the population. Bootstrap CIs test sensitivity 
to which player-GW records are included in the calculation.

---

## DAL functions called

- build_player_gameweek_spine()
- build_player_gameweek_state()

---

## Signals tested

Output signals only. Minutes signals excluded — playing time is a 
separate question, not a form signal.

### GK signals

| Signal | Rationale |
|---|---|
| total_points_avg_roll3 | Recent average output, short window |
| total_points_avg_roll5 | Recent average output, longer window |

Attacking signals (xg, xa, xgi, goals_scored, assists) excluded for GKs. 
GKs generate no attacking output — these signals are structurally zero 
with noise and cannot associate with GK returns. Running them produces 
artefacts, not findings.

Gap noted: GK-specific signals (save points, clean sheet rate, opponent 
shots-on-target) are not in the current signal set. GK form is 
underspecified by this study.

### DEF, MID, FWD signals

| Signal | Role |
|---|---|
| total_points_avg_roll3 | Recent average output, short window |
| total_points_avg_roll5 | Recent average output, longer window |
| xgi_roll3 | Construct signal — combined attacking threat, short window |
| xgi_roll5 | Construct signal — combined attacking threat, longer window |
| xg_roll3 | Decomposition — goal threat component, short window |
| xg_roll5 | Decomposition — goal threat component, longer window |
| xa_roll3 | Decomposition — assist threat component, short window |
| xa_roll5 | Decomposition — assist threat component, longer window |
| goals_scored_roll3 | Realised goal output, short window |
| goals_scored_roll5 | Realised goal output, longer window |
| assists_roll3 | Realised assist output, short window |
| assists_roll5 | Realised assist output, longer window |

xgi is the headline construct signal for attacking threat. xg and xa 
are reported as decomposition only — to show whether goal threat or 
assist threat drives the construct by position. Decided a priori, not 
selected post-run by rho magnitude.

---

## Pre-run decisions

- Population filter: played (minutes > 0) in >= 2 of last 3 available GWs — 
  consistent with ADR-001 minutes certainty definition. "Played" = any 
  appearance, no minutes threshold beyond minutes > 0
- "Last 3 available GWs" means last 3 fixture rows per player in the spine — 
  spine is fixture-driven so each row is an available GW, no calendar-GW 
  alignment needed
- Derived inline in study_a.py as _played / _played_last3 — not a DAL field
- GW 33 upper bound — GW 34 not yet ingested, no next-GW target available
- BGW handled by construction — spine is fixture-driven; blank-GW rows absent 
  by construction, no null or zero imputation needed
- Minutes signals excluded — playing time belongs in an availability study
- No magnitude threshold — signals where the bootstrap CI crosses zero 
  are treated as uninformative for SD. The population's own noise is the 
  bar, not an external effect-size criterion. All rhos reported regardless
- xgi is the construct signal for attacking threat — xg and xa are 
  decomposition, decided a priori
- Attacking signals excluded for GKs — structurally zero with noise
- NaN handling is pairwise — n varies per signal and is reported
- NaN counts reported explicitly as data quality findings
- Roll-5 is the primary window. If roll-3 and roll-5 diverge in direction 
  for the same position-signal pair, that signal is flagged as unstable 
  in the results. Exclusion from SD decided after reviewing the pattern 
  of divergence across positions — not automatically
- GW 4 lower bound — rolling windows not meaningful before that. Roll-5 
  signals are NaN at GW 4–5 and excluded by pairwise handling — effective 
  lower bound for roll-5 signals is GW 6
- Bootstrap CIs test sensitivity to which player-GW records are included, 
  not sampling error

---

## What this study describes

The true associations between output signals and returns in the 2025-26 
population. Not a prediction model. Not a generalisable finding. A 
description of what happened this season.

Next season: run identical methodology on 2026-27. The delta is the 
drift measurement — noting that a delta in rho conflates signal decay, 
different player compositions, and different competitive conditions. 
Richer design required at that point.

---

## Open questions

- GK signals are underspecified — save points, clean sheet rate, 
  opponent shots-on-target not in current signal set. GK form 
  study warranted separately.
- xg outranks xa for FWD, xa outranks xg for DEF/MID — may 
  partly reflect points weighting (goal = 2x assist in FPL) 
  rather than signal quality independent of scoring system. 
  Future study: disentangle points-weighting effect from genuine 
  signal difference.
- Expected metrics consistently outperform realised events — 
  finishing luck smoothed by xG. Worth testing whether this 
  holds across different season styles in 2026-27.
- DEF goals_scored near-zero — too rare to carry signal. 
  Consider dropping from future reruns.

---

## Outputs

| Output | Path |
|---|---|
| Results | research/studies/SA/results/spearman_correlations.json |
| MLflow run | experiment: studies, run tag: study_id=SA |

---

## Signal status

| Signal | Position | rho | CI lower | CI upper | n | Notes |
|---|---|---|---|---|---|---|
| total_points_avg_roll5 | GK | +0.098 | +0.019 | +0.177 | 577 | informative |
| total_points_avg_roll5 | DEF | +0.220 | +0.185 | +0.252 | 3042 | informative |
| total_points_avg_roll5 | MID | +0.333 | +0.304 | +0.360 | 4173 | informative |
| total_points_avg_roll5 | FWD | +0.387 | +0.334 | +0.436 | 1065 | informative |
| xgi_roll5 | DEF | +0.186 | — | — | — | informative |
| xgi_roll5 | MID | +0.281 | — | — | — | informative |
| xgi_roll5 | FWD | +0.360 | — | — | — | informative |
| goals_scored_roll3 | DEF | +0.016 | -0.020 | +0.053 | — | uninformative — CI crosses zero |

---

## What this unblocks

SC is independent. SD depends on SA signals once rerun is complete.
