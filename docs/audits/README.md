# Predictive-layer phase audits — index

Program-level code-quality cleanup: each phase assessed through platform-SWE / analytics-engineer /
data-scientist lenses to reuse shared components, delete redundancy, and set concern boundaries.
**Kit + reusable prompt:** [PHASE_AUDIT_KIT.md](PHASE_AUDIT_KIT.md). Runs produce `{phase}-audit.md`
(assessment + plan only). A final [PROGRAM_PLAN.md](PROGRAM_PLAN.md) folds them together.

| phase | audit doc | status | top actions |
|---|---|---|---|
| 0 — baselines + harness | (stress-test done; eval-consolidation shipped) | ✅ done | reusable core + CIs extracted |
| 1 — ICC / shrinkage / level | `phase1-audit.md` | ✅ executed (branch `phase1-cleanup`) | DONE: (1) CI+coverage on the D2/level gate via shared `score_topk_by_position` (the "within noise" null is now shown -- mean/shrunk CIs overlap everywhere); (2) triplicated per-position loop collapsed into one harness helper, `_position_k` -> public `position_k`; (3) reuse `population.canonical` + `base_season`. Frozen numbers reproduced to 4dp; both notebooks re-run clean |
| 2 — ranking | `phase2-audit.md` | ⬜ not run | — |
| 3.0 — points model | `phase30-audit.md` | ⬜ not run | — |
| 3.1 — simulator | `phase31-audit.md` | ⬜ not run | — |
| 4 — calibration | `phase4-audit.md` | ⬜ not run | — |
| 5 — decisions | `phase5-audit.md` | ⬜ not run | — |
| cross-phase synthesis | `PROGRAM_PLAN.md` | ⬜ not run | — |

**Rule for every run:** assessment + plan only; behavior-preserving (the frozen results docs are the
reproduction oracle); execution is a separate approved step, one phase per branch, numbers verified
before merge.
