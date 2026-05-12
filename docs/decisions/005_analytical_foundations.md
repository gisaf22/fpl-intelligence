# Decision 005 — EDA-1 Analytical Foundations — Gate Decisions

**Status:** LOCKED  
**Source:** EDA-1 (target distribution analysis), GW6–33 primary population (minutes >= 60)  
**Applies to:** All lens studies, all registry builds, all signal characterisation work

---

## Decisions

### Correlation method: Spearman

**Decision:** Use Spearman rank correlation throughout.  
**Evidence:** total_points distribution is right-skewed across all positions (overall skew=1.58,
Kurt=2.80). Spearman is justified at STRONG_EVIDENCE level. Pearson is not appropriate.  
**Applies to:** rho_pooled in the registry; all lens study correlation calculations.

### GW upper bound: cap at GW 33

**Decision:** All analysis uses GW 6–33 inclusive. GW 34 is excluded.  
**Evidence:** GW 34 had only 14 of 20 teams with a fixture — a reduced slate that introduces
unequal exposure across player-GW records. GW 31 also had 16 teams (legitimate reduced slate)
but is included because the reduction is not systematic.  
**Applies to:** `GW_MAX = 33` in parity test; `data_cutoff_gw` in prepared dataset builder;
all lens study GW windows.

### DGW treatment: FLAG

**Decision:** Double gameweek rows must be explicitly flagged and treated per lens study.
Do not pool DGW and SGW records without accounting for the fixture multiplier.  
**Evidence:** DGW raw mean = 6.50 vs SGW 3.83 (+70%). Normalised per-fixture: DGW = 3.25 vs
SGW = 3.83 (−0.57 when normalised). The minutes >= 60 filter is blunter for DGW rows because
minutes may span two fixtures. DGW sample size = 103 — small; interpret with caution.  
**Applies to:** Any lens study that pools all records without a DGW indicator. The `fixture_count`
signal in the registry partially captures this but does not replace explicit treatment.

### Analytical population: minutes >= 60

**Decision:** Primary population is player-GW records with minutes >= 60.  
**Evidence:** BGW rows are absent by construction (null minutes excluded naturally by >= 60).
Zero mass is low and consistent with this filter. GK and DEF elevated <=1pt mass is expected
(clean-sheet dependence), not a filter artefact.  
**Applies to:** `MINUTES_THRESHOLD = 60` in `dal/prepared/analytical_dataset.py`;
all registry build prepared datasets.

### Timing signal claim: permitted for all positions

**Decision:** Within-player variance dominates (89.9–93.4%) across all positions. Timing
signals are legitimately findable for GK, DEF, MID, and FWD.  
**Evidence:**
  - GK:  between=6.6%,  within=93.4%  (n=36 players)
  - DEF: between=10.1%, within=89.9%  (n=163 players)
  - MID: between=9.5%,  within=90.5%  (n=192 players)
  - FWD: between=9.7%,  within=90.3%  (n=49 players)

Between-player quality effects are small relative to event-level variation. This justifies
searching for timing signals at all positions without restricting to high-quality players.

---

## Target distribution reference statistics (GW6–33, minutes >= 60)

Overall: N=5,879 · Mean=3.87 · Median=3.00 · Std=3.22 · Skew=1.58 · P90=8.0 · P99=15.0

By position:
  GK:  N=567   Mean=3.39 Median=2.00 Std=2.75 P90=7.0  P99=11.0 Skew=1.35
  DEF: N=2,269 Mean=3.75 Median=3.00 Std=3.33 P90=8.0  P99=15.0 Skew=1.38
  MID: N=2,470 Mean=4.03 Median=3.00 Std=3.13 P90=9.0  P99=15.0 Skew=1.81
  FWD: N=573   Mean=4.14 Median=2.00 Std=3.49 P90=9.0  P99=16.0 Skew=1.58

Hauls (>15 pts): rare — GK=0.2%, DEF=0.7%, MID=0.7%, FWD=1.2%
