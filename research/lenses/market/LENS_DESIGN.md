# Study SB — Market Signal Association with Returns

**Status:** ARCHIVED — pre-methodology run. Redesign required before rerun under locked methodology.  
**Lag convention:** same-GW  
**Depends on:** none

---

## Question

Did crowd market signals — transfers and ownership — associate 
with returns in the same GW across the 2025-26 season?

---

## Population

Players with a fixture in the signal GW who started at least 2 
of their last 3 available GWs. Consistent with the pinned minutes 
certainty definition (ADR-001). Same activity filter as SA and SC.

DGW rows included — market signals (ownership, transfers) are 
assigned at GW level not fixture level. No ambiguity across 
multiple fixtures in the same GW.

Players without a fixture in the signal GW are excluded by 
construction — spine is fixture-driven, absent players have no row.

---

## Method

| Parameter | Value |
|---|---|
| GW range | 4–33 |
| Activity filter | minutes > 0 in >= 2 of last 3 available GWs — derived inline, consistent with SA and SC |
| SGW filter | None — DGW rows included |
| Target variable | total_points at GW N (same-GW) |
| Correlation method | Spearman |
| Positions | GK, DEF, MID, FWD |
| NaN handling | Pairwise — n varies per signal and is reported |
| Uncertainty | Bootstrap 95% CI, 1000 resamples |
| Reported per result | rho, CI lower, CI upper, n |

No p-values. 2025-26 is the population. Bootstrap CIs test 
sensitivity to which player-GW records are included in the 
calculation. Signals where the bootstrap CI crosses zero are 
treated as uninformative — consistent with SA and SC.

Same-GW design is intentional. Market signals at GW N reflect 
crowd expectations for GW N. The question is whether the crowd 
was right — did market movement associate with returns in that 
same GW?

---

## DAL functions called

- build_player_gameweek_spine()
- build_player_gameweek_state()

Note: transfers_in and transfers_out were added to 
_ANALYTICS_REQUIRED_COLS in get_player_gw_analytics() and to 
_SPINE_COLS/_SUM_COLS/_DTYPES in build_player_gameweek_spine() 
as a prerequisite DAL task before this study ran.

---

## Signals tested

Market sentiment signals only. Price excluded — it reflects 
affordability not market movement. Transfers and ownership 
capture crowd sentiment directly.

| Signal | Rationale |
|---|---|
| transfers_in | Crowd moving toward player this GW |
| transfers_out | Crowd moving away from player this GW |
| transfers_balance | Net crowd movement — composite signal |
| ownership_count | Total crowd conviction in player |

No rolling windows — market signals are point-in-time per GW. 
ownership_count reflects cumulative crowd conviction at GW N. 
transfers_in and transfers_out reflect GW N movement only.

---

## Pre-run decisions

- Same activity filter as SA and SC — derived inline, consistent 
  across all studies
- DGW rows included — market signals are GW-level, no fixture 
  ambiguity
- GW range 4–33 — GW 34 not yet ingested
- Price excluded — affordability signal, not market movement
- No rolling windows — market signals are point-in-time
- Same-GW design — crowd reacts to GW N information, question 
  is whether they are right in GW N
- No magnitude threshold — signals where bootstrap CI crosses 
  zero are uninformative. All rhos reported regardless
- NaN handling is pairwise — n varies per signal and is reported
- NaN counts reported explicitly as data quality findings
- Bootstrap CIs test sensitivity to which player-GW records are 
  included, not sampling error

---

## What this study describes

Whether crowd market behaviour — transfers and ownership — was 
associated with returns in 2025-26. Not a prediction model. 
A description of whether the crowd was right, by position, 
across the season.

Next season: run identical methodology on 2026-27. The delta 
measures whether crowd wisdom is stable or season-specific.

---

## Open questions

- transfers_in is the dominant market signal across all 
  positions — crowd movement toward a player is more 
  informative than movement away. Gap is clearest for FWD 
  (0.35 vs 0.23 for transfers_out).
- transfers_out uninformative for GK only — GK transfers 
  are rotation-driven not form-driven. Informative for 
  outfield positions but weaker than transfers_in.
- transfers_balance is partially redundant given both raw 
  signals are reported — adds less than transfers_in alone 
  in every position (0.13–0.16 vs 0.19–0.35).
- ownership_count scales with attacking opportunity — 
  GK 0.11, FWD 0.30. For attacking positions reflects 
  return expectations, not just safety picking.
- Signal strength increases along positional spectrum 
  GK < DEF < MID < FWD — market signals most informative 
  where attacking returns are most variable.
- How do market signals interact with form and fixture 
  signals? (→ SD)

---

## Known gaps

**transfers_in and transfers_out directionality**
transfers_balance is a net signal — heavy transfers_in with 
heavy transfers_out looks similar to low movement in both 
directions if the net is the same. Both raw signals are 
included to expose this but the interaction between them 
is not formally tested here.

**Ownership level vs ownership change**
ownership_count is a stock measure — total managers owning 
the player at GW N. It does not capture whether ownership 
is rising or falling week-on-week. A delta_ownership signal 
(change in ownership_count from GW N-1 to GW N) would be 
more sensitive to crowd momentum but is not in the current 
signal set. Derivable from the state layer if needed.

**Captaincy signal absent**
Captaincy rate is not available in the current DAL. High 
captaincy selections are a stronger crowd signal than 
ownership alone — a player owned by 30% but captained by 
20% is a different proposition than one owned by 50% but 
rarely captained. Not testable from current data.

---

## Outputs

| Output | Path |
|---|---|
| Results | research/studies/SB/results/spearman_correlations.json |
| MLflow run | experiment: studies, run tag: study_id=SB |

---

## Signal status

| Signal | Position | rho | CI lower | CI upper | n | Notes |
|---|---|---|---|---|---|---|
| transfers_in | GK | +0.1923 | +0.1102 | +0.2771 | 597 | informative |
| transfers_in | DEF | +0.2617 | +0.2281 | +0.2939 | 3141 | informative |
| transfers_in | MID | +0.3251 | +0.2975 | +0.3514 | 4323 | informative |
| transfers_in | FWD | +0.3536 | +0.3006 | +0.4051 | 1107 | informative |
| transfers_out | GK | +0.0624 | -0.0135 | +0.1421 | 597 | uninformative — CI crosses zero |
| transfers_out | DEF | +0.1534 | +0.1206 | +0.1886 | 3141 | informative |
| transfers_out | MID | +0.2051 | +0.1748 | +0.2340 | 4323 | informative |
| transfers_out | FWD | +0.2349 | +0.1751 | +0.2899 | 1107 | informative |
| transfers_balance | GK | +0.1272 | +0.0482 | +0.1982 | 597 | informative |
| transfers_balance | DEF | +0.1574 | +0.1198 | +0.1935 | 3141 | informative |
| transfers_balance | MID | +0.1646 | +0.1382 | +0.1957 | 4323 | informative |
| transfers_balance | FWD | +0.1296 | +0.0721 | +0.1886 | 1107 | informative |
| ownership_count | GK | +0.1071 | +0.0257 | +0.1853 | 597 | informative |
| ownership_count | DEF | +0.1932 | +0.1624 | +0.2268 | 3141 | informative |
| ownership_count | MID | +0.2394 | +0.2124 | +0.2663 | 4323 | informative |
| ownership_count | FWD | +0.2973 | +0.2399 | +0.3507 | 1107 | informative |

---

## What this unblocks

SD can consume SB signals once complete. SB is independent 
of SA and SC — SD needs all three before running.
