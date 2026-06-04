# LENS_DESIGN.md — LENS-MARKET

**Status:** LOCKED  
**Locked:** 2026-05-22  
**Governed by:** `signals/evaluation/EVAL_DESIGN.md` v1.5  
**Registry:** `signals/registry/SIGNAL_REGISTRY.md` v1.3 (MARKET-001 through MARKET-004)  
**EDA basis:** `studies/eda/findings/EDA_FINDINGS.md`

---

## 1. Study question

Do market activity signals (transfer demand, ownership, price) available before GW N
reliably associate with FPL returns at GW N+1? Do they carry independent information
beyond form signals, or do they simply reflect crowd consensus about form?

---

## 2. Signal set

| Signal ID | Signal | EDA basis |
|---|---|---|
| MARKET-001 | transfers_in | rho ~0.10-0.12, demand_inflow, caveated. May reflect crowd wisdom or popularity bias. |
| MARKET-002 | transfers_balance | rho ~0.02-0.08, net_demand, caveated. Net flow signal — smaller magnitude than raw inflows. |
| MARKET-003 | ownership_count | rho ~0.07-0.13, popularity_proxy, caveated. Representative of ownership/transfers_out pair — statistically redundant with transfers_out (rho 0.86 DEF), ownership_count preferred. |
| MARKET-004 | purchase_price | rho ~0.07-0.13, market_pricing, caveated. Price at time of purchase — embeds historical quality, role, and market effects. |

**Excluded:** `transfers_out` — statistically redundant with ownership_count (G-EDA6-05 analogous to G-EDA6-01 construct map finding). Use ownership_count as the representative popularity signal.

---

## 3. Target variable

**Target:** `total_points_next_gw` (lag-1), consistent with LENS-FORM (G-EDA0-01).

Market signals describe pre-GW crowd activity. The question is whether this activity
predicts next-GW returns, not whether it describes the current GW.

---

## 4. Population

`minutes >= 60` at GW N (G-EDA1-04). GW 3-33 (G-EDA1-02, G-EDA1-03).
DGW rows flagged (G-EDA1-05).

Market signals are raw (not rolling) — no warmup period. GW lower bound: 3.

---

## 5. GW block structure

Same three-block structure: early (GW 3-12), mid (GW 13-26), late (GW 27-33).

---

## 6. Correlation method

Spearman + bootstrap 95% CI. N=2000, seed=42 (G-EDA1-01).

Note: market signals (transfers_in, ownership_count) have highly right-skewed distributions
(median transfers_in=8,839, max=1,670,976). Spearman rank correlation handles this
naturally — no transformation required.

---

## 7. Classification logic

Same as LENS-FORM (EVAL_DESIGN.md §4.2): CI gate → decision relevance (Q5-Q1 ≥ 1.0,
monotonic) → block stability (≥2/3 blocks) → informative/uninformative/unstable/conditional.

Quintile gap threshold: 1.0 (total_points target, same as LENS-FORM).

---

## 8. Limitations

- Market signals reflect end-of-GW transfer data, not intra-GW. Transfer deadlines and
  GW timing mean these signals capture the crowd's state at deadline, not real-time.
- High right-skew in transfers_in and ownership_count: a small number of premium assets
  dominate. Quintile bins may be driven by these outliers.
- purchase_price embeds historical quality, not current form — its association may reflect
  player quality level rather than forward-looking signal.
- Single-season scope: 2025-26 only.

---

## 9. Design lock declaration

Locked 2026-05-22. No changes after first correlation run.
