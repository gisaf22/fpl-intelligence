# fpl-intelligence — agent rules

Standing rules and session start-up order. Loaded automatically at session start.
Project state, structure, and the document hierarchy live in `CONTEXT.md`.

---

## 9. Rules — never break these

Design before code — always design in Claude UI first, no code until design is agreed

Every design document must include a capabilities table (Determinism, Observability, Contracts,
Lineage, Idempotency, Testability, Operability, Evolvability) before the changes section —
see `docs/architecture/platform-capabilities.md` for definitions and status symbols

No SQL outside `dal/`

No study runs without a LENS_DESIGN.md agreed in Claude UI first

No signals enter the signal registry without a confirmed lens status

No signals enter SYNTH-01 without a confirmed registry entry

DAL contracts are code-enforced — `dal/fct/fct_contracts.py`, `dal/feat/feat_contracts.py`, `dal/validation/`

The governed registry must have real promotion_class values before any lens study design begins — this gate is now met

No production or workflow logic in `tests/` — it holds only thin software-engineering tests plus
the fixtures they need; anything the product runs moves to a real layer and the original is deleted

Clean break on every refactor — no shims, aliases, re-export wrappers, deprecation layers, or
old→new glossaries; repoint every caller, delete the old, and prune redundant tests rather than
porting them 1:1

No worktree agents for targeted refactors — mechanical, well-defined sweeps (column removals,
renames, contract updates) are done with direct edits; worktrees are only for genuinely
exploratory work that may be thrown away

No bare `git stash` / `git stash pop` — never use the stash as a "does this change belong to me"
probe; establish provenance with `git diff` / `git status` / `git log` on specific paths

Run `ruff check . && ruff format --check .` before pushing — `pytest` does not catch lint and CI
gates on it

---

## 10. How to start a new session

1. Read `CONTEXT.md` — current project state, structure, and the document hierarchy
2. Read `docs/architecture/adlc.md` — the authoritative analysis lifecycle and test contracts
3. Read `docs/implementation-plan.md` — the phased, dependency-ordered plan; start at Phase 0
4. Read `dal/pipeline.py` docstring for DAL entry points; read `dal/fct/fct_contracts.py` and `dal/feat/feat_contracts.py` for contract enforcement if any DAL work is planned
5. Read `docs/governance/eng-issues-2026.md` for active engineering issues
6. Read the relevant design document for the current task
7. Do not write code until the design is agreed in Claude UI

---

## 11. Decision-folder documentation

Applies to the four documents in any `decisions/*/` folder.

**The one-job-per-document charter.** Each answers exactly one question and carries exactly one
kind of content. Derived from how `decisions/starting_xi/`'s four are written.

| Document | The one question | Carries | Never carries |
|---|---|---|---|
| `DECISION.md` | What decision are we trying to make? | The decision's framing, its primary/secondary split, its cost model in prose, what is out of scope | The metric, the evidence, the design. It fixes neither the metric nor the harness and disclaims authority over both |
| `INVENTORY.md` | What data and capabilities exist in the repository today? | First-hand, verified repository facts, cited to file and line; unverifiable claims listed as such | Verdicts, reuse labels, proposals, recommendations, judgements about design fit. It governs nothing |
| `METRIC.md` | How could this decision be measured? | Candidate metrics characterised in full — what each measures, rewards, punishes, how it fails, what it requires; a tier per candidate | A selection. No candidate is "chosen", "recommended", "adopted", or described as having lost. Defects are stated as properties, not verdicts |
| `DESIGN.md` | Given the evidence, what system should we build? | The selections `METRIC.md` leaves open, with reasons; how the harness is built; prose reasoning | First-hand repository facts — every one is cited to `INVENTORY.md` |

`DECISION.md` governs `DESIGN.md`. `DESIGN.md` selects from `METRIC.md`'s candidates and cites
`INVENTORY.md`; it writes to neither. Where an upstream document conflicts with a downstream one,
the upstream governs and the conflict is recorded rather than silently reconciled. Retired
reasoning stays in the owning document's Provenance section with the reason it was withdrawn, so
it is not re-proposed.

**Required pre-edit checkpoint.** Before modifying any of these documents, emit this as plain text
in the response, before any edit tool call:

```
CHECKPOINT — <path>
Document:        <which of the four, or other>
Owns:            <the one question this document answers>
Does not own:    <the adjacent content that belongs to a named sibling>
Consulted:       <documents read this pass, with the sections relied on>
Unresolved:      <dependencies, gaps and open items that bear on this edit;
                  "none" only if genuinely none>
Planned changes: <what will change, section by section>
```

The `Does not own` line names the sibling that owns the excluded content. If that sibling cannot
be named, the edit is not ready to be made. An edit crossing a document boundary needs one
checkpoint per document, and the second edit does not begin until the first is complete.

**Ownership routing.** A fact belongs to exactly one document, determined by the charter table
rather than by which document happens to need it. A fact needed in two places is stated once by
its owner and cited everywhere else with a document-qualified section number — `INVENTORY.md`
§2.5, never a bare §2.5.

A missing fact means running a pass on the owning document, not asserting it locally. If
`DESIGN.md` needs a repository fact `INVENTORY.md` does not carry, that is a gap requiring an
`INVENTORY.md` pass; it is flagged as an open gap in the document that needs it and never asserted
first-hand there, however small the fact seems. The same holds in every direction — a missing
candidate characterisation is a `METRIC.md` pass, a missing framing is a `DECISION.md` pass. Do
not resolve a gap by widening a document's job; the pass is cheaper than the breakage.
