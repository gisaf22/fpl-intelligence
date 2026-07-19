# simulate.py slice — plan + decision doc (spec §1 item 5)

**Status:** plan to approve · **Type:** spec
**Parent:** [docs/model-redesign-spec.md](model-redesign-spec.md) (§1 concern map item 5, §2 registry iteration, §4 repro gate, §7 registry)
**Precedent:** the `team_goals_against` slice — [docs/model-redesign-team-goals-against-slice.md](model-redesign-team-goals-against-slice.md)
**Reference being strangled:** [model/forecast/simulator.py](../model/forecast/simulator.py) (`simulate_points`, `_draw_team_ga`, `_simulate_rows`, `simulator_consistency`)
**Builds on:** [model/compose.py](../model/compose.py) (already iterates the term registry)

## Why this slice, now

`simulate.py` is spec §1 item (5): terms → **points distribution** (P(haul), captaincy ceiling p90,
downside p10), not just the mean `compose.py` gives. It is the **only** remaining consolidation step
that is fully unblocked (no god-file deletion, no golden-freeze needed), and its prerequisite — a **raw
parameter panel** surfaced from compose — is *also* what later unblocks repointing the eval consumers
(`calibration.py`, `captaincy_backtest.py`) off `walk_forward_points`. So it is on the critical path,
not a detour.

## What the simulator actually needs (traced, not assumed)

The old simulator does **not** consume term *distributions*; it consumes the **raw parameters** and
draws them itself through the FPL scoring rules. Every parameter already exists inside
`compose._collect_views` — but compose surfaces only the *point-valued decomposition*, discarding the
raw views. Mapping (all confirmed present):

| Sim input | Source in compose today | Note |
|---|---|---|
| `e_goals`, `e_assists` | `views["goals"]`, `views["assists"]` | raw Poisson means ✓ |
| `e_saves` | `views["saves"]` | **raw count** (compose divides by 3 for points; view is raw) ✓ |
| `p_cs` | `views["clean_sheet"]` | raw P(GA=0), **un-gated** by p60 (sim applies its own `(ga==0)&play60`) ✓ |
| `p60` | `views["p60"]` | ✓ |
| `p_dc` | `views["defensive_contribution"]` | raw Bernoulli prob ✓ |
| `bonus_intercept`, `bonus_slope` | `BONUS_MODEL.meta["coefficients"]` per `(position, gw)` | **not surfaced** — compose merges then discards; must expose per-row |
| team-fixture key | `team_id`, `gw` | present in compose output ✓ |

## Stress-test findings (the forks)

### Fork A — sampling knowledge: contract vs local
Spec §1 item 5 says "terms' **distributions**," but the §2 `Term` contract emits a **point value**;
it has no declared sampling law. The old simulator hardcodes the family per component (goals→Poisson,
DC/p60→Bernoulli, team-GA→shared Poisson via `λ = -log p_cs`).
**Fork:** grow the Model/Term contract with a declared sampling law (clean, but an un-ratified §2
change), or keep the sampling knowledge **local to `simulate.py`** for this pass.
**Recommendation:** **local** — faithful, small, and defers the contract change (note it in §7's
"deferred" list). Do not expand §2 on one instance.

### Fork B — there is NO bit-identical golden (the invariant must change form)
This is the departure from every prior slice. A Monte-Carlo sim is **stochastic**, so:
1. It **cannot** reproduce the old simulator "to the bit," and
2. Its `sim_mean` **cannot** equal compose `e_points` to 4dp even in principle — the **bonus clip**
   (`E[clip(a+bR)] ≠ clip(a+b·E[R])`, Jensen) and the **saves integer floor** (`saves//3`) are real
   nonlinearities. The old `simulator_consistency` already concedes this ("small saves floor / bonus
   clip nonlinearities").
3. On **GK** rows it diverges from the old simulator **by design** — compose's robust GK `p60` replaces
   `walk_forward_points`'s flat-0.98 shortcut (the deliberate improvement carried from the compose slice).

**Fork:** what is the reproducibility gate?
**Recommendation:** split into two checks, matching what is actually true:
  - **(1) Repro gate = seed-pinned regression vector.** Fix `seed`; `sim_mean/sim_sd/p10/p50/p90/p_haul`
    on a small fixed panel reproduce to 4dp as a checked-in vector. This *replaces* "bit-identical to a
    god-file" for this slice and is the honest form of §4's repro gate for stochastic code.
  - **(2) Consistency check = tolerance, not equality.** `sim_mean ≈ compose e_points` within a stated
    tolerance on non-GK rows (bounds MC error + bonus-clip + saves-floor gap); **GK rows excluded and
    the divergence logged** as the same deliberate improvement.

### Fork C — the parameter-panel surface
`simulate.py` needs the raw views + bonus coeffs; compose discards them.
**Fork:** where does the panel live?
**Recommendation:** add **`compose_parameters(mart) -> DataFrame`** in `compose.py` (the master panel +
one column per raw view + `bonus_intercept`/`bonus_slope` per row). `compose_points` is refactored to
build on it (multiply views into points), so there is **one** view-collection path. `simulate.py` imports
`compose_parameters` (model→model, allowed). This is the surface item 2b (repointing eval consumers)
later reuses.

### Fork D — DGW handling (note, not a decision)
`compose._master_panel` drops `is_dgw` rows; the old simulator collapsed a team's two same-GW fixtures
into **one** `team_id_gw` key (a known limitation). Sim-on-compose therefore **won't score DGW rows** —
arguably cleaner than the collapse. Recorded as a scope limit in ASSUMPTIONS.md; not scored, not
silently wrong.

## Untested sampling assumptions (carried faithfully, recorded — not newly tested)
Ported verbatim from the old simulator's docstring; the move onto compose's panel does **not** change
them, and this slice does **not** newly validate them (that is Phase-4 distributional work — PIT /
haul-rate / CRPS):
- team goals-against drawn **once per team-fixture, shared** across the team's players (D-D co-movement
  of `clean_sheet` & `conceded`); exact for full-90, approximate for subs;
- **DC drawn independently** of GA given minutes (D-A);
- **goals ⊥ assists** within a player;
- bonus **co-moves via the drawn returns** (per-draw), competitive residual not sampled — this is why
  sim bonus ≠ compose's expected-returns bonus (Fork B point 2).

## Existing machinery — confirmed, stays put
- `research.kernels.inferential.resampling` (`bootstrap_spearman_ci`, …) is **rank-correlation CI for
  the gate**, not point Monte-Carlo. `model` *may* import `research.kernels` (import-linter
  `no_model_to_research_analysis` exempts kernels), but there is **nothing to reuse** — the sim's
  Poisson/Bernoulli sampling is a distinct concern. Bootstrap machinery **stays** in `research.kernels`.
- `domain/fpl_scoring.py` already owns the weights/constants the sim uses (`GK_SAVES_PER_POINT`,
  `BPS_BONUS_FIRST`, goal/CS mults) — **stays**; `simulate.py` imports from `domain` (allowed).
- **Conclusion:** `simulate.py`'s sampling loop is genuinely new model-layer code; no relocation.

## What moves (extract → `model/simulate.py`)

| From `simulator.py` | To |
|---|---|
| `_draw_team_ga` (shared team-GA draw, `λ = -log p_cs`) | `simulate.py` `_draw_team_ga` (keyed on compose panel's `team_id`,`gw`) |
| `_simulate_rows` (component draws → points) | `simulate.py` `_simulate_rows` (reads the compose parameter panel) |
| `simulate_points` (blocked MC, summaries) | `simulate.py` `simulate_points(params)` — input is `compose_parameters` output |
| `simulator_consistency` | Fork B check (2): tolerance vs compose `e_points`, GK excluded |

## Folder / files

```
model/
  compose.py         + compose_parameters(mart) -> raw param panel; compose_points refactored onto it
  simulate.py        _draw_team_ga · _simulate_rows · simulate_points(params, n_sims, seed) · consistency
  terms/
    test_simulate.py contract (columns) · seed-pinned repro vector (Fork B.1, 4dp) ·
                     consistency tolerance non-GK (Fork B.2) · team-fixture sharing key intact ·
                     warmup/NaN filter matches · DGW rows absent (Fork D)
  ASSUMPTIONS note   (in simulate.py docstring): the 4 sampling assumptions + DGW + GK divergence
```

## Invariant (restated for a stochastic step)
Not "bit-identical to a god-file." Instead: **seed-pinned summaries reproduce to 4dp** (repro gate) **+**
`sim_mean` consistent with compose `e_points` within tolerance on non-GK rows (GK divergence logged).
Import-linter 6/6 green; ruff clean. Verify: `pytest model/terms model/features -q`, `lint-imports`,
`ruff check model`.

## Commit sequence
1. `compose_parameters(mart)` + refactor `compose_points` onto it + panel-column test (Fork C). *(no
   behaviour change to `e_points` — existing compose tests stay green.)*
2. `simulate.py` (`_draw_team_ga`, `_simulate_rows`, `simulate_points`) on the parameter panel (Fork A: local sampling).
3. `test_simulate.py`: seed-pinned repro vector (Fork B.1) + consistency tolerance non-GK (Fork B.2) +
   key/warmup/DGW invariants (Fork D).
4. ASSUMPTIONS + output-stripped notebook if warranted; confirm contracts + ruff.
```
