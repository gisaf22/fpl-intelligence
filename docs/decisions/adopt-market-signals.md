# adopt-market-signals

**Stage:** validate · **Mode:** predictive · **Verdict:** partial · **Date:** 2026-05-22
**Evidence:** [studies/lenses/market/study.py](../../studies/lenses/market/study.py)

The MARKET lens evaluates transfer, ownership, and price signals against returns.
Partial-accept: **transfers_in approved for DEF and MID; purchase_price for DEF and FWD†;
ownership_count for MID.** Other signal/position pairs did not clear the gate.

† FWD purchase_price reverses on holdout GW 34–38 (rho = −0.095) — a phase-conditional
restriction is required, tracked as ENG-02. The ADLC §4 table groups market and fixture
into one row; they have opposite verdicts and are recorded separately
(see [reject-fdr-as-signal](reject-fdr-as-signal.md)).
