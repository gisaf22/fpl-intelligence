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

---

## Amendment A — GW window and late-block expansion (ADR-010)

**Amendment date:** 2026-06-07  
**Governing decision:** ADR-010 (layered decision model + full-season review)  
**Sections amended:** §4 (population/GW window), §5 (late block)

### §4 amendment

Original: "`minutes >= 60` at GW N (G-EDA1-04). GW 3-33 (G-EDA1-02, G-EDA1-03)."

**Amended:** Study window is GW 3 to **GW 38** inclusive (full season; holdout folded in).
ADR-010 lifted the original GW 34-38 holdout exclusion.
The study implementation uses `GW_MAX = 38`.

### §5 amendment

Original late block: "GW 27-33"

**Amended:** Late block is **GW 27-38** (11 GWs).
Implementation: `"late": (27, 38)` in `GW_BLOCKS`.

---

## Amendment B — Gate 2 quintile cut adopts characterization's ordinal binning

**Amendment date:** 2026-08-16  
**Governing decision:** `research/registry/CHARACTERIZE_DESIGN.md` §2  
**Sections amended:** §9 (quintile bin decision relevance), and by extension §7's Gate 2

### §9 amendment

Original: quintile stratification cut every signal, including `fdr_avg`, with
`pd.qcut(series.rank(method="first"), 5)` in `research/kernels/hypothesis/stratification.py`.

**Amended:** Gate 2's quintile cut for `fdr_avg` now consumes the ordinal bin scheme
characterization selects for FDR signals — `research/kernels/descriptive/binning.py::
select_bucketing_scheme`, which returns `("ordinal", (FDR_ORDINAL_BINS, FDR_ORDINAL_LABELS))`
for any signal in `FDR_SIGNALS`, per `CHARACTERIZE_DESIGN.md` §2. The rank-tie-break cut
manufactured quintile boundaries inside `fdr_avg`'s heavily tied values (e.g. 59% of DEF rows
sit at exactly 3.0); the ordinal scheme instead bins on the rating's own natural scale, one bin
per FDR value. `research/kernels/hypothesis/stratification.py::quintile_stratification` now
calls `select_bucketing_scheme` for every signal it evaluates and only proceeds with a quintile
split when the returned scheme is `ordinal` or a 5-way `quantile` cut; other schemes are not a
five-group quintile split and are reported as not decision-relevance-testable rather than forced
into one. `was_home` and `fixture_count` (this lens's other two signals) are both binary on the
mart (`nunique() == 2`) and route to the `discrete` scheme, so Gate 2 now returns "not
decision-relevant" for them (no quintile) rather than a manufactured 5-way split. This does not
change either signal's `decision_class`: both were already `uninformative`, and their
pre-amendment Q5-Q1 gaps (was_home DEF −0.03, MID +0.12; fixture_count DEF −0.60, MID −0.34) sit
far below the 1.0 threshold regardless of binning.

This changes Gate 2's outcome for `fdr_avg` at MID, FWD, and GK (recovers a monotonic profile);
DEF is not rescued (CHARACTERIZE_DESIGN.md §2 limit 1 — it still reverses at bins 1→2). See
CHARACTERIZE_DESIGN.md §2 and §3 for the full accounting, including the three named limits.
