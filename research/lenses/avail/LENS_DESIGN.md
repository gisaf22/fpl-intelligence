# Study SE — Minutes Consistency and Trend Association with Returns

**Status:** ARCHIVED — pre-methodology run. Redesign required before rerun under locked methodology.  
**Lag convention:** same-GW  
**Depends on:** none

---

## Question

Among all players with a fixture in 2025-26, did minutes volume 
and minutes trend associate with same-GW returns — and does a 
rising minutes trend associate with higher returns than a falling 
or stable trend?

---

## Population

Players who appeared in the signal GW (minutes > 0 in GW N). 
No rolling activity filter. SGW rows only. Removes structural 
zeros from non-playing players without conditioning on the 
rolling signals being tested.

DGW rows excluded — fixture_count == 1 (SGW rows only). Minutes 
in a DGW is a sum across two fixtures (max 180) — structurally 
different from SGW minutes and not comparable. Consistent with 
SC's DGW exclusion rationale.

Players without a fixture in the signal GW are excluded by 
construction — spine is fixture-driven, absent players have no row.

Note: SA, SC, and SB all apply the activity filter 
(minutes > 0 in >= 2 of last 3 available GWs). SE applies a 
signal GW appearance filter only (minutes > 0 in GW N) — not 
a rolling filter, and not circular for a minutes study. The 
population for SE is broader than SA, SC, and SB. SD will need 
to resolve this mismatch at design time.

---

## Method

| Parameter | Value |
|---|---|
| GW range | 4–33 |
| Activity filter | Signal GW appearance — minutes > 0 in GW N. Not a rolling filter. |
| SGW filter | fixture_count == 1 — DGW rows excluded |
| Target variable | total_points at GW N (same-GW) |
| Correlation method | Spearman |
| Positions | GK, DEF, MID, FWD |
| NaN handling | Pairwise — n varies per signal and is reported |
| Uncertainty | Bootstrap 95% CI, 1000 resamples |
| Reported per result | rho, CI lower, CI upper, n |
| Reported per trend bucket | E[points], P25, median, P75, P90, n |

No p-values. 2025-26 is the population. Bootstrap CIs test 
sensitivity to which player-GW records are included in the 
calculation. Signals where the bootstrap CI crosses zero are 
treated as uninformative — consistent with SA, SC, SB.

Same-GW design is intentional. Minutes signals describe recent 
availability and trend. The question is whether players with 
more minutes and rising trends were actually returning in that 
same GW — a description of what happened, not a forward 
prediction.

---

## DAL functions called

- build_player_gameweek_spine()
- build_player_gameweek_state()

No additional DAL functions needed — all minutes signals are 
present in the state output.

---

## Signals tested

Minutes volume and trend signals only. Output signals excluded 
— those belong to SA. Market signals excluded — those belong 
to SB.

| Signal | Type | Rationale |
|---|---|---|
| minutes_roll3 | Continuous | Recent minutes volume, short window |
| minutes_roll5 | Continuous | Recent minutes volume, longer window |
| minutes_trend | Categorical | Direction of minutes change — rising/falling/stable |

**minutes_trend handling:**
minutes_trend is categorical — rising, falling, stable, None. 
It cannot be passed directly to Spearman. Two approaches applied:

1. Encode as ordinal for Spearman — falling=0, stable=1, 
   rising=2. Decided a priori. Tests whether the ordered trend 
   direction associates with returns. Deciding the encoding 
   before seeing results ensures the method is a design choice, 
   not a result-driven choice.
2. Report conditional distributions per trend bucket — 
   E[points], P25, median, P75, P90 per position per trend 
   value. Primary actionable output for minutes_trend, 
   consistent with SC's FDR distribution approach.

minutes_trend None values excluded from both analyses — 
insufficient prior GW history. Exclusion predicate: 
pd.isna(minutes_trend). NaN count reported explicitly per 
position.

---

## Pre-run decisions

- Signal GW appearance filter — minutes > 0 in GW N. Not a 
  rolling filter. Players who did not appear in the signal GW 
  are excluded — their rolling signals and same-GW points are 
  both near-zero by construction, not a finding about minutes 
  consistency.
- DGW rows excluded — fixture_count == 1. Minutes in a DGW 
  is a sum across two fixtures, not comparable to SGW minutes
- GW range 4–33 — GW 34 not yet ingested
- Same-GW design — minutes signals describe current availability 
  and trend, question is whether they associate with same-GW 
  returns
- minutes_trend encoded as ordinal (falling=0, stable=1, 
  rising=2) for Spearman — decided a priori, not post-run
- minutes_trend None values excluded via pd.isna() — 
  insufficient history, NaN count reported explicitly
- Conditional distributions reported per trend bucket per 
  position — primary actionable output for minutes_trend
- Roll-5 is primary window — if roll3 and roll5 diverge in 
  direction for same position-signal pair flag as unstable, 
  consistent with SA rule
- Roll-5 effective lower bound is GW 6 — roll-5 signals are 
  NaN at GW 4–5, excluded by pairwise handling
- minutes_roll3 and minutes_roll5 are NaN for players with 
  insufficient prior fixture history — mid-season entrants, 
  late signings, players returning from long injuries. These 
  are excluded by pairwise handling. Effective population is 
  SGW players with sufficient rolling window history, not the 
  complete SGW fixture population. NaN counts reported 
  explicitly per signal per position
- No magnitude threshold — signals where bootstrap CI crosses 
  zero are uninformative. All rhos reported regardless
- NaN handling is pairwise — n varies per signal and is reported
- NaN counts reported explicitly as data quality findings
- Bootstrap CIs test sensitivity to which player-GW records 
  are included, not sampling error

---

## What this study describes

Whether minutes volume and trend associated with returns in 
2025-26 among players who appeared in the signal GW. Not a 
prediction model. A description of whether players with more 
minutes and rising trends were actually returning in the same GW.

Next season: run identical methodology on 2026-27. The delta 
measures whether minutes-returns relationships are stable or 
season-specific.

---

## Open questions

- GK all signals uninformative — minutes volume and trend do 
  not associate with GK same-GW returns among players who 
  appeared. Clean sheet is the dominant GK return mechanism, 
  not minutes volume. Consistent with SA and SC findings that 
  GK signals are underspecified.
- minutes_roll3 stronger than minutes_roll5 across all 
  informative positions — short window captures recent playing 
  time more precisely than the longer window.
- MID and FWD show strongest association (0.53, 0.55) — 
  players who have been playing more minutes recently return 
  more in the same GW for attacking positions.
- minutes_trend informative for DEF/MID/FWD (0.11–0.22) but 
  uninformative for GK — rising trend associates with higher 
  outfield returns.
- Trend distributions show separation at tails not median — 
  P75 and P90 are the decision-relevant outputs, consistent 
  with SC FDR distribution finding.
- Do minutes signals add information beyond form and fixture 
  signals when combined in SD? Minutes volume is strong for 
  MID/FWD — does it condition or interact with xgi_roll5 
  and fixture_difficulty_avg?
- GK minutes signals uninformative across SA, SC, and SE — 
  a dedicated GK study with position-specific signals 
  (saves, clean sheet rate, opponent xG) is warranted.

---

## Known gaps

**No started binary flag**
A clean binary started flag (minutes >= 45 or minutes >= 60) 
does not exist in the state layer. minutes_roll3 and 
minutes_roll5 are continuous averages — they capture volume 
but not a clean start/substitute distinction. Derivable inline 
if needed in a follow-on study.

**minutes_trend thresholds are fixed**
The rising/falling/stable thresholds (>30, <-30, |diff|<=30) 
are fixed in the state layer. These were design decisions made 
when the state layer was built — not tuned for this study. 
The threshold values are not tested here.

**DGW minutes inflation**
DGW rows are excluded precisely because minutes sums across 
two fixtures are not comparable to SGW minutes. The DGW 
minutes question — does playing two fixtures associate with 
higher returns — is a separate study not addressed here.

**Population mismatch with SA, SC, SB**
SE uses a broader population than SA, SC, and SB — signal GW 
appearance filter only vs the rolling 2-of-last-3 activity 
filter. When SD combines signals from all four studies, the 
populations will not align. SA, SC, SB rows are a subset of 
SE rows. SD will need to decide which population to apply to 
the combined signal dataset at design time — this is a known 
dependency that SD must resolve explicitly.

**GK underspecified across all studies**
SA, SC, and SE all find GK signals uninformative or weakly 
informative. minutes signals, output signals, and fixture 
signals do not explain GK returns adequately. A dedicated 
GK study with position-specific signals — save points, 
clean sheet rate, opponent attacking xG — is the next 
logical step for GK analysis. This is a recurring gap 
across the study programme, not just SE.

---

## Outputs

| Output | Path |
|---|---|
| Results | research/studies/SE/results/spearman_correlations.json |
| Trend distributions | research/studies/SE/results/trend_distributions.json |
| MLflow run | experiment: studies, run tag: study_id=SE |

---

## Signal status

| Signal | Position | rho | CI lower | CI upper | n | Notes |
|---|---|---|---|---|---|---|
| minutes_roll3 | GK | +0.0441 | -0.0421 | +0.1245 | 594 | uninformative — CI crosses zero |
| minutes_roll5 | GK | +0.0575 | -0.0282 | +0.1424 | 594 | uninformative — CI crosses zero |
| minutes_trend | GK | -0.0479 | -0.1271 | +0.0390 | 547 | uninformative — CI crosses zero |
| minutes_roll3 | DEF | +0.3188 | +0.2867 | +0.3529 | 3048 | informative |
| minutes_roll5 | DEF | +0.2813 | +0.2480 | +0.3125 | 3048 | informative |
| minutes_trend | DEF | +0.1077 | +0.0711 | +0.1438 | 2810 | informative |
| minutes_roll3 | MID | +0.5286 | +0.5037 | +0.5496 | 4148 | informative |
| minutes_roll5 | MID | +0.4810 | +0.4578 | +0.5040 | 4148 | informative |
| minutes_trend | MID | +0.1835 | +0.1551 | +0.2118 | 3791 | informative |
| minutes_roll3 | FWD | +0.5457 | +0.5001 | +0.5873 | 1094 | informative |
| minutes_roll5 | FWD | +0.5007 | +0.4502 | +0.5437 | 1094 | informative |
| minutes_trend | FWD | +0.2198 | +0.1590 | +0.2715 | 993 | informative |

---

## Trend distribution results

| Position | Trend | E[points] | P25 | Median | P75 | P90 | n |
|---|---|---|---|---|---|---|---|
| GK | rising | 3.000 | 1.0 | 2.0 | 3.0 | 7.0 | 57 |
| GK | stable | 3.316 | 2.0 | 2.0 | 5.0 | 7.0 | 490 |
| GK | falling | — | — | — | — | — | 0 |
| DEF | rising | 3.264 | 1.0 | 2.0 | 5.0 | 8.0 | 549 |
| DEF | stable | 3.102 | 1.0 | 2.0 | 5.0 | 8.0 | 2070 |
| DEF | falling | 2.010 | 1.0 | 1.0 | 2.0 | 6.0 | 191 |
| MID | rising | 3.488 | 2.0 | 2.0 | 4.0 | 8.0 | 627 |
| MID | stable | 2.923 | 1.0 | 2.0 | 4.0 | 7.0 | 2854 |
| MID | falling | 2.032 | 1.0 | 1.0 | 2.0 | 4.0 | 310 |
| FWD | rising | 3.934 | 2.0 | 2.0 | 5.25 | 9.0 | 136 |
| FWD | stable | 2.898 | 1.0 | 2.0 | 2.0 | 7.0 | 785 |
| FWD | falling | 1.875 | 1.0 | 1.0 | 2.0 | 5.0 | 72 |

---

## What this unblocks

SD can consume SE minutes signals once complete. SE is 
independent of SA, SC, SB. SD needs SA, SC, SB, and SE 
before running.

Population mismatch note: SA, SC, SB use the rolling activity 
filter. SE uses a signal GW appearance filter. SD should expect 
this mismatch and resolve the combined population definition 
explicitly at SD design time — not inherited from any single 
upstream study.
