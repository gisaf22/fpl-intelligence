# govern-signal-ledger

> **Historical record as of 2026-05-26.** File paths referenced below no longer exist
> post-`ae90398` (2026-08-16) — see [docs/PROJECT.md](../PROJECT.md) for current structure.
> Left unedited to preserve the decision trail.

**Stage:** model · **Mode:** govern · **Verdict:** accepted · **Date:** 2026-05-26
**Evidence:** [signals/governance/weight_registry.yaml](../../signals/governance/weight_registry.yaml)

The governed signal ledger is the system of record for every signal's lifecycle state,
lens outcome, and synthesis eligibility — `weight_registry.yaml` plus the
characterisation pipeline in [signals/characterisation/](../../signals/characterisation/).
No signal enters synthesis without a confirmed entry here. This is not a pass/fail
verdict on a hypothesis; it is the standing governance artifact that records the verdicts
the other slugs describe, guarded by the model-stage registry contract (weights sum,
valid lifecycle states, governance↔traceability consistency).
