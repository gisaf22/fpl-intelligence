# Research Layer — Analytical Strategy

**What this is:** the operating contract for the research layer — the order questions are
asked, the classes of analysis that answer them, the kill criteria that retire a signal early,
the firewall that separates exploration from confirmation, and the test discipline that makes a
verdict trustworthy.

**Scope.** This layer (`research/`) does one thing: turn DAL mart data into
**trusted verdicts about signals** — does this signal predict returns, is it stable, is it
non-redundant? It does *not* assign weights (that is `model/assemble`) and it does *not* build
features (that is `dal/feat`). Research stops at "this signal is trustworthy and additive."

**Status:** doctrine. Prescribe-first — the funnel and classes below are the contract; the folder
rename that makes the tree match them has landed (`studies → research`, see [adlc.md §7](../docs/architecture/adlc.md)).

> **Note on naming.** This file lives at `research/STRATEGY.md`. The topology rename has landed
> (`studies → research`, `synthesis → model/assemble`, `registry_sections + semantics → model/governance`).
> The doctrine never depended on the rename; it now matches the tree.

---

## 1. The funnel — cheapest kills first

A signal is guilty until proven useful. The research layer is a **funnel of progressively more
expensive tests**, ordered so that the cheapest way to kill a candidate runs first. By the time a
signal reaches the expensive out-of-sample confirmation, it has already survived four independent
ways of being wrong — and *that* is what makes the eventual verdict trustworthy.

```
  scope  →  describe  →  IS IT STABLE?  →  DOES IT MOVE WITH RETURNS?  →  IS IT NON-REDUNDANT?
   (who?)   (shape?)       (class 2)            (class 3)                     (class 4)
                                                                                  │
                                                       ═══ FIREWALL: pre-registration ═══
                                                                                  ▼
                                                              DOES IT PREDICT OUT-OF-SAMPLE?
                                                                       (class 6 — the verdict)
```

**The funnel is the *method*, not the filing system.** The five classes above define the order a
signal is interrogated — they are a per-study *template* and a `Mode:` tag, not the top-level
folders. The directory tree is organized by the durable **object** (the signal family), with the
**firewall** as the one process boundary that earns folder status:

```
research/
  kernels/                 shared pure-stats toolbox (no tier)
  foundation/              one-time, WHOLE-DATASET characterization (integrity, target &
                           population/scope validity) — the work that is not per-signal
  families/                PRIMARY AXIS — the durable object (signal family)
    form/
      explore/             below the firewall: describe · stability · associate (hypotheses)
      validate/            above the firewall: pre-registered confirmatory studies (verdicts)
      LENS_DESIGN.md       the family's pre-registration
    market/ · fixture/ · availability/      (same shape)
  findings/                FIRST-CLASS durable verdicts — a class × signal coverage matrix
```

**Why object-primary, not class-primary.** A signal is a thing you *own* and return to; "stability
analysis" is something you *do* to it. Folders encode ownership and durable objects; sequence and
process (the funnel, the lifecycle) live in metadata — the same rule [adlc.md](../docs/architecture/adlc.md)
applies to the lifecycle axis. Organizing by the five classes would scatter one signal's story
across five directories (object-centric lookup is the common case) and defer the catch-all problem
one level down (200 analyses in a flat `stability/`). The class view that *is* worth having —
"which signals lack a stability study?" — is served by the `findings/` coverage matrix, without the
fragmentation.

**Ownership model.** A *family* owns the full arc of its signals (`explore` → `validate`).
`foundation/` owns dataset-level characterization that precedes any single signal. `findings/` owns
the durable verdict of record and is the **only** handoff surface to `model/governance` (keyed by
the `signal@lens:target[#POS]` composite key). `kernels/` owns reusable math and depends on
nothing above it.

**Right-sizing.** Object-primary is the *target* topology. At current scale (~20 signals, 4
families) the physical layout is a minor concern; the load-bearing changes to make now are
first-class `findings/` and an explicit firewall. The full family inversion is **triggered** at >50
signals or a second domain (see the [adlc.md §7](../docs/architecture/adlc.md) trigger pattern).

**Evaluation grain.** Position (GK/DEF/MID/FWD) is not a tier — it is the unit *every* class is
evaluated at. Each class asks its question *within a position group*, so a verdict is
position-scoped (the `#POS` segment of the `signal@lens:target[#POS]` key). A signal may be
approved for one position and retired for another — e.g. `xgi_roll3` is approved for DEF only,
`xgi_roll5` for DEF and MID. There is no global, position-blind verdict.

---

## 2. The six classes of analysis + kill criteria

Every analysis carries exactly one of these classes as its stage/`Mode:` tag — the class is
metadata on the study, **not** its folder (see §1). If a study can't be placed in one class, it is
conflating questions and should be split. The "Lives in" column shows where the work physically
sits under the object-primary tree.

| # | Class | Question it answers | Lives in | Mode | Kernel | Kill criterion (retire the signal if…) |
|---|---|---|---|---|---|---|
| 0 | **Scope / eligibility** | Who is in the population? | `foundation/` | descriptive | `population`, `scoping` | population is so scope-sensitive the signal can't be evaluated stably |
| 1 | **Univariate / distributional** | What does this one signal look like — shape, spread, zero-mass, missingness? | `foundation/` (dataset) · `families/<f>/explore/` (per-signal) | descriptive | `distribution` | degenerate: near-constant, near-all-null, or no usable variance |
| 2 | **Temporal / stability** | Is the signal persistent across GWs, or noise? | `families/<f>/explore/` | descriptive→diagnostic | `stability`, `windows` | non-stationary / unstable across GW blocks — cannot inform next GW |
| 3 | **Relationship (signal↔target)** | Does it co-move with returns, and in what shape? | `families/<f>/explore/` | diagnostic | `correlation`, `geometry` | no marginal association with returns; no interpretable geometry |
| 4 | **Redundancy (signal↔signal)** | Is this *new* information or a duplicate? | `families/<f>/explore/` | diagnostic | `redundancy` | collinear with an already-trusted signal; partial-ρ ≈ 0 |
| 5 | **Conditioning / heterogeneity** | Does the relationship hold across context, or only in a subgroup? | `families/<f>/explore/` | diagnostic | `conditioning` | effect is a subgroup artifact; reverses or vanishes under a key moderator |
| 6 | **Predictive validation** | Does it forecast next-GW returns out-of-sample, lag-respecting? | `families/<f>/validate/` | predictive | `metrics`, `windows`, `multiplicity` | OOS rank-correlation fails the **pre-registered** threshold |

**What is NOT a research class:** combination/weighting (→ `model/assemble`), feature construction
such as rolling windows (→ `dal/feat`), lifecycle/governance bookkeeping (→ `model/governance`).

---

## 3. The firewall — exploration vs confirmation (Tukey EDA/CDA)

The single most defensive decision in this layer is to **physically separate hypothesis-generating
work from hypothesis-testing work**, because that is what prevents the garden-of-forking-paths
failure (snoop the data, then "confirm" the pattern you already saw) that destroys analytic trust.

**Below the firewall (`foundation/` + `families/<f>/explore/`) — EXPLORATORY.** Snooping is *allowed*. Output is **candidate
hypotheses**, never claims. Code is throwaway; the reviewed *finding* is the durable artifact. No
sentence produced here may be cited as a confirmed effect. (This is why the 60-minute boundary
finding is tagged explicitly *not causal*.)

**Crossing the firewall (`explore/ → validate/`) — PRE-REGISTRATION.** Before any confirmatory code runs, a
design is **git-committed**: population, signal, target, window, the accept/reject threshold, and
the full family of tests. The existing `LENS_DESIGN.md` per lens is exactly this artifact — the
contract is that it is committed *before* the study results, in git order.

**Above the firewall (`families/<f>/validate/`) — CONFIRMATORY.** Design is locked. No peeking, no re-tuning.
Output is a **verdict** (accept/reject) — and because it was pre-registered, a *reject is as
informative as an accept*.

**The loop is disciplined.** A rejected hypothesis loops back to exploration — but a confirmation
*failure* must reopen exploration with a **new question and a new pre-registration**. It must never
silently become "tweak the window and re-test on the same data." That asymmetry — failures reopen
exploration, they do not re-enter confirmation on the same evidence — is the line between a research
layer and a hindsight-fitting machine.

---

## 4. Claim ceiling (Gartner intent × Pearl rung)

The platform ascends Gartner's ladder all the way to `prescriptive` (in `serve`) while operating on
**Pearl rung 1 (association/prediction)**. Higher rungs are **gated, not foreclosed**:

- `descriptive` / `diagnostic` / `predictive` analyses are admissible now.
- `causal` (rung 2+, "what happens if I *change* X") is **never studied** without a redesign that
  justifies a structural causal model. Decision-counterfactuals ("what if I'd captained X") are
  arithmetic regret, not causal inference, and are admissible.

Every analysis carries one mode tag in its header (`Mode: predictive · Stage: validate · Status: …`).
The tag exists to make "this is descriptive, not causal" impossible to blur by accident.

---

## 5. Test strategy — SDET discipline for the research phase

You do **not** test the *conclusion* — you test the **instrument** and the **process**. The finding
itself is validated by the firewall + human review, never by an `assert`. Three layers:

| Layer | What you test | How |
|---|---|---|
| **Instrument** (`kernels/`) | pure stat functions compute correctly | unit + **metamorphic/property** tests |
| **Harness** (study runner) | determinism, leakage, accounting closure, verdict-artifact schema | a shared `StudyContract` test fixture every `validate` study inherits |
| **Process** (the firewall) | pre-registration order, no post-hoc thresholds, multiplicity control | **CI-enforced**, not convention |

**Leverage order** (an inverted pyramid — a leakage assertion catches what a thousand unit tests
miss): leakage → determinism → schema/accounting → study-logic → unit/metamorphic → golden.

**Non-negotiable contracts for `validate`:**

1. **Leakage / temporal integrity** — `kernels/windows.assert_no_future_leakage`, lag-1 respected.
   One silent leak inflates *every* downstream verdict. This is the P0 gate.
2. **Determinism** — identical fingerprint across runs; no hidden random state.
3. **No post-hoc thresholds** — the accept/reject criterion is read from the locked pre-registration,
   not hardcoded after results are seen.
4. **Multiplicity** — a study declares its test family; family-wise / false-discovery correction is
   applied via `kernels/multiplicity`. (Note: "FDR" elsewhere in this repo means *Fixture Difficulty
   Rating*, a conditioning variable — not False Discovery Rate. Do not conflate them.)
5. **Verdict golden-freeze** — the verdict artifact is snapshot-tested so a refactor cannot silently
   flip an accept→reject.

**Where PBT earns its keep.** The repo default is "no property-based testing until a recurring bug."
The exception is `kernels/` — pure math where metamorphic relations are cheap and catch whole classes
of silent error: rank-correlation invariant under monotonic transform, under row permutation, and
under positive rescaling.

**Known gaps this strategy closes** (tracked as deliverables, see [adlc.md §5](../docs/architecture/adlc.md)):
the four production lenses (`form`, `avail`, `market`, `fixture_gw`) currently lack study-logic tests;
there is no shared `StudyContract`; the firewall is convention, not CI-enforced; there is no
multiplicity control anywhere.

---

## 6. One-screen summary

- **One funnel, cheapest kills first:** scope → describe → stability → relationship → redundancy →
  **firewall** → predictive validation. A signal dies as early as it can.
- **Six classes are the *method* (a study template + `Mode:` tag), not folders.** The tree is
  object-primary: `kernels/` · `foundation/` · `families/<f>/{explore,validate}/` · `findings/`,
  with the firewall as the one structural process split.
- **The firewall is real:** exploration may snoop and emits hypotheses; confirmation is
  pre-registered and emits verdicts; failures reopen *exploration*, never re-test on the same data.
- **Claim ceiling:** Gartner→prescriptive while staying on Pearl rung 1; causal is gated.
- **Test the instrument and the process, never the conclusion.** Leakage is the P0 gate; the
  verdict is frozen; kernels get metamorphic tests; the firewall is CI-enforced.
