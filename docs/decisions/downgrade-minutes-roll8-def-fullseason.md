# downgrade-minutes-roll8-def-fullseason

**Stage:** monitor · **Mode:** diagnostic · **Verdict:** downgrade — proposed (not yet applied) · **Date:** 2026-06-06
**Evidence:** [research/families/availability/validate/evidence.yaml](../../research/families/availability/validate/evidence.yaml) · [ADR-010 §season-review](010-layered-decision-model.md)

Full-season (GW1–38) re-estimation of the AVAIL lens drops
`minutes_roll8@avail:played_next_gw#DEF` from `decision_class=informative` to **uninformative**
on full-season data (rho 0.22 — still numerically positive, so the flip is a gate failure, not a
sign change; see the evidence record for the failing gate). `minutes_roll8@DEF` is the sole approved
availability signal at DEF ([adopt-roll8-availability](adopt-roll8-availability.md)); folding the
end-of-season regime in (extended late block 27–38, ADR-010) costs it the informativeness gate.

**Proposed:** review `minutes_roll8@DEF` `lifecycle_state=approved` for downgrade for 2026-27.
**Not yet applied** — annotation verdict unchanged. Caveat: full-season is in-sample over the whole
year, not independently validated; 2026-27 is the real holdout. Same regime effect as
[downgrade-xgi-roll5-def-fullseason](downgrade-xgi-roll5-def-fullseason.md).
