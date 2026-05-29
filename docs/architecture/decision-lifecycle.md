# Decision Lifecycle

**Authoritative for:** the full flow from raw database state to a scored player output, and what the future measurement feedback loop will look like.  
**Companion:** [system-model.md](system-model.md) for plane classification · [layer-boundaries.md](layer-boundaries.md) for import rules.

---

## Overview

A single FPL decision (e.g. "rank captain candidates for GW 28") travels through four stages:

```
Stage 1: DAL         raw database state → validated (player_id, gw) features
Stage 2: Registry    governed signal manifest → scoring configuration loaded
Stage 3: Intelligence  features + configuration → ranked, scored output
Stage 4: Output       scored tables / weekly HTML report

[Stage 5: Measurement — not yet implemented]
future: actual GW returns → quality assessment → registry feedback
```

Each stage has a clear input contract, a clear output contract, and a defined failure mode. Stages 1–4 are implemented. Stage 5 is the Measurement Plane; only its design specification exists (`signals/evaluation/EVAL_DESIGN.md`).

---

## Stage 1 — DAL: Raw State → Validated Features

**What happens:**  
The DAL reads from the source database (`fpl.db`) and produces the canonical `(player_id, gw)` spine with validated state features. Every active player appears in every gameweek, including blank gameweek rows. Rolling window features, lag features, and derived state columns are computed here and nowhere else.

**Entry point:**
```python
from dal.access import get_curated_spine, get_state_features
spine    = get_curated_spine(db_path)      # (player_id, gw) grain, all GWs
features = get_state_features(spine)       # spine + rolling window columns
```

**Depends on:**  
- `fpl.db` populated by the upstream `fpl-ingest` pipeline.  
- No registry, no signal definitions, no scoring configuration. The DAL is configuration-free.

**Produces:**  
A `DataFrame` at `(player_id, gw)` grain with guaranteed columns: fixture context, performance history, rolling windows (roll3, roll5, roll8), lag features, BGW/DGW flags, availability signals. Schema is contractual — see `dal/fct/fct_contracts.py` (SPINE_COLS, DTYPES, NULL_RULES).

**What failure looks like:**
| Failure | Symptom | Source |
|---|---|---|
| Missing source tables | `KeyError` or empty DataFrame in staging | `fpl.db` not populated |
| Grain violation | Duplicate `(player_id, gw)` rows | Bug in curated layer join logic |
| Temporal causality breach | Feature uses future GW data | State layer using wrong lag |
| NULL semantics violation | Zero where NULL expected or vice versa | Staging null-handling error |
| Warmup period | Null roll3/roll5 values in early GWs | Expected behavior; GW 1–2 are warm-up period |

The DAL has no knowledge of what these features will be used for. It produces a validated data contract; downstream layers decide what to do with it.

---

## Stage 2 — Registry: Governed Signal Manifest

**What happens:**  
The scoring runner loads the governed registry artifact from `outputs/registry/gw{N}/`. This is a Control Plane operation: the manifest declares which signals exist, their Spearman rho values, promotion classes, and layer roles. This configuration drives what the scorer will do.

The lifecycle gate is enforced here:
```python
from signals.lifecycle.lifecycle import assert_operational_safe
assert_operational_safe(registry_path)
# Raises LifecycleViolationError if path is not under outputs/registry/
```

This gate exists because a registry under `studies/eda/findings/` is exploratory — its signals have not passed lens validation. Using it operationally would mean scoring against unconfirmed signal definitions.

**Depends on:**  
- `outputs/registry/gw{N}/registry.csv` — built offline by `signals/registry/runner.py` after lifecycle promotion.  
- `outputs/registry/gw{N}/build_metadata.json` — provenance record confirming the manifest was built correctly.

**Produces:**  
A signal configuration: which signals are confirmed (`core_signal`, `review_signal`), what their `rho_pooled` weights are, which signals are excluded and why. This configuration is what makes the scorer's behavior auditable and tied to evidence.

**What failure looks like:**
| Failure | Symptom | Source |
|---|---|---|
| Exploratory registry path | `LifecycleViolationError` | Passing a `studies/eda/findings/` path to an operational runner |
| Missing registry file | `FileNotFoundError` | `outputs/registry/gw{N}/` not bootstrapped |
| Schema contract violation | `validate_registry_contract()` raises | Registry CSV missing required columns |
| Zero confirmed signals after filtering | Empty scorer output | All signals below rho threshold, wrong promotion class, or excluded by role |
| Stale registry | GW N registry used for GW M scoring | Mismatch between registry build GW and scoring GW |

**The registry is not a pipeline stage.** It does not transform data. It is a configuration artifact read once at the start of each scoring run.

---

## Stage 3 — Intelligence: Features + Configuration → Ranked Output

**What happens:**  
`intelligence/scoring/` applies the registry-defined signal filters and rho weights to the DAL features. Three sequential filters narrow the signal set:

1. **Promotion class:** `promotion_class in {core_signal, review_signal}` — only EDA-confirmed signals
2. **Role exclusion:** `layer_role not in {points_component, contribution_index}` — no leakage signals
3. **Minimum rho:** `abs(rho_pooled) >= 0.15` — only signals with directional strength

Each confirmed signal is normalised within position to `[0, 1]`, then combined into a weighted composite:

```
composite = Σ(normalised_value_i × |rho_i|) / Σ(|rho_i|)
```

Players are ranked by composite within position. The composite and all component scores are included in the output — nothing is hidden.

In parallel, the `intelligence/` evaluation functions (captain, transfers, value, availability, fixtures) each apply their own explicit static weights to DAL features, independently of the registry-weighted scorer.

**Depends on:**  
- Stage 1 output: validated DAL features DataFrame  
- Stage 2 output: governed registry manifest with confirmed signals  
- Input validation: `intelligence/_base.py:validate_intelligence_inputs()` checks required columns are present

**Produces:**  
- `ScorerOutput`: list of `PlayerScore` objects with `composite_score`, per-signal raw and normalised values, and excluded signal reasons
- Ranked DataFrames from captain/transfer/value/availability/fixture functions
- The HTML report surface at Stage 4

**What failure looks like:**
| Failure | Symptom | Source |
|---|---|---|
| Missing DAL columns | `IntelligenceInputError` from `validate_intelligence_inputs()` | DAL not run or wrong DataFrame passed |
| Research proxy used instead of DAL features | `IntelligenceInputError` | EDA registry DataFrame passed to intelligence function |
| No confirmed signals | Empty `ScorerOutput.confirmed_signals` | Registry filtering eliminates all signals (see Stage 2) |
| Normalisation collapse | All players same score | All values for a signal are identical; handled via constant → 0.5 |
| Warmup null values | Low-confidence scores in early GWs | Expected; roll3/roll5 nulls filled with 0 |

---

## Stage 4 — Output: Artifacts

**What happens:**  
The execution plane produces its artifacts. These are the final system outputs consumed by the FPL decision maker.

**Artifacts produced:**

| Artifact | Path | Committed? |
|---|---|---|
| Governed registry manifest | `outputs/registry/gw{N}/registry.csv` | Yes (bootstrap only) |
| Registry build provenance | `outputs/registry/gw{N}/build_metadata.json` | Yes (bootstrap only) |
| Scored player HTML | `outputs/scorer/gw{N}_player_scores.html` | No — regenerated each run |
| Weekly signal intelligence report | stdout / DB snapshot | No |

The HTML output includes full explainability: per-signal component bars, rho weights in column headers, excluded signal reasons, and a methodology note. A reviewer with the HTML and the registry CSV can independently reconstruct any player's rank. See [explainability-model.md](explainability-model.md).

**What failure looks like:**  
Failures here are surfaced as missing files, empty HTML sections, or wrong GW in the output header. They typically trace back to Stage 1 (no DB data for the target GW) or Stage 3 (no confirmed signals after filtering).

---

## Stage 5 — Measurement (not yet implemented)

**What would happen:**  
After GW N resolves, actual FPL returns become available. The Measurement Plane would compare the system's ranked output for GW N against actual points, assess whether the ranking predicted performance, and feed that assessment back into the signal evaluation record.

**The design contract exists.** `signals/evaluation/EVAL_DESIGN.md` defines the locked success criteria and failure conditions for the 2025-26 methodology. When measurement is implemented, its outputs will be compared against these criteria.

**The implementation does not exist.** No mechanism captures system outputs at decision time, retrieves actual GW returns, or computes decision quality metrics.

```
[Future feedback loop]

Stage 4 outputs (GW N ranked decisions)
          ↓
    [capture at decision time]
          ↓
    actual GW N returns
          ↓
    quality assessment vs. EVAL_DESIGN.md criteria
          ↓
    findings → inform registry updates for GW N+1 / next season
```

**What this means for the current system:**  
The system produces correct, auditable, deterministic outputs — but without measurement, there is no empirical feedback loop confirming that those outputs lead to better FPL decisions. The system is built to be measurable. It is not yet being measured.

---

## Lifecycle mapping to planes

| Stage | Plane | Purpose |
|---|---|---|
| Stage 1: DAL | Execution | Produces validated runtime features |
| Stage 2: Registry | Control | Loads scoring configuration |
| Stage 3: Intelligence | Execution | Applies configuration to features |
| Stage 4: Output | Execution | Surfaces artifacts for decision making |
| Stage 5: Measurement | Measurement | Closes the feedback loop (incomplete) |

---

## The full run command sequence

```bash
# Prepare the DAL (Stage 1)
make prepare          # python -m dal.access --db fpl.db

# Build the registry (Control Plane — offline)
make build-registry   # python -m signals.registry.runner --gw N

# Score and report (Stages 2–4)
make weekly           # python -m intelligence.scoring.runner + reporting runner
```

Three commands. The first validates the data contract. The second assembles the configuration artifact. The third executes the decision pipeline. They are independent; each can be re-run without re-running the others.
