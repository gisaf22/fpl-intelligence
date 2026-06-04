# EDA-8 Design — Gap Study
## Layer 1: saves GK, xgc, penalties_saved | Layer 3: assists rolling windows

**Status:** DESIGN — locked before code runs
**Version:** 1.0
**Produced:** 2026-05-24
**Framework version:** EVAL_DESIGN.md v2.2
**Gate:** This document must exist and be reviewed before any notebook is opened.

---

## 1. Purpose

EDA-8 closes the four open-study gaps identified after EDA-0 through EDA-7 were scoped
against the updated three-layer pipeline framework. It does not reopen settled questions.

Gap sources:
- `research/findings/COVERAGE_MATRIX.md` — partial signals with Layer 1 or Layer 3 gaps
- `research/findings/FINDINGS.md` G-EDA6-06 — saves GK deferred pending Layer 1

Every gate decision produced here uses G-EDA8-NN format and is recorded in EDA_FINDINGS.md
before any downstream work depends on it.

---

## 2. Framework layer mapping

| Sub-study | Signal | Layer | Dependency |
|---|---|---|---|
| EDA-8A | saves (GK) | Layer 1 — raw association | None; GK assessable per EDA-2 |
| EDA-8B | xgc | Layer 1 + Layer 2 | None; no prior layer 1 exists |
| EDA-8C | penalties_saved | Layer 1 — sparsity characterisation | None |
| EDA-8D | assists_roll3, assists_roll5 | Layer 3 — representation validation | G-EDA3-04, G-EDA5-04 satisfied |

EDA-8A, EDA-8B, EDA-8C, and EDA-8D have no inter-dependencies. All may run in parallel.

---

## 3. Inherited population and method

All sub-studies inherit from EVAL_DESIGN.md v2.2 unless the sub-study specifies an override:

- **Method:** Spearman rank correlation throughout (G-EDA1-01)
- **GW bounds:** GW 6-33 inclusive; GW 34 excluded (G-EDA1-02)
- **Rolling warmup lower bound:** GW 6 for raw signals; GW 8 minimum for roll3 variants;
  GW 10 minimum for roll5 variants (G-EDA0-02, G-EDA1-03)
- **Population:** minutes >= 60 per player-GW record (G-EDA1-04)
- **DGW treatment:** flag or exclude; do not pool with SGW without accounting for fixture
  multiplier (G-EDA1-05)
- **Confidence intervals:** bootstrap 95% CI per signal-position pair
- **Temporal stability:** three-block structure — early (GW 6-15), mid (GW 16-25),
  late (GW 26-33); this is the LENS-FORM standard, not the two-block EDA-5 structure
- **Supplementary outputs (per EVAL_DESIGN.md v2.2 §4.2):** quintile EV lift
  (E[total_points | quintile] ± SD for Q1-Q5) and haul identification rate (fraction of
  top-10%-within-position outcomes in top signal quintile vs 20% base rate) required for
  all Layer 3 sub-studies

---

## 4. Sub-study specifications

---

### EDA-8A — saves (GK): Layer 1 raw association

**Question:** Does saves at GK associate with total_points at GK? Is the association
stable across GW blocks?

**Scope:** GK position only. DEF, MID, FWD structurally blocked (G-EDA2-03).

**Background:** saves GK showed partial_rho 0.88 with ict_index GK in EDA-6. ict_index
is excluded as a composite (G-EDA7-06), so this redundancy observation could not be formally
gated (G-EDA6-06). No rho_pooled for saves GK vs total_points has been established.

#### Step 1 — Sparsity pre-check

Before computing rho, characterise the distribution of saves at GK:

- Zero-rate: fraction of GK player-GW records where saves = 0
- Distribution: mean, median, 90th percentile, max, total occurrences across the season
- Flag if zero-rate > 80% — note concentration risk before proceeding

The pre-check does not gate the study. It contextualises the correlation findings.

#### Step 2 — Raw association

- rho_pooled: Spearman correlation between saves (lag-1) and total_points at GK
- 95% bootstrap CI
- Three-block temporal stability
- Association class: continuous_monotonic / weak_association / upper_tail_concentrated /
  unassessable

#### Step 3 — Active set redundancy check (conditional on informative)

If G-EDA8-01 = informative: assess the relationship between saves GK and xgc GK (if
EDA-8B also produces an informative finding at GK). Report pairwise rho and partial rho
between saves GK and xgc GK. This determines whether both can be registered as independent
candidates for any GK lens study.

**Required outputs:**
- saves GK: zero-rate, distribution summary
- rho_pooled, 95% CI, three-block stability, association class
- If informative and xgc GK also informative: pairwise and partial rho (saves, xgc)

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA8-01 | saves GK: `informative` (CI excludes zero) / `uninformative` |
| G-EDA8-02 | saves GK Layer 3 eligibility: `eligible` (informative, sparsity acceptable) / `ineligible` (uninformative or sparsity precludes rolling window) |

---

### EDA-8B — xgc: Layer 1 raw association + Layer 2 redundancy

**Question:** Does xgc associate with total_points at DEF and GK? If informative, is it
independent of goals_conceded and clean_sheets?

**Scope:** DEF and GK. xgc is team-scope — the same value is attributed to all eligible
players on the team in a given GW. MID and FWD are out of scope; xgc reflects defensive
process and has no structural basis for association with attacking returns.

**Background:** xgc appears in the EDA dataset (29 signals) but produced no gate decisions
in EDA-0 through EDA-7. EDA-7 §7.4 routed it to "LENS-FIXTURE-GW territory" as a topic
routing decision, not an EDA finding. No Layer 1 rho_pooled exists.

**Nature of signal:** xgc is a Process signal (team-scope, estimate temporal type) —
an expected goals conceded value reflecting the quality of chances allowed by the team,
measured from match process data. goals_conceded is the observed count outcome; clean_sheets
is the binary observed outcome. These are distinct in nature (pre-match-derivable estimate
vs post-match observation) but may carry overlapping information in practice.

#### Step 1 — Raw association (Layer 1)

- rho_pooled: Spearman correlation between xgc (lag-1) and total_points at DEF and GK
- 95% bootstrap CI
- Three-block temporal stability
- Association class

#### Step 2 — Redundancy check (Layer 2, conditional on Layer 1 informative)

If xgc passes Layer 1 at DEF or GK, assess whether it adds information beyond the
observed defensive outcome signals already in the LENS-FIXTURE-GW candidate set:

- Partial rho: xgc controlling for goals_conceded (lag-1)
- Partial rho: xgc controlling for clean_sheets (lag-1)
- If both partial rhos are low (< 0.30), xgc is absorbed by observed outcomes and
  adds limited independent information

**Required outputs:**
- rho_pooled per position (DEF, GK), 95% CI, three-block stability, association class
- If informative: partial_rho vs goals_conceded per position; partial_rho vs clean_sheets
  per position

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA8-03 | xgc DEF: `informative` / `uninformative` |
| G-EDA8-04 | xgc GK: `informative` / `uninformative` |
| G-EDA8-05 | xgc Layer 2 (if informative at any position): `independent` of goals_conceded and clean_sheets / `redundant` |

---

### EDA-8C — penalties_saved: Layer 1 sparsity characterisation

**Question:** Is penalties_saved too sparse for any representation to be analytically
meaningful?

**Scope:** GK position only. Structurally zero for all outfield players.

**Rationale:** EDA-2 blocked red_cards across all positions as "event too rare to form a
usable distribution." penalties_saved has an analogous structural concern — penalties faced
per GK per season are few, most GKs face none in a given GW, and many face none across the
full season. The distribution must be characterised before a correlation study is attempted.

This sub-study is a sparsity gate, not a full Layer 1 study. The output determines whether
Layer 1 is even viable — it does not produce rho_pooled.

#### Sparsity characterisation

- Total occurrences of penalties_saved > 0 across all GK player-GW records in the study window
- Count of distinct GKs with at least one penalties_saved across the season
- Zero-rate: fraction of GK player-GW records where penalties_saved = 0
- Distribution: mean, median, 90th percentile, max

#### Decision criteria

| Zero-rate | Total occurrences | Decision |
|---|---|---|
| > 95% | < 30 across season | Structurally sparse — Layer 1 ineligible |
| 80-95% | ≥ 30 | Assessable with caution — correlation reflects zero vs non-zero discrimination; note in gate |
| < 80% | — | Assessable — proceed to full Layer 1 study (design separately) |

**Required outputs:**
- Zero-rate, total occurrence count, distinct GK count, distribution summary
- Decision: assessable / assessable with caution / structurally sparse

**Gate decision:**

| ID | Decision |
|---|---|
| G-EDA8-06 | penalties_saved: `assessable` / `assessable-with-caution` / `structurally-sparse` (Layer 1 ineligible) |

---

### EDA-8D — assists rolling windows: Layer 3 representation validation

**Question:** Does assists_roll3 or assists_roll5 improve on raw assists and the naive
baseline at MID, FWD, and DEF?

**Layer 1 basis:** G-EDA3-04 (assists MID rho 0.49 stable; FWD rho 0.36 stable;
DEF rho 0.27 moderate_shift). Layer 1 is fully satisfied. Layer 3 may proceed.

**Layer 2 basis:** G-EDA6-04 (goals_scored and assists are structurally independent).
No redundancy exclusion applies to assists.

**Scope:** MID, FWD, DEF. GK assists blocked (G-EDA2-03).

**DEF caveat (G-EDA5-04):** assists DEF shows moderate_shift — gap 5.21 early vs 11.39
late season. Block-level rho must be reported separately for DEF. An aggregate result that
is driven by the late-season block only is flagged as conditionally informative, not
practically meaningful.

#### Signals evaluated

| Signal | Description | GW lower bound |
|---|---|---|
| assists (lag-1) | Raw assists, 1-GW lag | GW 6 |
| assists_roll3 | 3-GW rolling mean, lag-1 shifted | GW 8 |
| assists_roll5 | 5-GW rolling mean, lag-1 shifted | GW 10 |
| total_points (lag-1) | Naive baseline per G-EDA7-02 | GW 6 |

#### Required outputs per signal per position

- rho_pooled, 95% bootstrap CI
- Three-block temporal stability
- Quintile EV lift: E[total_points | quintile] ± SD for Q1-Q5
- Haul identification rate: fraction of top-10%-within-position outcomes in top quintile
  vs 20% base rate
- Comparison table: assists_roll3 vs assists (lag-1) vs naive baseline per position

#### Improvement criteria

A rolling window variant is considered to improve on the raw signal if:
1. rho_pooled is higher and CI does not overlap with raw assists CI, OR
2. Q5-Q1 EV gap is materially larger than raw assists Q5-Q1 gap
3. Temporal stability is no worse than raw assists

A rolling window variant is preferred over the raw signal only if it also clears the
naive baseline (total_points lag-1) on the same criteria.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA8-07 | assists_roll3 MID: `improves` on raw assists and naive baseline / `no improvement` |
| G-EDA8-08 | assists_roll3 FWD: `improves` on raw assists and naive baseline / `no improvement` |
| G-EDA8-09 | assists_roll3 DEF: `improves` / `no improvement` / `conditionally-informative` (late-season only) |
| G-EDA8-10 | assists preferred window: roll3 / roll5 / raw — per position based on rho and EV lift comparison |

---

## 5. Sequencing

```
EDA-8A ─┐
EDA-8B ─┼── independent; run in parallel ──── all findings → EDA_FINDINGS.md
EDA-8C ─┤
EDA-8D ─┘
```

After all sub-studies complete:
1. All G-EDA8-NN gate decisions recorded in EDA_FINDINGS.md
2. EDA_COVERAGE_MAP.md updated — partial signals reclassified per findings
3. EDA_COVERAGE_MAP.md partial count corrected for any newly covered signals
4. Behavior profiles written for newly covered signals (Phase 2 Step 2)

If EDA-8A or EDA-8B produce informative Layer 1 results, a separate Layer 3 lens study
must be designed before rolling window variants of saves or xgc are evaluated. That design
is out of scope for EDA-8 — it is a consequence of EDA-8 findings, not part of this study.

---

## 6. What this study cannot answer

- Whether assists_roll3/roll5 add information in a multi-signal synthesis context — SYNTH-01 scope
- Whether saves GK rolling window variants improve on raw saves — contingent on G-EDA8-02
  = eligible; a separate Layer 3 study must be designed if Layer 1 passes
- Whether xgc rolling window variants improve on raw xgc — same contingency as saves GK
- Whether any of these signals hold across 2026-27 — 2025-26 data only
- Whether penalties_saved carries information at positional sub-population level (e.g.,
  penalty specialists) — the population is too small to resolve

---

## 7. Gate decision index

| ID | Sub-study | Question |
|---|---|---|
| G-EDA8-01 | EDA-8A | saves GK: informative / uninformative |
| G-EDA8-02 | EDA-8A | saves GK: Layer 3 eligible / ineligible |
| G-EDA8-03 | EDA-8B | xgc DEF: informative / uninformative |
| G-EDA8-04 | EDA-8B | xgc GK: informative / uninformative |
| G-EDA8-05 | EDA-8B | xgc: independent / redundant vs goals_conceded and clean_sheets |
| G-EDA8-06 | EDA-8C | penalties_saved: assessable / assessable-with-caution / structurally-sparse |
| G-EDA8-07 | EDA-8D | assists_roll3 MID: improves / no improvement |
| G-EDA8-08 | EDA-8D | assists_roll3 FWD: improves / no improvement |
| G-EDA8-09 | EDA-8D | assists_roll3 DEF: improves / no improvement / conditionally-informative |
| G-EDA8-10 | EDA-8D | assists preferred window per position: roll3 / roll5 / raw |

---

*EDA-8 Design v1.0 — 2026-05-24 — locked before code runs*
