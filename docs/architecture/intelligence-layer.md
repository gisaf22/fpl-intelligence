# Intelligence Layer

## Purpose

The intelligence layer (`intelligence/`) produces concrete FPL decision-support outputs
from trusted, governed signal data. It sits at the top of the data pipeline:

```
fpl.db (source database)
  ↓
dal/ — validated, deterministic (player_id, gw) spine + state features
  ↓
outputs/registry/gw{N}/ — governed signal registry artifact
  ↓
intelligence/ — player scoring and weekly reporting  ← this layer
```

The layer answers: *"Can FPL-derived signals improve FPL decisions?"* through explicit,
reproducible artifacts — not through infrastructure alone.

---

## Registry consumption and lifecycle gate

The intelligence layer never reads directly from `studies/eda/findings/`. It consumes only
governed registry artifacts from `outputs/registry/gw{N}/`.

The gate is enforced at runtime by `signals/governance/lifecycle.py`:

```python
# Both operational runners call this before loading any registry:
assert_operational_safe(registry_path)
# Raises LifecycleViolationError if registry_path is under studies/eda/
```

This means the registry can only reach the scorer after:
1. Signals have `promotion_class` in `{core_signal, review_signal}` from system EDA
2. The registry builder (`signals/characterisation/registry_build_runner.py`) has validated the contract and written to `outputs/registry/gw{N}/`
3. The operational runner receives the path via `--registry-path outputs/registry/gw{N}/registry.csv`

See [docs/registry-governance.md](../registry-governance.md) for the full exploratory-vs-operational distinction.

---

## Signal filtering in the scorer

`intelligence/scoring/signal_selector.py` applies three filters when loading a registry:

| Filter | Condition | Rationale |
|--------|-----------|-----------|
| Promotion class | `promotion_class in {core_signal, review_signal}` | Only EDA-confirmed signals |
| Role exclusion | `layer_role not in {points_component, contribution_index}` | Leakage and outcome-component signals excluded |
| Non-null rho | `rho_pooled` not null (lens CI gate) | `MIN_RHO = 0.15` was removed; the CI gate is the sole magnitude authority |

After filtering, each retained signal contributes to composite scores weighted by its `rho_pooled`
value. Stronger correlations carry more weight; the weighting is transparent and declared in the
registry artifact, not hidden in code constants.

## Operational Outputs

Each output function accepts a features DataFrame produced by the canonical DAL entry points:

```python
from dal.pipeline import load as load_mart
from intelligence import (
    rank_captain_candidates,
    rank_transfer_targets,
    rank_value_players,
    flag_availability_risk,
    rank_fixture_opportunities,
)

features = load_mart().mart

captains  = rank_captain_candidates(features, target_gw=28)
transfers = rank_transfer_targets(features, target_gw=28)
value     = rank_value_players(features, target_gw=28)
risk      = flag_availability_risk(features, target_gw=28)
fixtures  = rank_fixture_opportunities(features, target_gw=28)
```

### Captain Candidates (`captain.py`)

Ranks players as captain options for a target gameweek.

| Component | Signal | Weight |
|-----------|--------|--------|
| `form_score` | `points_roll3` within position | 35% |
| `involvement_score` | `xgi_roll3` within position | 30% |
| `fixture_score` | `6 - fdr_avg` within position | 20% |
| `minutes_score` | `minutes_roll3` within position | 15% |

**Eligibility:** `minutes_roll3 >= 45` (must be starting reliably).

---

### Transfer Targets (`transfers.py`)

Identifies incoming transfer candidates with rising form and favorable conditions.

| Component | Signal | Weight |
|-----------|--------|--------|
| `recent_form_score` | `points_roll3` within position | 30% |
| `form_momentum_score` | `points_roll3 − points_roll5` | 25% |
| `fixture_score` | `6 - fdr_avg` within position | 20% |
| `involvement_score` | `xgi_roll3` within position | 15% |
| `minutes_stability_score` | `minutes_roll5` within position | 10% |

**Eligibility:** `minutes_roll5 >= 30`. Supports optional `position` filter.

Does not model: price changes, ownership trends, or market dynamics.

---

### Value Players (`value.py`)

Surfaces players with high point returns relative to FPL cost.

| Component | Signal | Weight |
|-----------|--------|--------|
| `efficiency_score` | `points_roll5 / purchase_price` | 50% |
| `form_score` | `points_roll3` within position | 30% |
| `consistency_score` | alignment between roll3 and roll5 | 20% |

**Eligibility:** `minutes_roll5 >= 30`, `purchase_price >= 3.5`.
Supports optional `max_price` ceiling.

---

### Availability Risk (`availability.py`)

Flags players with unstable or deteriorating minute patterns. This is an
**operational warning layer** — it does not predict injuries or suspensions.

| Risk Level | Condition |
|------------|-----------|
| HIGH | `minutes_roll3 < 30` |
| MEDIUM | `minutes_roll3 < 60` OR `minutes_trend == "falling"` OR divergence > 20 min |
| LOW | none of the above |

All players at the target gameweek are returned (not just risky ones), so
consumers can filter for LOW-risk players when building squads.

---

### Fixture Opportunities (`fixtures.py`)

Surfaces players with favorable near-term fixture windows.

| Component | Signal | Weight |
|-----------|--------|--------|
| `fdr_opportunity_score` | mean inverted FDR across window | 40% |
| `team_attack_score` | team's rolling goals scored (prior window) | 35% |
| `dgw_bonus_score` | DGW presence in window (binary) | 25% |

**Eligibility:** `minutes_roll5 >= 30`.
Accepts `horizon` parameter (default 3 GWs ahead).

Team attack strength uses a lookback window of equal length to the forward
window to avoid look-ahead. FDR data for future GWs must be present in the
features DataFrame for the forward window to be evaluated; when absent, a
neutral FDR is substituted.

---

## Deterministic scoring philosophy

All outputs follow the same design principles:

1. **Static weights** — all weights are declared as named constants in each
   module. No weights are learned from data.

2. **Within-position normalization** — signal normalization is position-scoped
   to prevent positional bias (e.g., GKP vs. FWD point scales differ).

3. **Explicit eligibility filters** — minimum minutes thresholds and price
   floors are named constants documented with rationale.

4. **Explainability columns** — every output DataFrame includes the component
   scores used to produce the composite. Nothing is hidden in the composite.
   A reviewer can reconstruct any player's final score from the output alone.

5. **Pure functions** — all output functions are side-effect free and
   produce identical output for identical input (deterministic).

6. **Rho-weighted registry signals** — when the scorer reads from the governed
   registry, signal weights are derived from `rho_pooled` in the registry artifact,
   not from hardcoded constants. This makes the weighting auditable and tied
   directly to the evidence that validated each signal.

## Weekly artifact lineage

A complete weekly run produces the following artifacts:

```
outputs/registry/gw{N}/
    registry.csv          — governed signal manifest (29 signals for gw36)
    build_metadata.json   — build timestamp, source path, row count, schema version

outputs/scorer/
    gw{N}_player_scores.html  — scored player table with explainability spans

intelligence/reporting/
    (weekly snapshot data written to DB or stdout via reporting runner)
```

**Committed vs ephemeral:**
- `outputs/registry/` is committed to git (`.gitignore` exception: `!outputs/registry/`).
  The `gw36/` artifact is a bootstrap — it enables `assert_operational_safe()` to pass
  in a fresh checkout without requiring a live DB run.
- `outputs/scorer/` is gitignored — HTML is regenerated on each score run.
- All other `outputs/*` are gitignored.

See [docs/architecture/runtime-artifacts.md](runtime-artifacts.md) for the full artifact lifecycle.

## Relationship to Research Signals

The intelligence layer consumes **DAL state features only** — the curated
spine plus rolling window columns derived from it. It does not consume:

- EDA registries from `studies/eda/findings/`
- Research-stage promoted signal lists
- Exploratory registry artifacts

This separation is enforced by `validate_intelligence_inputs()` in
`intelligence/intelligence_contracts.py`, which checks that all required columns are present
and raises `IntelligenceInputError` if not — catching accidental use of an
under-populated DataFrame from a non-DAL source.

For the relationship between research signals and the governed registry, see
[docs/registry-governance.md](../registry-governance.md) and
[docs/signal-promotion-states.md](../signal-promotion-states.md).

## Current Limitations

- **No fixture opponent data.** Opponent defensive weakness is proxied through
  team attack strength and FPL FDR ratings. The spine does not expose a direct
  opponent team ID at player-GW grain; a future enhancement could join the
  intermediate fixture layer to obtain this.

- **No price trajectory.** Transfer and value outputs use static current price.
  They do not model FPL price rises or falls.

- **Warmup period.** Rolling window signals require prior GW history.
  GW 1 rows will have null roll3/roll5 values; the intelligence functions
  handle this via `fillna(0)` fill defaults. Outputs for very early GWs
  should be interpreted cautiously.

- **Single-season scope.** The curated spine covers one FPL season. No
  cross-season signals are used.

- **BGW handling.** Blank gameweek rows have null performance columns by
  contract. FDR may also be null for BGW rows; the functions substitute
  a neutral FDR of 3.0 in this case.

- **Module weights are editorial, not calibrated.** The component weights in the
  tables above (e.g. captain's 35/30/20/15) are static editorial constants carried
  in `signals/governance/weight_registry.yaml` with `PROVISIONAL-EDITORIAL`
  provenance — set before the lens-study methodology existed and not yet validated
  by a calibration study. The *within-signal* rho weighting is evidence-based (from
  the registry); the *cross-component* module weights are not. Closing this is a
  `monitor`-stage calibration study, deferred to 2026/27.

- **No declared output contract.** Upstream layers publish enforced schemas
  (`MART_SCHEMA`, `FEAT_SCHEMA`); the recommendation outputs have no equivalent —
  they are golden-tested, not contract-validated. The output column set is a
  convention, not a guarantee.

*Together these two seams are why the [analytical-architecture.md](analytical-architecture.md)
maturity snapshot rates the Decision layer **Emerging**.*

## Non-Goals

This layer explicitly does not:

- Predict points totals
- Model injury probability
- Simulate transfer market dynamics
- Optimize squad selection (that is a combinatorial problem requiring
  explicit constraint handling)
- Replace human judgement on news, motivation, or manager rotation
- Consume external data sources beyond the DAL-governed database
