# Rolling xGI Horizon Study — Real Historical Validation

**Study:** [rolling-xgi-horizon-study.md](../rolling-xgi-horizon-study.md)  
**Executed:** 2026-05-19  
**Data:** 2024-25 governed spine via DAL (`~/.fpl/fpl.db`, GW1–GW37)  
**Evaluation window:** GW 6–33 (28 GWs)  
**Population:** FWD only, minutes_roll3 ≥ 60  
**Mean FWD population per GW:** 17.5 (range 15–21)

---

## Replication Summary

Rolling xGI windows continue to outperform the lag-1 baseline on real historical data.
However, rho magnitudes and stability are substantially weaker than the synthetic execution
suggested. All pre-defined thresholds are **not fully met** on real data.

### Signal Performance (Spearman rho vs next-GW total_points)

| Signal | Mean rho | Std rho | Lift vs lag1 | Top-1 return | Downside rate |
|--------|----------|---------|--------------|--------------|---------------|
| `xgi_lag1` | 0.137 | 0.259 | — (baseline) | 4.93 pts | 50.0% |
| `xgi_roll3` | 0.200 | 0.256 | **+0.063** | **5.07 pts** | 64.3% |
| `xgi_roll5` | 0.192 | 0.246 | +0.055 | 4.07 pts | 71.4% |
| `xgi_roll8` | **0.206** | **0.223** | **+0.069** | 4.21 pts | 75.0% |

*Downside rate: fraction of GWs where the top-ranked FWD returned < 4 points.*

### Threshold Assessment

| Criterion | Threshold | Real-data value | Result |
|-----------|-----------|-----------------|--------|
| Positive lift | > 0.02 (any rolling window) | 0.069 (roll8) | **MET** |
| Operational usefulness | mean rho > 0.25 (best window) | 0.206 (roll8) | **NOT MET** |
| Stability | std(rho) < 0.15 (best window) | 0.223 (roll8) | **NOT MET** |

---

## Operational Implications

**xgi_roll3 retains the best captain quality** (top-1 return 5.07 pts vs 4.93 for lag1, 4.07
for roll5, 4.21 for roll8). The rho-vs-captain-quality divergence observed synthetically
persists on real data: longer windows order the population slightly better but choose worse
individual captains.

**Confidence in the `INVOLVEMENT_WINDOW` assumption weakens.** The 30% weight on
`involvement_score` in `intelligence/captain.py` cannot be validated at the operational
usefulness threshold (rho < 0.25). Rolling aggregation does add marginal signal over lag-1,
but the per-GW variance is high. The signal is not stable enough to claim reliable weekly
advantage.

**No change to `INVOLVEMENT_WINDOW` is recommended at this stage.** Removing or reducing
`involvement_score` requires evidence that the weight actively harms decisions — the current
evidence shows a small positive return advantage for roll3 over lag1 on captain quality.
The uncertainty is in both directions.

**A second season of real data is required before promotion to `validated`.**

---

## Lifecycle Outcome

Per the study's interpretation guidance:

> *"If results are unstable (std(rho) > 0.15): Do not promote any xGI window to validated.
> Record as candidate with stability flag."*

| Signal | Prior status | New status | Reason |
|--------|-------------|-----------|--------|
| `xgi_roll3` | candidate | **candidate (stability flag)** | Lift met; usefulness and stability not met on real data |
| `xgi_roll5` | investigational | investigational | Weaker captain quality than roll3 on real data |
| `xgi_roll8` | investigational | investigational | Best rho but worst captain quality; not operationally superior |

xgi_roll3 does not regress to investigational because the positive lift criterion is met.
It does not advance to validated because the stability criterion fails.

---

## Recommendation

1. **Do not change `INVOLVEMENT_WINDOW`** or reduce `involvement_score` weight in
   `intelligence/captain.py`. The real-data evidence shows roll3 maintains marginal captain
   return advantage, but confidence is insufficient to drive a weight change in either
   direction.

2. **Advancement to `validated` requires a second season.** The single-season stability
   failure may reflect 2024-25 anomalies (injury patterns, rotation, small FWD pool).
   A second season of data resolves the ambiguity.

3. **Roll5 and roll8 remain investigational.** Neither shows enough captain-quality evidence
   to warrant advancement. Roll8 leads on population rho but produces 75% downside rate —
   not operationally useful for captain selection.

---

## Limitations

1. **Small FWD population.** 15–21 eligible FWDs per GW. Spearman rho estimates on n < 25
   have wide per-GW variance; this is the primary driver of the stability failure.

2. **Single season.** Real-data results describe 2024-25 only. GW-to-GW variation is
   substantial (rho range: −0.38 to +0.66 for roll3 across the 28 evaluation GWs).

3. **No DGW stratification.** Double gameweeks inflate raw xGI values; the combined
   population result includes DGW rows. The study design flags DGW analysis as supplementary;
   that sub-analysis is not performed here.

4. **Top-1 captain metric reflects only one pick per GW.** The signal comparison on
   downside rate uses a sample of 28 GWs. A 14% downside rate difference between roll3 and
   roll8 (64% vs 75%) is not interpretable as a reliable distinction at this sample size.
