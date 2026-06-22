# Composition layer — design and intent

**Status:** intent doc for the informative `composition/` layer
**Produced:** 2026-06-19 (descriptive-layer redesign)
**Class:** read-only informative artifact (no gate decisions, no PROCEED/STOP verdict)

---

## 1. Purpose and where we sit on the analytics maturity model

`composition/` is the **univariate, at-rest** half of the descriptive picture: it
characterises each column *in isolation*, season-pooled — what each signal *is*,
how the scoring engine turns components into points, and what a top-end
performance is made of. Where `exposure/` reads Y and X *against* the
position × minutes axes (relational), `composition/` describes the columns
themselves.

On **Gartner's analytics maturity model** the whole layer sits in the
**Descriptive** tier (*what happened?*). It does not explain *why* (Diagnostic),
forecast (Predictive), or recommend (Prescriptive). It is **cross-sectional**:
no within-player / longitudinal analysis (that is `temporal/` and the diagnostic
layer).

This layer replaces the older `target.ipynb`, `signal.ipynb`, and
`target_variance.ipynb`. The `variance_components.py` **kernel** is retained —
the variance-decomposition *notebook* is deferred to the diagnostic layer, which
will reuse the kernel (§5).

## 2. Notebooks

| Notebook | Question | Owns |
|---|---|---|
| `signal_taxonomy.ipynb` | What is each signal, what class is it, and where is it valid? | the signal reference card |
| `scoring_engine.ipynb` | How does FPL scoring work in practice, by position? | formula-**component** distributions + event rates + magnitude-when-fires + the `total_points` reconstruction |
| `haul_anatomy.ipynb` | When a player hauls (`total_points > 10`), which components drove it? | conditional component breakdown of the haul |

**Ownership boundaries.** `scoring_engine` owns the formula *components* and the
`total_points` *reconstruction* (the deterministic identity check), but **not**
the `total_points` distribution itself — that belongs to
`exposure/target_by_band.ipynb`. `haul_anatomy` conditions on the haul tail and
decomposes it; it does not re-describe the full Y distribution either.

## 3. Directive questions

**`signal_taxonomy.ipynb`** *(reference card — a table is the deliverable here)*
- Establish, for every mart signal, its `signal_layer`, `layer_role`, signal
  class (formula input vs leading indicator), feature-candidate eligibility, and
  interpretation caveat — read straight from `domain/signal_layers.py`.
- Establish, per position, which leading indicators are *alive* vs structural
  zeros, via the relevance kernel.

**`scoring_engine.ipynb`** *(DGW excluded — per-single-fixture event rates)*
- (a) Determine the distribution of each formula **component** by position.
- (b) Establish the **event rate** — the share of appearances in which each
  component fires.
- (c) Determine the **magnitude when it fires** — the conditional size of each
  component given a non-zero.
- (d) Reconstruct `total_points` from components and report a single
  pass/fail **formula-integrity** check (this is the section the
  `domain/fpl_scoring.py` defensive-contribution caveat points at).

**`haul_anatomy.ipynb`** *(DGW excluded — see §4)*
- Determine, conditional on a haul (`total_points > 10`), which components
  contributed the points, by position.
- Establish how the component mix of a haul differs across positions (e.g.
  attacking returns vs clean-sheet-plus-defensive-contribution hauls).

## 4. Shared method

- **GW range:** whole completed season, `GW 1 .. data_cutoff_gw` (dynamic).
- **Population:** `minutes > 0` participation (the player featured), not a
  performance gate.
- **Positions:** GK / DEF / MID / FWD; `scoring_engine` and `haul_anatomy` are
  per-position throughout.
- **DGW:**
  - `signal_taxonomy` — n/a (no row-level EDA).
  - `scoring_engine` — **excluded** (`is_dgw == False`): event rates are
    per-single-fixture; a DGW row sums two fixtures and would distort the "% of
    appearances each component fires" read.
  - `haul_anatomy` — **excluded** (`is_dgw == False`): a DGW haul is two
    fixtures, not one big game; excluding DGW isolates the genuine single-match
    ceiling. This is stated in the notebook.
- **Two signal classes** (from the domain sets — `domain/signal_layers.py`,
  never hardcoded): **formula inputs** (`layer_role ∈ TAUTOLOGICAL_LAYER_ROLES`)
  and **leading indicators** (`feature_candidate_eligible` not in the
  tautological set; plus composites `xgi`, `ict_index`). See
  `EXPOSURE_DESIGN.md` §4 for the full lists.
- **The tautology rule (mandate #1) here:** formula inputs are valid for
  **distribution, frequency, and decomposition** — which is exactly what
  `scoring_engine` and `haul_anatomy` do (component shapes, fire rates, haul
  decomposition). Neither notebook produces a same-gameweek **association**
  between a formula input and `total_points`; the `total_points` reconstruction
  in `scoring_engine` is a deterministic identity check, not an association.
- **Shared liveness logic:** the `(signal, position)` relevance map
  (`formula_input` / `formula_input_dead` / `leading_alive` / `structural_zero`)
  comes from `research/kernels/descriptive/relevance.py`. `signal_taxonomy`
  calls the kernel; it does not recompute the zero-mass / near-zero-variance
  heuristic that previously lived inside `signal.ipynb`.

## 5. Deferred — variance decomposition (diagnostic tier)

The `target_variance` *notebook* (variance components of `total_points`) is
**deferred to the diagnostic layer** — partitioning Y's variance is a *why*
question (how much of the spread is position vs player vs week), not a
descriptive shape. Its kernel, `research/kernels/descriptive/variance_components.py`,
is **kept** for that future notebook to reuse; only the notebook was removed.

## 6. Supporting modules

No structure-local modules. The shared `(signal, position)` relevance/liveness
logic lives in `research/kernels/descriptive/relevance.py` (§4), shared with the
`exposure/` presence and correlation notebooks.
