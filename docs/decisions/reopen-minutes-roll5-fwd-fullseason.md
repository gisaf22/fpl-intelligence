# reopen-minutes-roll5-fwd-fullseason

**Stage:** monitor · **Mode:** diagnostic · **Verdict:** re-open — proposed (not yet applied) · **Date:** 2026-06-06
**Evidence:** [research/families/availability/validate/evidence.yaml](../../research/families/availability/validate/evidence.yaml) · [ADR-010 §season-review](010-layered-decision-model.md)

Full-season (GW1–38) re-estimation of the AVAIL lens lifts
`minutes_roll5@avail:played_next_gw#FWD` from `decision_class=uninformative` to **informative**
(rho 0.21). FWD was a thin-sample position in-season — exactly the kind of sample-limited finding the
season review set out to re-open. The signal is currently `lifecycle_state=excluded` at FWD; its
full-season evidence now clears the informativeness gate.

**Proposed:** re-open `minutes_roll5@FWD` — review `excluded` for promotion to `candidate` for 2026-27.
**Not yet applied** — annotation verdict (`excluded`) unchanged; applying this lets the signal score at
FWD. Caveat: full-season is in-sample over the whole year, not independently validated — confirm against
2026-27 before relying on it. This is the inverse of the DEF downgrades
([downgrade-xgi-roll5-def-fullseason](downgrade-xgi-roll5-def-fullseason.md)): more data *strengthened*
a previously-thin FWD signal rather than weakening it.
