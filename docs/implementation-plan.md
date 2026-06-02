# Implementation Plan — Adopting the ADLC

**Authority:** [docs/architecture/adlc.md](architecture/adlc.md) — analysis lifecycle, mode tags, test contracts, ID-diet  
**Date authored:** 2026-06-02  
**Scope:** Sequence the open work the ADLC *names* — the coherence work that turns the design doc into the repo's actual workflow. Prescribe-only: this plan moves no code and renames no folders; the phases below are the plan for that work, not its execution.

This is **not** the engineering backlog. The bug/CI/study backlog lives in
[docs/governance/eng-issues-2026.md](governance/eng-issues-2026.md) and is referenced here only where
an ENG item is a *supporting prerequisite* for an ADLC phase (see "Supporting dependencies" at the end).

The spine is ADLC's own logic: make claims **legible** first (cheap, unblocking), make the **docs**
coherent, then do the **risky code migration** with a safety net under it, and close the deepest
**governance gap** last. Phases are ordered by dependency first, risk second.

---

## Phase 1 — Make every analysis legible (mode tags)

**ADLC source:** §3 (the mode tag) + §6 migration step 1.

**Goal:** Every study and notebook carries a one-line header naming its question, mode, stage, and status — so claim-type is readable off the file instead of living in the analyst's head. ADLC calls this "the single highest-value, lowest-cost change."

**Why first:** Mechanical, zero logic change, and it forces the axis-separation everything else depends on. It is literally step 1 of ADLC's migration plan, and it is the prerequisite for the decision-slug log (Phase 2) — you cannot write a clean verdict log over studies whose mode/stage you haven't yet declared.

**Tasks:**

1. Add the ADLC §3 header block to each study in `studies/` and each notebook in `studies/eda/`:
   ```
   # <plain-English question>
   Mode: predictive · Stage: validate · Status: REJECTED
   Population: minutes>0, DGW excluded, BGW accounted
   ```
2. Use the §4 audit table as the source of truth for each file's mode/stage/status (it already assigns them: A–G plus the unlettered rows).
3. Confirm the two methodological tripwires hold: nothing descriptive is tagged causal; `causal` appears nowhere (it is out of scope by design).

**Done criteria:** Every analysis file in `studies/` has a mode+stage+status header. A reader can `grep` for `Mode:` and recover the §4 audit table from the files themselves.

**Scope fence:** No logic changes, no ID-code edits, no file renames, no YAML migration. Header text only.

---

## Phase 2 — Decision-slug log

**ADLC source:** §6 ("keep two" — decision SLUGs) + the §4 audit verdicts.

**Goal:** One append-only `docs/decisions/` log keyed by human-readable slug — `reject-minutes-as-form`, `adopt-roll8-availability`, `set-synth-weights` — each entry naming its stage, mode, verdict, and date.

**Why second:** It depends on Phase 1 (verdicts must be mode/stage-tagged before they're logged), and it is the prerequisite for retiring the narrative ID codes in Phase 4 and the YAML codes in Phase 6 — you need a slug to point *to* before you can delete `SYNTH-01` / `FORM-006` as references.

**Tasks:**

1. Create one slug entry per verdict row in the ADLC §4 audit table (A–G and the unlettered rows).
2. Each entry: stage, mode, verdict (accept/reject/deferred), date, and a one-line evidence pointer.
3. Keep this distinct from the formal ADRs — slugs are the *narrative* verdict namespace; ADR-NNN remains for architectural decisions. (See Pending ADRs: ADR-004 formalises this split.)

**Done criteria:** `docs/decisions/` contains a slug entry for every §4 verdict. ADR-001 and ADR-002 are untouched and still sit alongside the new slug log.

**Scope fence:** Does not retire any ID code yet (that is Phases 4 and 6 — the slugs must exist first). Does not migrate YAML keys. Append-only; no existing decision file is rewritten.

---

## Phase 3 — Vocabulary reconciliation + remaining doc rows

**ADLC source:** §8 (the unmarked reconciliation rows + the DECIDED vocabulary rule).

**Goal:** Retire the *competing vocabulary*. ADLC §8 establishes that `adlc.md` is the sole owner of the word "lifecycle," and that the ✅ rows (merging `decision-lifecycle.md` + `operational-flow.md` → `runtime-execution.md`) are already executed. This phase finishes the three unmarked rows.

**Why third:** Adding the ADLC vocabulary without retiring the overlapping ones *is* the axis-conflation ADLC set out to fix. This is pure coherence work and largely docs — low risk, no code-load dependency — so it lands before the risky migration.

**Tasks:**

1. **`system-model.md`** — the 3-plane model (Control/Execution/Measurement) is a competing vocabulary. Resolve per ADR-005 (see Pending ADRs): either reframe it as a runtime/execution model subordinate to ADLC, or retain both with explicit, non-overlapping scope statements at the top of each doc.
2. **`layer-boundaries.md`** — keep its unique **ownership non-overlap matrix**; fold the import-direction narrative into a pointer to ADLC §2 so the flow story has one home.
3. **`test-coverage.md`** — keep as-is. ADLC §5 explicitly says this 54-invariant status map *is* the §5 contract made concrete; just cross-link it from §5.
4. **Correct ADLC §4 audit row B.** Row B labels `lenses/form/study.py` as "minutes as a returns signal — REJECTED (uninformative)," but the FORM lens as implemented evaluates *rolling xGI* form signals and **approved** xgi_roll3 (DEF) and xgi_roll5 (DEF, MID) per CONTEXT §5. The minutes-as-returns rejection belongs to the AVAIL reframing (row C), not the FORM lens. Fix: re-label row B to the FORM lens's real verdict (PARTIAL — xgi approved), and keep the "minutes alone is noise" narrative attached to the arc text, not to the form file. *(Flagged during Phase 1 mode-tagging; the form study's header already carries the corrected status with an inline note.)*
5. **Reconcile the mode vocabulary (§3 ↔ §2/§4).** Phase 2 surfaced an internal inconsistency: §3 defines the mode set as {descriptive, diagnostic, predictive, causal, prescriptive, operational}, but §2's stage table and §4's audit rows E/F use `assemble` and `govern` for the `model` stage — modes §3 never defines. The slug log faithfully copied them, so two slugs (`set-synth-weights`, `govern-signal-ledger`) now carry undefined mode tags. Fix per **ADR-008** (see Pending ADRs): restructure §3's mode table into two named families — **analysis modes** (Gartner intent axis: descriptive/diagnostic/predictive/prescriptive, with `causal`/counterfactual = Pearl rung 2+ retained as a *gated, not deleted* tripwire) and **process modes** (lifecycle activity, not a question type: `assemble`, `govern`, `operational`) — and state the project's *current* methodological stance with its reopening trigger: *today it ascends the Gartner ladder to `prescriptive` (serve) while operating on Pearl rung 1 (association); higher rungs are **gated, not foreclosed** — the layer may adopt them on a named trigger.* Frame the gate like ADLC §7's "build it only when…" pattern, not as a permanent exclusion: distinguish **decision-counterfactuals** (alternatives observable → arithmetic regret, admissible now) from **causal/physical counterfactuals** (require a structural model → gated pending a redesign that justifies it). This keeps the design open: a future version of this layer can promote to higher rungs without contradicting the doc. Mode tags in the study headers and slugs do not need rewording (the values are already correct); only §3's definition expands to recognize them.

**Done criteria:** No active doc except `adlc.md` carries "lifecycle" in its framing. `system-model.md`'s relationship to ADLC is resolved by ADR-005. `layer-boundaries.md` keeps only what's unique. ADLC §3 defines every mode used in §2/§4 and in the slug log (no undefined `assemble`/`govern`), resolved by ADR-008. Inbound links (`navigation-map.md`) still resolve.

**Scope fence:** Does not delete `test-coverage.md` or `layer-boundaries.md` (both carry unique content). Does not touch `EVAL_DESIGN.md` (it stays — it's the detailed design for the not-yet-built `monitor` stage). No code.

---

## Phase 4 — Capture durable findings, then retire run-dirs

**ADLC source:** §6 migration step 3 + the "kill four" table (timestamped run dirs).

**Goal:** Extract any durable conclusion still trapped in `studies/runs/*` and `signals/runs/*` into its stage artifact (the mode-tagged study / the slug log), after which the timestamped run dirs become safe to delete.

**Why fourth:** Depends on Phases 1–2 — a durable finding needs a mode-tagged artifact and a slug entry to land in before its run-dir can be discarded. Medium risk because it involves deletion; the dependency ordering is what makes the deletion safe.

**Tasks:**

1. Inventory `studies/runs/*` and `signals/runs/*` for any conclusion not already captured in a stage artifact.
2. Move each durable finding into its mode-tagged study artifact or its slug-log entry.
3. Once a run-dir holds nothing not captured elsewhere, retire it (they are already gitignored churn).
4. Drop ID-namespace strings from `kernels/` docstrings ("EDA-5", "spine") — the domain-agnostic substrate must not carry lifecycle codes.

**Done criteria:** No durable conclusion lives only in a timestamped run-dir. `kernels/` docstrings carry no lifecycle ID codes.

**Scope fence:** Does not touch the YAML key migration (Phase 6). Does not rename `phase9_backtest.py` (deferred to whenever the monitor stage is next touched, per ADLC §6). Does not delete `studies/eda/` notebooks or their `G-EDA*` codes — those are read-only historical records until the migration phase decides their fate.

---

## Phase 5 — Test-contract hardening (the safety net)

**ADLC source:** §5 (the SDET column + open holes).

**Goal:** Put the safety net in place *before* the risky YAML-key migration: the fixture-coverage meta-test and a clear path to a blocking `mypy`. ADLC: "Tests here are the specification, not afterthought coverage."

**Why fifth:** ADLC's whole §5 stance is "tests are the contract." The ID-diet migration (Phase 6) is "a code change with tests, not a cosmetic sweep" — so the contract that catches a botched migration should exist first.

**Tasks:**

1. **Fixture-coverage meta-test** — assert `tests/fixtures/test.db` contains each hard case (BGW, DGW, mid-season transfer, warm-up sub, zero-minute, red card, multi-position), so edge-case coverage is itself tested.
2. **mypy path to blocking** — `mypy` is currently `continue-on-error` with 8 known errors (documentation, not a gate). Fix the 8, then make it blocking. This is the §5 "open hole to close."

**Done criteria:** A meta-test fails if any curated scenario is missing from the fixture DB. The 8 mypy errors are fixed and `mypy` is a blocking gate (or, if the 8 can't all clear yet, each remaining one has a tracked reason and mypy stays documented — no silent `continue-on-error`).

**Scope fence:** Does **not** add property-based testing — ADLC §5 guardrail: not until a *recurring* invariant bug actually slips past example-based tests. Does not rewrite existing tests beyond what the meta-test and mypy fixes require.

---

## Phase 6 — ID-diet code migration (composite keys)

**ADLC source:** §6 ("keep two" — composite signal key) + the feasibility caveat.

**Goal:** Migrate the load-bearing ID codes (`FORM-006`, `AVAIL-001`, `G-SYNTH1-*`) to the self-describing composite scheme — `minutes_roll3@form:total_points` vs `minutes_roll3@avail:played_next_gw` — in the YAMLs that `intelligence/weight_registry.py` reads, and update the loader.

**Why sixth (the highest-risk phase):** ADLC's feasibility caveat is explicit — these codes are **load-bearing keys** in `evaluation_metadata.yaml` and `synth01_decisions.yaml`, which `weight_registry.py` reads and *hard-fails* on. This is "a code change with tests, not a cosmetic sweep." It needs: CI to exist (ENG-01, a supporting prerequisite), the slug log (Phase 2) for the narrative references, and the test net (Phase 5) under it.

**Tasks:**

1. Define the composite key grammar: `(signal × lens/target × position)` → `signal@lens:target`. Record it as ADR-003 *before* migrating (see Pending ADRs).
2. Migrate keys in `signals/governance/evaluation_metadata.yaml` and `synth01_decisions.yaml` to the composite form.
3. Update the `intelligence/weight_registry.py` loader to read composite keys; add migration tests that assert the loader resolves every key and still hard-fails on a genuinely missing one.
4. Retire the narrative codes (`SYNTH-01`, `ENG-*` as study/run codes, `Phase N`, `LENS-*` as references) from prose, pointing instead at the slug log and stage names. Retire `G-EDA{N}` gate codes in favour of a finding's plain title.

**Done criteria:** The two YAMLs use composite keys; `python -m intelligence.scoring.scoring_runner` runs green; migration tests pass in CI; the four killed namespaces no longer appear as *load-bearing keys* (they may survive in archived docs and historical notebooks).

**Scope fence:** Does not rename folders (ADLC §7: keep the map in the doc; folders can lag). Does not rename `phase9_backtest.py`. Does not retire `ENG-NN` *issue* IDs in `eng-issues-2026.md` — those are issue tracking, not study namespacing.

---

## Phase 7 — Close the model-stage governance gap

**ADLC source:** §4 ("the model stage is only partly governed — say so").

**Goal:** Make the *model* stage honestly whole. ADLC documents it as "part governed-ledger, part editorial, with one material unimplemented effect." This phase closes the two open halves.

**Why last:** It's the deepest analytical work and it depends on supporting lens studies (the ENG/PENDING-EVAL backlog) to produce the evidence. It also wants the legibility, slug log, and stable keys from earlier phases so the new verdicts land in a coherent structure.

**Tasks:**

1. **Calibrate the editorial module weights** — the intelligence module weights (captain, value, transfers, fixtures) are flagged `PROVISIONAL-EDITORIAL`: "editorial judgments set before the lens-study methodology was established." A `monitor`-stage calibration study (ADLC names this as the trigger) replaces each with a governed weight or an explicit, evidenced retention. *(Supported by the PENDING-EVAL lens studies and ENG-06 GK governance in the engineering backlog.)*
2. **Decide the FDR-quartile conditioning** — SYNTH-01 found FDR-quartile conditioning changes signal rank ordering in >15% of cases (a `MATERIAL` effect); implementation is deferred with binary-DGW as the current proxy. Either implement the conditioning or formally accept the proxy with evidence. Record as ADR-006.

**Done criteria:** No intelligence module weight is `PROVISIONAL-EDITORIAL` without a linked calibration verdict. The FDR-conditioning effect is resolved by a decision record, not left indefinitely deferred.

**Scope fence:** Does not build the full `monitor` stage (that is the `EVAL_DESIGN.md` deliverable, beyond this plan's coherence scope — ADLC names the stage; `EVAL_DESIGN.md` specifies it). Does not redesign the additive-weighted scoring approach (ADR-002 stands).

---

## Supporting dependencies (from the engineering backlog)

These are **not** ADLC phases — they live in `eng-issues-2026.md` — but specific ADLC phases can't land without them. Listed so the sequencing is honest.

| ADLC phase | Needs from the engineering backlog | Why |
|---|---|---|
| Phase 6 (ID-diet migration) | **ENG-01** (CI), and the pipeline must run at all — **ENG-13** (stale `synth01_decisions.yaml` path is a hard runtime failure today) | A risky YAML-key migration cannot be verified without CI, and can't even start if the loader hard-fails on a broken path first |
| Phase 7 (model-stage governance) | **PENDING-EVAL-01/02/03** lens studies; **ENG-06** (LENS-GK); **ENG-04** (threshold validation) | Calibrating the editorial weights needs the lens evidence those items produce |

In short: the engineering backlog supplies the *foundation and evidence*; this plan supplies the *coherence*. They meet at Phases 6 and 7.

---

## Pending ADRs

Decisions named in ADLC §4, §6, and §8 that are candidates for formal ADR entries but have not been written. Each should produce a `docs/decisions/ADR-NNN` file **before** its triggering phase executes, so the rationale is recorded before the choice is locked in.

| Candidate ADR | ADLC source | Decision | Triggering phase |
|---|---|---|---|
| **ADR-003: Signal-finding composite key scheme** | §6 | Adopt `signal@lens:target` as the canonical finding key. Must record *why* the naive "use the column name" rule is wrong: `minutes_roll3` is `FORM-006` (REJECTED) **and** `AVAIL-001` (approved at MID) — same column, opposite verdicts. The key is `(signal × lens/target × position)`. | Phase 6 (before migration) |
| **ADR-004: Decision-slug log as the narrative verdict namespace** | §6 | Adopt `docs/decisions/` slug log for all non-ADR verdicts, replacing `SYNTH-*`/`Phase N`/`LENS-*` as narrative references. Scope boundary: slugs = human-readable verdicts; ADR-NNN = architectural decisions. | Phase 2 (before slug log is created) |
| **ADR-005: system-model.md vocabulary reconciliation** | §8 | Resolve the competing vocabularies. ADLC §8 marks `adlc.md` as the sole owner of "lifecycle" but leaves `system-model.md`'s 3-plane model unreconciled. Decide: (a) ADLC primary, system-model reframed as runtime/execution; or (b) retain both with explicit non-overlapping scope. | Phase 3 (before reconciliation) |
| **ADR-006: FDR-quartile conditioning vs binary-DGW proxy** | §4 | Implement FDR-quartile conditioning, or formally accept binary-DGW as the permanent proxy with evidence. The >15% MATERIAL rank-order effect cannot remain indefinitely deferred without a record. | Phase 7 (before acting on the effect) |
| **ADR-007: LENS-GK evaluation methodology** | §4 / ENG-06 | Record the GK population boundary and evaluation target (saves, clean sheets, bonus per appearance vs `total_points` rank), and why the three-gate framework applies or needs modification. GK is the only position with zero governed signals. | Phase 7 support (before LENS-GK design locks) |
| **ADR-008: Mode vocabulary — Gartner spine, Pearl gate, process modes** | §3 vs §2/§4 | Resolve the mode-tag inconsistency Phase 2 surfaced. Adopt Gartner's intent ladder as the analysis-mode spine (descriptive/diagnostic/predictive/prescriptive) with `causal`/counterfactual kept as *gated, reopenable* Pearl rungs (not deleted), and carve out a second **process-mode** family (`assemble`, `govern`, `operational`) for the model/monitor stages — modes §4 already uses but §3 never defined. Record the *current* stance and its reopening trigger: ascend Gartner to `prescriptive`, operate on Pearl rung 1 today, with higher rungs gated-not-foreclosed (decision-counterfactuals admissible now; causal/physical ones pending a justifying redesign). Design stays open by construction. | Phase 3 (before §3 is rewritten) |
