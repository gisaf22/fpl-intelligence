# Predictive plan — assumptions audit & board stress test

**Status:** standing audit (governs Phases 2–6; update as assumptions are tested/retired)
**Date:** 2026-07-06
**Scope:** flush out untested hypotheses baked into [predictive-layer-plan.md](predictive-layer-plan.md)
and the phase designs, stress-test the sequencing, and register each assumption with a test or a
mitigation. Companion to [analysis-strategy-review.md](analysis-strategy-review.md).
**Board:** panel-data econometrician · ML forecasting engineer · FPL domain analyst · skeptical
statistician (causal) · data/pipeline engineer.

**Discipline this doc installs:** no phase ships a result that *rests* on an unvalidated assumption
without either (a) testing it, or (b) recording it as a stated scope limit. "Reasonable prior" is a
starting point, never a conclusion. Same standard that demoted the minutes-offset (Phase 2 §3).

---

## 1. Cross-cutting assumptions (highest impact — these touch every phase)

| # | Assumption baked in | Where | Why it's risky | Test / mitigation | Severity |
|---|---|---|---|---|---|
| X1 | **Conditional on appearance is the right target** — everything ranks players *given `minutes > 0`* | all phases | A manager picks **before** knowing who starts. Conditioning on realized minutes selects on a post-decision (future) variable; "ranking given played" may not be the decision-relevant quantity, and can flatter accuracy. | Quantify the gap: score the *unconditional* (pick-time) problem — predict points incl. DNP=0 — vs the conditional one; report both. **Elevate availability (Phase 6.1) earlier** or at least model P(play) as a multiplier before Phase 5 decisions. | **High** |
| X2 | **Gaussian likelihood on a count/zero-inflated target** | Phase 1 (shipped D1), any LMM | D1's MixedLM assumes Normal random-intercept + residual; weekly points are zero-inflated counts. ICC as a variance *share* survives, but the **LRT p-values and CIs rest on normality** we know is violated. | Sensitivity check: refit ICC via a Poisson/NB GLMM (or bootstrap the ICC distribution-free) and confirm the between/within split and ordering hold. Record as a caveat on the shipped D1 numbers. | **High** (debt on shipped work) |
| X3 | **Single-season stationarity** — within-season relationships are stable | all | Manager changes, injuries, fixture congestion, winter, tactical shifts create regime breaks. Walk-forward tolerates slow drift but every fit assumes one regime. | Add a within-season stability read (rolling-window coefficient / rolling baseline Spearman across GW blocks). Don't claim a stable relationship without it. | Medium |
| X4 | **DGW exclusion is harmless** | population, all | Double-gameweeks are *excluded everywhere* — yet they are the highest-value decision moments (captaincy, chips). The stack is silent exactly when it matters most. | State explicitly that forecasts don't cover DGWs (a real product gap), and scope a DGW handling path (sum of two single-GW forecasts) before Phase 5. | Medium |
| X5 | **Player identity is a stable within-season unit** | Phase 1, panel | Mid-season transfers, role changes (benchwarmer→nailed), position reclassification break the fixed random intercept. | Flag movers; check ICC robustness excluding transferred/role-changed players. | Low-Med |
| X6 | **xG/xA are clean, non-leaky, and predictive** | Phase 2 features | Expected stats are computed from the *same match* → must be strictly lagged (leakage risk). And "xG predicts future goals better than goals do" is an empirical claim, not a given. | Enforce `.shift(1)`; **test** lagged-xG vs lagged-goals as predictors head-to-head before trusting xG. Verify source coverage/missingness. | Medium |

## 2. Per-phase assumption register

### Phase 0 (frozen) — mostly clean, minor
- **A0.1** "Level persists / deviations mean-revert" — *partly verified* by the baseline ranking (season-avg best, last-GW worst). Accept, but it's an association read, not a guarantee.
- **A0.2** Operational thresholds (`WARMUP_GW=3`, `MIN_ROWS_PER_POS=10`, `TOP_K=20`, `_position_k`) are **arbitrary** (admitted). Low risk but they shape every downstream comparison → sensitivity-check the headline gate to ±1 on these once.
- **A0.3** Common-evaluation-set may **select toward established players** (rows where all baselines defined) → mildly optimistic. Report coverage alongside (already done).

### Phase 1 (shipped) — see X2 (Gaussian-on-counts) — the main debt
- **A1.1** Method-of-moments variance ratio (D2) is **noisy early season** — mitigated by warmup + prior-row floor; D2 shipped as a null anyway.
- **A1.2** ICC ≠ SS-share on unbalanced panels — *handled* (reconciled to tolerance).

### Phase 2 (design)
- **A2.1 Component independence.** Composing E[points] = Σ scoring·E[component] treats goals, assists, CS as **independent**, but they co-move (an attacking game lifts all). The *mean* is unbiased under independence, but variance/haul-probability is **not** — a real problem for Phase 3, and it understates covariance even at the mean if features interact. Test the residual correlation across components; defer joint modeling to Phase 3 explicitly.
- **A2.2 Scoring-map completeness.** Deferring **bonus (BPS), cards, saves** caps accuracy — bonus is a large, component-correlated share of premium players' points. Quantify the deferred share (what % of points is un-modeled) before claiming the map is "good enough".
- **A2.3 Linear-additive signal combination** (elastic net, 2.2) assumes no important interactions/non-linearities. Check against a non-linear reference (e.g. gradient boosting) as a ceiling probe, not necessarily to ship.
- **A2.4 xG > goals as a predictor** — see X6; it's the core Phase-2 bet and must be tested, not assumed.

### Phase 3 (design)
- **A3.1 Weak reconciliation gate.** "Simulator mean ≈ point forecast" only checks the *center* — it says **nothing about the tails/shape**, which is the entire reason to simulate. Add a distributional check (simulated vs empirical haul-rate, PIT histogram) — but that overlaps Phase 4, so **consider merging the distributional validation of Phase 3 into Phase 4** rather than a self-referential mean check.
- **A3.2 Dependence structure** inherited from A2.1 — a simulator with independent components will mis-estimate haul probability (hauls are correlated events).
- **A3.2 Odds availability** — hard blocker, already flagged.

### Phase 4 (design)
- **A4.1 Calibration tolerance is unspecified** — "within tolerance" needs a pre-registered threshold and enough GWs to estimate reliability; **isotonic/Platt can overfit** on ~35 GWs. Pre-register the tolerance and use CV recalibration.

### Phase 5 (design)
- **A5.1 Single-season decision backtest is one path.** 38 GWs is *one* realization; captain/transfer/chip rules backtested on it are **high-variance and prone to overfitting the season's meta**. Report decision results with uncertainty (block bootstrap over GWs) and resist ranking rules on a single-season point estimate. This is the weakest evidential link in the plan.
- **A5.2 Decision layer needs price/ownership data** (transfers, chips, effective ownership) that is **not yet in the mart** — Phase 5 is under-specified until that lands (see strategy review).

### Phase 6
- **A6.1** Cross-season blocked (acknowledged). **A6.2** Survival needs adequate event counts — verify. **A6.3** PyMC gated on EB proven — fine.

## 3. Board stress test — the voices

- **Panel-data econometrician:** "You shipped an ICC from a **Gaussian** LMM on zero-inflated counts (X2). The variance share is defensible; the *p-values and CIs* are on borrowed assumptions. Add a count-GLMM or bootstrap sensitivity before anyone cites the LRT."
- **ML forecasting engineer:** "Your evaluation is **conditional on appearance** (X1) end-to-end. That's a legitimate *sub-problem*, but you're one step from reporting it as forecast skill. Model P(play) before Phase 5, or the decision numbers are optimistic. Also: single-season backtest (A5.1) — put error bars on every decision claim or don't rank on them."
- **FPL domain analyst:** "You exclude DGWs (X4) and defer bonus (A2.2) — that's the captaincy and the premium-player edge gone. And no ownership/price (A5.2) means you can't actually model a transfer. The model will be 'accurate' on the part of FPL that matters least."
- **Skeptical statistician:** "Phase 3's gate (A3.1) validates a simulator against its own mean — circular. The real test is calibration (Phase 4). Consider collapsing 3-validation into 4. And component independence (A2.1) will make your haul probabilities wrong in the same direction every time."
- **Data/pipeline engineer:** "xG is a same-match stat (X6) — one missed `.shift(1)` and the whole Phase-2 lift is leakage. Add an explicit component-target leakage assertion, mirroring `_assert_no_leakage`, and a data-quality/coverage gate on xG/xA before fitting."

## 4. Recommended actions

**Before building Phase 2:**
1. **Pre-Phase-2 validation sprint** (small, cheap): test X6 (lagged xG vs lagged goals), X2 (count-GLMM ICC sensitivity — retro-check the shipped D1), and A2.2 (quantify the deferred-points share). These three de-risk the biggest bets.
2. Add a **component-target leakage assertion** to the Phase-2 harness contract.

**Plan amendments:**
3. **Elevate availability / P(play) (X1)** from Phase 6 to a *pre-Phase-5 dependency* — decisions need it. Keep full survival modeling in 6, but a simple P(play) multiplier is required earlier.
4. **Merge Phase 3's distributional validation into Phase 4** (A3.1) — drop the self-referential mean gate; validate the distribution where calibration lives.
5. **Flag Phase 5 as data-blocked on price/ownership** (A5.2) — same status as cross-season is on 2nd-season data. Don't open 5 without it.
6. **Attach uncertainty to every decision/gate claim** (A5.1) via block bootstrap over GWs.

**Standing discipline:**
7. This register is **living**: each assumption is `open / tested-holds / tested-fails / accepted-scope-limit`. A phase's promotion gate includes "its assumptions are resolved to one of those states." No silent assumptions.

## 5. Verdict

The plan's **skeleton is sound** — benchmarks first, calibration before decisions, honest-null fallbacks.
The exposed risks are not in the sequencing but in **three baked-in framings**: conditional-on-appearance
(X1), Gaussian-on-counts (X2, already shipped), and single-season decision evidence (A5.1) — plus two
**product gaps** (DGWs X4, ownership/price A5.2) that make "accuracy" and "usefulness" diverge. None block
Phase 2; all must be *stated and scheduled*, not discovered later. Recommended immediate move: the small
**pre-Phase-2 validation sprint** (actions 1–2), then build 2.1.
