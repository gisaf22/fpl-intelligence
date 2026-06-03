# Decisions

This folder holds two kinds of decision record. They share a folder but are **separate
namespaces** — see [ADR-004](004-decision-slug-log.md) for the rationale.

## ADRs — architectural decisions (numbered)

Formal, durable design choices. Full Context / Decision / Alternatives / Consequences.

- [ADR-001 — Spearman as the evaluation metric](001-spearman-as-evaluation-metric.md)
- [ADR-002 — Additive weighted scoring](002-additive-weighted-scoring.md)
- [ADR-003 — Composite signal-finding key scheme](003-composite-signal-finding-key.md)
- [ADR-004 — The decision-slug log as the narrative verdict namespace](004-decision-slug-log.md)

*(ADR-005, 006, 007 are reserved for later phases — see `docs/implementation-plan.md`
"Pending ADRs".)*

## Decision slugs — analytical verdicts (named, not numbered)

One file per verdict in the ADLC §4 audit table. Filename **is** the slug. Each entry
carries: Stage · Mode · Verdict · Date · Evidence, plus a sentence or two of rationale.
Append-only — superseded verdicts get a new entry that links the old one, never an
edit-in-place. **Documentation only: nothing in the code parses these files.**

| Slug | Stage | Verdict |
|---|---|---|
| [confirm-60min-population-valid](confirm-60min-population-valid.md) | explore | accepted |
| [describe-60min-boundary](describe-60min-boundary.md) | explore | accepted (descriptive) |
| [adopt-xgi-rolling-form](adopt-xgi-rolling-form.md) | validate | partial |
| [adopt-roll8-availability](adopt-roll8-availability.md) | validate | accepted |
| [select-xgi-window](select-xgi-window.md) | validate | accepted (selection) |
| [adopt-market-signals](adopt-market-signals.md) | validate | partial |
| [reject-fdr-as-signal](reject-fdr-as-signal.md) | validate | rejected |
| [reject-minutes-stability-conditioning](reject-minutes-stability-conditioning.md) | validate | rejected |
| [set-synth-weights](set-synth-weights.md) | model | partial |
| [govern-signal-ledger](govern-signal-ledger.md) | model | accepted |
| [backtest-synth-recommendations](backtest-synth-recommendations.md) | monitor | deferred |

## Which do I write?

- A **verdict** on whether a signal/study worked → a **slug**.
- A **design choice** about how the system is built → an **ADR**.

If a new verdict can't be written as one slug with one stage and one mode, it's conflating
axes (ADLC §4) — split it.
