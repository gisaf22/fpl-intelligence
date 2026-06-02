# Runtime Execution

**What this is:** how the *built* system runs each gameweek — the command sequence, the stage
inputs/outputs, and what failure looks like at each step. This is the **execution** path, not the
analysis lifecycle.

**Companion:** [adlc.md](adlc.md) owns the *analysis lifecycle* (`explore → validate → model →
serve → monitor`) — how signals get researched and chosen. This doc is the seam ADLC calls `serve`
+ `monitor`: running the model that the lifecycle produced. For *what each component is for*
(the 3-plane model), see [system-model.md](system-model.md).

> This doc supersedes the former `decision-lifecycle.md` and `operational-flow.md`. There is no
> Makefile — its run targets had drifted to nonexistent module paths; the commands below are the
> single source of truth and are verified against the code.

---

## The run sequence

Four steps. Each is independent and re-runnable; replace `36` with the target gameweek.

```bash
# 1. Build the analytical dataset (the mart). Requires the live DB.
python -m dal.pipeline run          # build mart.parquet + manifest
python -m dal.pipeline load         # (optional) validate + inspect the built mart

# 2. Build the governed registry artifact for the gameweek.
python -m signals.characterisation.registry_build_runner --gw 36

# 3. Score players against the governed registry.
python -m intelligence.scoring.scoring_runner --gw 36

# 4. Generate the weekly signal intelligence report.
python -m intelligence.reporting.weekly_report_runner --gw 36
```

Tests and import checks (CI runs `pytest` directly; these are the local equivalents):

```bash
pytest -m "not integration"   # DB-free unit + contract tests (fast)
pytest                        # full suite (requires the live/fixture DB)
lint-imports                  # enforce the 6 import contracts in .importlinter
```

---

## Stage 1 — DAL: raw state → validated features

The DAL (`dal/`) reads the source database and produces the canonical `(player_id, gw)` mart with
validated state features. Every active player appears in every gameweek, including blank-gameweek
rows. Rolling-window, lag, and derived state columns are computed here and nowhere else.

**Entry point:** `from dal.pipeline import load as load_mart; mart = load_mart().mart`
**Depends on:** `~/.fpl/fpl.db` (populated by the upstream `fpl-ingest` pipeline). No registry, no
signal definitions — the DAL is configuration-free.
**Produces:** a DataFrame at `(player_id, gw)` grain with a contractual schema
(`dal/fct/fct_contracts.py`, `dal/feat/feat_schema.py`, `dal/mart/mart_schema.py`).

| Failure | Symptom | Source |
|---|---|---|
| Missing source tables | `KeyError` / empty DataFrame in staging | `fpl.db` not populated |
| Grain violation | duplicate `(player_id, gw)` rows | bug in the fct join logic |
| Temporal causality breach | a feature uses future-GW data | state layer using the wrong lag |
| NULL semantics violation | zero where NULL expected (or vice versa) | staging null-handling error |
| Warmup period | null `roll3`/`roll5` in early GWs | expected; GW 1–2 are warm-up |

---

## Stage 2 — Registry: governed signal manifest

`signals.characterisation.registry_build_runner` assembles the governed registry artifact under
`outputs/registry/gw{N}/`. It declares which signals exist, their rho weights, promotion classes,
and layer roles. The lifecycle gate is enforced here:

```python
from signals.governance.lifecycle import assert_operational_safe
assert_operational_safe(registry_path)   # raises if path is not under outputs/registry/
```

A registry under `studies/eda/findings/` is *exploratory* — its signals have not passed lens
validation. Path determines operational safety, not content.

**Depends on:** `outputs/registry/gw{N}/registry.csv` + `build_metadata.json`.
**Produces:** the signal configuration that makes the scorer auditable and tied to evidence.

| Failure | Symptom | Source |
|---|---|---|
| Exploratory registry path | `LifecycleViolationError` | passing a `studies/eda/findings/` path operationally |
| Missing registry file | `FileNotFoundError` | `outputs/registry/gw{N}/` not bootstrapped |
| Schema contract violation | registry-contract validation raises | registry CSV missing required columns |
| Zero confirmed signals | empty scorer output | all signals below threshold / wrong class / excluded |
| Stale registry | GW N registry used for GW M scoring | registry-build GW ≠ scoring GW |

**The registry is not a pipeline stage.** It does not transform data — it is configuration read
once at the start of each scoring run.

---

## Stage 3 — Intelligence: features + configuration → ranked output

`intelligence/scoring/` applies the registry's signal filters and rho weights to the DAL features.
Three sequential filters narrow the set: promotion class ∈ {core, review}; role exclusion (no
leakage signals); minimum |rho|. Each confirmed signal is normalised within position to `[0, 1]`,
then combined:

```
composite = Σ(normalised_value_i × |rho_i|) / Σ(|rho_i|)
```

In parallel, the `intelligence/` decision functions (captain, transfers, value, availability,
fixtures) apply their own static weights to DAL features.

> **Governance note.** Those module weights are `PROVISIONAL-EDITORIAL` (see
> `signals/governance/weight_registry.yaml`) — editorial judgments, not yet calibrated. Only the
> SYNTH-01 signal-composition weights (DEF/MID) are evidence-based. See `adlc.md` §4.

**Depends on:** Stage 1 features + Stage 2 registry. Inputs validated by
`validate_intelligence_inputs()` in `intelligence/intelligence_contracts.py`.
**Produces:** `ScorerOutput` (per-signal raw + normalised values, excluded-signal reasons) and the
ranked decision tables.

| Failure | Symptom | Source |
|---|---|---|
| Missing DAL columns | `IntelligenceInputError` | DAL not run / wrong DataFrame passed |
| Research proxy used | `IntelligenceInputError` | an EDA registry DataFrame passed to intelligence |
| No confirmed signals | empty `ScorerOutput.confirmed_signals` | registry filtering eliminated all signals |
| Normalisation collapse | all players same score | a signal's values are identical (constant → 0.5) |

---

## Stage 4 — Output: artifacts

| Artifact | Path | Committed? |
|---|---|---|
| Governed registry manifest | `outputs/registry/gw{N}/registry.csv` | yes (bootstrap only) |
| Registry build provenance | `outputs/registry/gw{N}/build_metadata.json` | yes (bootstrap only) |
| Scored player HTML | `outputs/scorer/gw{N}_player_scores.html` | no — regenerated each run |
| Weekly signal intelligence report | stdout / DB snapshot | no |

The HTML includes full explainability (per-signal component bars, rho weights, excluded-signal
reasons). See [explainability-model.md](explainability-model.md).

---

## Stage 5 — Measurement (not yet built)

After GW N resolves, actual returns become available; the Measurement step would compare the ranked
output against actual points and feed the assessment back into signal evaluation. **Only the design
exists** (`signals/governance/EVAL_DESIGN.md`) — no mechanism yet captures outputs at decision time,
retrieves returns, or computes decision-quality metrics. This is the `monitor` stage in
[adlc.md](adlc.md), and closing it (plus the editorial-weight calibration) is the project's main
remaining engineering. The system is built to be measurable; it is not yet being measured.

---

## Plane mapping (pointer)

| Stage | Plane | See |
|---|---|---|
| 1 DAL · 3 Intelligence · 4 Output | Execution | [system-model.md](system-model.md) |
| 2 Registry | Control (configuration) | [system-model.md](system-model.md) |
| 5 Measurement | Measurement (design-only) | `signals/governance/EVAL_DESIGN.md` |
