# downgrade-xgi-roll5-def-fullseason

**Stage:** monitor · **Mode:** diagnostic · **Verdict:** downgrade — proposed (not yet applied) · **Date:** 2026-06-06
**Evidence:** [research/families/form/validate/evidence.yaml](../../research/families/form/validate/evidence.yaml) · [ADR-010 §season-review](010-layered-decision-model.md)

Full-season (GW1–38) re-estimation of the FORM lens — adopted in the season review after the
descriptive/diagnostic stages were made all-inclusive (holdout folded in, ADR-010) — drops
`xgi_roll5@form:total_points#DEF` from `decision_class=informative` to **uninformative**
(rho 0.11, down from the in-sample GW33 estimate). The signal was approved in-season
([set-synth-weights](set-synth-weights.md)); its full-season evidence no longer clears the
informativeness gate at DEF.

**Proposed:** downgrade `xgi_roll5@DEF` from `lifecycle_state=approved` toward `candidate`/`excluded`
for 2026-27. **Not yet applied** — the annotation verdict (`approved`) is human-pinned and unchanged;
applying this changes scoring. Caveat: the full-season estimate is **in-sample over the whole year**,
not independently validated — the real out-of-sample test is 2026-27 data. Pair with
[downgrade-minutes-roll8-def-fullseason](downgrade-minutes-roll8-def-fullseason.md) (same regime effect,
same position).
