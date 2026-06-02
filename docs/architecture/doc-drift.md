# Documentation Drift Inventory

**What this is:** a one-time audit of `docs/` against the actual code, produced 2026-06-02
alongside `adlc.md`. It lists every place a doc authoritatively cites a path, module, directory,
or count that **no longer exists** in the repository.

**Why it matters:** a doc that confidently sends a reader to `signals/registry/` — a directory
that was renamed away — is *worse than no doc*. It costs trust and time. The `docs/` tree is
well-structured (it has a `navigation-map.md`, authority tables, reading-orders-by-role), but it
has fallen out of sync with the code after the DAL/signals refactors. This inventory is the
punch-list to re-sync it.

**Scope:** active docs only (`docs/**/*.md`). `docs/archive/` is intentionally excluded — archived
docs are historical records and are *expected* to reference old structure.

> **Scope gap — drift is NOT confined to `docs/`.** This sweep covered Markdown only. A later
> verification of governance artifacts found the same drift inside **code-adjacent config**:
> `signals/governance/weight_registry.yaml` points to `signals/evaluation/synth01_decisions.yaml`,
> but the real path is `signals/governance/synth01_decisions.yaml`. That matters more than a stale
> doc, because `intelligence/weight_registry.py` reads these YAMLs and **hard-fails** on bad keys.
> **The `.yaml`/`.py` config layer has not been swept** and should be, as a follow-up — at minimum
> `signals/**/*.yaml`, `*/contracts*.py`, and any module docstring citing a path. Treat the doc
> drift below as the *visible* portion of a larger sync debt.

**Status:** diagnostic only. This PR fixes nothing; it records the drift so a later cleanup PR
can act on it. `adlc.md` §8 depends on this being fixed first.

---

## 1. Stale path → real path (the substitution table)

These are the renames the docs missed. Find-and-replace candidates, but **verify each in context**
— some docs describe a *role* that also moved, not just a path.

| Doc says (stale) | Reality in code | Notes |
|---|---|---|
| `signals/registry/` | `signals/characterisation/` (build) + `signals/governance/` (lifecycle) | the single biggest drift — 14 docs |
| `signals/lifecycle/` | `signals/governance/lifecycle.py` | 7 docs |
| `signals/evaluation/EVAL_DESIGN.md` | `signals/governance/EVAL_DESIGN.md` | 10 docs |
| `signals/eda/`, `signals/lenses/`, `signals/synthesis/`, `signals/experiments/` | `studies/eda/`, `studies/lenses/`, `studies/synthesis/`, `studies/experiments/` | research lives under `studies/`, not `signals/` — `research-lifecycle.md` has this throughout |
| `signals/registry/SIGNAL_REGISTRY.md` | `signals/characterisation/SIGNAL_REGISTRY.md` | |
| `dal/curated/`, `dal/state/` | `dal/fct/`, `dal/feat/` | the layer rename `curated→fct`, `state→feat` is not reflected |
| `dal/prepared/`, `dal.prepared.analytical_dataset` | `dal/mart/`, `dal.pipeline.load` / `dal.pipeline.run` | |
| `dal.get_analytics_dataset(db_path)` | `dal.pipeline.load()` | the canonical entry point changed |
| `intelligence/_base.py` | `intelligence/intelligence_contracts.py` | the function `validate_intelligence_inputs()` lives in `intelligence_contracts.py`. Stale `_base.py` appears in `decision-lifecycle.md`, `system-model.md`, `intelligence-layer.md`. NB: `layer-boundaries.md` cites the **correct** path — do not "fix" it |
| `core/governance/`, `core/signals/` | no `core/` package exists | `research-lifecycle.md` |
| `scorer/`, `report/` | `intelligence/scoring/`, `intelligence/reporting/` | 6 docs use the bare top-level names |

---

## 2. Dangling references — cited but does not exist at all

| Reference | Cited in | Problem |
|---|---|---|
| `docs/adr/006-layer-architecture.md`, `docs/adr/010-enforcement-contract.md`, `docs/adr/012-dal-design-rationale.md` | `testing-strategy.md`, `system-purpose.md` | **`docs/adr/` directory does not exist.** These are cited as the *source of authority* for import contracts and DAL rationale — a load-bearing citation pointing at nothing |
| `signals/registry/runner.py`, `signals/registry/builder.py` | `system-model.md`, `decision-lifecycle.md` | both gone. Real: `signals/characterisation/registry_build_runner.py` and `registry_assembler.py` (note: "assembler", not "builder") |
| `studies/runs/` as durable artifact store | `layer-boundaries.md` | these are timestamped throwaway run dirs (the ID-diet targets them) — not a durable interface |

---

## 3. Stale counts and figures

| Claim | Doc | Reality |
|---|---|---|
| "Total tests: 739 (738 passing, 1 skipped)" | `testing-strategy.md` | **897** test functions (`grep -rc "def test_"`); CI runs 858 unit tests |
| "DB-free (unit): 655 / Integration: 84" | `testing-strategy.md` | breakdown stale by the same drift |

**Verified correct (not drift):** "Import-linter contracts: 6 active" — `.importlinter` exists
and defines exactly 6 contracts. `outputs/registry/gw36/` exists, so `decision-lifecycle.md`'s
`outputs/registry/gw{N}/` references are accurate. Do not touch these.

---

## 4. Competing-vocabulary overlap (not drift, but related)

Three architecture models coexist by design — but the overlap compounds the maintenance burden,
because a single rename has to be chased across all three vocabularies:

- **4-layer import hierarchy** — `layer-boundaries.md`, `navigation-map.md`
- **3-plane model** (Control / Execution / Measurement) — `system-model.md`, `system-purpose.md`
- **4-stage decision lifecycle** — `decision-lifecycle.md`

`adlc.md` adds a **5-stage + mode-tag** framing. **Decided (see `adlc.md` §8):** `adlc.md` is the
sole owner of the word "lifecycle"; `decision-lifecycle.md` + `operational-flow.md` **merge into a new
`runtime-execution.md`** (keep the failure-mode tables + 3-command sequence; drop "lifecycle" and the
4-stage framing). This is a design decision executed *as part of* the drift fix — see step 4 below.

---

## 5. Fix order — EXECUTED in the drift-cleanup PR

1. ✅ **Dangling references fixed** (§2) — the `docs/adr/*` citations pointed at a directory that
   doesn't exist; removed them (no ADRs were created), citing the real source (`.importlinter`, code).
2. ✅ **Substitution table run** (§1) doc-by-doc. The two migration **changelogs**
   (`platform-evaluation-2026.md`, `eng-issues-2026.md`) were **deliberately left untouched** — they
   document the renames, so the old paths are correct historical content there (same rule as `archive/`).
3. ✅ **Counts de-hard-coded** (§3) — `testing-strategy.md` now cites the CI job, not a frozen number.
4. ✅ **Lifecycle merge executed** (§4): `runtime-execution.md` created from `decision-lifecycle.md` +
   `operational-flow.md`; both source docs deleted; cross-linked from `adlc.md`. The broken `Makefile`
   was deleted (CI never used it; its only non-trivial targets pointed at nonexistent modules) and its
   commands moved into `runtime-execution.md` as the single runbook.
5. ✅ **`navigation-map.md` re-pointed** to `adlc.md` + `runtime-execution.md`.

**Still open (not done here):** the config-layer sweep flagged in the scope note above
(`signals/**/*.yaml`, module docstrings) — e.g. `weight_registry.yaml` → `signals/evaluation/...`.
That is a code-adjacent change and was left for a follow-up.

Worst offenders (now fixed): `research-lifecycle.md` (was stale throughout — `signals/eda`, `core/`,
`scorer/`, `report/`), `system-model.md`, and the now-merged `decision-lifecycle.md`.
