# Evaluation Gate Criteria

**Status:** ACTIVE
**Version:** 2.0
**Produced:** 2026-05-26
**Revised:** 2026-05-27 — MIN_RHO resolved (G-OPS-02); Phase 8 Registry Rebuild
**Scope:** Defines what "passes evaluation" means for all lens studies in the fpl-intelligence methodology
**Companion data:** `signals/governance/evaluation_metadata.yaml` — per-signal-position structured findings
**Evaluation framework:** `signals/governance/EVAL_DESIGN.md`

---

## Purpose

This document makes evaluation gate criteria machine-interpretable. EVAL_DESIGN.md defines the evaluation philosophy; this document operationalises it into the specific gates a signal must clear to advance in the lifecycle.

No signal may advance to SYNTH-01 without a confirmed `decision_class` and `lifecycle_state` entry in `signals/governance/evaluation_metadata.yaml`.

---

## Gate 1 — CI gate

**Rule:** The bootstrap 95% confidence interval for `rho_pooled` must exclude zero.

- Positive signal: `rho_ci_lower > 0`
- Negative signal: `rho_ci_upper < 0`
- CI crosses zero → signal is **uninformative** at this position

Gate 1 is the minimum gate. A signal that fails Gate 1 does not proceed to Gate 2 analysis. Note: rho magnitude alone is not the gate. A signal with rho = 0.30 whose CI crosses zero is uninformative. A signal with rho = 0.09 whose CI excludes zero may still carry real information (subject to Gate 2).

This is the methodology stated in EVAL_DESIGN.md §4.2: "Signal status (informative / uninformative) determined by whether CI crosses zero — not by rho magnitude alone."

---

## Gate 2 — Decision relevance gate

**Rule:** The signal must demonstrate meaningful and ordered outcome separation across ranked player groups.

Two sub-criteria:

1. **Monotonicity** — the mean outcome across quintile bins must be monotonically ordered (no reversals). A reversal (Q3 > Q2 when Q4 > Q3, for example) means the signal does not provide graded discrimination despite aggregate correlation.

2. **Q5-Q1 gap** — the difference between the top quintile mean outcome and the bottom quintile mean outcome must exceed a meaningful threshold. The operative threshold from lens studies is approximately 1.0 FPL points for total_points lens targets and 0.10 probability for availability lens targets. This threshold is observational, not formally established.

A signal can pass Gate 1 (CI excludes zero) and fail Gate 2 (non-monotonic bins). This pattern appears frequently in the fixture signals (fdr_avg, fixture_count, was_home) and in some market signals at uninformative positions.

---

## Gate 3 — Block stability gate

**Rule:** The signal must pass Gates 1 and 2 in at least 2 of the 3 GW temporal blocks.

Block structure: the season is divided into 3 temporal blocks (early, mid, late season) of approximately equal size. A signal that passes in aggregate but fails 2+ blocks is classified as **unstable** and is not a synthesis candidate.

**Threshold: `block_stability_count ≥ 2` (out of 3 blocks)**

This threshold is observational — it is the de facto cut established by the lens study evidence:
- purchase_price DEF: 2/3 blocks → included as synthesis candidate
- minutes_roll5 FWD: 1/3 blocks → excluded (unstable)
- minutes_roll3 FWD (AVAIL): 1/3 blocks → excluded (unstable)

A value of 2/3 is conservative: it requires a signal to hold in the majority of the season, not just a peak period.

---

## decision_class vocabulary

| Value | Meaning |
|---|---|
| `informative` | Passes all three gates at this position; advances to synthesis candidate |
| `uninformative` | Fails Gate 1 (CI crosses zero) OR Gate 2 (fails decision relevance) OR Gate 3 (< 2/3 blocks) |
| `conditional` | Passes gates but with a documented scope constraint — e.g., approved only as a naive baseline, not as an independent synthesis candidate; or position-specific caveat documented |
| `excluded` | Position not in scope for this signal by ontological design (e.g., GK for xgi, FWD/GKP for fixture_count) |

---

## lifecycle_state vocabulary

| Value | Meaning |
|---|---|
| `candidate` | Signal-position pair approved for SYNTH-01 entry |
| `excluded` | Not advancing to synthesis |
| `not_applicable` | Position not studied; excluded by design before lens study ran |

---

## MIN_RHO — resolved (Phase 8, 2026-05-27)

`MIN_RHO = 0.15` has been **removed** from `intelligence/scoring/signal_selector.py` as of Phase 8 (G-OPS-02 resolution).

**SYNTH-01 finding (Phase 7):** All three signals that were incorrectly caveated by the magnitude filter received `APPROVED-*` decisions via partial Spearman rho:

| Signal | Position | bivariate rho | partial rho (SYNTH-01) | Decision |
|---|---|---|---|---|
| xgi_roll3 | DEF | 0.123 | 0.0401 (G-SYNTH1-01) | APPROVED-PRIMARY |
| xgi_roll5 | DEF | 0.113 | 0.0271 (G-SYNTH1-02) | APPROVED-SECONDARY |
| purchase_price | DEF | 0.121 | 0.0550 (G-SYNTH1-06) | APPROVED-SECONDARY |

Since all three received `APPROVED-*` decisions, the resolution rule from the Operational Convergence Plan applies: **remove MIN_RHO entirely**. No minimum magnitude threshold is warranted by SYNTH-01 evidence. The CI gate (Gate 1) is the sole authority for signal confirmation in the scoring manifest.

The scoring manifest loader now confirms any signal with a non-null `rho_pooled` that passes the leakage and outcome-component exclusion checks. Evaluation governance enforcement (via `_assert_governance_compliance`) continues to block any signal with `lifecycle_state=excluded` or `downstream_status=blocked` in the evaluation record.

---

## Threshold audit — hardcoded analytical constants in operational files

As of 2026-05-27 (Phase 8 complete):

| File | Constant | Value | Status |
|---|---|---|---|
| `intelligence/scoring/signal_selector.py` | `MIN_RHO` | — | **REMOVED** (Phase 8, G-OPS-02) |

The following hardcoded constants in operational files are **editorial judgment weights**, not analytical thresholds. They are not governed by this evaluation gate criteria document:

| File | Constants | Status |
|---|---|---|
| `intelligence/captain.py` | form_score: 0.35, involvement_score: 0.30, fixture_score: 0.20, minutes_score: 0.15 | Editorial; wired via weight_registry.yaml (Phase 6). Calibration deferred to Phase 9. |
| `intelligence/value.py` | efficiency_score: 0.50, form_score: 0.30, consistency_score: 0.20 | Editorial; wired via weight_registry.yaml (Phase 6). Calibration deferred to Phase 9. |
| `intelligence/fixtures.py` | team_attack_score: 0.35, dgw_bonus_score: 0.25 | Editorial; fdr_avg removed (Phase 6, GAP-TRACE-02). Calibration deferred to Phase 9. |

---

## Relationship to other documents

| Document | Role |
|---|---|
| `signals/governance/EVAL_DESIGN.md` | Evaluation philosophy; success/failure criteria; what the system claims |
| `signals/characterisation/SIGNAL_REGISTRY.md` | Per-signal lifecycle governance; lens status; synthesis status; known caveats |
| `signals/governance/evaluation_metadata.yaml` | Machine-readable per-signal-position findings: rho_pooled, CI, block_stability_count, decision_class, lifecycle_state |
| `docs/foundations/representation-rules.md` | Representation governance — allowed and forbidden transforms per signal family |
| `docs/archive/architecture-execution-plan.md` | Phase-by-phase execution plan (archived — system complete) |
