# Temporal layer — design and intent

**Status:** intent doc for the informative `temporal/` layer
**Produced:** 2026-06-16
**Class:** read-only informative artifact (no gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose

The `structure/` layer answered *what the target and each signal look like at
rest*, season-pooled. The `temporal/` layer asks the next question on one more
axis: **does that picture hold across the season, or does it move?** If a
signal's or the target's distribution drifts from the early third to the late
third, a model that reads it off a single season-pooled fingerprint will
mis-rate late-season players.

Every notebook here is a **read-only informative artifact**. The stability
verdicts are **operational heuristics** (fixed normalised-shift thresholds),
offered as analytical guidance — not statistical tests, not a gate. Nothing
downstream is blocked by an `unstable` verdict here.

## 2. Notebooks

| Notebook | Question | Unit of analysis |
|---|---|---|
| `target_stability.ipynb` | Does `total_points` (Y) drift across the season? Is a position more/less volatile at different points? | (position × block) |
| `signal_stability.ipynb` | Does each X signal drift across the season? Which (signal, position) pairs are poolable vs must be read within-block? | (signal × position × block) |
| `serial_dependence.ipynb` | *(stub — deferred)* Does a player's own last-GW value predict this-GW value (within-player autocorrelation)? | within-player |

`serial_dependence.ipynb` is a deliberate stub: within-player week-to-week
dynamics are a distinct treatment, deferred. Its verdict is not required for the
block-pooled stability read the other two notebooks provide.

## 3. Shared method (both active notebooks)

Inherited from the informative-EDA conventions established in `structure/`:

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic from
  the mart). No early-GW lower bound — the GW-6 cut in the older EDA-1 record
  was a *predictive-evaluation* device, not relevant to descriptive
  characterisation.
- **Population:** `minutes > 0` — a **participation** filter (the player
  appeared), not a performance gate. The 60-minute boundary is deferred to the
  `population/` layer.
- **Temporal unit:** three contiguous, near-equal GW **blocks** (early / mid /
  late), computed dynamically as thirds of the live GW range. Boundaries are
  editorial thirds, **not** data-driven regime change-points (see
  `docs/foundations/statistical-framework.md` gap #9).
- **Stats kernel:** `compute_signal_block_distributions` (median/IQR/etc. per
  block), then `assess_distribution_stability` → `{stable, moderate_shift,
  unstable}` from the largest normalised median shift, mapped to a pooling
  decision by `resolve_pooling_strategy`.
- **Heuristic thresholds:** `STABLE_THRESHOLD = 0.5`, `UNSTABLE_THRESHOLD = 1.5`
  on the normalised median shift. Operational heuristics, not power-justified.

## 4. DGW confound (the temporal-specific honesty note)

Most candidate signals are **additive per fixture**, so a double-gameweek row
roughly **doubles** them. DGW rounds are **not** evenly spread — they cluster
**late** (around blank-gameweek reshuffles). So a signal or the target can look
like it "drifts up" in the late block purely because more late-block rows carry
two fixtures. These distributions **pool SGW and DGW rows** (no normalisation,
no exclusion) and flag the confound rather than treating it. Per-fixture
normalisation is a *treatment*, deferred to the `fixture/` layer. Read every
late-block shift on an additive signal with this confound in mind.

## 5. Signal set for `signal_stability.ipynb` (design decision)

`structure/signal.ipynb` selects signals dynamically; `signal_stability.ipynb`
narrows to a curated set. The rule is simple: **study the composite, not its
parts.** For each composite family we keep only the parent (`xgi`, `ict_index`,
`defensive_contribution`) and drop its components — never both, since a
composite and its parts carry the same information. Standalone signals that
belong to no composite (`xgc`, `bps`, `bonus`) are kept as-is. Near-degenerate
signals that never move are also dropped (see below), because a stability read
is only meaningful on a signal that actually varies.

**Composite narrowing (parent only).** A composite (parent) and its components
carry the *same* underlying information — `domain/fpl_signals.py`:
*"including a composite and its components together double-counts."* For a
stability read we want one representative per family, so we keep the **parent**
and drop the components, narrowing **programmatically** from
`domain.fpl_signals.COMPOSITE_SIGNALS`:

| Parent (kept) | Components (dropped) |
|---|---|
| `xgi` | `xg`, `xa` |
| `ict_index` | `influence`, `creativity`, `threat` |
| `defensive_contribution` | `clearances_blocks_interceptions`, `tackles`, `recoveries` |

`defensive_contribution` is registered as a composite in `fpl_signals.py` for
exactly this purpose — it is the FPL-computed CBIT/CBIRT count and subsumes its
raw defensive actions (position-dependently; see that module). The notebook
imports `COMPOSITE_SIGNALS` and drops every component automatically, so the
narrowing tracks the single source of truth rather than a hand-list.

**Final signal set (composite parents + standalones):**
`xgi`, `xgc`, `ict_index`, `bps`, `bonus`, `defensive_contribution`.

`bps` and `bonus` are both kept: `bonus` is the ordinal rank-transform of `bps`
within a match, not a clean additive identity, and the two drift differently
(raw continuous vs 0/1/2/3 ordinal), so neither is registered as a composite of
the other.

**Excluded by design:**
- `own_goals`, `penalties_missed` — near-degenerate at every position (99%+
  zero-mass per `structure/signal.ipynb`); a stability verdict on a signal that
  fires in <1% of appearances is not a meaningful drift claim.
- Discrete count outcomes (`goals_scored`, `assists`, `clean_sheets`,
  `goals_conceded`, `saves`, `penalties_saved`, `starts`, cards) — these are the
  target's *components*, studied as outcomes elsewhere; the temporal layer reads
  *signal* drift, not outcome drift. (`xg`/`xa`/`xgi` are the process proxies
  for the goal/assist outcomes and stand in for them here.)

`defensive_contribution@GK` is structurally 0 (the rule does not apply to GK)
and will surface as a degenerate/NaN-block cell, read against the `n` column —
not a real stability claim.
