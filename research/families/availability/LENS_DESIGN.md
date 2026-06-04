# LENS_DESIGN.md — LENS-AVAIL

**Status:** LOCKED  
**Locked:** 2026-05-22  
**Governed by:** `signals/evaluation/EVAL_DESIGN.md` v1.5  
**Registry:** `signals/registry/SIGNAL_REGISTRY.md` v1.3 (AVAIL-001 through AVAIL-003)  
**EDA basis:** `research/findings/FINDINGS.md`

---

## 1. Study question

Does rolling playing time consistency at GW N reliably predict whether a player will earn
a full appearance (≥ 60 minutes) at GW N+1? And does this availability consistency
associate independently with FPL returns beyond what form signals already capture?

The 60-minute threshold is the FPL scoring rule at which a player earns an additional
appearance point. It is not a generic participation indicator — it defines the population
of players in a "started and completed" state whose return distributions are stable enough
to characterise. Players below this threshold (partial minutes, late substitutions) are
in an erratic return state not relevant to captaincy or transfer decisions.

This lens characterises availability signals as **forward-looking full-appearance
predictors**, not generic participation flags. The output informs SYNTH-01: which players
are reliably expected to earn a full appearance next GW, and which carry rotation or
injury risk that would degrade form signal reliability.

---

## 2. Signal set

| Signal ID | Signal | EDA basis |
|---|---|---|
| AVAIL-001 | minutes_roll3 | Raw minutes blocked as form signal (G-EDA2-02); AVAIL is primary venue (G-EDA7-05). FORM-006 found uninformative for returns — this lens tests a different question: availability prediction. |
| AVAIL-002 | minutes_roll5 | Same basis as AVAIL-001; tests 5-GW horizon. |
| AVAIL-003 | minutes_roll8 | Same basis; tests longest available horizon (8-GW). May capture structural playing time over form-driven rotation. |

**Excluded:**
- `minutes_trend` (categorical string: stable/rising/falling) — requires ordinal encoding assumption not supported by a priori rationale; excluded.
- `starts` (raw binary/count) — not in DAL state layer as a rolling signal; excluded pending DAL enhancement.
- `starts_roll*` — not available in DAL state layer.

---

## 3. Target variable

**Primary target:** `played_next_gw` (binary: `minutes_next_gw >= 60`, else 0)

The threshold is the FPL appearance bonus rule. The question is not "will they be on
the pitch?" but "will they earn a full appearance again?" — which is the decision-relevant
question for transfers and captaincy. A player who plays 45 minutes off the bench is not
a valid captaincy candidate and is correctly classified as 0 here.

Spearman is appropriate for a binary target — it ranks by outcome value (0 or 1).

**Secondary target:** `total_points_next_gw` (lag-1, same as LENS-FORM)

The secondary analysis confirms whether availability consistency adds incremental return
prediction beyond LENS-FORM findings. Results from the secondary analysis are descriptive
only — the primary classification is based on the binary target.

**Base rates (primary population, GW 3-33):**

| Position | P(played_next_gw = 1) |
|---|---|
| GKP | 0.925 |
| DEF | 0.799 |
| MID | 0.762 |
| FWD | 0.748 |

GKP has a near-constant target (92.5%). GKP results are expected to be uninformative —
included to confirm, not expected to classify as informative.

---

## 4. Population

**Qualified-start threshold:** `minutes >= 60` at GW N (G-EDA1-04).

This is the FPL appearance bonus threshold, not a generic participation filter. The
population is players who earned a full appearance this GW. The target (`played_next_gw`)
then asks whether they earn a full appearance again at GW N+1.

**DGW rows:** Included with `is_dgw` flag. Reported with and without DGW rows (G-EDA1-05).

---

## 5. GW window

**Study window:** GW 3 to GW 33 inclusive.

- AVAIL-001 (minutes_roll3): GW 3+ (G-EDA0-02)
- AVAIL-002 (minutes_roll5): GW 6+
- AVAIL-003 (minutes_roll8): GW 9+

---

## 6. GW block structure

Same three-block structure as LENS-FORM (G-EDA5-01):

| Block | GW range |
|---|---|
| early | GW 3-12 |
| mid | GW 13-26 |
| late | GW 27-33 |

AVAIL-002 effective early block starts at GW 6 (7 GWs). AVAIL-003 effective early block
starts at GW 9 (4 GWs) — late block analysis for AVAIL-003 will have small sample sizes.

---

## 7. Correlation method

**Method:** Spearman rank correlation with bootstrap 95% CI (G-EDA1-01).

**Parameters:** N=2000, seed=42, CI=95% (consistent with LENS-FORM).

**Resampling unit:** (player, GW) observation pairs.

---

## 8. Classification logic

Same decision sequence as LENS-FORM (EVAL_DESIGN.md §4.2), with one threshold adjustment
for the binary primary target:

**Quintile gap threshold for `played_next_gw`:** Q5 − Q1 ≥ **0.10** (10 percentage points).

Rationale: the target range is [0, 1]. A 10 percentage point gap between top and bottom
quintile represents meaningful separation for an availability prediction outcome. The
LENS-FORM threshold of 1.0 was calibrated for total_points (range ~0-20) and does not
translate directly to a binary outcome.

| Condition | Classification |
|---|---|
| CI excludes zero AND Q5-Q1 ≥ 0.10 AND monotonic AND ≥2/3 blocks pass | `informative` |
| CI crosses zero | `uninformative` |
| CI excludes zero in aggregate but <2/3 blocks pass | `unstable` |
| CI excludes zero but only specific positions | `conditional` |

---

## 9. Limitations

- Single-season scope: 2025-26 only.
- GKP near-constant target (92.5%): informative classification for GKP is structurally unlikely.
- AVAIL-003 (8-GW): early block reduced to GW 9-12 (4 GWs) — small block sample.
- `played_next_gw` uses the FPL appearance bonus threshold (minutes ≥ 60), not a generic
  participation flag. A player who starts and is subbed off at 55 minutes is classified
  as 0. This is correct: they did not earn the appearance bonus and are not a valid
  captaincy or full-return candidate.
- This lens does not characterise injury or suspension risk — only recent full-appearance
  consistency as a predictor of future full-appearance probability.

---

## 10. Design lock declaration

Locked 2026-05-22. No changes after first correlation run.
