# CHARACTERIZE_DESIGN.md — the characterization layer

**Status:** LOCKED
**Locked:** 2026-08-16
**Type:** design lock · **Governs:** `research/registry/sections.py`, `research/registry/assembler.py`,
`research/kernels/descriptive/*`, `research/kernels/diagnostic/{shape,stability,panel,tail}.py`,
`research/kernels/inferential/monotonicity.py`
**EDA basis:** `research/findings/FINDINGS.md`
**Peers:** the four `research/families/*/LENS_DESIGN.md` files (qualification). This document is their
upstream counterpart and mirrors their structure.

This is a record of what characterization *is*, written after the code existed. Characterization is the
one stage in this repository that never had a locked design — `docs/predictive-layer-plan.md:31` names
that absence directly ("the characterization layer is the one stage with no locked design doc, unlike
the four family `LENS_DESIGN.md` files"), and it is the reason the layer drifted: with no design to say
what it was for, `sections.py` was filed under `research/registry/` beside a promotion/publication
pipeline and came to look like a second verdict system rather than the diagnostic it is. This document
fixes what it is, and §3 records a live contradiction it exists to end.

---

## 1. Purpose

Characterization answers one question: **what is the shape of this signal's relationship to the
target?**

Concretely, for each (signal × position) cell it produces four sections:

| Section | What it establishes | Kernel |
|---|---|---|
| **geometry** | the bin scheme the signal warrants, the per-bin target means, the relationship shape (`monotonic_positive`, `monotonic_negative`, `threshold`, `non_monotonic`, …), the Q1→Q5 mean gap, and a bootstrap `monotonicity_confidence` | `kernels/descriptive/binning.py` → `kernels/diagnostic/shape.py` → `kernels/inferential/monotonicity.py` |
| **stability** | whether the signal's distribution holds across the three season blocks, and the pooling verdict that follows | `kernels/descriptive/block_distributions.py` → `kernels/diagnostic/stability.py` |
| **decomposition** | how much of the association is *between* players (identity) versus *within* a player (state), with a player-clustered bootstrap and a CI-gated `panel_class` | `kernels/diagnostic/panel.py` |
| **haul** | whether the association survives removal of haul rows, i.e. whether it is carried by the tail | `kernels/diagnostic/tail.py` |

In CRISP-DM terms this is **Data Understanding shading into Data Preparation**. It describes the
material and decides how the material should be cut before anything is tested on it. It is not
Modeling.

**Characterization does not gate signals.** It emits no pass/fail, no `lens_status`, no approval. A
signal that comes out `non_monotonic` here is not rejected — it is *described* as non-monotonic, and
qualification decides what that is worth under its own pre-registered gate. The verdict authority for
"does this signal carry usable information" belongs to the four lens studies and to nothing else.

This bears stating because the code as it stands invites the opposite reading: `assembler.py` attaches
an `association_class`, and `model/governance/{semantics,promotion}.py` attach a `promotion_class` and
a `downstream_status` — three labels that look like verdicts sitting on characterization output. They
are *interpretations of shape*, not qualification outcomes. Under this design they carry no gate
authority, and PROJECT.md §2's five-parallel-vocabularies problem is theirs to answer, not
characterization's to extend.

---

## 2. The one concrete link: characterization's binning is qualification's binning

This is the substantive design decision in this document, and the only place characterization is
permitted to reach downstream.

**Decision.** Characterization owns bin geometry for the whole research layer. Qualification's Gate 2
(quintile decision-relevance) must consume the bin scheme characterization selects for a signal, via
`research/kernels/descriptive/binning.py::select_bucketing_scheme`. It must not cut its own.

The scheme selector is already written and already position-aware in its inputs:

- `fdr_avg` (and any signal in `FDR_SIGNALS`) → **ordinal**, on
  `FDR_ORDINAL_BINS = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]` with labels `1…5` — that is, binned on the
  rating's own natural scale, one bin per FDR value;
- fewer than `SPARSE_THRESHOLD = 10` distinct non-zero values → **discrete** (`0 / 1 / 2+`);
- zero-fraction above 0.60 → **two-stage** (zero bin, then `low_nz / mid_nz / high_nz`);
- otherwise → **quantile**, `QUANTILE_N_BINS = 5`.

Qualification today does none of this. `research/kernels/hypothesis/stratification.py:64-70` cuts every
signal the same way:

```python
ranked["quintile"] = pd.qcut(ranked[signal].rank(method="first"), 5, labels=[...])
```

`method="first"` breaks ties **by row order**. On a continuous signal that is harmless. On a heavily
tied ordinal signal it is not: it manufactures boundaries inside a single value and then reads the
difference across that boundary as if it were signal.

**What this replaces, and what it resolves.** `docs/PROJECT.md` §5 documents the consequence on the
mart as it stands: `fdr_avg` takes exactly seven distinct values, and at DEF **1,684 of 2,837 rows —
59% — sit at exactly 3.0**. The rank-tie-break cut puts Q2 and Q3 at **100% `fdr_avg == 3.0` at both
DEF and MID** — the same fixtures, split by row order — and their means differ by 0.34 (DEF) and 0.24
(MID) from that alone. That difference *is* the single reversal that sets `is_monotonic=False` and
fails `fdr_avg` at Gate 2. Cut on `FDR_ORDINAL_BINS` instead, the trend is recovered: MID −1.978
strictly monotonic, FWD −1.815 strictly monotonic, GK −2.143 strictly monotonic, DEF −2.891 with one
reversal at bins 1→2.

So the design decision is: **the ordinal scheme is upstream input to the quintile gate, replacing the
`qcut(rank(method="first"), 5)` tie-break.** Adopting it changes the fixture lens's Gate-2 outcome for
`fdr_avg` at MID, FWD and GK, and does not cleanly rescue DEF.

Three limits on that claim, recorded here so the change is not oversold:

1. **DEF is not rescued.** The ordinal DEF profile still reverses at bins 1→2 (+0.105, on 143 and 358
   rows). A binning fix is not an outcome fix.
2. **MID passes at low confidence.** `eda_03_joint_registry.csv` gives `fdr_avg@MID` a
   `monotonicity_confidence` of 0.675, below the schema's `MONO_CONF_HIGH` of 0.80. It passes flagged.
3. **The same tie-break is used elsewhere.** `model/assemble/composition_study.py::_fdr_moderation_check`
   builds its FDR quartiles the same way, so that check's middle strata are arbitrary in the same
   manner. This document does not govern `model/assemble/`; the defect is recorded, not fixed here.

**This link is a design-time dependency, not a runtime one.** Qualification imports the *scheme
selector* (a kernel). It does not read a characterization artifact at run time, and characterization
does not execute inside a lens study. See §6.

---

## 3. The contradiction this design exists to end

Two committed artifacts in this repository state opposite monotonicity verdicts for the same feature,
at the same position, against the same same-GW target:

| Artifact | Records | Value |
|---|---|---|
| `research/findings/records/eda_03_joint_registry.csv` | `fdr_avg@MID` → `relationship_geometry` | **`monotonic_negative`**, `q1_q5_mean_gap = −1.868`, `monotonicity_confidence = 0.675` |
| `research/families/fixture/validate/evidence.yaml` | `fdr_avg@MID` → `decision_class` | **`uninformative`**, via Gate 2 with `monotonic = False` |

Neither artifact is wrong about its own computation. Both are correct reports of what their own binning
produced. The difference is *entirely* the binning scheme — ordinal-on-the-native-scale versus
rank-tie-broken quintiles — and nothing in either file tells a reader that.

**Under this design, both cannot be authoritative.** The resolution is directional, not diplomatic:

> Qualification's binning is replaced by characterization's. It is not run in parallel with it, and the
> two are not to be reported side by side as complementary reads.

A verdict system in which the answer depends on which of two committed files you happen to open is not
a verdict system. Characterization is the layer whose job is bin geometry; qualification is the layer
whose job is the gate. Each does one of those, and Gate 2 is evaluated on the geometry characterization
selected.

**What this does not do.** It does not retroactively flip any committed `evidence.yaml`. The four
`evidence.yaml` and `annotations.yaml` files are the frozen record of studies run under
`LENS_DESIGN.md` as locked on 2026-05-22 and amended once by ADR-010; they stand as measurement, and
this document does not amend them. Adopting §2 means the *next* execution of the fixture lens produces
a different Gate-2 outcome for `fdr_avg`, under an amended `LENS_DESIGN.md` §9 that cites this
document. Until that amendment is written and the lens re-run, the contradiction above is live and both
files remain on disk saying opposite things. That is the state, recorded.

**A second, unrelated labelling defect sits nearby and is not characterization's to fix.**
`research/families/{form,market}/validate/evidence.yaml:2` both read `target: total_points` while the
studies that wrote them set `TARGET = "total_points_next_gw"`. That is a qualification-layer bug
(PROJECT.md §5). It is noted here only because §5 below turns on exactly that distinction, and a reader
comparing evidence files across lenses cannot currently tell the same-GW study from the lag-1 ones.

---

## 4. What is computed and does not feed anywhere: the panel CIs

`research/kernels/diagnostic/panel.py::bootstrap_panel_decomposition` runs a **1,000-resample
player-clustered bootstrap** (`SectionBuildConfig.panel_n_bootstrap = 1000`, deliberately raised from
the sections' general `n_bootstrap = 200` to remove Monte-Carlo class jitter) and returns five
intervals: `rho_pooled_ci`, `rho_between_ci`, `rho_within_ci`, `within_share_ci`, `dominance_ci`.

`sections.py` spreads all five into every decomposition row. `assembler.py`'s `DECOMPOSITION_COLUMNS`
then selects `rho_pooled, rho_between, rho_within, within_share, panel_class, decomposition_flag,
n_players, support_flag` — **the point estimates, and not one `*_ci`**. The bootstrap runs, the
intervals are computed, and the persisted registry carries `rho_between = 0.024` with no indication of
how precisely it is known. The same is true of `q1_q5_mean_gap` in the geometry section. The panel
decomposition is the only place characterization quantifies uncertainty, and it is the place the
uncertainty is dropped.

**Design position: this is scoped out, deliberately, and it is not future work.**

The reason is that the CIs *are* used — just not persisted. `panel.py::_dominance_class` consumes
`pooled_ci`, `diff_ci`, `between_ci` and `within_ci` to decide `panel_class`, which is the
CI-gated classifier the whole between/within read rests on (`identity_dominant` and `state_sensitive`
are asserted only when the dominance-contrast CI clears zero; otherwise the kernel abstains to
`mixed` / `indeterminate` / `undecomposable` / `insufficient_support`). The uncertainty is therefore
already discharged into the classification the artifact carries. Persisting the raw intervals as well
would widen the registry contract for a column no consumer reads — and characterization has no runtime
consumer at all (§6).

Two consequences follow, recorded so the choice is not mistaken for an oversight:

- A reader of `eda_03_joint_registry.csv` **cannot** attach an error bar to `rho_between`,
  `rho_within`, `within_share` or `q1_q5_mean_gap`. They must read `panel_class` (which is CI-gated)
  and `monotonicity_confidence` (which is bootstrap-derived) as the uncertainty summary, and treat the
  point estimates as unqualified.
- If a future consumer needs the intervals — a qualification design that wants to gate on
  `within_share` with a CI, say — the fix is a two-line widening of `DECOMPOSITION_COLUMNS`, not new
  computation. The numbers already exist at run time.

---

## 5. Population and target

**Target: `total_points`, same gameweek.** `SectionBuildConfig.target_column = "total_points"`, with no
shift. Characterization describes the contemporaneous relationship between a signal's value and the
points scored in the same gameweek.

**Population:** the prepared analytical dataset built from the mart over the controlled signal set in
`domain/registry_signals.py::REGISTRY_BUILD_INPUT_COLUMNS` (34 signals), across all four positions
(`POSITIONS = [GK, DEF, MID, FWD]`), with `gw_block` assigned by `config.py::assign_gw_block`
(early ≤ 14, mid ≤ 24, late otherwise — note this is *not* the lens studies' early 3–12 / mid 13–26 /
late 27–38 split, and the two block schemes are not interchangeable). Geometry requires
`MIN_N_SHAPE = 100` rows in a cell and `MIN_N_PER_BIN = 20` per bin; cells below those floors are
recorded as insufficient rather than estimated.

**The contrast with qualification, and the limit it implies.** Three of the four lens studies score a
*lagged* target — `total_points_next_gw` (form, market) or `played_next_gw` (availability) — on a
`minutes >= 60` population. Only the fixture lens shares characterization's same-GW target, and it does
so for a specific reason (`fixture/validate/study.py:1-9`: the signal describes the fixture the player
faces *this* GW).

Therefore:

> **Characterization cannot replace, corroborate, or contradict any lagged qualification result.** It
> is a different question — association within a gameweek, not prediction of the next one. Its only
> sanctioned downstream use is the one in §2: telling qualification how to cut the signal.

This limit is what makes §3's contradiction resolvable at all. The fixture lens and characterization
*do* share a target, which is why their disagreement is a genuine contradiction about binning rather
than two answers to two questions. Had the fixture lens been lag-1, there would have been nothing to
reconcile — and there is nothing to reconcile between characterization and the form, market or
availability lenses. A same-GW `monotonic_negative` says nothing about whether a signal ranks next
week's points.

One further consequence, already visible in the committed artifact: the only signals characterization
classes `continuous_monotonic` are contemporaneous components of the target itself — `goals_scored`,
`assists`, `bonus`, `bps`, `goals_conceded`. Against a same-GW target those are the scoring formula
measuring itself. They are descriptive, not predictive, and nothing downstream may treat their geometry
as evidence of anything else.

---

## 6. What "done" looks like for a characterization run

**There is no promotion or publication step.** `model/governance/promote.py`, which published to
`outputs/registry/`, is deleted; `outputs/registry/gw36/` was removed at `ae90398` with the note that
its only consumer was gone, after `domain/registry/{verdict,governance_lookup,governance_types}.py`
and the whole of `serve/scoring/` and `serve/reporting/` — the runtime surfaces that read it — had
already been deleted. This design does not restore any of that. A characterization run **must not**
create `outputs/registry/`, and no runtime component may acquire a dependency on characterization
output.

**The durable output is a CSV finding.** `research/registry/build.py` writes to
`DEFAULT_FINDING_OUTPUT_ROOT = research/findings/registry_builds/gw{N}/`, an exploratory location — and
now the only kind there is, since `model/governance/promote.py` and the path-based lifecycle gate that
distinguished promoted artifacts were both deleted. The committed reference artifact
of this shape is `research/findings/records/eda_03_joint_registry.csv` — **104 signal-position rows,
38 columns**, `RESEARCH_REGISTRY_PATH` in `domain/registry/schema.py`, which `build.py` currently reads
as its own source. A run is done when that CSV-equivalent exists and its contract validates
(`domain/registry/validation.py`).

**Its consumer is a design document, not a program.** Characterization is consulted when a
`LENS_DESIGN.md` is written or amended — specifically when §9 (quintile bin decision relevance) fixes
how a signal is cut. That is a human reading a CSV and writing a design, and the §2 link is exercised
by qualification importing a *kernel*, not by a study reading an artifact. Characterization has, and
under this design should have, **zero runtime importers**.

**Current state of the machinery, recorded plainly.** The build is *built but never run in its present
form*: `build.py` reads `eda_03_joint_registry.csv` and writes to `research/findings/registry_builds/`,
which does not exist on disk. Its only exercisers are `tests/test_registry_{build_runner,assembly,
build_parity,contract}.py`. Nothing about §6 changes that, and nothing about it needs to: a stage whose
output is consulted at design time rather than read at run time is not required to have a fresh
artifact on disk to be doing its job. What it *was* required to have, and did not, is this document.

---

## 7. Limitations

1. **One season.** 2025-26, GW 1–38, ~3,000 rows per position. Every geometry, every panel class, every
   stability verdict is conditional on that sample. `monotonicity_confidence` quantifies resampling
   uncertainty within the season; it says nothing about another one.
2. **Thresholds are operational heuristics, not statistical derivations.** `SPARSE_THRESHOLD = 10`, the
   0.60 zero-fraction cut, `MIN_N_SHAPE = 100`, `MIN_N_PER_BIN = 20`, `MIN_ACTIVE_BINS`, the stability
   kernel's normalized-shift bands, and `MONO_CONF_HIGH = 0.80` are all chosen, not estimated. The
   stability kernel's own docstring says so ("treat classifications as analytical guidance, not
   statistical claims").
3. **Association only — Rung 1.** No causal claim is made or supported anywhere in this layer (ADR-008).
4. **Two block schemes coexist.** Characterization's early/mid/late (≤14 / ≤24 / rest) and the lens
   studies' (3–12 / 13–26 / 27–38) are different partitions of the season. A stability verdict from one
   is not comparable to a block-count from the other.
5. **The `association_class` ladder is retained but demoted.** `domain/registry/association.py` assigns
   `unassessable` → `temporally_unstable` → `tail_dependent` → … by precedence. Under §1 it is a
   shape-interpretation label with no gate authority. It remains one of the five parallel verdict
   vocabularies PROJECT.md §2 catalogues, and collapsing those is scoped as a separate reconciliation
   task, not undertaken here.

---

## 8. What this design does not do

- It does not gate, approve, exclude or promote any signal.
- It does not amend any committed `evidence.yaml` or `annotations.yaml`.
- It does not amend `research/families/*/LENS_DESIGN.md`. Adopting §2 requires such an amendment,
  citing this document; that amendment is not part of this design lock.
- It does not fix `model/assemble/composition_study.py::_fdr_moderation_check`, which reuses the same
  defective tie-break (§2, limit 3).
- It does not restore `outputs/registry/`, `model/governance/promote.py`, or any published artifact.
- It does not reconcile the five verdict vocabularies (§7.5).

---

## 9. Design lock declaration

This design fixes, before any further characterization run: the four sections computed (§1), the
sanctioned downstream link and the binning decision that constitutes it (§2), the resolution direction
for the `fdr_avg` contradiction (§3), the deliberate non-persistence of the panel CIs (§4), the
same-GW target and the limit that follows from it (§5), and the definition of a completed run with no
promotion step (§6).

Changes to §2, §3, §4 or §5 require an amendment appended to this file, dated and numbered, in the
manner of the `LENS_DESIGN.md` files' Amendment A.
