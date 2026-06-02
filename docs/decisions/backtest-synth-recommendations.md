# backtest-synth-recommendations

**Stage:** monitor · **Mode:** operational · **Verdict:** deferred (design/partial) · **Date:** 2026-05-27
**Evidence:** [studies/operational/phase9_backtest.py](../../studies/operational/phase9_backtest.py)

Retrospective season backtest: tests the SYNTH-01 approved compositions against actual
25/26 outcomes over the full season (GW 1–38), with GW 34–38 held out (unseen by
SYNTH-01, which used GW_MAX=33). Status is design/partial — the backtest *is* the test
artifact for the monitor stage, which is otherwise still design-only. This stage is the
one back-edge in the lifecycle: a drift finding here loops back to explore.
