# set-synth-weights

**Stage:** model · **Mode:** assemble · **Verdict:** partial · **Date:** 2026-05-26
**Evidence:** [studies/synthesis/synth01_study.py](../../studies/synthesis/synth01_study.py)

SYNTH-01 integrates the surviving lens signals into composition weights. Verdict is
partial: **DEF/MID composition weights are evidence-based** (partial Spearman rho with
bootstrap CIs; equal weights preferred per the ≥0.02 materiality rule — see ADR-002).
Two halves remain open: the intelligence **module** weights are still
`PROVISIONAL-EDITORIAL`, and **FDR-quartile conditioning is deferred** despite a MATERIAL
(>15%) rank-order effect, with binary-DGW as the current proxy. Both are closed in Phase 7
(see ADR-006 for the FDR decision).
