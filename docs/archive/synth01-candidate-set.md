# SYNTH-01 Candidate Set

**Status:** FROZEN — Phase 4 complete  
**Issued:** 2026-05-27  
**Authority:** Operational Convergence Plan Phase 4 (§4.1, §4.2)  
**Source:** `signals/evaluation/evaluation_metadata.yaml` — all entries where `lifecycle_state=candidate` AND `downstream_status` in `["eligible", "caveated"]`  
**Frozen registry:** `signals/registry/synth01_candidates.yaml`

---

## Purpose

This document declares the complete, frozen synthesis candidate set that Phase 5 (SYNTH-01 execution) will evaluate. No candidates may be added after Phase 4 completes without restarting Phase 4. Additions require a governance decision recorded here and in the frozen registry.

The candidate set was constructed by mechanical extraction from `evaluation_metadata.yaml`. Every entry has a lens gate provenance. No editorial additions are permitted.

---

## Candidate Set — 14 Entries

Sorted by position, then signal, then window. Column abbreviations: `rho` = rho_pooled, `ci` = bootstrap 95% CI, `stab` = block_stability_count / 3, `status` = downstream_status.

| Signal | Position | Lens | Target | rho | ci_lower | ci_upper | stab | status | Source ID |
|--------|----------|------|--------|-----|----------|----------|------|--------|-----------|
| `xgi_roll3` | DEF | FORM | total_points | 0.123 | 0.084 | 0.161 | 3/3 | eligible | FORM-001 |
| `xgi_roll5` | DEF | FORM | total_points | 0.113 | 0.071 | 0.155 | 3/3 | eligible | FORM-002 |
| `minutes_roll8` | DEF | AVAIL | played_next_gw | 0.219 | 0.174 | 0.261 | 3/3 | eligible | AVAIL-003 |
| `transfers_in` | DEF | MARKET | total_points | 0.187 | 0.146 | 0.226 | 3/3 | eligible | MARKET-001 |
| `ownership_count` | DEF | MARKET | total_points | 0.156 | 0.117 | 0.196 | 3/3 | eligible | MARKET-003 |
| `purchase_price` | DEF | MARKET | total_points | 0.121 | 0.082 | 0.162 | 2/3 | **caveated** | MARKET-004 |
| `xgi_roll3` | MID | FORM | total_points | 0.144 | 0.107 | 0.182 | 3/3 | **caveated** | FORM-001 |
| `xgi_roll5` | MID | FORM | total_points | 0.157 | 0.118 | 0.197 | 3/3 | **caveated** | FORM-002 |
| `minutes_roll3` | MID | AVAIL | played_next_gw | 0.232 | 0.198 | 0.269 | 3/3 | eligible | AVAIL-001 |
| `minutes_roll5` | MID | AVAIL | played_next_gw | 0.227 | 0.190 | 0.265 | 3/3 | eligible | AVAIL-002 |
| `minutes_roll8` | MID | AVAIL | played_next_gw | 0.222 | 0.180 | 0.261 | 3/3 | eligible | AVAIL-003 |
| `transfers_in` | MID | MARKET | total_points | 0.190 | 0.153 | 0.230 | 3/3 | eligible | MARKET-001 |
| `ownership_count` | MID | MARKET | total_points | 0.168 | 0.130 | 0.205 | 3/3 | eligible | MARKET-003 |
| `purchase_price` | FWD | MARKET | total_points | 0.155 | 0.077 | 0.237 | 2/3 | **caveated** | MARKET-004 |

**Total: 14 signal-position pairs across 8 distinct signals.**

---

## Position Coverage Map

| Position | Candidate count | Synthesis-eligible | Note |
|----------|----------------|-------------------|------|
| DEF | 6 | Yes (≥ 2) | Composite synthesis in scope |
| MID | 7 | Yes (≥ 2) | Composite synthesis in scope |
| FWD | 1 | No | purchase_price only; single-signal qualified score, no composite |
| GK | 0 | No | No evaluation evidence from any lens; deferred — see §GK Scope Decision |

Minimum for composite synthesis: ≥ 2 candidates at the same position from at least one lens. FWD does not meet this minimum. GK has no candidates at all.

---

## Caveated Inclusion Rationale

Four entries carry `downstream_status=caveated`. Each requires explicit justification for inclusion over exclusion.

### xgi_roll3 MID — `caveated`

**Caveat:** Does not clear the naive baseline. points_roll5 MID rho = 0.158; xgi_roll3 MID rho = 0.144. Naive baseline marginally outperforms the candidate on pooled rho.

**Inclusion justification:** The naive baseline (points_roll5 MID) is itself excluded from SYNTH-01 on evaluation circularity grounds (G-EDA7-02 — lagged target). When the naive baseline is absent from the synthesis model, its clearance criterion becomes irrelevant — there is no circularity-free signal against which to benchmark it. xgi_roll3 MID passed all three gates independently (G1-PASS, G2-PASS, G3-PASS: 3/3 blocks). SYNTH-01 must test whether xgi_roll3 MID adds independent information in the absence of points_roll5.

**Failure condition:** If SYNTH-01 finds that xgi_roll3 MID contributes zero marginal information over a model without it, issue decision `EXCLUDED-INSUFFICIENT` at MID.

### xgi_roll5 MID — `caveated`

**Caveat:** Borderline below naive baseline. points_roll5 MID rho = 0.158; xgi_roll5 MID rho = 0.157. Difference is within CI noise (CI width ~0.079).

**Inclusion justification:** Same reasoning as xgi_roll3 MID. Passed all three gates (G1, G2, G3: 3/3 blocks). The 1-decimal-place gap to the naive baseline is indistinguishable given bootstrap variance. The independence test in SYNTH-01 is the correct resolution mechanism, not pre-exclusion.

**Failure condition:** Same as xgi_roll3 MID. If either xgi window is found redundant with the other in SYNTH-01, one is excluded; they are not both automatically excluded.

### purchase_price DEF — `caveated`

**Caveat:** 2/3 temporal blocks (G3-WEAK). Passed Gate 1 and Gate 2, but temporal stability is borderline — not the full 3/3 criterion.

**Inclusion justification:** G3-WEAK does not constitute gate failure under the evaluation gate criteria. It is a caveat, not a rejection. The CI clearly excludes zero (0.082–0.162). The price-tier signal has a credible mechanism at DEF: higher-priced defenders are structural starters with lower rotation risk. SYNTH-01 must test partial correlation controlling for form signals — if price captures only form-correlated variation, it will be excluded on redundancy grounds.

**Failure condition:** If SYNTH-01 finds that purchase_price DEF has partial rho CI spanning zero after controlling for xgi and market signals, issue `EXCLUDED-INSUFFICIENT`.

### purchase_price FWD — `caveated`

**Caveat:** 2/3 temporal blocks (G3-WEAK). Sole FWD candidate — no composite synthesis possible at FWD.

**Inclusion justification:** Same temporal caveat as DEF. Retained in the frozen registry as a single-signal qualified score. The signal provides a quality-tier proxy at FWD (higher-priced forwards are primary playing options). FWD synthesis is not possible (1 candidate below minimum), but the signal itself is not rejected — it is excluded from composite synthesis while remaining eligible for use as a single-signal availability-weighted score in the intelligence layer.

**Action:** purchase_price FWD is not evaluated by SYNTH-01 composition analysis. It is declared as a qualified single signal with the MARKET-004 gate evidence as its sole provenance. Intelligence module consumption must acknowledge the G3-WEAK caveat.

---

## Redundancy Classification — EDA-06 Evidence

Pairwise Spearman rho values are sourced from `studies/eda/findings/eda_06_pairwise_rho.csv` (base signal correlations, pre-rolling).

### Within-Position Candidate Pairs — DEF

| Signal A | Signal B | Pairwise rho | Classification |
|----------|----------|-------------|----------------|
| `xgi` | `minutes` | 0.030 | Low — independent |
| `xgi` | `transfers_in` | 0.142 | Low — independent |
| `xgi` | `ownership_count` | 0.109 | Low — independent |
| `xgi` | `purchase_price` | 0.139 | Low — independent |
| `minutes` | `transfers_in` | 0.147 | Low — independent |
| `minutes` | `ownership_count` | 0.155 | Low — independent |
| `minutes` | `purchase_price` | 0.065 | Low — independent |
| `ownership_count` | `transfers_in` | **0.794** | **HIGH REDUNDANCY — composition decision required** |
| `ownership_count` | `purchase_price` | 0.479 | Moderate — monitor |
| `purchase_price` | `transfers_in` | 0.398 | Moderate — monitor |

### Within-Position Candidate Pairs — MID

| Signal A | Signal B | Pairwise rho | Classification |
|----------|----------|-------------|----------------|
| `xgi` | `minutes` | 0.156 | Low — independent |
| `xgi` | `transfers_in` | 0.322 | Moderate — monitor |
| `xgi` | `ownership_count` | 0.334 | Moderate — monitor |
| `minutes` | `transfers_in` | 0.192 | Low — independent |
| `minutes` | `ownership_count` | 0.191 | Low — independent |
| `ownership_count` | `transfers_in` | **0.831** | **HIGH REDUNDANCY — composition decision required** |

### High-Redundancy Resolution Protocol

Both flagged pairs (`ownership_count × transfers_in` at DEF and MID) exceed the 0.70 threshold. The pre-Phase-5 governance decision is:

**Retain both signals as candidates.** SYNTH-01 (Phase 5) will compute marginal gain of adding each signal to a model containing the other. Resolution criteria:
- If `marginal_gain(ownership_count | transfers_in) < 0.02`: classify as `SUBSTITUTE`; retain transfers_in (higher rho at both positions: DEF 0.187 vs 0.156; MID 0.190 vs 0.168); exclude ownership_count with decision `EXCLUDED-REDUNDANT`.
- If `marginal_gain ≥ 0.02` in either direction: classify as `COMPLEMENTARY`; retain both.
- The tiebreak rule (retain higher-rho signal) applies only if marginal gain is symmetric (both < 0.02 in both directions).

**Phase 5 may not proceed without resolving this pair before finalizing composition weights.**

### Within-Window-Family Redundancy

Three signal groups contain multiple rolling windows of the same base signal. EDA-06 pairwise rho covers base signals only; inter-window pairwise correlations are not directly documented but are structurally expected to be high due to window overlap.

| Family | Affected candidates | Expected redundancy | Resolution |
|--------|--------------------|--------------------|------------|
| `xgi` windows | xgi_roll3 DEF, xgi_roll5 DEF; xgi_roll3 MID, xgi_roll5 MID | High — overlapping 3/5 GW windows share 3 GWs of data | SYNTH-01 marginal gain test per position |
| `minutes` windows | minutes_roll3/5/8 MID | High — three nested windows of the same series | SYNTH-01 marginal gain; expect that the window with highest partial rho dominates |
| `minutes` single | minutes_roll8 DEF only | Not applicable — no within-family pair at DEF | n/a |

For xgi and minutes families, SYNTH-01 is expected to find that one window dominates at each position. Retention of both windows in the frozen registry does not pre-commit to retaining both post-synthesis.

---

## Forward Constraints for Phase 5

1. The 14 candidates above are the only inputs to Phase 5 composition analysis. No signal absent from this table may be introduced into any SYNTH-01 model.
2. The high-redundancy pair (`ownership_count × transfers_in`) must be resolved by the marginal gain test before composition weights are finalized.
3. FWD is excluded from composite synthesis. purchase_price FWD is retained as a qualified single signal only.
4. GK is deferred — see `synth01-design.md §GK Scope Decision`.
5. Any `EXCLUDED-*` decision issued by SYNTH-01 must be reflected in a subsequent update to `docs/governance/state-representation-inventory.md` and in `_GOVERNED_ROLLING_COLS`.
