# Signal Redundancy Map, Sparsity Classification, and Spine Review

**Produced:** 2026-05-24
**Phase:** 2, Step 2 — Phase gate tasks (architecture-execution-plan.md)
**Gate decisions cited:** EDA_FINDINGS.md

---

## 1. Redundancy Map

Redundancy is assessed at the representation level, not at the raw spine level.
A signal is flagged redundant when gate decisions establish that it carries no independent
information beyond a signal already in the active candidate set.

| Redundant signal | Absorbed by | Relationship | Gate | Decision |
|---|---|---|---|---|
| xa | xgi | xa is a linear component of xgi (xgi = xg + xa); xa_roll* add nothing independent | G-EDA6-02 | Excluded as independent rolling-window candidate |
| xg (FWD) | xgi | partial_rho 0.93 at FWD; xgi dominates | G-EDA6-03 | Excluded at FWD |
| xg (MID) | xgi | partial_rho 0.74 at MID; xgi dominates | G-EDA6-03 | Excluded at MID |
| fdr_max | fdr_avg | rho 1.0 pooled across all GWs; no independent signal | G-EDA6-01 | Excluded as independent analytical signal |
| fdr_min | fdr_avg | rho 1.0 pooled across all GWs; no independent signal | G-EDA6-01 | Excluded as independent analytical signal |

**Notes:**
- `xg` at DEF and GK: structurally zero; blocked by position, not redundancy.
- `fdr_max`/`fdr_min` redundancy (rho 1.0) is driven by SGW rows where all three FDR
  values are identical. For DGW rows the values can differ, but the DGW share of the
  dataset is small and the pooled finding stands. These fields are retained in the spine
  as DGW structural metadata (see §3).
- `bonus` and `bps` are excluded for target leakage (G-EDA7-06), not redundancy.
  They are not listed here.

---

## 2. Sparsity Classification — Event Family Signals

Event signals are discrete occurrences that may be zero for most player-GW records.
Sparsity is classified by expected zero-rate and the behavioral consequence for rolling windows.

| Signal | Scope | Position | Sparsity class | Zero-rate basis | Behavioral consequence |
|---|---|---|---|---|---|
| goals_scored | Individual | MID, FWD | sparse | Right-tailed; most GW records are 0 | Rolling mean destroys burst structure; FORM-003 uninformative all positions |
| assists | Individual | MID, FWD, DEF | moderate | Less sparse than goals_scored; rho 0.49 MID informative | Rolling window viable pending EDA-8D gate |
| clean_sheets | Team | DEF, GK | sparse | Binary (0/1); team scope; half of matches result in ≥1 goal conceded | Team-scope annotation required; rolling mean viable for DEF/GK |
| goals_conceded | Team | DEF, GK | moderate | Count per game; non-zero most GWs for most teams | Team-scope annotation required; rolling window viable; DEF moderate_shift (G-EDA5-04) |
| saves | Individual | GK only | moderate (GK) | GK faces shots every game; zero-rate lower than goals_scored | Layer 1 pending EDA-8A; rolling window eligibility pending G-EDA8-02 |
| penalties_saved | Individual | GK only | **structurally-sparse** | Penalties faced per GK per season are few; most GKs face none in any given GW | Layer 1 ineligible pending sparsity gate G-EDA8-06; assumed structurally sparse |

**Notes on structurally sparse signals:**
A signal is structurally sparse when the event is rare enough that rolling mean representations
are analytically meaningless — the distribution is dominated by zeros and a rolling mean of
nearly all zeros adds no information. This mirrors the red_cards exclusion in EDA-2.

`penalties_saved` is assumed structurally sparse pending the formal EDA-8C sparsity gate
(G-EDA8-06). The profile is stubbed; no representation decision is made until the gate runs.

---

## 3. Spine Review Against Redundancy Map

The spine (`SPINE_COLS` in `dal/curated/contracts.py`) contains the raw FPL API fields.
The review question is: for each fully-redundant signal, remove from spine or retain?

The boundary matters: the redundancy map operates at the **representation** level (rolling
windows, derived features, analytical signal candidates). The spine contains **raw source
data**. These are distinct concerns.

### 3.1 `xa` — retain

**Reason:** `xa` is a raw FPL API field. It is one of the two components of `xgi` (`xgi = xg + xa`).
Removing `xa` from the spine would break data lineage and prevent component-level attribution.
The G-EDA6-02 decision governs representations — specifically that `xa_roll3` and `xa_roll5`
are not eligible as independent candidates in lens studies or STATE. The raw `xa` field is
the source data, not a representation. It stays in the spine.

**Decision:** Retain in `SPINE_COLS`. No rolling window representations permitted (G-EDA6-02).

### 3.2 `fdr_max` and `fdr_min` — retain with annotation

**Reason:** These are genuine DGW structural metadata. For a DGW row:
- `fdr_min` is the difficulty of the easier fixture
- `fdr_max` is the difficulty of the harder fixture
- The range `fdr_max - fdr_min` encodes fixture-difficulty spread within the week

The rho 1.0 finding (G-EDA6-01) is dominated by SGW rows where all three FDR values
are identical by construction. For DGW-specific analysis, `fdr_min` and `fdr_max` are
not redundant.

These fields are retained in the spine as structural metadata. They are not eligible as
independent analytical signals in any representation or lens (G-EDA6-01 stands for that use).

**Operational note:** `fdr_min` appears in `_REQUIRED_SPINE_COLS` in
`intelligence/_base.py` but is not consumed by any current scoring or captain computation.
This is an over-declaration. It should be removed from `_REQUIRED_SPINE_COLS` in a future
Phase 4/5 cleanup — it is not needed by any intelligence function. This is not a correctness
issue (the column exists in the spine), but the contract overstates consumption.

**Decision:** Retain in `SPINE_COLS`. No analytical representation permitted (G-EDA6-01).
Remove `fdr_min` from `_REQUIRED_SPINE_COLS` in a Phase 4 cleanup pass (not urgent).

### 3.3 Summary

| Signal | Spine action | Rationale |
|---|---|---|
| xa | Retain | Raw FPL source field; xgi component; redundancy governs representations not raw data |
| fdr_max | Retain | DGW structural metadata; not an independent analytical signal |
| fdr_min | Retain | DGW structural metadata; remove from _REQUIRED_SPINE_COLS in Phase 4 |

---

*Signal Redundancy Map, Sparsity Classification, and Spine Review — 2026-05-24*
