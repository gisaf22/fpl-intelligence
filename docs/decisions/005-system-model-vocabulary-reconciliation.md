# ADR-005 — system-model.md Vocabulary Reconciliation

**Status:** Accepted
**Date:** 2026-06-02 (ADLC adoption, Phase 3)
**Applies to:** `docs/architecture/system-model.md`, its relationship to `docs/architecture/adlc.md`

---

## Context

ADLC §8 made `adlc.md` the sole owner of the word "lifecycle" and resolved the
`decision-lifecycle.md` / `operational-flow.md` overlap (merged into `runtime-execution.md`).
It left one row unresolved: `system-model.md`'s **3-plane model** (Control / Execution /
Measurement), flagged as a "competing vocabulary" against ADLC's 5-stage analysis lifecycle.

A reader hits two "big picture" maps of the same system and must work out which is primary
and how they relate. That is the axis-conflation ADLC exists to remove.

On review, `system-model.md` is already most of the way to a clean split:

- It declares its own scope ("Authoritative for: conceptual classification of system
  components") and carries a relationship table that divides the territory by question type
  (imports → layer-boundaries; *what each part is for* → this doc; runtime decision → runtime-
  execution; *how the model is researched* → adlc).
- It carries **unique content ADLC deliberately omits**: the Control/Execution/Measurement
  plane frame, the "the registry is *configuration*, not a pipeline step" insight, the
  component-classification table, and the "what's missing in Measurement" analysis.
- All its outbound links resolve (`research-lifecycle.md` exists; the earlier dead-link
  suspicion was wrong).

There is precedent for keeping it: ADLC §2 already cedes the runtime path to a sibling doc
("the runtime path is *not* a lifecycle; it is execution" → `runtime-execution.md`). So
"runtime/operational anatomy gets its own home" is an established pattern, not a new exception.

But the two docs are **not cleanly non-overlapping**. Two seams genuinely overlap ADLC and
must be deconflicted for the "they describe different things" claim to be honest:

1. **Measurement Plane ≈ ADLC `monitor` stage** — both describe backtest/replay/feedback-loop,
   both flagged "not implemented," each re-derived independently.
2. **"studies = research, not a plane" (system-model lines 67, 147–149) silently competes with
   ADLC**, which treats those same studies as its first three stages (explore/validate/model).

---

## Decision

**Retain both documents (Option B), with explicit, deconflicted non-overlapping scope.**
`system-model.md` is *not* demoted to a subordinate footnote and *not* deleted; it remains the
authority for the **runtime / operational anatomy** of the system. ADLC remains the authority
for the **analysis lifecycle**.

Concretely, the reconciliation edits to `system-model.md` are:

1. **Tighten the top scope header** to name ADLC explicitly as owner of the analysis lifecycle
   (explore → validate → model → serve → monitor), and to state that this doc owns the runtime
   plane anatomy (Control / Execution / Measurement) — the two are orthogonal views, neither
   supersedes the other.
2. **Deconflict the Measurement Plane** — point it at ADLC's `monitor` stage (and
   `EVAL_DESIGN.md` as the spec) as its lifecycle counterpart, rather than re-deriving the same
   not-yet-built gap.
3. **Deconflict the research-stage framing** — state explicitly that the components classified
   here as "research methodology / evidence source for the Control Plane" *are* ADLC's
   explore/validate/model stages viewed from the runtime angle, with a cross-reference, instead
   of an implicit competing claim.

This is a **fence-tightening, not a rewrite.** The plane frame, the classification tables, and
the unique insights are all kept verbatim.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| **Option A — demote the 3-plane model to subordinate runtime/execution vocabulary** | Throws away a useful orthogonal frame (Control/Execution/Measurement) and the "registry is configuration" insight for no gain; ADLC already cedes runtime to a sibling doc, so a runtime-anatomy doc is legitimate as a peer, not a footnote |
| **Delete `system-model.md`, fold into ADLC** | ADLC deliberately omits runtime anatomy (§2 sends runtime to `runtime-execution.md`); folding it in re-conflates the analysis and runtime axes ADLC set out to separate |
| **Leave both untouched (status quo)** | The two genuinely overlap on the monitor/measurement and research-stage seams; without deconfliction the "they describe different things" claim is partly false and the reader confusion persists |

---

## Consequences

- `system-model.md` stays as the runtime/operational-anatomy authority; ADLC stays as the
  analysis-lifecycle authority. The scope split is stated at the top of `system-model.md`, not
  left implicit in a table at the bottom.
- The Measurement Plane and ADLC `monitor` stage now cross-reference instead of independently
  re-deriving the same unbuilt gap — one home for that story (`EVAL_DESIGN.md` as the spec).
- No content is lost: the plane frame and classification tables are retained verbatim.
- **`research-lifecycle.md` renamed → `signal-promotion-states.md`.** Surfaced during this
  task: that file carried "lifecycle" in its name (an ADLC §8 violation — it was not in §8's
  reconciliation table) and its overview framed itself as a competing lifecycle. On review it
  is **not** rendered obsolete by ADLC: it owns the registry's **signal governance state
  machine** (exploratory → … → operationalized, with per-state allowed-consumers and promotion
  gates) — a different axis from ADLC's *work* stages, and content ADLC does not replicate.
  Resolution (same shape as this ADR): keep the content, drop the competing-vocabulary framing.
  The file is renamed `signal-promotion-states.md`, its overview reframed with an explicit
  scope split (governance *states* here; analysis *stages* in `adlc.md`), and all inbound links
  repointed (`navigation-map.md`, `system-purpose.md`, `registry-governance.md`,
  `intelligence-layer.md`, `rolling-xgi-horizon-study.md`). The archived `doc-drift.md`
  references are left as historical record.
