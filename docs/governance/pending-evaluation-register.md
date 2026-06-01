# Pending Evaluation Register

**Status:** ACTIVE  
**Version:** 1.0  
**Created:** 2026-05-31  
**Authority:** Analytical Architecture Stabilisation — Phase 1

---

## Purpose

This register tracks novel analytical metrics that are currently in production intelligence modules but have not been evaluated via a named lens study. Each entry carries production weight yet has no evidence base from the three-gate evaluation framework.

These metrics are not governance violations in themselves — they are editorial heuristics that are operationally reasonable but analytically unvalidated. They must not have their weights increased, be added to new modules, or be promoted to signal status without completing the lens evaluation process documented in `evaluation-gate-criteria.md`.

---

## Open Entries

### PENDING-EVAL-01 — `consistency_score` (`intelligence/value.py`)

**Description:** A measure of alignment between xgi_roll3 and xgi_roll5, computed as:
```
1 - |xgi_roll3 - xgi_roll5| / xgi_roll5
```
Clipped to [0, 1]. High score = recent xgi matches medium-term xgi (stable contributor, not a one-week spike). FWD players receive neutral 0.5 (both xgi values zeroed before computation).

**Module:** `intelligence/value.py`  
**Weight:** 20% of `value_score`  
**Lens evidence:** None. No study evaluates rolling xgi alignment as a predictor of future total_points.  
**Hypothesis:** Players with consistent xgi output over rolling windows deliver more reliable point returns than one-week spikes.  
**Evaluation path:** Lens study required: target = `total_points` (or `points_next_gw`), population = minutes ≥ 60, signal = consistency_raw, 3-gate evaluation per position.  
**Risk if unevaluated:** 20% of value_score is driven by a metric that may be noise. High consistency_score may simply select players with low xgi variance (bench-warmers), not genuinely reliable attackers.

---

### PENDING-EVAL-02 — `team_goals_roll5` / `team_attack_score` (`intelligence/fixtures.py`)

**Description:** Team-level attacking strength derived as the mean of each team's total `goals_scored` across a rolling lookback window, normalized to [0, 1] across teams. Maps to individual players via `team_id`.

**Module:** `intelligence/fixtures.py`  
**Effective weight:** ~58% of `fixture_opportunity_score` (exact weight depends on registry; team_attack_score vs dgw_bonus_score split)  
**Lens evidence:** None. No lens study evaluates team-level goal rate as a predictor of individual player returns. This is a team-level aggregate, not a player-level signal.  
**Hypothesis:** Players on high-scoring teams are more likely to accrue attacking returns (assists, goals, bonus points) than players on low-scoring teams.  
**Evaluation path:** Requires a team-context lens study: target = `total_points` (individual), signal = team_goals_roll5 mapped to players, population = minutes ≥ 60. The team-level aggregation may need to be validated at the position level (attacking returns for MID/FWD vs defensive context for DEF/GK).  
**Risk if unevaluated:** ~58% effective weight on a metric with no individual-level predictive validation. Team goal rate correlates with fixture difficulty confounders. May be highly collinear with fdr_avg (which is excluded).

---

### PENDING-EVAL-03 — `form_momentum_score` (`intelligence/transfers.py`)

**Description:** The difference between recent and medium-term xgi:
```
form_momentum_score = xgi_roll3 - xgi_roll5
```
Positive when recent 3-GW xgi exceeds 5-GW baseline (rising form). Normalized within position. FWD players receive neutral 0.5 (both xgi operands zeroed before computation).

**Module:** `intelligence/transfers.py`  
**Weight:** 25% of `transfer_score`  
**Lens evidence:** None. No study evaluates xgi acceleration (first derivative of form) as a predictor of future total_points.  
**Hypothesis:** Players with rising xgi trends (roll3 > roll5) are more likely to deliver points in upcoming gameweeks than players with flat or declining form.  
**Evaluation path:** Lens study required: target = `total_points` (lag-1 window), population = minutes ≥ 60, signal = xgi_roll3 - xgi_roll5, 3-gate evaluation per position. Must test whether momentum adds independent predictive signal beyond xgi_roll3 alone.  
**Risk if unevaluated:** 25% of transfer_score is driven by xgi trend. MID momentum signal may overlap heavily with xgi_roll3 alone (SYNTH-01 found xgi_roll3×MID EXCLUDED-REDUNDANT vs xgi_roll5 — xgi_roll3−xgi_roll5 at MID is likely also redundant).

---

## Resolution Criteria

An entry is closed when:
1. A named lens study with ID (e.g., MOMENTUM-001) has been completed.
2. The signal has passed or failed all three gates (G1: CI ≠ 0, G2: monotonic quintile ordering, G3: ≥2/3 block stability).
3. The traceability matrix has been updated with the gate decisions.
4. If excluded: the module guard has been added (zeroing or removal).
5. If approved: the `downstream_status` in the registry has been updated from `caveated` to `eligible`.

---

## Constraints

- No new modules may consume PENDING-EVAL signals without completing the evaluation process.
- No weight increases may be made to PENDING-EVAL metrics without lens evidence.
- PENDING-EVAL-03 (`form_momentum_score`) is at elevated risk: xgi_roll3×MID was EXCLUDED-REDUNDANT in SYNTH-01 (G-SYNTH1-07), suggesting the derivative of that redundant signal is likely also redundant at MID.
