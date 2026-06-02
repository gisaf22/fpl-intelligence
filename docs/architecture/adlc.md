# Analytical Development Lifecycle (ADLC)

**What this is:** the one map of how a question becomes a recommendation in this repo —
the stages, the single artifact each stage emits, the question-type tag each analysis
carries, and the test contract that holds each stage honest.

**Right-sizing note.** This is a solo, single-season (2025/26) heuristic project: an
additive-weighted scorer over a local DAL. The lifecycle below is deliberately lean. It is
*not* a data-team operating model. Where a heavier pattern (feature store, model registry
service, property-based testing) might apply, this doc says **"don't build it yet"** and gives
the trigger that would change that.

**Status:** design + audit. Prescribe-only — no code or directories move because of this
document. The ID-diet and run-dir cleanup below are a **plan**, not a migration.

---

## 1. The problem this fixes

The repo currently conflates three independent axes onto one folder tree:

1. **Data assets** — the DAL (`staging → intermediate → fct → feat → mart`). This axis is
   healthy; leave it.
2. **Analysis lifecycle** — organized by *study name* (`lenses/`, `synthesis/`, `experiments/`),
   not by *where in the process* a study sits. You cannot read the folder tree and see knowledge
   flowing from question to verdict to model.
3. **Question type** — implicit. Whether a study is descriptive, predictive, or causal lives only
   in the analyst's head and the prose, never as a tag you can filter on.

Symptom: ID-code sprawl. `G-EDA1-04`, `AVAIL-001`, `SYNTH-01`, `LENS-FORM`, `ENG-02`, `Phase 9`,
and timestamped run directories (`SYNTH-01-20260527_113400`) are six namespaces doing the work
that **two** could do. High cognitive load, no payoff for a solo project.

The fix is to name the three axes separately:

- **Axis 1 (data)** stays as the DAL substrate.
- **Axis 2 (lifecycle)** becomes five named stages with one artifact type each.
- **Axis 3 (question type)** becomes a one-word **mode tag** on every analysis.

---

## 2. The map — one substrate + five stages

```
        ┌─────────────────────────────────────────────────────────────┐
SUBSTRATE│  dal/   data substrate  → the mart (player_id, gw)          │
        └─────────────────────────────────────────────────────────────┘
                                  │ the artifact every stage reads
                                  ▼
   explore  ──►  validate  ──►  model  ──►  serve  ──►  monitor
 (hypotheses)   (verdicts)    (spec)    (recommend.)  (drift/backtest)
      ▲              │                                        │
      │     shared lib: kernels/ (pure stats)                 │
      └──────────────────────── loop back ───────────────────┘
```

**One substrate, not two.** The data substrate is `dal/` — ~3,080 LOC that *emits an artifact*
(the mart) with a real contract (`MART_SCHEMA`, grain), read by every stage including serve. That
is what "substrate" means: the thing everything stands on.

**`kernels/` is a shared library, not a substrate.** It is ~910 LOC of pure, domain-agnostic
statistics (its docstring: *"no FPL-specific constants, no governance imports, no signal
classification strings"*), and it is imported by only the two *analysis* stages — explore and
validate (plus tests). `serve` never touches it. It emits no artifact; it emits functions you
call. That's the difference between the database and numpy — and you don't put numpy on the
architecture diagram. So it rides along as a footnote on the flow, not a box.

Its one architecturally-load-bearing property is that `kernels/windows.py` *enforces* the lag-1
leakage contract — worth naming so that guarantee has a single home (see §5), but that's a
sentence, not a pillar.

**Knowledge flows one way.** A stage reads the artifacts of earlier stages and the two
substrates — never the reverse, and never sideways into a peer stage's internals. The only
back-edge is `monitor → explore`: a drift finding *re-opens* a question, it does not reach into
serve's code.

| Stage | Current folder(s) | One question it answers | Mode(s) | Emits (one artifact type) |
|---|---|---|---|---|
| **dal** *(substrate)* | `dal/` | "What is the validated state of every player each GW?" | — | the **mart** |
| **explore** | `studies/eda/` | "What's in the data — what's worth testing?" | descriptive, diagnostic | **hypotheses** (durable findings; throwaway code) |
| **validate** | `studies/lenses/`, `studies/experiments/` | "Does this signal actually predict returns?" | predictive, causal | **verdicts** (pre-registered, accept/reject) |
| **model** | `studies/synthesis/`, `signals/` | "Which signals, at what weights, governed how?" | assemble / govern | **model spec** (the governed ledger) |
| **serve** | `intelligence/` | "Who do I captain / transfer / hold?" | prescriptive | **recommendations** |
| **monitor** | `studies/operational/` | "Is the model still right in-season?" | operational | **drift / backtest** (loops to explore) |

The folders do not have to be renamed to adopt this. The **map is the contract**; the rename is
optional cosmetics that can follow later (§7).

---

## 3. The mode tag — question type as Axis 3

Every analysis carries exactly one **mode tag** in its header. This is the single highest-value,
lowest-cost change: it makes claim-type legible and stops descriptive work from being read as
causal.

| Mode | Pearl/Gartner | The question | The honest statistic |
|---|---|---|---|
| `descriptive` | assoc. (rung 1) | "What does the data look like?" | distribution, median/quantiles, hit-rate |
| `diagnostic` | assoc. (rung 1) | "Why did this happen / what co-moves?" | conditional distributions, decomposition |
| `predictive` | assoc. (rung 1) | "Does X forecast Y (lag-respecting)?" | out-of-sample rho, lift, calibration |
| `causal` | intervention (rung 2+) | "What happens if I *change* X?" | requires a design (RCT/IV/DiD) — **not in scope** |
| `prescriptive` | — | "What should I *do*?" | decision rule + expected value |
| `operational` | — | "Is it still working?" | drift, backtest error |

**Two methodological tripwires this tag exists to catch:**

1. **`descriptive` ≠ `causal`.** The 60-minute boundary notebook
   (`eda_pop_boundary_scatter.ipynb`) shows that the points distribution shifts across the 60-min
   line. That is `descriptive`. "An extra 30 minutes *causes* +X points" is `causal` (Pearl rung 2)
   and is **deliberately never studied** — this project stays on rungs 1 and prediction. The tag
   makes that boundary impossible to cross by accident.
2. **Gartner is not Pearl.** Gartner's four tiers (descriptive/diagnostic/predictive/prescriptive)
   are *question types*; they say nothing about causation. Causal inference is its own axis (Pearl's
   ladder). The mode set above keeps `causal` as a first-class, separately-gated tag rather than
   smuggling it inside "predictive."

**Header format** (drop the ID codes; keep the tag):

```markdown
# <plain-English question>
Mode: predictive · Stage: validate · Status: REJECTED
Population: minutes>0, DGW excluded, BGW accounted
```

---

## 4. Audit — every analysis on the map

This is the worked arc the rest of the repo should be read through. Each row is a real analysis,
its mode, its stage, its verdict, and the test contract that guards it.

| # | Analysis (real path) | Mode | Stage | Status | Test contract |
|---|---|---|---|---|---|
| A | 60-min **population validity** — `eda_04_population_validity.ipynb` | descriptive/structural | explore | **answered** — filter doesn't distort | framework helpers unit-tested; finding reviewed |
| B | **minutes as a returns signal** — `lenses/form/study.py` (FORM) | predictive | validate | **REJECTED** — uninformative | study-logic: determinism, leakage, no post-hoc |
| C | **availability prediction** — `lenses/avail/study.py` (minutes_roll8 → played_next_gw) | predictive | validate | **accepted** — roll8 for DEF/MID | study-logic + lag-1 leakage assertion |
| D | **minutes-stability conditioning of xGI** — `experiments/minutes_stability_study.py` | predictive/conditioning | validate | **REJECTED** — FRINGE > STABLE | study-logic: 31 tests (the template) |
| E | **signal integration** — `synthesis/synth01_study.py` | assemble | model | **partially set** — see note | registry contract (weights sum, lifecycle) |
| F | **signal ledger** — `signals/characterisation/` + `signals/governance/weight_registry.yaml` | govern | model | **the ledger** | governance consistency, traceability |
| G | **60-min boundary** — `eda_pop_boundary_scatter.ipynb` | descriptive | explore | **describes a regime shift** | helpers unit-tested; explicitly NOT causal |
| — | rolling-xGI window choice — `experiments/rolling_xgi_study.py` | predictive | validate | (window selection) | study-logic + leakage |
| — | fixture/market lenses — `lenses/fixture_gw/`, `lenses/market/` | predictive | validate | (per verdict) | study-logic |
| — | season **backtest** — `operational/phase9_backtest.py` | operational | monitor | **design/partial** | the backtest *is* the test artifact |

**The arc reads cleanly with no back-references:**

> A defines the population → B fails (minutes alone is noise) → C reframes the same raw signal as
> an *availability* question and succeeds → D tries to rescue xGI by conditioning on stability and
> fails → E integrates the survivors into weights → F records them in the governed ledger →
> G describes the boundary that started it all. Then monitor loops back to explore.

If a future analysis can't be placed on this table with one mode and one stage, that's the signal
it's conflating axes again.

**The `model` stage is only partly governed — say so.** "Weights set" is too clean. The real state,
per `weight_registry.yaml` and `synth01_decisions.yaml`:

- **Evidence-based:** SYNTH-01 produced composition weights **only for the DEF/MID signal groups**
  (`G-SYNTH1-*` decisions, with partial-rho thresholds and weight CIs).
- **Still editorial:** the intelligence **module** weights (captain, value, transfers, fixtures)
  are flagged `PROVISIONAL-EDITORIAL` — *"editorial judgments set before the lens-study methodology
  was established."* They have **not** passed a calibration study.
- **Known and deferred:** SYNTH-01 found FDR-quartile conditioning changes signal rank ordering in
  **>15% of cases** (a `MATERIAL` effect); implementation is deferred, with binary-DGW as the current
  proxy.

So the model spec is *part governed-ledger, part editorial, with one material unimplemented effect.*
The `model` stage's test contract (§5) covers the governed half; the editorial weights are a **known
gap**, not a validated choice. A `monitor`-stage calibration study is the trigger to close it.

---

## 5. Per-stage test contract (the SDET column)

Tests here are the **specification**, not afterthought coverage. For analytics, an inverted
pyramid wins: a schema contract or a leakage assertion catches whole *classes* of silent error
that a thousand unit tests miss. Data correctness ≠ line coverage.

**Test stack, ordered by leverage:**

1. **Schema / contract** — Pandera at each boundary (`MART_SCHEMA`, `FEAT_SCHEMA`), grain,
   dtype/null. *The spec.* Already live: `dal/mart/mart_schema.py`, `tests/test_mart_schema.py`.
2. **Invariant / data-quality** — BGW→null perf, DGW→`fixture_count == 2`, no negative minutes,
   referential integrity.
3. **Determinism / reproducibility** — identical fingerprint across runs, no hidden random state.
4. **Leakage / causality** — `assert_no_future_leakage`, lag-1 respected. *One silent leak
   inflates every downstream study.* Enforced structurally in `kernels/windows.py`.
5. **Unit** — pure transforms.
6. **Integration** — layer joins, no row loss / fan-out (fixture DB).
7. **E2E** — one `pipeline.run() → load()`.
8. **Golden / regression** — freeze scorer recommendations + mart slices.
9. **Study-logic** — per study: determinism, accounting closure, no post-hoc thresholds.
   `minutes_stability_study`'s 31 tests are the template.

**Stage → contract:**

| Stage | Artifact | Test contract |
|---|---|---|
| dal *(substrate)* | mart | schema + invariant + join + determinism + leakage |
| kernels *(shared lib)* | stat functions | unit (pure math) + determinism |
| explore | hypotheses | framework code unit-tested; **findings reviewed, not unit-tested** |
| validate | verdicts | study-logic: determinism, leakage, accounting closure, no post-hoc thresholds |
| model | spec / registry | registry contract: weights sum, lifecycle states valid, governance↔traceability consistent |
| serve | recommendations | golden/regression + **consumes** the mart contract (doesn't re-validate it) |
| monitor | backtest / drift | the backtest *is* the test artifact |

**The fixture DB is a first-class test artifact.** `tests/fixtures/test.db` (gitignored, built by
`create_test_db.py`) must be *curated* to contain the hard cases: BGW, DGW, mid-season transfer,
warm-up sub, zero-minute, red card, multi-position. Add a **fixture-coverage meta-test** that
asserts each scenario is present — so coverage of edge cases is itself tested. **Never** default a
test to the live `~/.fpl/fpl.db` (non-deterministic, local-only — that was the original CI bug).

**CI lanes** (markers): `unit` + `contract` on every push; `integration` on PR; `e2e` / `live`
nightly or self-hosted only.

**Open hole to close:** `mypy` is `continue-on-error` with 8 known errors. Make it **blocking**
once those 8 are fixed. Until then it's documentation, not a gate.

**Right-size guardrail:** prioritize contract + determinism + leakage + a handful of golden tests.
**No property-based testing** until a *recurring* invariant bug actually appears.

---

## 6. ID-diet — six namespaces down to two

**Keep two:**

1. **Signal *findings* keyed by a composite, not a bare column name.** The naive version of this
   rule ("just use the column name") is **wrong**, and the governance data proves it: `minutes_roll3`
   is evaluated as **both** `FORM-006` (lens FORM, target `total_points` → REJECTED) **and**
   `AVAIL-001` (lens AVAIL, target `played_next_gw` → approved at MID). Same column, opposite verdicts.
   The column names the *input*; a finding is `(signal × lens/target × position)`. So the durable key
   is the **composite** — e.g. `minutes_roll3@form:total_points` vs `minutes_roll3@avail:played_next_gw` —
   not an opaque `AVAIL-001`, but not the bare column either. The win over the status quo is that the
   key is *self-describing* (you can read what was tested), where `FORM-006`/`AVAIL-001` are not.
2. **Decision SLUGs in one decision log.** Human-readable, e.g. `reject-minutes-as-form`,
   `adopt-roll8-availability`, `set-synth-weights`. One append-only `docs/decisions/` log keyed by
   slug, each entry naming its stage, mode, verdict, and date.

> **Feasibility caveat.** The codes being retired (`FORM-006`, `AVAIL-001`, `G-SYNTH1-*`) are
> **load-bearing keys** in `signals/governance/evaluation_metadata.yaml` and `synth01_decisions.yaml`,
> which `intelligence/weight_registry.py` reads and *hard-fails* on. The ID-diet is therefore **not a
> docs-only rename** — it requires migrating those YAML keys to the composite scheme and updating the
> loader. Treat it as a code change with tests, not a cosmetic sweep. This is why §6 stays *prescribe-only*.

**Kill four:**

| Killed | Was | Replaced by |
|---|---|---|
| `G-EDA{N}-{NN}` gate codes | EDA→lens gate references | a finding's plain title in the explore artifact |
| `SYNTH-01`, `ENG-02`, `LENS-*` | study/run codes | the study's folder name + a decision slug |
| `Phase N` (e.g. `phase9_backtest`) | sequencing labels | the stage name (`monitor`) |
| timestamped run dirs (`SYNTH-01-20260527_113400`) | one dir per execution | durable findings live in the stage artifact; runs are throwaway |

**Migration plan (prescribe-only — not executed here):**

1. Add the mode/stage header to each existing study + notebook (mechanical, no logic change).
2. Create `docs/decisions/` with one slug entry per verdict in the §4 audit table.
3. Extract any durable conclusion still trapped in `studies/runs/*` and `signals/runs/*` into its
   stage artifact, then the run dirs become safe to delete (they're already gitignored churn).
4. Rename `phase9_backtest.py → backtest.py` when monitor is next touched. No rush.

Code-namespace strings inside the domain-agnostic `kernels/` (a few docstrings still say "EDA-5",
"spine") should drop the IDs too — substrate must not carry lifecycle codes.

---

## 7. When to graduate a layer (anti-over-engineering triggers)

Default answer to "should we add infrastructure?" is **no**. Each row is the *specific* condition
that flips it to yes. Until then, the heavier tool is cost without benefit on a solo project.

| Tool you might add | Build it only when… | Until then |
|---|---|---|
| **Model-registry service** | more than one person *or* more than one model edits the weights | `weight_registry.yaml` + governance code is enough |
| **Feature store** | features are recomputed by ≥2 independent consumers and drift between them | the mart *is* the feature store |
| **MLflow / experiment tracker** | you run sweeps you can't reconstruct from git + the decision log | git history + `docs/decisions/` slug log |
| **Property-based testing** | a *recurring* invariant bug slips past example-based tests | curated fixture DB + golden tests |
| **Orchestration (Airflow/Dagster)** | the pipeline has external schedules/retries/backfills | `make` + `pipeline.run()` |
| **Folder renames** to match stage names | the study-name folders actively mislead a reader | keep the map in this doc; folders can lag |

**Out of scope by design** (note, don't build): MLOps-at-scale, security/privacy, performance,
cost optimization, product/UX. All N/A or trivial for a solo, single-season, local heuristic.

---

## 8. Doc reconciliation — overlap, migrate, and a drift warning

`adlc.md` is the authority for the **analysis lifecycle and its test contracts**. It does *not*
claim to replace the existing architecture docs wholesale — some of them carry detail this doc
deliberately omits and which should be **kept or migrated, not deleted**. The honest split:

| Existing doc | Relationship to ADLC | Action |
|---|---|---|
| `decision-lifecycle.md` | overlaps the stage flow, but its **per-stage failure-mode tables** are unique and valuable | **merge** into `runtime-execution.md` (with `operational-flow.md`); keep the failure tables, drop the "lifecycle" name + 4-stage framing |
| `layer-boundaries.md` | overlaps §2 flow rules, but its **ownership non-overlap matrix** is unique | keep the matrix; the import-direction story becomes §2 |
| `operational-flow.md` | the 3-command run sequence | **merge** into `runtime-execution.md` (with `decision-lifecycle.md`); keep the run sequence |
| `system-model.md` | the 3-plane model (Control/Execution/Measurement) — a **competing vocabulary** | reconcile: pick one model (see note below) |
| `testing-strategy.md` | overlaps §5, but lists the **real test inventory** | keep the inventory; the strategy framing becomes §5 |
| `test-coverage.md` | the **54-invariant status map with real test names** — unique and valuable | keep as-is; it *is* the §5 contract made concrete |

This PR is prescribe-only — no deprecation headers added, no files edited. The table is the plan.

**Vocabulary decision (DECIDED).** The repo runs three parallel mental models that "coexist": the
4-layer import hierarchy, the 3-plane model (`system-model.md`), and the 4-stage decision lifecycle.
ADLC's 5-stage + mode-tag framing would be a *fourth* — adding a vocabulary without retiring one *is*
the axis-conflation this redesign set out to fix. **Resolution:** `adlc.md` is the sole owner of the
word **"lifecycle."** The runtime path is *not* a lifecycle; it is execution. Concretely:

- **`adlc.md`** = the analysis lifecycle (`explore → validate → model → serve → monitor`).
- **`decision-lifecycle.md` + `operational-flow.md` → merge into `runtime-execution.md`** — a single
  runtime doc that keeps the **failure-mode tables** + the **3-command run sequence**, drops the word
  "lifecycle" and the 4-stage framing, and is cross-linked from ADLC's `serve`/`monitor` stages (the
  seam where the two meet). No file in the repo carries "lifecycle" in its name except `adlc.md`.

This is a rename **+ merge** (3 docs → 2), so it breaks inbound links and must scrub stale paths along
the way — it belongs in the drift-cleanup PR, sequenced in `doc-drift.md` §5, not this branch.

**Drift warning (read `doc-drift.md` first).** Several of the docs above are **factually stale** —
they cite module paths, directories, and test counts that no longer exist in the code
(`signals/registry/`, `dal/state/`, `intelligence/_base.py`, `docs/adr/*`, "739 tests"). A doc
that authoritatively points at a path that's gone is worse than no doc. The full inventory is in
[`doc-drift.md`](doc-drift.md). **Fix the drift before acting on any supersede/migrate decision
above** — otherwise you'd be migrating content that already describes the wrong system.

`EVAL_DESIGN.md` (the Measurement-Plane spec) stays — it's the detailed design for the `monitor`
stage, which is still design-only (Stage 5 / "Measurement" is not yet built). ADLC names the
stage; `EVAL_DESIGN.md` specifies it.

---

## 9. One-screen summary

- **One substrate** (`dal/`, the mart) feeds **five stages**:
  `explore → validate → model → serve → monitor`. Knowledge flows one way; only `monitor → explore`
  loops back. `kernels/` is a shared pure-stats library the analysis stages import — a footnote,
  not a pillar.
- **Each analysis = one mode tag + one stage.** `descriptive`/`diagnostic`/`predictive`/`causal`/
  `prescriptive`/`operational`. `causal` is gated and out of scope by choice.
- **Tests are the contract**, leverage-ordered: schema → invariant → determinism → leakage →
  unit → integration → e2e → golden → study-logic. Fixture DB is curated and meta-tested. Make
  `mypy` blocking once 8 errors clear.
- **Two ID namespaces** survive: signal = column name; decision = slug in `docs/decisions/`.
  Everything else (`G-*`, `SYNTH-*`, `Phase N`, run-dir timestamps) is retired.
- **Build heavier infra only on its named trigger.** Default is no.
