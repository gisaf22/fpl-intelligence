# Implementation Plan — Adopting the ADLC

**Authority:** [docs/architecture/adlc.md](architecture/adlc.md) — analysis lifecycle, mode tags, test contracts, ID-diet  
**Date authored:** 2026-06-02  
**Scope:** What is still open and unscheduled — the ADRs not yet written, and the questions that gate the `starting_xi` slice. Prescribe-only: this document moves no code and renames no folders.

This is **not** the engineering backlog. The bug/CI/study backlog lives in
[docs/governance/eng-issues-2026.md](governance/eng-issues-2026.md).

**The ADLC adoption phases are retired, not paused.** This document carried a seven-phase narrative
for adopting the ADLC. Phases 1–5 are done, and their durable record is elsewhere: the ADRs
(`docs/decisions/`), the decision-slug log, [`test-coverage.md`](architecture/test-coverage.md), and
`.github/workflows/ci.yml`. Phases 4–7 named `studies/`, `signals/`, `intelligence/`, `lenses/`,
`kernels/` and `population/` — every one of which has since been deleted or moved, so the narrative
described a topology that no longer exists. It is removed rather than rewritten, because rewriting it
would mean specifying a migration nobody is going to run. What survived it is below.

---

## Decision-slice blocking items (`decisions/starting_xi/`)

These are **questions that gate work from starting**, not planned work with a known shape. They are listed here because routed-within-the-slice is not routed if the plan that schedules work cannot see them. The reasoning stays in the slice documents; this table carries the question, its status, and a pointer. The slice's design is settled — [`DESIGN.md`](../decisions/starting_xi/DESIGN.md) — so one of the two rows below is now closed and is kept for the trail.

| Item | Blocks | Status | Detail |
|---|---|---|---|
| **`points_roll3` governance verdict** — is the governed mart's exclusion of `total_points` from feat's `_ROLL_COLS` a governance decision that binds a *baseline ranker*, or an omission specific to the signal registry's purposes? The slice's recent-form baseline is one of three floor rankers and cannot be built until this is answered. Settled by reading the lens record behind the `evaluation_circularity / G2-FAIL` annotation in `dal/feat/feat_player_gameweek.py`. | **F3, the recent-form floor ranker** (`rankers.py`) | Open — a gate, not a note | [`decisions/starting_xi/METRIC.md`](../decisions/starting_xi/METRIC.md) §5 |
| **Import-graph home for `decisions/starting_xi/`** — where can the harness legally live? The harness needs `p_play`, which is `model`, and `serve` may not import `model` while `research` may not either, so no existing layer could host it. *The question was originally recorded as needing `model` **and** `research` — the resampling kernels — and that second half was mistaken rather than merely dated: no symbol the slice needs comes from `research/`, because `METRIC.md` §5 fixes the resample count at the call site regardless of which implementation supplies it, and an equivalent of the one function in question already sits in `model/eval`. The design records the correction and why the permission was dropped rather than granted unused.* | **The harness build** — **no longer blocked** | **Closed.** `decisions/starting_xi/` becomes an importable package under a two-tier import contract: a model-free core (`harness.py`, `sampler.py`, `formations.py`, `results.py`) and a single ranker edge (`rankers.py`, `uncertainty.py`). `research/` is admitted to neither tier, so the gameweek interval is taken from `model/eval/metrics.py` instead. Needs two file edits — `pyproject.toml` and `.importlinter` — plus a new `domain/fpl_squad.py`. | [`DESIGN.md`](../decisions/starting_xi/DESIGN.md) §3 (contract), §3.9 (why `research/` was dropped from the permitted set), §8.2 (bootstrap call site, and why it is `model/eval`), §1.5 (what remains open) |

A measured finding sits behind the first item and is worth knowing before anyone reuses that code path: `operational.backtest.backtest_decision` is **unrunnable against the governed mart** — it raises on `assert_no_future_leakage`, which requires the same absent `points_roll3`, so the existing decision backtest has only ever run on fixtures that fabricate the column. Run output recorded in [`INVENTORY.md`](../decisions/starting_xi/INVENTORY.md) §5.7.

---

## Pending ADRs

Decisions named in ADLC §4 that are candidates for formal ADR entries but have not been written. Each should produce a `docs/decisions/ADR-NNN` file **before** the work it gates locks in, so the rationale is recorded before the choice is. ADR-003, 004, 005 and 008 were also listed here and have since been written; the table carries only what is still open.

| Candidate ADR | ADLC source | Decision | Gate |
|---|---|---|---|
| **ADR-006: FDR-quartile conditioning vs binary-DGW proxy** | §4 | Implement FDR-quartile conditioning, or formally accept binary-DGW as the permanent proxy with evidence. The >15% MATERIAL rank-order effect cannot remain indefinitely deferred without a record. | Before the effect is acted on |
| **ADR-007: LENS-GK evaluation methodology** | §4 / ENG-06 | Record the GK population boundary and evaluation target (saves, clean sheets, bonus per appearance vs `total_points` rank), and why the three-gate framework applies or needs modification. GK is the only position with zero governed signals. | Before the LENS-GK design locks |
