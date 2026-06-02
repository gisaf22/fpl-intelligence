# adopt-roll8-availability

**Stage:** validate · **Mode:** predictive · **Verdict:** accepted · **Date:** 2026-05-22
**Evidence:** [studies/lenses/avail/study.py](../../studies/lenses/avail/study.py)

After minutes proved uninformative as a *returns* signal, the AVAIL lens reframes the
same raw minutes signal as an *availability* question — does recent minutes predict
whether a player features next GW (binary `played_next_gw`)? Reframed this way it
succeeds: **minutes_roll8 approved for DEF; minutes_roll3 and minutes_roll8 approved
for MID.** The lag-1 leakage contract is asserted in the study.

This is the same column as the rejected form signal, opposite verdict — the case that
motivates the composite-key scheme (ADR-003, Phase 6).
