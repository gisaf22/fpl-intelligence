# Workflow Map — fpl-intelligence

Structural audit as of 2026-08-15, branch `predictive-cleanup-and-redesign-spec`
(HEAD = uncommitted work atop `c475873`). Descriptive only: no quality judgments,
no recommendations. Claims are grounded in imports/file contents/git log; anything
inferred is marked UNVERIFIED.

> **Amended 2026-08-16.** Commit `ae90398` (one day after this audit) deleted
> `serve/scoring/`, `serve/reporting/`, `outputs/registry/`,
> `domain/registry/{verdict,governance_lookup,governance_types}.py`,
> `model/governance/{SIGNAL_REGISTRY.md,evaluation_metadata.yaml,generate_*.py,verdict_records.py,signal_traceability.yaml}`
> and `tests/test_downstream_governance.py`. **Workflows G and H no longer exist** — their
> entries below are kept as a record of what was removed and are marked REMOVED.
> Workflows A–F are unaffected.

---

## 1. Entry point inventory

| Entry point | Path | Kind |
|---|---|---|
| DAL build/load | `dal/pipeline.py::run`, `::load` | library entry, root of everything |
| DAL quickstart | `examples/quickstart.py` | CLI smoke test |
| Forecast assembly | `model/predictions.py::assemble_forecast` | library entry |
| Per-term model build | `model/terms/*/notebook.ipynb` (goals, assists, minutes, bonus, saves, defensive_contribution, team_goals_against, p_play) | notebooks |
| Composition study | `model/assemble/composition_study.py` | script → `synth01_recommendations.yaml` |
| **Live recommendation runner** | `operational/recommend.py::main` (`--target-gw`) | **CLI, live path** |
| Backtest runner | `operational/backtest.py::backtest_decision` | library entry |
| ~~Composite scoring CLI~~ | ~~`serve/scoring/scoring_runner.py`~~ | **REMOVED at `ae90398`** |
| ~~Weekly report CLI~~ | ~~`serve/reporting/weekly_report_runner.py::main`~~ | **REMOVED at `ae90398`** |
| Archived monitor | `archive/monitor/phase9_backtest.py` | CLI, archived |
| Research/diagnostic notebooks | `research/foundation/**`, `research/diagnostic/**`, `model/eval/notebooks/**`, `model/features/opp_xgc_scoping.ipynb` | render-only for humans |
| "How to run X" docs | `docs/PROJECT.md`, `dal/README.md`, `docs/architecture/adlc.md` | doc only |

At the time of the audit there were three mutually independent CLI paths rooted in `serve/`.
After `ae90398` **only one remains**: `operational/recommend.py` (decision engine). The composite
scorer and the weekly report CLI were deleted.

---

## 2. Workflows

### A — DAL spine
- **Purpose:** produce the validated deterministic `(player_id, gw)` mart every other layer reads.
- **Status:** active/live.
- **Entry:** `dal/pipeline.py::run`/`load`; `examples/quickstart.py`.
- **Components:** `dal/staging`, `dal/intermediate`, `dal/fct`, `dal/feat`, `dal/mart`, `dal/validation`, `dal/README.md`.
- **Artifacts:** cached mart parquet + manifest; `dal/feat/feat_schema.py::FEATURE_REGISTRY`.
- **Consumed by:** everything — `research/*`, `model/*`, `operational/*`.
- **Fork point:** none. Shared root; belongs to no single workflow.

### B — Predictive-layer research program
- **Purpose:** build and validate the per-term probabilistic points model (level → components → points equation → simulator → calibration → decision evaluation).
- **Status:** active/live in code; **its master plan doc is stale** (see divergence #5).
- **Entry:** `docs/predictive-layer-plan.md` (index), `model/terms/*/notebook.ipynb`, `model/eval/notebooks/*`.
- **Components:** `research/kernels/*` (shared with F); `model/features/{spec,build}.py`; `model/terms/*/`; `model/forecast/{count_models,level_estimators,shrinkage}.py`; `model/eval/{walkforward,calibration,scorer,scoring_conformance,baselines,forecast_diagnostics,population}.py`; `docs/studies/results/predictive-phase0..5-*.md`; `docs/model-redesign-spec.md`, `-changelog.md`, `-mean-features-plan.md`.
- **Artifacts:** `assemble_forecast` columns (`e_points`, `e_points_uncond`, `p10/p50/p90`, `p_haul`, `sim_*`); frozen `predictive-phase*.md` result docs.
- **Consumed by:** forecast columns → `serve/{captain,value,transfers}.py` via `operational/recommend.py` (live). Result docs → documentation only, no programmatic consumer.
- **Fork point:** ADR-011 (2026-08-01, `06aa438`) is where this workflow's output began feeding serve, displacing Workflow D.

### C — Captaincy decision-evaluation audit (in flight, uncommitted)
- **Purpose:** re-test the frozen Phase-5.1 "captaincy is largely irreducible" verdict under a realistic owned-pool / per-position / lagged-ownership framing rather than the pooled full-universe framing.
- **Status:** partial / in progress — uncommitted code + untracked docs, not folded into the plan doc.
- **Entry:** `docs/studies/results/predictive-phase5-captaincy-realistic-pool.md` → `-diagnostic-rerun.md` → `-by-position.md`.
- **Components:** modified `model/eval/captaincy_backtest.py` (adds `lagged_ownership`, `captaincy_paired_deltas`, pool `min_candidates`), `model/eval/captaincy_diagnostics.py` (generalized `divergence_winrate`, new `oracle_rank_hits`, dual-CV `oracle_discrimination`), `model/eval/metrics.py` (new `BLOCK_GWS`, `block_bootstrap_draws`); the three untracked result docs.
- **Artifacts:** those three markdown docs — currently self-referential; not linked from `docs/predictive-layer-plan.md`'s status table.
- **Consumed by:** nothing yet.
- **Fork point:** branches off B at the "RESUME HERE: Door 2 (multi-season data)" pointer in `docs/predictive-layer-plan.md` — this thread re-audits Door 1 (pool construction) on the single season instead. Notes explicitly that "frozen study numbers no longer reproduce against current code."

### D — SYNTH-01 composite scoring
- **Purpose:** the original ADR-002 additive-weighted signal composite — derive per-position weights from partial-Spearman evidence, rank players by weighted composite.
- **Status:** superseded for ranking by ADR-011; its runtime surface (the Workflow-G CLI) was deleted at `ae90398`. What remains is the study code and the `synth01_*.yaml` chain, importable and tested, with no consumer.
- **Entry:** `model/assemble/composition_study.py`. (`model/governance/generate_synth01_decisions.py` was deleted at `ae90398`.)
- **Components:** `model/assemble/composition_study.py`, `synth01_candidates.yaml`, `synth01_decisions.yaml`, `synth01_recommendations.yaml`; `model/governance/{promotion,semantics}.py`, `EVAL_DESIGN.md`; `domain/registry/*`. (`generate_synth01_decisions.py`, `generate_evaluation_metadata.py`, `verdict_records.py`, `signal_traceability.yaml`, `evaluation_metadata.yaml`, `SIGNAL_REGISTRY.md` and the `domain/registry/{verdict,governance_lookup,governance_types}.py` leaf were deleted at `ae90398`; `promote.py` — the publication step to `outputs/registry/` — was deleted 2026-08-16.)
- **Artifacts:** `synth01_decisions.yaml`, `synth01_recommendations.yaml`. (`outputs/registry/gw36/{registry.csv,build_metadata.json}` was deleted at `ae90398` — its only consumer was gone.)
- **Consumed by:** *not* the live decision path. `tests/test_runtime_consumer_alignment.py` states in its own docstring that the weight-registry / hardcoded-weight / `score_provenance` consumer contracts "were removed with the serve signal composites... there is no weight_registry or provenance surface left to align against." `serve/weight_registry.yaml` no longer exists (only a stale `.pyc`), and `docs/navigation-map.md` no longer lists it.
- **Fork point:** ADR-011 (`docs/decisions/011-model-forecast-supersedes-composites.md`; commits `22e49f6`, `d728b33`, `a93f262`, `da22c41`, `89a7b35`). Captain/value/transfers each clean-broke to the forecast, then the shared weighting machinery was swept. The study + governance ratification chain was left in place, importable and tested.

### E — Phase-9 operational baseline monitor
- **Purpose:** backtest approved SYNTH-01 compositions across 25/26 with a GW34-38 holdout.
- **Status:** superseded, archived, terminal.
- **Entry:** `archive/monitor/phase9_backtest.py`.
- **Components:** `archive/monitor/{phase9_backtest.py,__init__.py}`.
- **Artifacts:** `outputs/phase9_backtest_results.yaml`, `outputs/operational-baseline.md`.
- **Consumed by:** nothing programmatic. `outputs/operational-baseline.md` is still linked from `docs/navigation-map.md` under "Operational outputs," and cites its source script as `studies/operational/phase9_backtest.py` — a path that no longer resolves after the `studies/` → `research/` migration.
- **Fork point:** rode on D; superseded in the same ADR-011 wave. Relocated to `archive/` rather than deleted.

### F — Decision-as-contract runtime (ADR-012) — **the live path**
- **Purpose:** make "a decision" (captain/value/transfers pick) a first-class declarative contract with a generic ranking engine and a serve-agnostic backtest harness.
- **Status:** active/live, and **further along than ADR-012's own status text claims** — the ADR says Phase 4 (eval harness) is "current scope / in scoping," but Phase 4 shipped in `c475873`: `model/eval/decision/{spec,backtest,baselines,metrics,__init__}.py` exists and `tests/helpers/` is now empty but for `__init__.py`, confirming the full replacement the ADR called for.
- **Entry:** `operational/recommend.py::main`; `operational/backtest.py::backtest_decision`.
- **Verified call chain:** `operational/recommend.py` → `dal.pipeline.load` + `model.predictions.assemble_forecast` → `domain.decision.DecisionSpec` + `serve.decision_engine.run_decision` over `serve.captain.CAPTAIN` / `serve.value.VALUE` / `serve.transfers.TRANSFERS`. `operational/backtest.py` → `model.eval.decision` harness with `serve.{captain,value,transfers}.rank_*` injected as `pick_fn`.
- **Components:** `domain/decision.py`; `serve/decision_engine.py`; `serve/{captain,value,transfers,availability,input_contracts}.py`; `model/eval/decision/*`; `research/kernels/inferential/resampling.py` (**shared** with B); `operational/{recommend,backtest}.py`.
- **Artifacts:** intended `outputs/decisions/gw{N}/{captain,value,transfers}.csv` + `recommendations.md`. The directory does not exist in the tree and `outputs/*` is gitignored — UNVERIFIED whether the runner has ever been executed with persisted output. `operational/backtest.py` returns in-memory `BacktestResult`; no persisted artifact found.
- **Consumes:** B's forecast, A's mart.
- **Fork point:** supersedes the "operational runner" ADR-011 gestured at but never built — ADR-012 §Context states plainly: *"The operational runner ADR-011 refers to does not exist — it is prose and test scaffolding."* Absorbs the old split evaluation (`model/eval/captaincy_*` forecast-level + `tests/helpers/{captain,value,transfers}.py` ranker-level) into `model/eval/decision/`.

### G — Composite scoring CLI (`serve/scoring`) — **REMOVED at `ae90398`**
- **Status:** **deleted.** `serve/scoring/` holds nothing but a stale `__pycache__`. Its dependency
  `domain/registry/verdict.py` was deleted in the same commit. Retained here only as a record of what
  the tree looked like before the sweep.
- **What it was:** a standalone argparse CLI that scored a gameweek from a governance-approved signal
  manifest and rendered it — `scoring_runner` → `dal.pipeline.load` +
  `serve.scoring.signal_selector.load_manifest_from_path` → `serve.scoring.engine.score` →
  `serve.scoring.renderer.render`. It was D's runtime surface, never reached from
  `operational/recommend.py`.
- **Why it went:** ADR-011 removed the ranking role it served; with no consumer on the live path and
  its registry inputs frozen at the gw36 snapshot, `ae90398` deleted the package, its tests, and the
  `outputs/registry/` artifact it read.

### H — Weekly report CLI (`serve/reporting`) — **REMOVED at `ae90398`**
- **Status:** **deleted.** `serve/reporting/` holds nothing but a stale `__pycache__`.
- **What it was:** a standalone CLI producing weekly registry-derived reports, snapshots and insight
  cards — `weekly_report_runner` → `domain.registry.operational.load_registry` +
  `domain.registry.validation.validate_registry_contract` →
  `serve.reporting.insight_card_writer.write_insight_cards`.
- **Why it went:** it read the registry, not the forecast, so it was never in ADR-011's blast radius
  and never joined the ADR-012 path; `ae90398` retired the registry surface it depended on and the
  package with it. Its tests were deleted in the same commit.

---

## 3. Divergence map

1. **D → B/F.** The composites and the serve rankers shared the role "rank players for a decision" until **ADR-011** (2026-07-31 → 08-01; `22e49f6`, `d728b33`, `a93f262`, `da22c41`, `89a7b35`). After that, `serve/{captain,value,transfers}.py` rank by `assemble_forecast` columns directly. B/F replaced D's ranking role. **D's study code and `synth01_*.yaml` chain remain**, still tested, with zero runtime consumers; its `serve/scoring` CLI and most of its governance scripts were deleted at `ae90398`.

2. **E rode on D.** Phase-9 validated D's compositions. When D lost its ranking role, E's validation target went with it. E's script was moved to `archive/monitor/` rather than deleted; its published output `outputs/operational-baseline.md` is still indexed in `docs/navigation-map.md` as current; its source-path citation was corrected from `studies/operational/phase9_backtest.py` to `archive/monitor/phase9_backtest.py` on 2026-08-16.

3. **B's evaluation machinery forked into two homes that coexist by design.** `model/eval/captaincy_backtest.py` / `captaincy_diagnostics.py` (forecast-level, pre-ADR-012, still actively extended by Workflow C) vs `model/eval/decision/` (pick-level, ADR-012 Phase 4, `c475873`). ADR-012 §"Open decisions" asks whether pick-level backtest fully absorbs `captaincy_backtest` and records **"Lean coexist"** — the code confirms coexist is what happened.

4. **F supersedes a workflow that never existed.** ADR-011 promised an operational runner; only `tests/helpers/*` stood in for it. ADR-012 Phase 3 built the real one (`operational/recommend.py`, `operational/backtest.py`) and Phase 2 emptied `tests/helpers/*` to `__init__.py`. **ADR-012's own status line is stale relative to its own implementing commit** — `c475873`'s message announces the eval harness the ADR still calls "in scoping."

5. **B's plan doc vs C's actual frontier.** `docs/predictive-layer-plan.md` (last updated 2026-07-10) marks Phase 5.1 done and points to "Door 2 (multi-season data)." Work continued past that pointer down a different road (C's captaincy pool audit, three docs dated 2026-08-14 + uncommitted code) without the plan's status dashboard being updated. **The status doc and the work have diverged.**

6. **Two indexing schemes over one codebase.** `docs/model-redesign-spec.md` (organizes B *by concern*) and `docs/predictive-layer-plan.md` (organizes B *by phase*) both describe the same `model/terms/`, `model/features/`, `model/eval/` code. `docs/model-redesign-changelog.md` states the spec supersedes phase-based organization going forward while the phase-numbered `predictive-phase*.md` docs remain the immutable historical evidence trail. Both live simultaneously by design — per the changelog: "Phases were a timeline... this spec keeps the timeline as a changelog."

7. **`domain/registry/*` was the last shared spine between the retired and live worlds.** D (governance), G (scoring CLI) and H (weekly reports) all imported it; F (the live decision path) never did — it depends on `domain/decision.py`. With G and H deleted at `ae90398` (along with the `verdict`/`governance_lookup`/`governance_types` leaf), only D still reads what remains of `domain/registry/`, and it has no runtime consumer.

### Where the live path actually runs

```
dal.pipeline.load ──► model.predictions.assemble_forecast ──► serve.decision_engine.run_decision
                                                                 (CAPTAIN | VALUE | TRANSFERS specs)
                                                                        └─► outputs/decisions/gw{N}/*
                        [entry: operational/recommend.py --target-gw]
```

Everything in D and E is off this line; G and H no longer exist.

---

## 4. Orphans and stale references

- ~~**`outputs/operational-baseline.md`** — cites `studies/operational/phase9_backtest.py`~~ — fixed 2026-08-16 to `archive/monitor/phase9_backtest.py`.
- ~~**`outputs/registry/gw36/`**~~ — confirmed to have no reader and deleted at `ae90398`.
- **`research/findings/COVERAGE_MATRIX.md`, `FINDINGS.md`, `research/findings/records/*.csv`** — indexed by `docs/navigation-map.md` reading order; no programmatic consumer traced. UNVERIFIED whether documentary only.
- **`docs/decisions/006`, `007`** — reserved, never written (per `docs/decisions/README.md`). Numbering gaps, not code orphans.
- **`docs/governance/{threshold-registry,evaluation-gate-criteria,eng-issues-2026}.md`** — listed as authoritative in the navigation map; not cross-checked against code.
- **`docs/studies/results/predictive-phase*.md`** — not orphans (they are B's evidence trail) but have no programmatic consumer by design.

*Superseded by `ae90398`:* the initial pass resolved `serve/scoring/*` and `serve/reporting/*` as live-but-disconnected Workflows G and H rather than orphans. They were deleted the next day.

---

## 5. UNVERIFIED

- Whether `operational/recommend.py` has ever been executed with persisted output — `outputs/decisions/` does not exist and is gitignored, so there is no artifact evidence either way.
- Whether `research/findings/*` CSVs and `research/registry/*` have current programmatic consumers or are purely historical.
- Import edges of `model/governance/{promotion,semantics}.py` individually — their membership in D was inferred from the shared `synth01_decisions.yaml` grep hit, not traced per-module.
- `docs/governance/{threshold-registry,evaluation-gate-criteria,eng-issues-2026}.md` — not opened.
- Whether `docs/model-redesign-spec.md`'s self-declared status ("draft to build against") is stale given `model/terms/` and `model/features/` already match the spec structurally.
