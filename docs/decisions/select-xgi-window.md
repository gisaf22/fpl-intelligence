# select-xgi-window

**Stage:** validate · **Mode:** predictive · **Verdict:** accepted (window selection) · **Date:** 2026-05-22
**Evidence:** [studies/experiments/rolling_xgi_study.py](../../studies/experiments/rolling_xgi_study.py)

Horizon-selection study for forwards: does rolling xGI outperform raw (lag-1) xGI, and
which window (3/5/8 GW) is best, when predicting next-GW total points? This is a
selection verdict that fixes which xGI horizon the form lens carries forward, executing
the design in `docs/studies/rolling-xgi-horizon-study.md`. Population: FWD only,
GW 6–33, minutes_roll3 ≥ 60; lag-1 respected.
