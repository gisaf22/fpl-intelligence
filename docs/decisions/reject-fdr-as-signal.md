# reject-fdr-as-signal

**Stage:** validate · **Mode:** predictive · **Verdict:** rejected · **Date:** 2026-05-22
**Evidence:** [research/families/fixture/validate/study.py](../../research/families/fixture/validate/study.py)

The FIXTURE-GW lens tests whether single-GW fixture difficulty (fdr_avg) predicts
returns. Rejected as a standalone signal: the relationship is non-monotonic, so fdr_avg
is **excluded** from the composite scorer. It is **reserved as a binary moderator**
(the binary-DGW proxy referenced in [set-synth-weights](set-synth-weights.md)), not used
as a continuous signal. The ADLC §4 table groups this with the market lens; their verdicts
are opposite and recorded separately (see [adopt-market-signals](adopt-market-signals.md)).
