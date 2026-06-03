# Explainability Model

**Authoritative for:** how scores are computed, why specific design decisions were made, and what a consumer can verify from the output alone.

---

## Design contract

Every player score produced by this system is fully reconstructable from the output itself. No scoring logic is hidden in a composite. No weights are learned from data or stored outside the governed registry. A reviewer with the HTML output and the registry CSV can independently verify every rank.

This is not an accident — it is a design requirement. The system answers an empirical question ("do signals associate with returns?") and its outputs must be auditable against the evidence that produced them.

---

## Scoring pipeline

```
DAL mart (dal.pipeline.load().mart)
    ↓
Governed registry artifact (outputs/registry/gw{N}/registry.csv)
    ↓
Signal selection (intelligence/scoring/signal_selector.py)
    ↓
Within-position normalisation
    ↓
Rho-weighted composite
    ↓
ScorerOutput → HTML with explainability columns
```

---

## Signal selection

`intelligence/scoring/signal_selector.py` applies three sequential filters to the governed registry:

| Filter | Condition | Rationale |
|--------|-----------|-----------|
| Promotion class | `promotion_class in {core_signal, review_signal}` | Only EDA-confirmed signals. Exploratory signals have no confirmed association; including them contaminates the composite with noise. |
| Role exclusion | `layer_role not in {points_component, contribution_index}` | Signals that mechanistically encode or derive the scoring target (FPL points) are excluded — using them would be leakage, not prediction. |
| Non-null rho | `rho_pooled` is not null | A non-null `rho_pooled` means the signal cleared the lens CI gate, which is the sole magnitude authority. The former `abs(rho_pooled) >= 0.15` filter was removed after the synthesis study approved signals with rho < 0.15 via partial rho. |

Signals that pass all three filters become **confirmed** signals. Signals that fail any filter become **caveated** — they appear in the HTML output with their specific exclusion reason, so the consumer understands exactly what was filtered and why.

---

## Rho weighting

The composite score for each player is a weighted mean of normalised signal values:

```
composite = Σ(normalised_value_i × |rho_pooled_i|) / Σ(|rho_pooled_i|)
```

Weights are `abs(rho_pooled)` drawn directly from the governed registry artifact — not hardcoded in source code. This means:

1. **Weight traceability.** Every weight in the composite is traceable to the Spearman rank correlation computed during system EDA. A stronger historical association with FPL returns carries more weight.

2. **Weight auditability.** The `rho_pooled` value is shown in the HTML column header for each signal. A consumer can verify that weights match the registry.

3. **Weight stability.** Weights change only when the registry is rebuilt from new EDA findings. They do not silently drift based on run-to-run data variation.

Direction (`+1` or `-1`) is also derived from `rho_pooled`: a negative rho means the signal correlates inversely with returns, and the engine negates the raw values before normalisation. The HTML renders a `↓` arrow for inverted signals.

---

## Within-position normalisation

Before computing the composite, each signal is normalised to `[0, 1]` **within position** (GK, DEF, MID, FWD), not across the full player set. This is required because:

- Raw point scales differ by position. A forward scoring 8 points is a different outcome from a goalkeeper scoring 8 points.
- Signal distributions differ by position. Minutes for defenders cluster differently than minutes for forwards.
- Cross-position normalisation would systematically bias the composite toward high-volume positions.

Normalisation is min-max within position: `(x - min) / (max - min)`. Constant-valued signals normalise to 0.5 (no information). Players with null signal values receive the directed within-position mean so absent data does not penalise or reward them.

---

## Explainability outputs

Every `PlayerScore` in the output contains:

| Field | Content |
|-------|---------|
| `composite_score` | Weighted composite `[0, 1]`; multiplied by 10 in the HTML display |
| `signal_values` | Raw value for each confirmed signal at this player-GW |
| `signal_normalised` | Position-normalised value `[0, 1]` for each confirmed signal |

The HTML report surfaces all three:
- **Rank** — position within the player's position group
- **Score** — `composite_score × 10` (0–10 scale)
- **Per-signal bar charts** — normalised value shown as a directional bar; raw value shown below
- **Column headers** — signal name, direction arrow, `ρ={value}` from the registry
- **Excluded signals section** — all caveated signals with their specific exclusion reason
- **Methodology note** — plaintext description of the scoring formula in the HTML header

Nothing is hidden. The entire composite can be independently reconstructed from the displayed values and the published formula.

---

## Why not ML-based weights

ML weights are not used for three reasons specific to this system's state:

1. **No validated signal set exists yet.** Lens studies have not completed. Computing ML weights on unvalidated signals produces a model whose weights cannot be diagnosed or improved when it fails.

2. **Interpretability is a first-class requirement.** The system must answer "why is this player ranked above that one?" in terms a human can verify against evidence. A neural network weight cannot be traced back to a historical association.

3. **Weight stability matters for week-to-week decision making.** A player's rank should change because their form changed, not because the model updated its weights. Rho-based weights are stable across the season; ML weights would shift on every retrain.

ML experiments (`studies/experiments/`) are planned as a downstream layer that consumes validated, synthesised signals. ML belongs after the registry is populated — not before.

---

## Verifying a score independently

Given the HTML output and `outputs/registry/gw{N}/registry.csv`:

1. Read the registry CSV. Filter to `promotion_class in {core_signal, review_signal}`, `layer_role not in {points_component, contribution_index}`, and `rho_pooled` is not null for the player's position.
2. For each retained signal, take the player's raw value and all players in the same position.
3. Compute `normalised = (raw * direction - min) / (max - min)` across the position group.
4. Compute `composite = Σ(normalised_i × |rho_i|) / Σ(|rho_i|)`.
5. Rank players by composite descending.

The result should match the HTML output exactly. If it does not, that is a bug — not a design choice.
