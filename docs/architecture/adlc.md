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
| **explore** | `research/foundation/`, `research/families/<f>/explore/` | "What's in the data — what's worth testing?" | descriptive, diagnostic | **hypotheses** (durable findings; throwaway code) |
| **validate** | `research/families/<f>/validate/` | "Does this signal actually predict returns?" | predictive, causal | **verdicts** (pre-registered, accept/reject) |
| **model** | `model/assemble/`, `model/governance/`, `signals/` | "Which signals, at what weights, governed how?" | assemble / govern | **model spec** (the governed ledger) |
| **serve** | `intelligence/` | "Who do I captain / transfer / hold?" | prescriptive | **recommendations** |
| **monitor** | `archive/monitor/` | "Is the model still right in-season?" | operational | **drift / backtest** (loops to explore) |

The folders do not have to be renamed to adopt this. The **map is the contract**; the rename is
optional cosmetics that can follow later (§7).

---

## 3. The mode tag — question type as Axis 3

Every analysis carries exactly one **mode tag** in its header. This is the single highest-value,
lowest-cost change: it makes claim-type legible and stops descriptive work from being read as
causal. Modes fall into **two families** (see ADR-008 for the rationale): **analysis modes**
(what kind of *question* — Gartner's intent ladder, with `causal` kept as a gated Pearl rung)
and **process modes** (a lifecycle *activity*, not a question — for the model/monitor stages).

**Analysis modes** — the question type (Gartner intent axis; Pearl rung in brackets):

| Mode | Pearl rung | The question | The honest statistic |
|---|---|---|---|
| `descriptive` | assoc. (rung 1) | "What does the data look like?" | distribution, median/quantiles, hit-rate |
| `diagnostic` | assoc. (rung 1) | "Why did this happen / what co-moves?" | conditional distributions, decomposition |
| `predictive` | assoc. (rung 1) | "Does X forecast Y (lag-respecting)?" | out-of-sample rho, lift, calibration |
| `causal` | intervention (rung 2+) | "What happens if I *change* X?" | requires a design (RCT/IV/DiD) — **gated, not foreclosed** (see stance below) |
| `prescriptive` | — (decision) | "What should I *do*?" | decision rule + expected value |

**Process modes** — a lifecycle activity, not a claim about the data (model/monitor stages):

| Mode | Stage | The activity |
|---|---|---|
| `assemble` | model | combine validated signals into a candidate spec (weights, composition) |
| `govern` | model | record signals + decisions in the governed ledger (lifecycle, traceability) |
| `operational` | monitor | "Is it still working?" — drift, backtest error |

**The stance (current, with reopening trigger).** This project ascends the Gartner ladder all
the way to `prescriptive` (the serve stage) while operating on **Pearl rung 1 (association)**.
Higher rungs are **gated, not foreclosed** (framed like the §7 "build it only when…" triggers):

- **Decision-counterfactuals** ("what if I had captained X?") are *admissible now* — in FPL the
  alternative's outcome is observed (all players' points are public), so it is arithmetic
  regret/opportunity-cost, not rung-3 inference.
- **Causal/physical counterfactuals** ("what if this player had played 90 minutes?") stay
  *gated pending a redesign* that justifies a structural causal model. Reopening is allowed.

**Two methodological tripwires this tag exists to catch:**

1. **`descriptive` ≠ `causal`.** The 60-minute boundary analysis
   (`research/foundation/population/population_boundary.ipynb`) shows that the points distribution shifts across the 60-min
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
| A | 60-min **population validity** — `research/findings/FINDINGS.md` (G-EDA4-*) | descriptive/structural | explore | **answered** — filter doesn't distort | framework helpers unit-tested; finding reviewed; notebook retired |
| B | **rolling xGI as a form signal** — `research/families/form/validate/study.py` (FORM) | predictive | validate | **PARTIAL** — xgi_roll3 (DEF), xgi_roll5 (DEF, MID) approved | study-logic: determinism, leakage, no post-hoc |
| C | **availability prediction** — `research/families/availability/validate/study.py` (minutes_roll8 → played_next_gw) | predictive | validate | **accepted** — roll8 for DEF/MID | study-logic + lag-1 leakage assertion |
| D | **minutes-stability conditioning of xGI** — `research/families/form/explore/minutes_stability_study.py` | predictive/conditioning | validate | **REJECTED** — FRINGE > STABLE | study-logic: 31 tests (the template) |
| E | **signal integration** — `model/assemble/composition_study.py` | assemble | model | **partially set** — see note | registry contract (weights sum, lifecycle) |
| F | **signal ledger** — `signals/characterisation/` + `signals/governance/weight_registry.yaml` | govern | model | **the ledger** | governance consistency, traceability |
| G | **60-min boundary** — `research/foundation/population/population_boundary.ipynb` | descriptive | explore | **describes a regime shift** | explicitly NOT causal; notebook retired to informative population layer |
| — | rolling-xGI window choice — `research/families/form/explore/rolling_xgi_study.py` | predictive | validate | (window selection) | study-logic + leakage |
| — | fixture/market lenses — `research/families/fixture/validate/`, `research/families/market/validate/` | predictive | validate | (per verdict) | study-logic |
| — | season **backtest** — `archive/monitor/phase9_backtest.py` | operational | monitor | **design/partial** | the backtest *is* the test artifact |

**The arc reads cleanly with no back-references:**

> A defines the population → B finds rolling xGI *partially* informative as a form signal
> (xgi_roll3/roll5 for DEF/MID), while minutes alone proves uninformative as a returns signal →
> C reframes that raw minutes signal as an *availability* question and succeeds → D tries to
> rescue xGI by conditioning on stability and fails → E integrates the survivors into weights →
> F records them in the governed ledger → G describes the boundary that started it all. Then
> monitor loops back to explore.

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

> The concrete realisation of this contract is [`test-coverage.md`](test-coverage.md) — the
> 70-invariant status map with real test names (incl. the fixture-coverage meta-tests, the
> mypy gate, and the ADR-003 key-grammar migration tests). This section is the *principle*; that doc is
> the *current state* made concrete. Keep them cross-linked; do not duplicate the invariant
> list here.

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

**Closed (Phase 5):** `mypy` is a **blocking gate**. `uv run mypy` runs in CI with no
`continue-on-error`, scoped to production modules (`[tool.mypy] files = ["dal", "signals",
"intelligence", "domain", "population"]`). The pre-existing errors it surfaced (the count had
drifted from 8 to 10) were *fixed*, not silenced — including a real optional-type bug in
`stg_schema.py` and a guarded `None` comparison made type-visible in `association.py`.

**Right-size guardrail:** prioritize contract + determinism + leakage + a handful of golden tests.
**No property-based testing** until a *recurring* invariant bug actually appears.

---

## 6. ID-diet — two namespaces, not six

The repo keeps **two** ID namespaces and retires the other four:

1. **Signal findings** keyed by a self-describing composite — `signal@lens:target[#POS]`, not a bare
   column name and not an opaque code. The grammar, the worked `minutes_roll3` collision (FORM-rejected
   vs AVAIL-approved), and the hard-failing loader contract are owned by
   [ADR-003](../decisions/003-composite-signal-finding-key.md).
2. **Decision verdicts** as human-readable slugs in one append-only log — owned by
   [ADR-004](../decisions/004-decision-slug-log.md); the log itself is [docs/decisions/](../decisions/).

Retired: `G-EDA*` gate codes, `SYNTH-01`/`ENG-*`/`LENS-*` study codes, `Phase N` sequencing labels, and
timestamped run dirs. The composite-key migration was a load-bearing **code** change (the killed codes
were keys the governance loader hard-fails on), now executed — ADR-003 is the record, not this section.

Loose end: a few `kernels/` docstrings still carry old IDs (`EDA-5`, `spine`); the substrate must not
carry lifecycle codes, so drop them when kernels is next touched.

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

## 8. Doc reconciliation

`adlc.md` is the authority for the **analysis lifecycle and its test contracts**, and the sole owner of
the word **"lifecycle"** in the repo. It does not replace the other architecture docs — each owns a
different axis, mapped in [analytical-architecture.md](analytical-architecture.md). The reconciliations:

- The **3-plane runtime model** (`system-model.md`) is an orthogonal peer, not a competing vocabulary —
  the split is settled in [ADR-005](../decisions/005-system-model-vocabulary-reconciliation.md).
- `decision-lifecycle.md` + `operational-flow.md` were merged into
  [runtime-execution.md](runtime-execution.md) — failure-mode tables and the run sequence kept, the
  "lifecycle" framing dropped.
- [`EVAL_DESIGN.md`](../../signals/governance/EVAL_DESIGN.md) remains the detailed spec for the
  `monitor` stage, which is still design-only; ADLC names the stage, EVAL_DESIGN specifies it.

---

## 9. One-screen summary

- **One substrate** (`dal/`, the mart) feeds **five stages**:
  `explore → validate → model → serve → monitor`. Knowledge flows one way; only `monitor → explore`
  loops back. `kernels/` is a shared pure-stats library the analysis stages import — a footnote,
  not a pillar.
- **Each analysis = one mode tag + one stage.** Two mode families (ADR-008): *analysis modes*
  `descriptive`/`diagnostic`/`predictive`/`causal`/`prescriptive` (Gartner intent + gated Pearl
  rung) and *process modes* `assemble`/`govern`/`operational` (model/monitor activity). The
  project ascends Gartner to `prescriptive` while staying on Pearl rung 1; higher rungs are
  gated-not-foreclosed.
- **Tests are the contract**, leverage-ordered: schema → invariant → determinism → leakage →
  unit → integration → e2e → golden → study-logic. Fixture DB is curated and meta-tested.
  `mypy` is a blocking CI gate (production scope).
- **Two ID namespaces** survive: signal finding = composite key (`signal@lens:target[#POS]`);
  decision = slug in `docs/decisions/`. Everything else (`G-*`, `SYNTH-*`, `Phase N`, run-dir
  timestamps) is retired.
- **Build heavier infra only on its named trigger.** Default is no.
