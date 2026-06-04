# Research Layer — Migration Blueprint

**Role:** Principal Analytics Engineer / Repository Architect assessment.
**Date:** 2026-06-03.
**Status:** assessment + migration blueprint only. No files moved, no code changed.
**Authority:** [studies/STRATEGY.md](../../studies/STRATEGY.md) is the *accepted target operating model* and is treated as fixed. This document evaluates the repo against it.

**Target structure (accepted):**

```
research/
  kernels/                         shared pure-stats toolbox (no tier)
  00_scope/                        eligibility & population validity
  01_describe/                     integrity · target & signal distributions
  02_stability/                    temporal persistence across GWs
  03_associate/
    relationship/                  signal ↔ target (class 3)
    redundancy/                    signal ↔ signal (class 4)
    conditioning/                  heterogeneity / interaction (class 5)
  04_validate/                     out-of-sample predictive confirmation (class 6)
  findings/                        durable verdicts (the "Finding" sink)   ← see Part 4 note
```

Research owns **Feature → Research → Finding**. It does **not** own entity/feature construction (DAL), signal governance, weighting, recommendation assembly, or serving.

---

## Part 1 — Current State Inventory

| Artifact (current path) | Purpose | Inputs | Outputs | Dependencies | Consumers |
|---|---|---|---|---|---|
| `studies/kernels/distribution.py` | univariate stats: completeness, atomic stats, cohort/tail | DataFrame | dicts | numpy, scipy | eda notebooks (`_target_distribution_helpers`) |
| `studies/kernels/stability.py` | block-distribution stability classification | DataFrame | classification str | numpy, pandas | `test_signals_stability` |
| `studies/kernels/windows.py` | temporal-integrity / lag-1 leakage enforcement | features df | assertion | pandas | `rolling_xgi`, `minutes_stability`, tests |
| `studies/kernels/redundancy.py` | pairwise + partial Spearman, redundant-pair flagging | DataFrame | matrix / pairs / float | numpy, scipy | `test_signals_redundancy`, `eda_08` (re-impl) |
| `studies/kernels/correlation/panel.py` | panel-structure Spearman decomposition (`decompose_rho`) | DataFrame | dict | scipy | `registry_sections_study`, `_joint_helpers`, tests |
| `studies/kernels/correlation/tail.py` | tail/haul-concentration (`haul_concentration`) | DataFrame | dict | scipy | `registry_sections_study`, `_joint_helpers`, tests |
| `studies/kernels/metrics.py` | operational evaluation metrics (rank-corr, hit-rate, regret…) | series/collections | scalars/None | pandas | `rolling_xgi`, `minutes_stability` |
| `studies/kernels/conditioning.py` **(new)** | conditional-ρ across strata + heterogeneity classification | DataFrame | DataFrame/str | numpy, scipy | `test_kernels_conditioning` |
| `studies/kernels/multiplicity.py` **(new)** | BH / Holm multiple-comparison control | p-values | dict of arrays | numpy | `test_kernels_multiplicity` |
| `studies/kernels/resampling.py` **(new)** | bootstrap Spearman CI | arrays | dict/None | numpy, scipy | `test_kernels_resampling` |
| `studies/eda/population.py` | dual-scope ρ + population-robustness classification (EDA-4) | mart | classification | scipy | `test_signals_population` |
| `studies/eda/scoping.py` | exposure-aware dual-scope summaries + EDA-2 registry assembly | mart | DataFrame/registry | `eda.profiling` | `_signal_distribution_helpers` |
| `studies/eda/profiling.py` | signal profiling: zero-mass, variance, block homogeneity, status table | mart | DataFrames | numpy, scipy | `scoping`, notebook helpers |
| `studies/eda/association.py` | association-class assignment (study-layer copy) | row dicts | class str | — | `_joint_helpers`, `test_relationship_geometry` |
| `studies/eda/geometry.py` | signal↔target relationship **shape** (study-layer copy) | bin stats | geometry class | numpy | `registry_sections_study`, `_joint_helpers`, tests |
| `studies/eda/semantics.py` | signal-layer enrichment (inlined governance vocab) | registry | enriched df | — | (registry build chain) |
| `studies/eda/eda_08_study.py` | EDA-8 gap study (saves/xgc/penalties/assists): 8A–8D | mart | findings dir | kernels, geometry | run-once; findings durable |
| `studies/eda/EDA_08_DESIGN.md` | EDA-8 pre-spec | — | doc | — | humans |
| `studies/eda/findings/*` | durable EDA verdicts (CSVs + `EDA_FINDINGS.md`, `EDA_COVERAGE_MAP.md`) | — | findings | — | coverage map, lens designs, humans |
| `studies/eda/notebooks/eda_00_integrity` | data integrity / missingness | mart | findings | helpers | humans |
| `studies/eda/notebooks/eda_01_target` | target (points) distribution | mart | findings | `distribution` | humans |
| `studies/eda/notebooks/eda_02_signals` | signal profiling + scoping | mart | `eda_02_*` csv | `profiling`,`scoping` | humans |
| `studies/eda/notebooks/eda_03_joint` | signal↔target association / geometry | mart | `eda_03_*` csv | `_joint_helpers` | humans |
| `studies/eda/notebooks/eda_04_population_validity` | scope robustness | mart | `eda_04_*` csv | `population` | humans |
| `studies/eda/notebooks/eda_05_signal_stability` | temporal stability | mart | `eda_05_*` csv | `stability` | humans |
| `studies/eda/notebooks/eda_06_redundancy` | redundancy / partial-ρ | mart | `eda_06_*` csv | `redundancy` | humans |
| `studies/eda/notebooks/eda_07_signal_synthesis` | exploratory joint-registry assembly | findings | `eda_07_*` csv | helpers | (feeds registry thinking) |
| `studies/eda/notebooks/eda_pop_boundary_scatter` | 60-min boundary describe | mart | figure | helpers | humans |
| `studies/lenses/form/` | predictive lens: rolling xGI → next-GW points | mart | lens verdict (json) | kernels | registry build (file) |
| `studies/lenses/avail/` | predictive lens: minutes_roll → `played_next_gw` | mart | lens verdict | kernels | registry build (file) |
| `studies/lenses/market/` | predictive lens: transfers/price/ownership → next-GW points | mart | lens verdict | kernels | registry build (file) |
| `studies/lenses/fixture_gw/` | predictive lens: fixture signals → **same-GW** points | mart | lens verdict | kernels | registry build (file) |
| `studies/experiments/minutes_stability_study.py` | conditioning: does minutes-stability moderate xGI? | mart | findings (31-test template) | kernels | `test_minutes_stability_study` |
| `studies/experiments/rolling_xgi_study.py` | predictive: xGI window choice (3/5/8) | mart | findings | kernels | `test_rolling_xgi_study`, `…_real_validation` |
| `studies/experiments/registry_sections_study.py` | builds registry relationship sections | prepared data | sections | `geometry`, `correlation` | `test_registry_build_parity`, `test_relationship_computation`, registry build |
| `studies/synthesis/synth01_study.py` | composition weights + FDR(fixture-difficulty) moderation | mart | `signals/governance/synth01_decisions.yaml` | kernels, dal | governance (file) |
| `studies/operational/phase9_backtest.py` | retrospective season backtest | mart | `outputs/phase9_*.yaml` | dal | (monitor — parked) |
| `studies/STRATEGY.md` | research-layer doctrine | — | doc | — | humans |

**Not research (inventoried for boundary clarity):** `domain/fpl_scoring.py` (scoring constants — domain), `population/populations.py` (named populations — shared/domain, consumed by research+governance+serve), `signals/` (governance), `intelligence/` (serve).

---

## Part 2 — Classification Assessment

| Current location | Target class | Confidence | Reasoning |
|---|---|---|---|
| `kernels/distribution.py` | 1 (tool) | High | univariate distribution math; pure |
| `kernels/stability.py` | 2 (tool) | High | block-stability classification; pure |
| `kernels/windows.py` | 2/6 (tool) | High | temporal integrity — used by stability + validation |
| `kernels/redundancy.py` | 4 (tool) | High | pairwise/partial ρ |
| `kernels/correlation/*` | 3 (tool) | High | Spearman decomposition / tail dependence |
| `kernels/metrics.py` | 6 (tool) | High | OOS evaluation metrics |
| `kernels/conditioning.py` | 5 (tool) | High | new; heterogeneity |
| `kernels/multiplicity.py` | 6 (tool) | High | new; firewall multiplicity |
| `kernels/resampling.py` | cross (tool) | High | new; uncertainty |
| `eda/population.py` | **0 Scope** | High | population robustness = eligibility |
| `eda/scoping.py` | **0 Scope** | High | exposure-aware scoping |
| `eda/profiling.py` | **1 Describe** | High | signal marginal profiling |
| `eda/association.py` | **3 Relationship** | High | association-class logic; *also a duplication smell (study-layer copy)* |
| `eda/geometry.py` | **3 Relationship** (→ kernel) | High | relationship-shape; domain-agnostic — belongs in `kernels/` |
| `eda/semantics.py` | **NOT research** (→ governance) | High | inlines governance vocab; enriches registry layers |
| `eda/eda_08_study.py` | **3 + 1 + 4 (ambiguous)** | Medium | multi-class executable (sparsity=1, association=3, redundancy=4) |
| `eda/findings/*` | **Finding sink** | High | durable verdicts; output of research, not a class |
| `notebooks/eda_00_integrity` | 1 Describe | High | integrity/missingness |
| `notebooks/eda_01_target` | 1 Describe | High | target distribution |
| `notebooks/eda_02_signals` | 1 Describe (+0) | High | profiling + scoping |
| `notebooks/eda_03_joint` | 3 Relationship | High | association/geometry |
| `notebooks/eda_04_population_validity` | 0 Scope | High | population validity |
| `notebooks/eda_05_signal_stability` | 2 Stability | High | block stability |
| `notebooks/eda_06_redundancy` | 4 Redundancy | High | partial-ρ redundancy |
| `notebooks/eda_07_signal_synthesis` | **ambiguous (→ model/assemble?)** | Low | exploratory *combination*; combination is `model/assemble`, but this is pre-firewall exploratory |
| `notebooks/eda_pop_boundary_scatter` | 1 Describe (+0) | High | descriptive boundary |
| `lenses/form` | 6 Validate | High | predictive, pre-registered (`LENS_DESIGN.md`) |
| `lenses/avail` | 6 Validate | High | predictive (binary target) |
| `lenses/market` | 6 Validate | High | predictive |
| `lenses/fixture_gw` | 6 Validate | High | predictive (same-GW target — see SoC note) |
| `experiments/minutes_stability_study.py` | **5 Conditioning** (confirmatory) | High | misfiled in `experiments/`; it is a validate-stage conditioning study |
| `experiments/rolling_xgi_study.py` | **6 Validate** | High | misfiled; predictive window-selection |
| `experiments/registry_sections_study.py` | **NOT research** (→ governance) | High | self-tagged "framework helper, no standalone verdict"; builds registry |
| `synthesis/synth01_study.py` | **NOT research** (→ model/assemble) | High | combination/weighting |
| `operational/phase9_backtest.py` | **NOT research** (→ archive) | High | monitor stage, dropped |

**Verdict on placement:** correctly *conceptually* but wrong *folder* for ~everything (the layer is organized by historical implementation: `eda/`, `lenses/`, `experiments/`). Three genuine ambiguities: `eda_08_study.py` (multi-class), `eda_07_signal_synthesis` (research vs model), and the `geometry`/`association`/`semantics` "study-layer copies" (duplication, not placement).

---

## Part 3 — Research Funnel Traceability

Chain: **Feature → Research Study → Finding → Governance Record → Decision Consumer.**

| Step | Link type | Evidence | Status |
|---|---|---|---|
| Feature → Study | **implicit / grep-only** | studies call `dal.pipeline.load`; no declared feature→study manifest | weak |
| Study → Finding | **explicit but scattered** | `eda/findings/*.csv` + finding statuses in docstrings + lens JSON outputs — *three different sinks* | partial |
| Finding → Governance | **semi-explicit (key-mediated)** | composite key `signal@lens:target[#POS]` (ADR-003) ties lens verdicts to `weight_registry.yaml` | partial |
| Governance → Consumer | **explicit / contract** | `intelligence` reads `outputs/registry/gw{N}/`; guard tests enforce | strong |

**Traceability score: 2 / 5.**

Navigation failures:
1. **Dual ID namespaces.** Findings still use `G-EDA*`, `LENS-*`, `EDA-N` (see `EDA_COVERAGE_MAP.md`) while governance uses composite keys — a manual translation gap between Finding and Governance.
2. **No single Finding index.** Verdicts live in `eda/findings/`, lens docstrings, *and* lens JSON outputs. A contributor cannot point to one place for "all findings."
3. **Feature→Study is grep-only.** No declared link from a `dal/feat` feature to the study that characterised it.
4. **eda_07 straddle** blurs where exploratory synthesis ends and `model/assemble` begins.

---

## Part 4 — Folder Architecture Assessment

| Folder | Owns | Clear? | New contributor understands? | Name matches strategy? |
|---|---|---|---|---|
| `studies/` | "analysis" (everything) | ✗ | ✗ — no entry point | ✗ (→ `research/`) |
| `studies/eda/` | one-time characterisation | partial | ✗ — mixes scope/describe/associate/redundancy in one dir | ✗ |
| `studies/eda/notebooks/` | the actual EDA, by historical number | partial | partial (numbers imply order) | ✗ (numbers ≠ classes) |
| `studies/eda/findings/` | durable verdicts | ✓ | ✓ | partial (no `findings/` in strategy yet) |
| `studies/lenses/` | predictive validation | ✓ | ✓ | partial (→ `04_validate/`) |
| `studies/experiments/` | **catch-all** | ✗ | ✗ | ✗ — holds a conditioning study, a validation study, *and* a registry-build helper |
| `studies/synthesis/` | combination | ✓ | partial | ✗ (belongs to `model/assemble`) |
| `studies/operational/` | backtest | partial | ✗ ("operational" reads like serve) | ✗ |
| `studies/kernels/` | pure stats toolbox | ✓ | ✓ | ✓ |

**Reflects historical implementation, not analytical purpose.** Highlights:
- **Mixed-responsibility:** `eda/` (4 classes in one dir), `experiments/` (3 unrelated things).
- **Misleading names:** `operational/` (sounds like serving), `experiments/` (sounds throwaway but holds the 31-test template and a build helper), `synthesis/` (a model concern).
- **Catch-all:** `experiments/`.
- **Funnel violations:** none structural — order is *latent* in `eda/` numbering but mis-sequenced (scope=04, stability=05 *after* associate=03).

**Design decision flagged:** STRATEGY.md's funnel ends in "Finding" but the target tree has no `findings/` folder. Recommend adding `research/findings/` as the single durable-verdict sink (closes Part 3 failures #1–2). This is an *additive clarification*, not a strategy change.

---

## Part 5 — Separation of Concerns Assessment

| Severity | Location | Issue | Recommended boundary |
|---|---|---|---|
| **High** | `eda/semantics.py`, `eda/geometry.py`, `eda/association.py` | "study-layer copies" with inlined governance/schema constants — duplication to dodge the import rule | geometry/association → `research/kernels/` (domain-agnostic); semantics → `model/governance/` |
| **High** | `experiments/registry_sections_study.py` | registry-build logic living in research; imported by registry-build tests | → `model/governance/` |
| **High** | `synthesis/synth01_study.py` | combination/weighting in research | → `model/assemble/` |
| **Medium** | `eda_07_signal_synthesis` | exploratory combination blurs research↔model | keep as exploratory in research OR move to `model/assemble` exploratory; decide explicitly |
| **Medium** | findings split across `findings/` + docstrings + lens JSON | ownership ambiguity for "the Finding" | single `research/findings/` index |
| **Medium** | `operational/phase9_backtest.py` | monitor concern in research | → `archive/` (monitor dropped) |
| **Low** | `fixture_gw` lens uses **same-GW** target (`total_points`), not `_next_gw` | it is a *contemporaneous predictor*, not a lag-respecting forecaster — fine, but should be labelled so it isn't read as out-of-sample | annotate in `04_validate/`; not a move |
| **Low** | `population/populations.py` (top-level) consumed by research, governance, serve | shared definition — correct as-is, just confirm it stays out of `research/` | keep in `population/` (shared) |

No DAL→research leakage found (research reads the mart via the canonical `dal.pipeline.load`). No research→serve leakage (guard tests enforce `intelligence` must not import `studies`).

---

## Part 6 — Target Mapping (complete)

| Current path | Target path | Reason |
|---|---|---|
| `studies/` (pkg) | `research/` | rename layer to its role |
| `studies/STRATEGY.md` | `research/STRATEGY.md` | doctrine moves with layer |
| `studies/kernels/**` | `research/kernels/**` | toolbox (keep names) |
| `studies/eda/geometry.py` | `research/kernels/geometry.py` | relationship-shape is a domain-agnostic kernel |
| `studies/eda/association.py` | `research/03_associate/relationship/association.py` | class 3 |
| `studies/eda/population.py` | `research/00_scope/population.py` | class 0 |
| `studies/eda/scoping.py` | `research/00_scope/scoping.py` | class 0 |
| `studies/eda/profiling.py` | `research/01_describe/profiling.py` | class 1 |
| `studies/eda/semantics.py` | `model/governance/semantics.py` | not research (governance vocab) |
| `studies/eda/eda_08_study.py` | `research/03_associate/eda_08_gap_study.py` | dominant class = associate/redundancy; keep whole (executable) |
| `studies/eda/EDA_08_DESIGN.md` | `research/03_associate/EDA_08_DESIGN.md` | with its study |
| `studies/eda/findings/**` | `research/findings/**` | single durable-Finding sink |
| `studies/eda/notebooks/eda_00_integrity.ipynb` | `research/01_describe/` | class 1 |
| `…/eda_01_target.ipynb` | `research/01_describe/` | class 1 |
| `…/eda_02_signals.ipynb` | `research/01_describe/` | class 1 (+scope) |
| `…/eda_pop_boundary_scatter.ipynb` | `research/01_describe/` | class 1 |
| `…/_integrity_helpers.py`, `_signal_distribution_helpers.py`, `_target_distribution_helpers.py` | `research/01_describe/` | helpers for class 1 |
| `…/eda_04_population_validity.ipynb` | `research/00_scope/` | class 0 |
| `…/eda_05_signal_stability.ipynb` | `research/02_stability/` | class 2 |
| `…/eda_03_joint.ipynb`, `_joint_helpers.py` | `research/03_associate/relationship/` | class 3 |
| `…/eda_06_redundancy.ipynb` | `research/03_associate/redundancy/` | class 4 |
| `…/eda_07_signal_synthesis.ipynb` | `model/assemble/` (exploratory) **[decision]** | combination concern |
| `studies/lenses/form/**` | `research/04_validate/form/**` | class 6 |
| `studies/lenses/avail/**` | `research/04_validate/avail/**` | class 6 |
| `studies/lenses/market/**` | `research/04_validate/market/**` | class 6 |
| `studies/lenses/fixture_gw/**` | `research/04_validate/fixture_gw/**` | class 6 |
| `studies/experiments/minutes_stability_study.py` | `research/03_associate/conditioning/minutes_stability_study.py` *(or `04_validate/`)* | conditioning study (confirmatory) — see note |
| `studies/experiments/rolling_xgi_study.py` | `research/04_validate/rolling_xgi_study.py` | class 6 window-selection |
| `studies/experiments/registry_sections_study.py` | `model/governance/registry_sections.py` | registry-build helper, not research |
| `studies/synthesis/synth01_study.py` | `model/assemble/composition_study.py` | combination/weighting + rename off ID code |
| `studies/operational/phase9_backtest.py` | `archive/monitor/phase9_backtest.py` | monitor dropped |

> **Note on `minutes_stability`.** Class 5 (conditioning) is *exploratory* in the funnel, but this study is *confirmatory* (pre-registered FRINGE-vs-STABLE test). Recommend `04_validate/` (it crossed the firewall) with its mode tag `conditioning`, rather than `03_associate/conditioning/`. Flagged as the one real placement judgment call.

---

## Part 7 — Phased Implementation Plan

Use `git mv` throughout (preserves history). Each phase = one PR. **Sequence Phase B *after* the `phase6-composite-key-migration` branch lands** — this blueprint assumes a clean main.

**Phase 1 — Structural prerequisites.**
- Objective: decouple moves from import-breaks; agree decisions.
- Files: none moved. Add `research/__init__.py` plan; resolve the two `[decision]` items (`eda_07`, `research/findings/`); pre-write the guard-test string updates (`test_dal_architecture`, `test_intelligence_outputs` assert *"must not import studies"* → `research`).
- Risk: low. Dependency order: first. Rollback: trivial (no moves).

**Phase 2 — Folder creation.**
- Objective: create the target tree empty.
- Files: `research/{kernels,00_scope,01_describe,02_stability,03_associate/{relationship,redundancy,conditioning},04_validate,findings}/__init__.py`.
- Risk: low. Order: after 1. Rollback: delete dirs.

**Phase 3 — Low-risk migrations (no Python importers).**
- Objective: move artifacts consumed only file-based or by humans.
- Files: `STRATEGY.md`, `eda/findings/` → `research/findings/`, `operational/` → `archive/`, `synthesis/synth01` → `model/assemble/` (verified: nothing imports `studies.synthesis`), the 8 EDA notebooks + helpers (only `eda_01`,`eda_02` import `studies`, internal), `profiling.py`, `scoping.py`, `semantics.py` → governance.
- Risk: low–medium (notebook internal imports). Order: after 2. Rollback: `git mv` back per file.

**Phase 4 — Validation-study migration.**
- Objective: relocate the confirmatory tier.
- Files: `lenses/*` → `04_validate/*` (consumers are file-based + string refs in `test_composite_key_migration`/`test_registry_lifecycle` — update strings); `experiments/minutes_stability_study.py`, `experiments/rolling_xgi_study.py` → `04_validate/` (update direct imports in `test_minutes_stability_study`, `test_rolling_xgi_study`, `…_real_validation`).
- Risk: medium (direct test imports). Order: after 3. Rollback: revert PR.

**Phase 5 — Cleanup + high-blast-radius.**
- Objective: kernels move, dedupe, governance relocation, ID retirement.
- Files: `kernels/**` → `research/kernels/**` (update ~8 test import paths); `eda/geometry.py` → `research/kernels/geometry.py` + delete the study-layer copy + repoint `registry_sections`, `_joint_helpers`, `test_relationship_geometry`; `eda/association.py` → `03_associate/relationship/`; `experiments/registry_sections_study.py` → `model/governance/` (repoint `test_registry_build_parity`, `test_relationship_computation`, registry build); retire `G-EDA*`/`LENS-*`/`EDA-N` codes in `research/findings/`; delete empty `studies/`; update `adlc.md §2/§4`, `layer-boundaries.md`, `downstream-dependency-governance.md`, navigation-map.
- Risk: high. Order: last. Rollback: revert PR (kept isolated for this reason).

---

## Part 8 — Diff-Level Refactor Plan (PR-ready)

Representative actions (full set = Part 6 rows). Format per request.

```
Action: KEEP
Current: studies/kernels/{distribution,stability,windows,redundancy,metrics,correlation/*}.py
Target:  research/kernels/ (folder move only, names unchanged)
Justify: already correct as the pure-stats toolbox; only the parent folder renames.
Risk:    Medium — ~8 test files import studies.kernels.*; update paths in same PR.

Action: MOVE
Current: studies/eda/population.py
Target:  research/00_scope/population.py
Justify: class 0 (eligibility/population validity).
Risk:    Low — only test_signals_population imports it.

Action: MOVE+RENAME
Current: studies/synthesis/synth01_study.py
Target:  model/assemble/composition_study.py
Justify: combination/weighting is model, not research; retire SYNTH-01 ID code.
Risk:    Low — no Python importer (writes yaml; consumed file-based).

Action: MOVE (promote to kernel) + DELETE duplicate
Current: studies/eda/geometry.py  (study-layer copy)
Target:  research/kernels/geometry.py
Justify: relationship-shape is domain-agnostic; removes the inlined-constants duplication smell.
Risk:    High — imported by registry_sections, _joint_helpers, test_relationship_geometry; repoint all.

Action: MOVE
Current: studies/experiments/registry_sections_study.py
Target:  model/governance/registry_sections.py
Justify: self-tagged "framework helper, no standalone verdict"; builds the registry.
Risk:    High — test_registry_build_parity + test_relationship_computation + registry build import it.

Action: MOVE
Current: studies/operational/phase9_backtest.py
Target:  archive/monitor/phase9_backtest.py
Justify: monitor stage dropped for a research platform.
Risk:    Low — referenced by docs only.

Action: MOVE
Current: studies/eda/semantics.py
Target:  model/governance/semantics.py
Justify: inlines governance vocab + enriches registry layers — a governance concern.
Risk:    Medium — registry-build chain consumer; repoint.

Action: CREATE
Current: —
Target:  research/findings/ (single durable-Finding sink) + research tier __init__.py files
Justify: closes traceability failures #1–2; gives "Finding" a home.
Risk:    Low.

Action: MOVE
Current: studies/lenses/{form,avail,market,fixture_gw}/
Target:  research/04_validate/{...}/
Justify: class 6, pre-registered (LENS_DESIGN.md is the firewall artifact).
Risk:    Medium — string path refs in key-migration/lifecycle tests.

Action: MOVE
Current: studies/experiments/minutes_stability_study.py, rolling_xgi_study.py
Target:  research/04_validate/
Justify: confirmatory predictive/conditioning studies misfiled in a catch-all.
Risk:    Medium — direct test imports; update in same PR.
```

---

## Part 9 — Final Verdict

**1. Does the current structure reflect the accepted strategy?**
**No — conceptually aligned, structurally not.** The analysis *is* per-position, leakage-controlled, and pre-registered (the lens `LENS_DESIGN.md` files), but the folders are organized by **historical implementation** (`eda/`, `experiments/`, `synthesis/`) rather than analytical class. A new contributor cannot read the tree as the funnel.

**2. Areas that align well (leave them):**
- `studies/kernels/` — correct boundary and name; pure, no governance imports.
- `studies/lenses/` — already the confirmatory tier, *with* pre-registration artifacts; only needs the `04_validate/` parent.
- `studies/eda/findings/` — durable findings correctly separated from code.
- The **per-position grain** and the **composite-key verdict identity** (ADR-003) — already enforce the strategy's evaluation grain.
- DAL↔research and research↔serve boundaries — clean, guard-tested.

**3. Architecturally inconsistent:**
- `experiments/` (catch-all: conditioning + validation + a build helper).
- `synthesis/` (model concern in research) and `operational/` (monitor concern, misleading name).
- `eda/` mixes 4 classes in one directory; numbering encodes a *mis-ordered* funnel.
- "Study-layer copies" (`geometry`, `association`, `semantics`) — duplication + one governance leak.
- Findings fragmented across three sinks; dual ID namespaces break Finding→Governance traceability.

**4. Minimum high-leverage change set** (in order of ROI):
1. **Rename `studies/ → research/` and split `eda/` into `00_scope`/`01_describe`/`02_stability`/`03_associate`** — the single change that makes the tree readable as the funnel.
2. **Dissolve `experiments/`**: conditioning + validation → `04_validate/`; `registry_sections` → `model/governance`.
3. **Move `synthesis/ → model/assemble`, `operational/ → archive`** — removes the two non-research concerns.
4. **Promote `geometry` to a kernel; relocate `semantics` to governance** — kills the duplication/leak.
5. **One `research/findings/` sink + retire `G-EDA*`/`LENS-*` in favour of composite keys** — restores traceability (2/5 → 4/5).

Everything else is cosmetic.

**5. Do NOT change (already matches target):**
- `kernels/` internals and naming.
- The lens **methodology** and its `LENS_DESIGN.md` pre-registration pattern.
- The per-position evaluation grain and composite-key scheme.
- The DAL contract and the research↔serve guard tests.
- `population/populations.py` and `domain/fpl_scoring.py` (shared, correctly outside research).

**Bottom line:** this is a **folder-and-name migration, not an analytical redesign.** The strategy is already honoured in behaviour; the work is making the repository *legible* — renaming three layers, splitting one directory by class, dissolving one catch-all, and relocating three non-research concerns. No new analytical concepts required.
