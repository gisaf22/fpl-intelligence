# reject-minutes-stability-conditioning

**Stage:** validate · **Mode:** predictive/conditioning · **Verdict:** rejected · **Date:** 2026-05-22
**Evidence:** [studies/experiments/minutes_stability_study.py](../../studies/experiments/minutes_stability_study.py)

Tests whether minutes stability conditions the usefulness of rolling xGI for forwards —
i.e. whether xGI predicts returns more strongly for minutes-stable players. Rejected:
the effect ran the wrong way (FRINGE forwards showed stronger correlation than STABLE),
so stability is not a useful conditioning variable here. This study's 31 study-logic
tests are the template for the validate-stage test contract.
