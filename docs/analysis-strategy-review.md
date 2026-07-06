# Analysis strategy review — segmentation, cohorts, data, and where to reach

**Status:** strategic reference (not a build spec)
**Date:** 2026-07-06
**Context:** taken after the Phase 0/1 checkpoint (baselines + ICC), before opening Phase 2.
Answers four standing questions: do we segment / do cohort analysis, do we need more data, are
we over-reaching, and which analyses give the best joint FPL-value × recruiter-signal × practice
return. Companion to [predictive-layer-plan.md](predictive-layer-plan.md).

---

## 1. Segmentation vs cohort analysis

- **Segmentation — done pervasively.** Every analysis is sliced: per **position** throughout, by
  **minutes band** (1–29 / 30–59 / 60+), and by **signal quintile**. Machinery: `stratification.py`,
  `conditioning.py`, the population layer's bands. This is a strength — no headline number rests on
  an unsliced pool.
- **Cohort / longitudinal analysis — never done (genuine gap).** A cohort follows a *defined group
  with shared entry/history over time* (e.g. promoted-team players, sub-£5.0m defenders, GW1-nailed
  starters). We have never tracked a group's trajectory across a season. This is a *different*
  question from segmentation (shared history/entry, not just a slice) and is currently blocked mainly
  by single-season data.

## 2. Data — do we need more / different?

Ranked by unlock-per-effort:

| Data | Unlocks | Effort | Priority |
|---|---|---|---|
| **≥ 2 seasons** ⭐ | Cross-season drift, cohort tracking, the D2 shrinkage re-run, out-of-season validation. Dissolves most "single-season" scope limits. | Medium (fetch + season key; pipeline half-anticipates it) | **Highest — before Phase 3** |
| **Ownership / price / transfers** | Effective-ownership strategy, template vs differential, price-change modeling — the FPL meta-game we currently ignore. | Low–medium (FPL API exposes it) | High (decision layer) |
| **Bookmaker odds** | External benchmark for clean sheets / anytime-scorer; calibration-vs-market recruiter signal. Already a Phase 3 item. | Medium (odds source) | Medium (Phase 3) |
| **Set-piece / penalty roles** | A large, cheap chunk of the predictable within-player variance for MID/FWD. | Low (public data) | Medium (Phase 2 feature) |

**Read:** Phase 2 does **not** need new data (features exist). But **acquiring a second season is the
single highest-value data move on the board** and should precede Phase 3.

## 3. Are we over-reaching?

**No — the rung/gate discipline is the anti-over-reach mechanism.** Over-reach looks like building a
Bayesian simulator before proving identity is a thin slice; we do the opposite — every phase must beat
a frozen baseline or it does not ship (D2 was told "no" and shelved cleanly). That is disciplined
ambition, not star-reaching.

**The real risk is breadth creep, not height.** Many interesting threads exist (autocorrelation,
cohorts, deeper segmentation). The antidote: tie every analysis to a **decision or a gate**, not to
curiosity. Land phases; don't fan out.

## 4. High-value analyses — joint FPL × recruiter × practice score

| Analysis | FPL value | Recruiter signal | Transferable practice |
|---|---|---|---|
| **Count/GLM target model (Phase 2.1)** ⭐ | High — the core forecaster | High — GLMs, overdispersion, proper metrics | Bread-and-butter applied DS |
| **Calibration + proper scoring (Phase 4)** ⭐ | High — trustworthy probabilities | **Very high** — rare skill done well | Risk, forecasting, ML eval |
| **Cohort / survival for availability** | High — "will he play?" is half the battle | **Very high** — survival analysis is rare | Churn, reliability, medicine |
| **Ownership / EO decision analysis** | Very high — actual rank strategy | Medium–high — decision science | Pricing, competitive strategy |
| **Autocorrelation / form persistence** | Medium — do form features earn their place | Medium — time-series literacy | Forecasting, econometrics |
| **Multi-season drift / stability** | High — do signals hold year to year | High — distribution shift is *the* prod problem | MLOps, monitoring |

## 5. Recommendation (the standing plan)

1. **Do not widen yet. Land Phase 2 (count model)** — simultaneously the highest FPL value, a top
   recruiter signal, and the most transferable practice.
2. **Fold the autocorrelation / form-persistence read into Phase 2's design** (predictive framing is
   legitimate there and can be gated), using the existing `serial.py` kernel.
3. **Acquire a second season before Phase 3** — it unlocks cohorts, drift, and the D2 re-run at once.
4. **Reserve the "reach" for the rare, high-signal muscles:** survival-for-availability and
   calibration. These are where ambition pays the best recruiter return.
