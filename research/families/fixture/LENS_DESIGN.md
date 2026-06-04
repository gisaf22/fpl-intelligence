# LENS_DESIGN.md — LENS-FIXTURE-GW

**Status:** LOCKED  
**Locked:** 2026-05-22  
**Governed by:** `signals/evaluation/EVAL_DESIGN.md` v1.5  
**Registry:** `signals/registry/SIGNAL_REGISTRY.md` v1.3 (FIXTURE-001 through FIXTURE-003)  
**EDA basis:** `research/findings/FINDINGS.md`

---

## 1. Study question

Do single-gameweek fixture context signals — known before a gameweek begins — reliably
associate with FPL returns in that gameweek? And do they provide decision-relevant
discrimination across the player population?

---

## 2. Signal set and lag

| Signal ID | Signal | Lag | EDA basis |
|---|---|---|---|
| FIXTURE-001 | fdr_avg | same-GW | rho −0.10 to −0.20, fixture_difficulty, caveated. Representative of fdr_avg/max/min — all three perfectly redundant (G-EDA6-01). Negative association: harder fixture = fewer expected points. |
| FIXTURE-002 | was_home | same-GW | rho ~0.04-0.07, match_environment, caveated. Binary. |
| FIXTURE-003 | fixture_count | same-GW | rho ~0.09-0.15, schedule_volume, caveated. DEF/MID only — FWD and GKP blocked in EDA (G-EDA2-01). |

**Lag rationale:** Fixture signals describe GW N context. They are known before GW N begins
(fixture lists published before deadlines). Target is `total_points` at GW N — same-GW
alignment. This is distinct from form signals (lag-1). Both are valid pre-decision inputs:
form signals predict forward from past; fixture signals characterise the upcoming context.

**Excluded:** `fdr_max`, `fdr_min` — perfectly redundant with fdr_avg (G-EDA6-01).
`clean_sheets`, `goals_conceded`, `xgc` — these are GW N outcomes, not pre-GW inputs.

---

## 3. Target variable

**Target:** `total_points` at GW N (same-GW). No shift needed — the fixture signal and
the return are measured in the same gameweek. The fixture is known before kickoff.

---

## 4. Population

`minutes >= 60` at GW N (G-EDA1-04). GW 3-33 (G-EDA1-02, G-EDA1-03).

For same-GW analysis, the population filter applies to the same GW as the target.
Players who did not play (minutes < 60) score 0-2 points on average and cannot be
selected anyway — filtering to qualified starters is appropriate.

DGW rows: included with `is_dgw` flag (G-EDA1-05). DGW sensitivity reported separately.
`fixture_count` is particularly relevant for DGW rows — it is 2 for DGW, 1 for SGW.

FIXTURE-003 positions: DEF, MID only (FWD and GKP blocked in EDA — G-EDA2-01).

---

## 5. GW block structure

Same three-block structure: early (GW 3-12), mid (GW 13-26), late (GW 27-33).

---

## 6. Correlation method

Spearman + bootstrap 95% CI. N=2000, seed=42.

Note: `fdr_avg` is expected to show negative rho (harder fixture = fewer points).
CI gate applies to both directions: `ci_upper < 0` means CI excludes zero on the
negative side. The classification logic handles both positive and negative rho correctly.

---

## 7. Classification logic

Same as LENS-FORM: CI gate → decision relevance (Q5-Q1 ≥ 1.0, monotonic) → block
stability (≥2/3 blocks).

For `fdr_avg` with negative rho, decision relevance is assessed as: Q1 mean > Q5 mean
(low FDR = easy fixture = more points, so Q1 is highest, Q5 is lowest). The gap is
Q1 − Q5 ≥ 1.0 and the ordering is monotonically decreasing. The quintile analysis
handles this by checking is_monotonic in either direction.

---

## 8. Limitations

- Same-GW target: fixture signals are contextual, not predictive in the same sense as
  form signals. They describe match difficulty, not player quality. SYNTH-01 will test
  whether fixture context conditions form signal value.
- fdr_avg temporal stability: insufficient_data for most positions in EDA (only MID is
  stable in EDA-03). Block analysis will reveal whether FDR discrimination is consistent.
- fixture_count DGW effect: DGW rows have fixture_count=2. If DGW rows are included, the
  fixture_count correlation reflects the DGW bonus, not fixture difficulty per se.
- Single-season scope: 2025-26 only.

---

## 9. Design lock declaration

Locked 2026-05-22. No changes after first correlation run.
