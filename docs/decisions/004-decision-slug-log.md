# ADR-004 — The Decision-Slug Log as the Narrative Verdict Namespace

**Status:** Accepted
**Date:** 2026-06-02 (ADLC adoption, Phase 2)
**Applies to:** `docs/decisions/` — all non-ADR analytical verdicts

---

## Context

The repo accumulated six overlapping ID namespaces (`G-EDA1-04`, `AVAIL-001`,
`SYNTH-01`, `LENS-FORM`, `ENG-02`, `Phase 9`, timestamped run dirs) doing the work
that two could do. ADLC §6 ("ID-diet — six namespaces down to two") prescribes keeping
exactly two: a self-describing composite **signal-finding key** (Phase 6), and a
human-readable **decision slug** for every verdict.

The verdicts themselves already exist — they live in the ADLC §4 audit table and in
the Phase-1 mode/stage headers now carried by each study. What was missing was a single,
legible place that records each verdict as a standalone, linkable note.

A separate question is how these notes relate to the existing formal ADRs
(`001-spearman`, `002-additive-weighting`). They are different kinds of decision and must
not be conflated.

---

## Decision

Adopt an append-only **decision-slug log** under `docs/decisions/`, with **one Markdown
file per verdict**, named by a plain-English slug (`adopt-roll8-availability.md`), not a
number. Each entry carries a one-line header — Stage · Mode · Verdict · Date · Evidence —
and one or two sentences of plain-English rationale.

**The namespace boundary is explicit:**

- **Slugs** = *analytical verdicts*. "Did this signal/study work?" Named, not numbered.
  One per §4 audit row. This is the narrative namespace that replaces `SYNTH-*`,
  `LENS-*`, `Phase N`, and the `G-EDA*` gate codes as the thing prose points *to*.
- **ADR-NNN** = *architectural decisions*. Numbered, formal, with Context / Decision /
  Alternatives / Consequences. Reserved for durable design choices (the evaluation metric,
  the scoring method, this convention itself).

The two share a folder but are different shelves. Numbering belongs to ADRs only; slugs are
deliberately name-keyed so they read as English and link cleanly.

**The slug log is documentation only.** Nothing in the code parses it, and it must stay that
way. This is what makes Phase 2 zero-risk — unlike the Phase 6 composite-key migration, which
touches load-bearing YAML keys that `intelligence/weight_registry.py` hard-fails on.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| One big append-only log file | Noisy git diffs; hard to link to a single verdict; entries bleed together |
| Numbered like ADRs (`003-`, `004-` …) | Collapses the two namespaces — the whole point is that everyday verdicts are *not* architectural decisions; numbering implies a formality and review weight they don't carry |
| YAML frontmatter with a parsed schema | Would make the log load-bearing, re-importing the exact coupling Phase 6 exists to migrate away from; breaks the zero-risk property |
| Keep verdicts only in §4 + study headers | No single linkable home; can't point Phase 4/6 references at a stable target before retiring the old ID codes |

---

## Consequences

- `docs/decisions/` now holds two namespaces side by side: numbered ADRs and named slug
  notes. A `README.md` index explains the split to any reader.
- Phases 4 and 6 can retire the narrative ID codes (`SYNTH-01`, `LENS-*`, `Phase N`,
  `G-EDA*`) by re-pointing prose at the corresponding slug, because a stable target now
  exists. (Retirement is those phases' work, not this one.)
- The log is append-only: existing entries are not rewritten. A reversed or superseded
  verdict gets a new entry that references the old slug, rather than an edit-in-place.
- A new verdict that cannot be written as one slug with one stage and one mode is a signal
  that it is conflating axes — the same tripwire ADLC §4 names.
