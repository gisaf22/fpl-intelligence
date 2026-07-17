# Model workflow redesign — spec (draft)

**Status:** draft to build against · **Type:** spec
**Purpose:** re-architect the predictive layer by **concern**, not by **phase**, so the flow is
self-explanatory, DRY, and analytically defensible. Phases were a *timeline* (the order we learned
things); they are the wrong axis for file structure because one phase touches modelling + evaluation +
composition at once. This spec keeps the timeline as a **changelog** and shapes the code by concern.

---

## 0. Principles — two pillars

Every choice must satisfy **both**. Clean code that is analytically indefensible fails; a rigorous
result that is unmaintainable spaghetti fails.

**A. Software-engineering practice**
- **Separation of concerns** — one self-contained unit per scoring *term*; shared code written once.
- **DRY & reusable** — primitives written once (kernels / eval / domain), consumed everywhere.
- **Self-explanatory** — names, folders, and specs read as documentation; no cryptic phase labels.
- **Stable interfaces** — a fixed Term contract; adding a term = adding a folder, never editing a god-file.
- **Testable** — invariants (lag-safety, monotonic GW, no dupes) + frozen-number reproduction in CI.

**B. Data-science rigour**
- **Traceable** — every input has provenance + lag-safety; every claim a pre-registered hypothesis.
- **Trustworthy** — proper scoring + calibration + bootstrap CIs; a result carries its uncertainty.
- **Honest about power** — detectability floor before a null; out-of-sample before a yes (generalizable,
  or explicitly not).
- **Conservative gates** — a pass is trustworthy; a fail is *inconclusive*, never a licence to abandon.
- **Discovery ≠ validation** — families *propose* (non-authoritative); terms *validate*.
- **Declared, not coded** — features, hypotheses, assumptions are **data** (specs), not hardcoded lists.
- **Understandable / presented** — notebooks render the story (render-not-decide), co-located with code.

---

## 1. Concern map (layers, one direction)

Reusable analytics split across **two** homes — this matters because of the layering rule
(**research must not import model**):

- **`research/kernels/`** = data-general *statistical* primitives, already **tiered** — NOT all
  "inferential". They operate on raw data, know nothing about a fitted model.
- **`model/eval/`** = *measurement of a fitted model* (baselines, gate, calibration, proper scoring).
  These depend on model output, so they are **model-layer, not kernels** (research can't import them).

```
research/kernels/                       # (1) reusable STATISTICAL primitives (research layer, tiered)
    descriptive/   distribution, variance_components (SS-share)
    diagnostic/    shape (dispersion lives here), serial, tail, stability
    inferential/   resampling (bootstrap CI), variance_components (ICC), monotonicity
    hypothesis/    multiplicity (FDR), stratification
research/families/                      # (1') discovery — proposes candidate features (NON-authoritative)

model/
  features/               # (2) feature engineering — declared, lag-safe columns from specs
    spec.py               #     FeatureSpec + candidate pools per term
    build.py              #     spec -> lag-safe column (+ leakage property test)
  terms/                  # (3) one self-contained model per scoring term
    _base.py              #     the Term contract
    goals/                #       goals.py · spec.py · test_goals.py · notebook.ipynb · ASSUMPTIONS.md
    assists/  clean_sheet/  saves/  defensive_contribution/  minutes/  bonus/
  compose.py              # (4) terms -> E[points] via domain scoring rule
  simulate.py             # (5) terms' distributions -> points distribution
  decide.py               # (5) captaincy / decision
  eval/                   # (6) measurement of models (model layer) — baselines, walkforward,
                          #     metrics (ranking), scorer (gate), calibration, proper_scoring (deviance/CRPS)
domain/fpl_scoring.py     # (4) the rulebook (single source of the weights)
```

Import direction: `domain <- kernels/families <- features <- terms <- compose/simulate/eval <- decide`
(enforced by import-linter, extending today's contracts).

---

## 2. Model + Term contracts (kills the god-files)

**A `Model` is fitted; a `Term` is a scored quantity it emits.** Usually 1 model → 1 term, but some
models are **joint**: one `TeamGoalsAgainst` model emits **two** terms (`clean_sheet` = P(GA=0) and
`conceded` = E[-floor(GA/2)]). So the fittable unit is the *model*; terms are *views* on its output.
This is why the contract is split (resolves open-decision #2).

```python
class Model(Protocol):                 # the fittable unit (1 folder)
    name: str
    candidates: FeaturePool            # declared candidate pool; the minimal + selected models draw from it
    family: sm.families.Family         # GLM choice, justified by its dispersion check
    grain: Literal["player_gw","team_gw"]   # the grain it is fit at (see §3 join step)
    hypotheses: list[Hypothesis]       # pre-registered; success threshold written BEFORE the run

    def check_assumptions(self, train) -> AssumptionReport   # dispersion + detectability (pre-fit)
    def fit(self, train) -> Fitted                           # walk-forward; inner temporal split for tuning
    def emit(self, fitted, test) -> dict[str, np.ndarray]    # {term_name: prediction}, one+ terms

class Term(Protocol):                  # a scored quantity a Model emits
    name: str
    model: Model                       # which model produces it (shared for joint terms)
    point_value: PositionWeights       # the fixed FPL weights (from domain), per position
    baseline_col: str                  # its OWN naive bar, e.g. "clean_sheets_roll3"

    def validate(self, mart) -> GateResult   # vs baseline_col (shared eval gate)
    def diagnose(self, mart) -> Diagnostics  # residuals + ablation
```

`compose.py` / `simulate.py` iterate the **term registry**; each term pulls its model's `emit`
output — **no hardcoded lists**. Adding a term = adding one folder that registers a `Model` (+ the
term views on it).

---

## 3. Inputs — FeatureSpec + candidate pool

Features become **data**, not code. **One candidate pool per model.** From that pool, two models are
built (resolves open-decision #3):
- **minimal** — 2–3 mechanistic features: a *fast* smoke-test + the comparison **bar** the selected
  model must beat (proves selection *added* value, like the old `p21` bar). Not shipped, but always run.
- **selected** — regularized over the *full* pool: the **shipped** model.

One pool, two draws → fast *and* correct *and* informative (the delta = what selection bought).

```python
FeatureSpec(
    name="xg_roll3",
    source="xg", transform="roll", window=3,   # window is a SWEPT param (see below), not baked into the name
    grain="player_gw",                          # player_gw | team_gw — drives the join/broadcast step
    lag_safe=True,                              # asserted + property-tested (not a comment)
    known_future=False,                         # was_home => True (allowed); else strictly prior
    rationale="xG > realized goals as a leading indicator",
    prior="families: xgi rho 0.14",             # provenance
)
```

**Grain + join (resolves #4).** Features live at their natural grain — player-GW (xG, minutes) or
team-GW (team xG, opponent conceded). `features/build.py` produces each at its grain, then **joins/
broadcasts** to the model's grain. The `grain` field is explicit so the join is checked, not implicit.

**Window sweep is leakage-safe (resolves #5).** Sweeping 3/5/8/EWMA is a *selection*, so it runs inside
the **inner temporal split** of the training window (earlier GWs fit, latest GWs pick the window) — the
same anti-leakage scheme as penalty selection. Never pick the window on the eval set.

**Feature-engineering axes to explore** (current roster = mostly player-own rolling *means* — ~20% of
the space):
1. **Aggregation** — median / max(ceiling) / slope(trend) / std(volatility) / EWMA(decay), not just mean.
2. **Opponent-adjusted** — xG adjusted for the *specific* upcoming opponent's strength (beyond `fdr_avg`).
3. **Fixture-forward** — the opponent's conceded/xGC for *this* match; home/away splits.
4. **Role** — penalty/set-piece taker; nominal-vs-actual position.
5. **Team attacking context** — team overall xG (opportunity), a team-grain feature broadcast to players.
6. **Rotation/availability** — start probability, days-since-start, congestion (feeds the minutes term).
7. **Feature-level shrinkage** — shrink noisy early-season xG toward the position mean (Phase-1 idea on inputs).
8. **Window sweep** — 3/5/8/EWMA selected, not guessed.

---

## 4. The workflow — where each check sits and when it runs

| Stage | Runs | Checks that live here |
|---|---|---|
| **0 Build** | spec -> lag-safe columns | **leakage/lag-safety property test** (every column); **lineage** from spec |
| **1 Pre-fit** | per term, before fit | **dispersion/deviance** (family justified?); **detectability floor** (learnable at this N?) |
| **2 Fit** | walk-forward GLM | statsmodels GLM (inference tool, count/binary families, explicit design) |
| **3 Predict+compose** | terms -> points | **invariants** (monotonic GW, no dupes) |
| **4 Gate** | vs baseline | within-position Spearman + block-bootstrap CI + coverage (shared `scorer`) |
| **5 Diagnose** | after the gate | **residual/error analysis** (which players/GWs fail); **ablation** (drop each feature/term, re-gate) |
| **CI (every PR)** | — | **property tests** + **reproducibility gate** (frozen numbers to 4dp) |

Triggers: **invariants + repro run in CI** (regression contracts, not part of a run); **assumptions are
pre-fit gates**; **diagnostics are post-gate reports**. A term's `run()` = build → pre-fit → fit → gate
→ diagnose.

---

## 5. Baselines — two levels (don't conflate)

- **Per-term:** each term's model vs **its own** rolling average (`clean_sheets_roll3`, `dc_roll3`, …).
  Answers "is this term predictable from signals?"
- **Composed:** assembled `e_points` vs the **points** average (`base_season`) [+ best single signal;
  + the partial model as a bar]. Answers "does the assembled stack out-rank the naive points average?"

A term proves itself against *its own* history; the *stack* proves itself against the *points* average.

---

## 6. Tooling per stage (right tool for the question)

- **Inference / per-term fit:** `statsmodels` GLM — count/binary families (Poisson/logistic), std
  errors, deviance, unregularized control, explicit design matrices for the walk-forward.
- **Selection among many collinear signals:** **regularized** per-component GLM (`fit_regularized`,
  elastic net), penalty chosen by an **inner temporal split** (never random k-fold — leaks across GWs).
  NOT a Gaussian sklearn ElasticNet (would lose the count/binary shape).
- **Interactions:** engineer explicit product columns for a *few* known ones (keeps the array API);
  probe *whether* interactions matter at all with a GBM ceiling check before specifying many.

---

## 7. Cross-cutting techniques (homes + meaning)

- **Pre-registration** — each term declares `hypotheses` (claim · test · **success threshold written
  before** · due-by · status). No infra: a dataclass per term, auto-aggregated into a generated index
  (the successor to the plan's §4 register).
- **Detectability floor vs generalizability** — *power* ("could I see this effect at this N?" — gate
  a null on it) is distinct from *generalizability* ("does it transfer to a new season?" — gate a win
  on it). Require detectability before claiming a null; out-of-sample before claiming a yes.
- **Property-based invariants** — lag-safety, monotonic GW, no dupes: properties on *every* feature/
  term, run at build-time and in CI (not per-file smoke checks).
- **Reproducibility gate** — frozen numbers to 4dp on every PR.
- **Residual/error analysis** — per term, post-gate: which players/GWs the model misses.
- **Ablation** — drop each feature/term, re-gate, to **measure** contribution (today it's inferred).
- **Config over constants** *(deferred, noted)* — `WARMUP_GW`, `MIN_ROWS`, windows, thresholds into one
  typed config.
- **Registry pattern** *(deferred, noted)* — terms self-register for `compose`/`simulate` discovery.

---

## 8. Families' new role

- **Non-authoritative prior / hypothesis generator.** Family verdicts never gate the model again (the
  A-F1 mistake: `total_points` marginal reads treated as truth). A family finding enters only as a
  candidate + rationale in a term's `FeatureSpec.prior`.
- **Lenses/studies = discovery** — propose features and mechanisms (opponent effects, form, role) at the
  association grain; they do not validate.
- **Terms = validation** — re-test every candidate, component-appropriately, walk-forward, vs its baseline.
- Direction: **families "what to try & why" -> features/ "declared lag-safe inputs" -> terms "does it
  beat the baseline".** Discovery and validation are separate layers. New FE axes (§3) give families a
  forward agenda instead of a closed verdict list.

---

## 9. Docs & notebooks conventions

- **Every doc declares a type:** `spec | frozen-result | changelog | archived`. `archived` moves to
  `docs/archive/` and is never linked from live structure.
- **Flag for archival/deletion** when a doc: describes deleted code, duplicates a frozen result, is a
  resolved point-in-time audit, or narrates a footnote as a stage (e.g. overdispersion / minutes-exposure
  become per-term ASSUMPTIONS.md sections, not standalone phase docs).
- **Notebooks are co-located** with the unit they render (one per term/question, in that term's folder),
  **render-not-decide**, and **output-stripped in git** (resolves #1). Consequence, made explicit: the
  notebook is a *re-runnable view*, **not** the record — the **frozen-result doc is the sole record** of
  the numbers. Notebooks reproduce the story on demand; the results doc is what you cite.

---

## 10. Migration (strangler, not big-bang)

Invariant throughout: **frozen numbers reproduce to 4dp; contracts stay green.**
1. Add `features/spec.py` + `build.py` (grain + leakage property test) and the config skeleton.
2. Define `Model` + `Term` + `_base.py`; add `compose.py` that consumes the term registry.
3. Extract **one** model (`goals`) into `terms/goals/`, satisfy the contract (minimal + selected),
   prove 4dp reproduction, add its test + ASSUMPTIONS.md.
4. Do a **joint** model early (`team_goals_against` → `clean_sheet` + `conceded`) to prove the
   Model-emits-many-Terms shape before it bites.
5. Repeat per model; delete `component_forecast.py` / `points_model.py` when empty.
6. Retype/​archive docs; co-locate + strip notebooks; auto-generate the hypotheses index.
7. `phase*` becomes a **changelog** in docs, not structure.

Each step is independently reviewable behind the reproducibility gate — same discipline as the
pre-Phase-2 relocation.

---

## 11. Resolved decisions (open items closed 2026-07-17)

1. **Notebooks = re-runnable views, not the record.** Output-stripped in git; the **frozen-result doc
   is the sole record** of the numbers.
2. **Model emits Terms (not Term = Model).** Joint models (`team_goals_against` → `clean_sheet` +
   `conceded`) fit once and emit multiple terms; terms are views. Contract split accordingly (§2).
3. **One pool, two draws.** A cheap **minimal** model (fast smoke-test + comparison bar) and the
   regularized **selected** model (shipped) draw from the *same* candidate pool; the delta shows what
   selection bought. Fast, correct, informative.
4. **Explicit feature grain + join.** Each `FeatureSpec` declares `grain`; `build.py` joins/broadcasts
   to the model's grain (checked, not implicit).
5. **Window sweep runs in the inner temporal split** (safe default) — window is *selected* like the
   penalty, never on the eval set. *(Left blank in feedback; adopt safe default, revisit if desired.)*
```
