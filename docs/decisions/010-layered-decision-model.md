# ADR-010 — Layered Decision Authority Model

**Status:** Accepted — 2026-06-05 (Phase 2 + rulings a/b/c/d shipped; evidence-provenance re-run adopted 2026-06-06; full-season season-review evidence adopted 2026-06-06)
**Applies to:** `domain/`, `research/`, `model/governance/`, `model/assemble/`, `serve/` — and the
governance docs (`docs/architecture/layer-boundaries.md`), the import-linter contracts (`.importlinter`),
and the governance drift tests (`tests/test_generate_evaluation_metadata.py` and successors).
**Supersedes the implicit contract** sketched in the post-ADR-009 audit series (single-slot
"one true source per decision"). **Does not supersede** ADR-009; it generalizes the provenance
model ADR-009 established for the scoring verdict to every decision type.

---

## Context

Four successive audits over the post-ADR-009 architecture (responsibility, authority, recommendation-vs-decision,
taxonomy) converged on the same five recurring findings — leakage, composition, composition weighting, module
weighting, traceability — flagged variously as COLLAPSED, SHADOWED, or SPLIT AUTHORITY.

The final taxonomy pass introduced a system axiom to explain them: *every decision must have one authority and
one representation.* That axiom is **too strict to be realizable in this design**, because the system contains
structurally dual-aspect decisions. Critique of the axiom established the root cause: a **single-slot contract
conflates three different kinds of truth** the platform legitimately holds separately.

**The three truths:**

1. **Ontological truth** — what a thing *means* (owned by `domain`).
2. **Governance truth** — what the system *decides* (owned by `model/governance`).
3. **Operational truth** — what the system *executes* (owned by `serve`).

Several "violations" are not governance failures; they are **cross-layer transformations that were
under-specified**. Leakage, for example, is a single concept with an ontological aspect (classification, in
`domain/signal_layers.py`) and an operational aspect (exclusion enforcement, in `serve/scoring/signal_selector.py`).
Forcing those into one slot mislabels a real semantic/operational split as a defect.

The corrected goal is not "one source per decision system-wide." It is a layered invariant plus explicit mappings
between layers — and, for the genuine defects the relaxation does **not** dissolve, a recorded ruling.

## Decision

### 1. The revised invariant (LOCKED)

Every decision must satisfy:

1. **One authority per layer** — not one per system. A decision may have an ontological authority, a governance
   authority, and an operational authority, but **at most one in each layer**.
2. **One canonical representation per layer** — no layer holds two competing copies of the same decision.
3. **Cross-layer mappings are explicit, not implicit** — when a decision is transformed across layers
   (meaning → policy, evidence → decision, decision → execution config), the transformation is a declared,
   ideally executable, mapping; the downstream layer **derives from** the upstream representation rather than
   re-originating it.

A decision is a **violation** only when it breaks one of these three — e.g. two authorities *in the same layer*,
two canonical copies *in the same layer*, or an *implicit* cross-layer copy. Dual-aspect decisions across
different layers are permitted **iff** the mapping between them is explicit.

### 2. What each layer is allowed to decide

| Layer | May decide | May NOT decide |
|---|---|---|
| **Domain** | meaning, ontology, vocabulary, contracts, classification | nothing operational; no enforcement policy |
| **DAL** | acquisition / transformation / validation / materialization | no analytical or governance decisions |
| **Research** | evidence, findings, evaluation methodology; *recommendations* | no operational publication; no final governance decision |
| **Model** | governance decisions (lifecycle, downstream, promotion), composition rules, **weighting**, publication | not meaning (domain's); not runtime enforcement (serve's) |
| **Serve** | execution, scoring, reporting, runtime *enforcement* of decisions made upstream | no origination of governance decisions or weighting |

### 3. The four rulings (resolving the recurring findings)

These are the governance rulings that the doc series could not encode because they had not been made.

**(a) Weighting — Model owns; ratify `synth01`.**
`model/assemble/synth01_decisions.yaml` (study-derived) is the **single weighting authority**. Module/blend weights
in `serve/weight_registry.yaml` must **derive from or defer to** it; Serve does not originate weighting. The
ownership model is unchanged (Model owns weighting). This resolves the SPLIT AUTHORITY: the evidence-backed
weights gain an operational consumer; the editorial set becomes a derived (or explicitly-deferred) representation,
not an independent authority.

**(b) Traceability — retire as authority.**
`evaluation_metadata.yaml` is the canonical decision-of-record. `model/governance/signal_traceability.yaml` is
**retired as a source**: `serve/provenance.py` reads caveats from the canonical decision-of-record (via the
existing `domain.registry` read model), not from the matrix. This removes the SHADOW representation rather than
papering over it with a relabel. (A descriptive, explicitly-derived projection MAY exist later, but only if
generated and drift-guarded — never hand-maintained under a GENERATED banner.)

**(c) Composition — require separation.**
The collapse in `model/assemble/composition_study.py` (one script computes evidence, applies the rule, and emits
the APPROVED/EXCLUDED decision with no governance gate) is **not sanctioned**. The intended end state separates
**computation** (the study, producing evidence + a recommendation) from **decision authority** (a governance step
that ratifies the recommendation into a published decision). This is a design change beyond the no-redesign scope
of the audits; ADR-010 records the **intent and direction**, not an immediate refactor. Until executed, the
collapse is a *known, recorded* exception, not an accepted steady state.

**(d) Leakage — Domain owns classification; Serve derives enforcement.**
Leakage **classification** is ontology, owned by `domain/signal_layers.py`. The exclusion **enforcement** in
`serve/scoring/signal_selector.py` is a **derived enforcement** of that mapping — a declared cross-layer mapping,
ideally referencing the domain classification rather than re-listing it in `frozenset`s. Under invariant §1.3 this
is permitted (different layers, explicit mapping), not a COLLAPSE.

### 4. Diagnostic labels are not constraints

COLLAPSED / SHADOWED / SPLIT AUTHORITY are **diagnostic labels** used by audits, not terms in the enforced
contract. The enforced contract is the three-part invariant (§1) plus the layer-decision table (§2). Audits map
findings to the invariant; they do not introduce new categories into the contract.

### 5. Governance stays executable

This repo governs by executable contract (import-linter, drift tests, pandera schemas, fail-closed loaders). ADR-010
adds **no parallel prose control hierarchy**. Every invariant that *can* be mechanized is encoded as a test or
linter rule (Phase 2 below); prose is reserved for what cannot. This ADR is the single canonical statement of the
decision model — it does not compete with, or claim supremacy over, other ADRs.

## Migration path (phased; each independently shippable + green)

**Phase 1 — record the model (this ADR).** Adopt the invariant (§1), the layer-decision table (§2), and the four
rulings (§3). Update `docs/architecture/layer-boundaries.md` to reference ADR-010. No code change.

**Phase 2 — mechanize the invariant.**
- A drift-style test: **no file may carry a `GENERATED` banner without a generator that reproduces it** (the
  pattern already used by `tests/test_generate_evaluation_metadata.py`). This permanently closes the
  `signal_traceability.yaml` class of defect.
- Ruling (a): a test/generator tying `serve/weight_registry.yaml` to `synth01_decisions.yaml` as its authority
  (derive-or-defer), so Serve cannot originate weighting.
- Ruling (d): a check that `serve` enforcement constants reference the `domain` leakage classification rather than
  re-listing it.

**Phase 3 — enact rulings (b) and (c).**
- (b) Repoint `serve/provenance.py` at the canonical decision-of-record; retire the matrix as a source.
- (c) The composition computation/decision separation — a design change tracked as its own follow-up (a future
  ADR or implementation-plan item), not bundled here.

**Phase 4 — audits become validators.** Re-run the governance audit against ADR-010, reporting only violations of
the three-part invariant; infer no new categories.

## Consequences

- **Positive:** the recurring five findings each have a recorded ruling; the contract is realizable (per-layer, not
  per-system) and matches the system's genuine three-truth structure; governance stays executable; no parallel
  doc hierarchy or doc-layer split authority is introduced.
- **Costs / deferred:** ruling (c) (composition separation) is direction-only and remains open as a design change;
  the backfilled evidence provenance (`evidence_run.source = backfill:…`) is unchanged here and remains the open
  reproducibility item from ADR-009.
- **Unchanged:** the `DAL → research → model → serve` (+ `domain` leaf) topology, the import-linter contracts, and
  the ADR-009 scoring-verdict provenance chain.

## Alternatives considered

- **Keep the strict single-slot axiom** ("one authority + one representation system-wide"). Rejected: not
  realizable — it mislabels structurally dual-aspect cross-layer decisions (leakage) as defects.
- **Author four parallel control docs** (ARCHITECTURE_CONTRACT / PRINCIPLES / TAXONOMY / BINDING_RULES, each
  claiming supremacy over inferred architecture). Rejected: heavy overlap; creates a multi-representation of
  governance at the doc layer (shadow authority) and a split authority against the existing ADRs — the very
  pathologies this ADR exists to prevent. A single ADR plus executable tests is the aligned mechanism.
- **Sanction the composition collapse** (declare COLLAPSED-by-design). Rejected by ruling (c): separation is the
  intended direction.
- **Relabel `signal_traceability.yaml` DERIVED/MANUAL** instead of retiring it. Rejected by ruling (b): a
  hand-maintained file is neither generated nor derived; retiring it as a source is the honest resolution.

## Status of the migration (as shipped 2026-06-05)

- **Phase 2 (banner invariant) — done.** `tests/test_generated_banner_invariant.py` enforces "no GENERATED
  banner without a generator that reproduces it."
- **Ruling (b) — done.** `serve/provenance.py` reads caveats from the canonical decision-of-record via the
  domain governance read model; `signal_traceability.yaml` is relabeled MANUAL/INTERIM/NON-AUTHORITATIVE and is no
  longer a code consumer's source (it survives only as descriptive routing lineage, tested for completeness).
- **Ruling (a) — done.** `serve/weight_registry.yaml` declares `synth01_decisions.yaml` as the single weighting
  authority and references only findings the authority evaluated; `tests/test_weighting_authority.py` enforces
  derive-or-defer.
- **Ruling (d) — done.** Leakage / outcome-component classification lives in
  `domain.signal_layers.{LEAKAGE_LAYER_ROLES, OUTCOME_COMPONENT_LAYER_ROLES}`; `serve/scoring/signal_selector.py`
  references those sets rather than re-listing; `tests/test_leakage_authority.py` enforces the binding.
- **Ruling (c) — done.** Composition recommendation and decision authority are separated, mirroring the lens
  pattern (ADR-009 Phase C): `composition_study.run()` now writes `model/assemble/synth01_recommendations.yaml`
  (evidence + rule-*recommended* decision/weight/role); governance ratifies via the human-authorable
  `model/governance/synth01_annotations.yaml` (accept or override); `model/governance/generate_synth01_decisions.py`
  merges them into the now-generated `synth01_decisions.yaml`. Drift- and override-guarded by
  `tests/test_generate_synth01_decisions.py`; the generated file is registered in the banner invariant. Seeded by a
  lossless backfill (`model/governance/_backfill_synth01_records.py`).

## Evidence-provenance re-run (resolved 2026-06-06)

The backfilled `evidence_run` (`source: backfill:evaluation_metadata.yaml@v3.0`) — the residual circular
provenance from ADR-009 — has been replaced with genuine study runs. Resolution:

- **Study↔DAL drift repaired (form only).** The form study referenced `points_roll3/5` + `goals_scored_roll3`,
  which the governed mart deliberately does not materialize (blocked naive baselines / excluded signals; and
  `*_next_gw` targets are excluded as scoring-time leakage). The study now derives them locally with the DAL's
  lag-1 convention (`shift(1).rolling(N).mean()`), mirroring how the other studies already derive their targets.
  All four lens studies + the composition study now run against the real DB.
- **All evidence re-run and adopted.** `evidence.yaml` now carries real `evidence_run` sources; the
  decision-of-record + `synth01_decisions.yaml` are regenerated from real evidence. **No verdict moved**:
  `lifecycle_state`/`downstream_status` are identical; `rho_pooled` matches the backfill to 3 decimals (≤5e-4
  precision refresh) — confirming the hand-authored backfill was faithful.
- **`transfers_balance` retired cleanly.** It was deliberately removed from the market study's `SIGNALS`
  (vacated `MARKET-002`) but kept on record as excluded. Its `decision_class` is now annotation-pinned
  (`uninformative`) so its documented rejection survives provenance refreshes without re-running a retired signal;
  `rho_pooled` is honestly `null` (not evaluated).
- **FWD composition weight corrected.** A stale `0.0`/`null` carried by the prior hand record is realigned to the
  study recommendation (`1.0`/`primary`) so recommendation and ratification agree (descriptive only —
  `composition_weight` is not consumed by the scorer).

## Season review — full-season evidence (2026-06-06)

The season being complete (DB holds GW1–38), the governed evidence was re-estimated on the **full season**.
Rationale: descriptive/diagnostic (Gartner pre-predictive) stages are characterization, not model fitting — they
should use the whole population, not a holdout. The prior `GW_MAX=33` + held-out `GW34–38` split was a
predictive/ML device and, being a fixed end-of-season tail, a *confounded* validation set (it conflates
generalization with regime shift). Studies now run `GW_MAX=38` with the temporal late block extended to
`(27, 38)` so the end-of-season regime enters the block-stability diagnostic instead of being hidden in a holdout.
(Foundation-tier EDA full-season refresh is a separate follow-up — most are notebooks; `eda_08` left at GW33.)

**Verdict movement:** `lifecycle_state`/`downstream_status` did **not** change (human-pinned in annotations —
governance does not auto-flip). Study-computed `decision_class` flipped for 4 (signal, position) pairs, surfacing
three genuine **evidence-vs-verdict tensions** for 2026-27 re-classification review (not auto-applied):
- `xgi_roll5@form DEF` — **approved**, but full-season `decision_class=uninformative` (rho 0.11): weakens.
- `minutes_roll8@avail DEF` — **approved**, but full-season `uninformative` (rho 0.22): fails a late-block gate.
- `minutes_roll5@avail FWD` — **excluded**, but full-season `informative` (rho 0.21): a re-open candidate.
- (`purchase_price@market FWD` flipped to `uninformative` too, but it is already `excluded` — no tension; this is
  ENG-02's end-of-season reversal confirmed once GW34–38 fold in.)

These are research re-classification decisions (a `monitor`-stage verdict), deliberately left for human judgment.

## Open decisions

- **2026-27 re-classification of the three tensions above** — whether full-season weakening downgrades
  `xgi_roll5@DEF` / `minutes_roll8@DEF`, and whether `minutes_roll5@FWD` is re-opened. Research verdict, not a refactor.
- The remaining ADR-009-inherited provenance item is closed by the in-sample re-run; this season-review pass
  supersedes it with full-season evidence.
