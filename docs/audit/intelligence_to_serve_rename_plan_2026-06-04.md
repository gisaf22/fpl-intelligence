# `intelligence/` → `serve/` Rename — Migration Plan

**Status:** PROPOSED (not started). The remaining half of the deferred object-primary
topology step (memory `project-phase7-signals-serve-consolidation`). The `signals →
governance` half completed at commit `dfcfd5c`; this renames the top (serve) layer.

**Scope:** rename the `intelligence/` Python package to `serve/`. This is a **pure rename**
(relabel the box) — no code moves between layers, no responsibilities change. The layer
order stays `dal → research → model → serve`, with `domain/registry/` as the shared leaf.

> **Why low-risk but wide.** `intelligence/` is the top layer: **nothing imports it** except
> itself and the test suite (verified — zero `from intelligence` / `import intelligence`
> outside `intelligence/` + `tests/`). So there is no upstream consumer to break. The cost is
> breadth, not depth: 21 package modules, ~21 test files, the import-linter root + one named
> contract, the mypy/pre-commit file lists, the `test_dal_architecture` guard, a handful of
> path strings, and the `signal_traceability.yaml` consumer_modules lists.

---

## 0. Current state

`intelligence/` (21 `.py` modules + `weight_registry.yaml`):

```
intelligence/
  __init__.py  availability.py  captain.py  fixtures.py  intelligence_contracts.py
  provenance.py  transfers.py  value.py  weight_registry.py  weight_registry.yaml
  reporting/  __init__.py insight_card_writer.py reports.py signal_intelligence.py
             snapshots.py weekly_report_runner.py
  scoring/   __init__.py contracts.py engine.py renderer.py scoring_runner.py signal_selector.py
```

### What references `intelligence` (the package)

| Surface | Detail |
|---|---|
| Internal imports | within `intelligence/` (self-references — move with the rename) |
| Test imports | 21 test files import `intelligence.*` |
| External imports | **none** (top layer) |
| Path strings (code) | `provenance.py` (2 `registry_source` strings), `weight_registry.py` (`_WEIGHT_REGISTRY_PATH`), tests (`test_runtime_consumer_alignment`, `test_spine_traversal_metadata`, `test_downstream_governance`, `test_dal_architecture`) |
| `.importlinter` | `intelligence` is a root package + source of `no_intelligence_to_research_or_model` + appears in 4 other contracts' `forbidden_modules` |
| `pyproject.toml` | mypy `files = [..., "intelligence", ...]` (NB: `name = "fpl-intelligence"` is the **distribution** name — out of scope, leave it) |
| `.pre-commit-config.yaml` | `files: ^(dal\|signals\|intelligence\|domain\|population)/` (also still lists the now-deleted `signals` — fix in passing) |
| `test_dal_architecture.py` | `INTELLIGENCE_ROOT`, test names, the "intelligence must not import research" guard |
| `weight_registry.yaml` | header comments ("the intelligence layer") |
| `model/governance/signal_traceability.yaml` | `consumer_modules` lists `intelligence/captain.py`, `value.py`, `transfers.py` (×6 blocks) |
| Docs | 42 `.md` files mention "intelligence"; most use it as a generic word. Repoint **package-path** refs in the authoritative set + `intelligence-layer.md` |

---

## 1. `.importlinter` changes

- `root_packages`: `intelligence` → `serve`.
- Rename contract `no_intelligence_to_research_or_model` → `no_serve_to_research_or_model`;
  `source_modules: intelligence` → `serve`.
- Replace `intelligence` → `serve` in `forbidden_modules` of `no_domain_to_anything`,
  `no_population_to_upper_layers`, `no_research_to_downstream`, `no_dal_to_system_layers`.
- Contract count unchanged at **6**; verify `lint-imports` reports 6 kept, 0 broken.

---

## 2. PR phasing — gate green each PR

> Convention: one PR = one commit; full green gate before commit; pause for review after each.
> Because this is one atomic rename (the package can't half-exist), the natural split is
> **code+config in one PR, docs in a second** — mirroring how the prior migrations batched docs.

- **S-PR-1 — Rename the package + all code/test/config refs (one commit).**
  `git mv intelligence serve`. Then repoint, in order:
  1. Python imports: `from intelligence` / `import intelligence` → `serve` across `serve/`
     internals + 21 test files.
  2. Path strings: `Path("intelligence/...")` and the `provenance.py` `registry_source`
     strings → `serve/...`; `weight_registry.py` `_WEIGHT_REGISTRY_PATH`.
  3. `.importlinter` (§1), `pyproject.toml` mypy `files`, `.pre-commit-config.yaml` regex
     (drop `signals`, swap `intelligence`→`serve`).
  4. `test_dal_architecture.py`: `INTELLIGENCE_ROOT` → `SERVE_ROOT`, test/function names,
     guard docstrings.
  5. `model/governance/signal_traceability.yaml`: `consumer_modules` `intelligence/*` → `serve/*`.
  6. `weight_registry.yaml` header comments.
  Gate: ruff / mypy (70 files; `serve` replaces `intelligence` in scope) / lint-imports 6 kept
  / full suite green.

- **S-PR-2 — Docs refresh.** Repoint package-path references in the authoritative docs
  (`layer-boundaries.md`, `CONTEXT.md`, `navigation-map.md`) and `intelligence-layer.md`
  (rename the file → `serve-layer.md` and update inbound links, or keep the filename and
  retitle — decide at execution). Leave generic-word uses of "intelligence" (e.g. "signal
  intelligence report") and historical audit/archive docs untouched.

---

## 3. Risk analysis

- **Lowest structural risk of the three migrations** — no consumer imports the package, so the
  rename cannot break an upstream layer. The import-linter root swap is mechanical.
- **Sneaky:** the `provenance.py` `registry_source` strings and `weight_registry.py` path are
  not caught by mypy/import-linter — only by tests that load `weight_registry.yaml`
  (`test_spine_traversal_metadata`, `test_runtime_consumer_alignment`). Confirm they exercise
  the new path.
- **`signal_traceability.yaml` consumer_modules** are read by `test_traceability_completeness`
  (non-empty check) — repoint for accuracy even though the test won't fail on stale paths.
- **Stale `signals` in `.pre-commit-config.yaml`** — pre-existing drift from the consolidation;
  fix while we're in the file.
- **Distribution name** `fpl-intelligence` in `pyproject.toml` — intentionally **not** renamed
  (package import name ≠ PyPI/dist name; changing it is unrelated churn).

---

## 4. Out of scope

- Renaming the distribution/project name `fpl-intelligence`.
- Any behavioral change to scoring, reporting, or governance.
- The broad historical docs pile (audit/archive) — generic "intelligence" word usage stays.
