# ADR-008 — Mode Vocabulary: Gartner Spine, Pearl Gate, Process Modes

**Status:** Accepted
**Date:** 2026-06-02 (ADLC adoption, Phase 3)
**Applies to:** `docs/architecture/adlc.md` §3 (the mode tag), §2/§4 mode columns, and the
decision-slug log mode fields

---

## Context

Phase 2 (the decision-slug log) surfaced an internal inconsistency in ADLC. §3 defines the
mode vocabulary as {descriptive, diagnostic, predictive, causal, prescriptive, operational},
but §2's stage table and §4's audit rows E and F use **`assemble`** and **`govern`** for the
`model` stage — modes §3 never defines. The slug log faithfully copied them, so two slugs
(`set-synth-weights`, `govern-signal-ledger`) now carry mode tags the canonical vocabulary
does not recognize.

Underneath the bug is a real design question: which mode taxonomy should the project use?
Two candidate ladders exist and they are **not the same axis**:

- **Gartner's analytics ladder** (descriptive → diagnostic → predictive → prescriptive) is an
  *intent / value* axis: "what kind of question am I asking?"
- **Pearl's ladder of causation** (association → intervention → counterfactual) is an
  *epistemic-rigor* axis: "what rung of causal claim am I making?"

They are orthogonal. A `descriptive` and a `predictive` study both sit on Pearl rung 1
(association) — Gartner moved, Pearl did not. The project's signature methodological stance is
exactly this: it climbs the Gartner ladder all the way to `prescriptive` (the serve stage)
while operating on Pearl rung 1. That stance was implicit; it should be explicit.

Separately, `assemble`/`govern`/`operational` are not question types at all — they describe a
*lifecycle activity* (building the spec, recording the ledger, checking drift), not a claim
about the data. Forcing them into the same flat list as `predictive` is the axis-conflation
ADLC exists to remove.

---

## Decision

Restructure §3's mode vocabulary into **two named families**, and record the project's
current stance with an explicit reopening trigger.

**1. Analysis modes** — Gartner intent ladder as the spine:
`descriptive`, `diagnostic`, `predictive`, `prescriptive`, with **`causal` (Pearl rung 2+)
retained as a gated, not-deleted tripwire.** These tag the explore / validate / serve stages.

**2. Process modes** — lifecycle activity, not a question type:
`assemble`, `govern`, `operational`. These tag the model / monitor stages. This legitimizes
the `assemble`/`govern` tags §2/§4 and the slug log already use.

**3. The stance (current, with trigger):** the project ascends the Gartner ladder to
`prescriptive` (serve) while operating on **Pearl rung 1 (association)** today. Higher rungs
are **gated, not foreclosed** — framed like ADLC §7's "build it only when…" triggers, not as a
permanent exclusion. Specifically:

- **Decision-counterfactuals** — "what if I had captained X / made transfer Y?" — are
  **admissible now**, because in FPL the alternative's outcome is *observed* (every player's
  points are public), so it is arithmetic regret/opportunity-cost analysis, not rung-3
  inference requiring a structural model.
- **Causal / physical counterfactuals** — "what if this player had played 90 minutes?" —
  remain **gated pending a redesign** that justifies a structural causal model. Reopening is
  allowed; it is simply not in scope today.

Existing mode tags in study headers and slugs do **not** need rewording — the values are
already correct. Only §3's *definition* expands to recognize them.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| **Pure Pearl** | Too coarse — nearly every study is rung 1; ~9 of 11 slugs would tag identically. Useless as a filter, and has no home for `prescriptive`/`govern`/`operational` |
| **Pure Gartner** | No home for `causal` (the descriptive≠causal tripwire disappears) and no home for `assemble`/`govern`/`operational` |
| **One flat 8-item list (status quo)** | Exactly the axis-conflation ADLC was built to kill — it pretends `govern` and `predictive` are the same *kind* of thing |
| **Permanently exclude higher Pearl rungs ("out of scope by design")** | The layer may be redesigned to use counterfactual/causal rungs; a permanent exclusion would make a future, legitimate promotion contradict the doc. Gated-not-foreclosed keeps the design open |

---

## Consequences

- §3 gains a two-family mode table; `assemble`/`govern` become defined modes, so the §4 audit
  and the slug log point at a recognized vocabulary (closes the Phase 2 finding).
- The "ascend Gartner, stay on Pearl rung 1" stance is written down, with the
  decision- vs. causal-counterfactual distinction as the reopening trigger.
- The two methodological tripwires §3 already names (descriptive ≠ causal; Gartner is not
  Pearl) are preserved and sharpened, not removed.
- No study header or slug is reworded. This ADR is a definition change, not a re-tagging.
- A future redesign that adopts a higher Pearl rung does so by meeting the stated trigger and
  updating this ADR's stance — not by contradicting it.
