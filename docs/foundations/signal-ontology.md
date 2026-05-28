# Signal Ontology

**Status:** ACTIVE  
**Version:** 3.2  
**Produced:** 2026-05-24  
**Scope:** Conceptual classification of analytical signal families

---

## 1. Purpose

This document defines the conceptual families of all analytical signals recognised by the system.
It classifies what a signal represents — not how it is measured, evaluated, or used.

The ontology is upstream of research, governance, and operationalisation. It does not encode
analytical findings, evaluation outcomes, or methodological constraints.

---

## 2. Boundary

**This document defines:**
- What conceptual family a signal belongs to
- What that family fundamentally represents
- Which signals are members of each family
- Minimal semantic invariants necessary to distinguish families

**This document does not define:**
- Whether a signal is analytically informative
- How signals should be evaluated, tested, or validated
- Rolling windows, lag structures, or temporal transformations
- Registry governance, lifecycle gates, or synthesis eligibility
- Operational scoring, model configuration, or feature engineering

A statement belongs here if it remains true regardless of any analytical outcome, methodological
choice, or implementation change. A statement that depends on how signals are used does not
belong here.

---

## 3. Signal Families

| Family | Signals |
|---|---|
| Outcome | total_points |
| Allocation | bonus, bps |
| Event | goals_scored, assists, saves, penalties_saved, clean_sheets, goals_conceded |
| Process | xg, xa, xgi, xgc |
| Participation | minutes |
| Market | transfers_in, transfers_out, ownership_count |
| Structural Tier | purchase_price |
| Context | fdr_avg, fdr_max, fdr_min, was_home, fixture_count |

---

## 4. Semantic Definitions

### Outcome — `total_points`

The FPL system's terminal aggregate gameweek score for a player. An FPL construct with no
direct football counterpart — it is the final scored result, not a component of it.

---

### Allocation — `bonus`, `bps`

Intermediate constructs produced by the FPL scoring mechanism, sitting between raw football
events and the aggregate score.

- **bps**: a continuous index computed from in-match actions. Input to bonus allocation.
- **bonus**: a discrete points allocation made by the FPL system based on relative bps standing.

Neither signal represents a directly observed football event.

---

### Event — `goals_scored`, `assists`, `saves`, `penalties_saved`, `clean_sheets`, `goals_conceded`

Directly observed discrete occurrences in a match. These events exist in football independently
of the FPL system.

Individual-scope signals are attributed to a specific player. Team-scope signals are attributed
to the team. However, FPL encodes some team events with player-level conditioning:

- **clean_sheets**: team event, but FPL awards clean_sheets=1 only to players who played ≥60
  minutes. Values differ across teammates by minutes played — not uniform across the squad.
- **goals_conceded**: team event, uniform across all players on the same team in a given match.

Some signals are structurally associated with specific positional roles.

---

### Process — `xg`, `xa`, `xgi`, `xgc`

Numerical estimates produced by a statistical model applied to match-process data. Not directly
observed.

- **xg**: estimated goal-scoring probability from shots. Individual-scope.
- **xa**: estimated assist probability from chances created. Individual-scope.
- **xgi**: combined xg and xa estimate. Individual-scope.
- **xgc**: estimated goals-conceded probability from chances allowed. Team-level defensive
  process, but FPL assigns distinct xgc values to different field-player positions within
  the same fixture (documented SC-14) — not uniform across all teammates.

---

### Participation — `minutes`

Direct measurement of time on pitch. Directly observed. Individual-scope.

---

### Market — `transfers_in`, `transfers_out`, `ownership_count`

Population-aggregate records of FPL manager behaviour. Not individual-player football statistics
— counts across the FPL manager population.

- **transfers_in**: count of manager purchases of this player in a given gameweek.
- **transfers_out**: count of manager sales of this player in a given gameweek.
- **ownership_count**: count of managers holding this player at a point in time.

---

### Structural Tier — `purchase_price`

The FPL system's computed price for a player. A system-mediated encoding of player valuation
— the FPL price algorithm takes transfer activity as input, so in-season prices change with
manager behaviour. Distinct from Market signals in that it is a system output, not a direct
count of manager actions.

---

### Context — `fdr_avg`, `fdr_max`, `fdr_min`, `was_home`, `fixture_count`

Properties of the fixture or fixture set in a gameweek. Fully determined before any match
begins. Not descriptive of player or team action within the match.

- **fdr_avg / fdr_max / fdr_min**: aggregations of FPL's per-fixture difficulty rating across
  the player's gameweek fixtures.
- **was_home**: home/away indicator for the fixture.
- **fixture_count**: number of fixtures the player's team plays in the gameweek.

---

## 5. Signal Membership Reference

**Temporal types:**

- **rate** — continuous measurement of a quantity per unit time; meaningful as a fraction
- **count** — discrete integer count of occurrences within a bounded period
- **stock** — point-in-time level of a quantity that persists and changes between periods
- **indicator** — binary or categorical flag with no magnitude interpretation
- **estimate** — model-produced continuous estimate of an underlying unobserved quantity

| Signal | Family | Scope | Temporal Type |
|---|---|---|---|
| total_points | Outcome | Individual | count |
| bonus | Allocation | Individual | count |
| bps | Allocation | Individual | count |
| goals_scored | Event | Individual | count |
| assists | Event | Individual | count |
| saves | Event | Individual | count |
| penalties_saved | Event | Individual | count |
| goals_conceded | Event | Team | count |
| transfers_in | Market | Population | count |
| transfers_out | Market | Population | count |
| fixture_count | Context | Match | count |
| clean_sheets | Event | Team | count |
| was_home | Context | Match | indicator |
| ownership_count | Market | Population | stock |
| purchase_price | Structural Tier | Individual | stock |
| minutes | Participation | Individual | rate |
| xg | Process | Individual | estimate |
| xa | Process | Individual | estimate |
| xgi | Process | Individual | estimate |
| xgc | Process | Team | estimate |
| fdr_avg | Context | Match | estimate |
| fdr_max | Context | Match | estimate |
| fdr_min | Context | Match | estimate |

---

## 6. Anti-Creep Principles

A statement belongs in this document if and only if it remains true when the registry changes,
the methodology changes, the evaluation framework changes, the scoring system changes, or the
implementation changes.

**Maintain:** family boundaries based on what signals fundamentally represent in the world.  
**Add:** only when a new signal genuinely cannot be expressed by any existing family.  
**Remove:** any claim that implies how a signal should be used, evaluated, or operationalised.  
**Never encode:** NULL handling, storage conventions, statistical behaviour, or analytical
performance.  
**Never prescribe:** rolling windows, lag structures, population filters, or modelling choices.

---

*Document version 3.2 — 2026-05-24 — added temporal_type field to signal membership reference*
