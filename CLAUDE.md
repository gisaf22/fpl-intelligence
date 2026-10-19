# fpl-intelligence — agent rules

Standing rules and session start-up order. Loaded automatically at session start.
Project state, structure, and the document hierarchy live in `CONTEXT.md`.

---

## Working on board items

Items on the [FPL Platform board](https://github.com/users/gisaf22/projects/3) follow
[AGENT_WORKFLOW.md](https://github.com/gisaf22/.github/blob/main/AGENT_WORKFLOW.md) in
`gisaf22/.github`, the one place its rules are written. "Pick up #N" means: run that
procedure for #N. Read it before starting, then apply the domain playbook from
[`playbooks/`](https://github.com/gisaf22/.github/tree/main/playbooks) that fits the item.
This section is identical in fpl-ingest, fpl-warehouse and fpl-intelligence.

Fetch the workflow, and list the playbooks, with:

```sh
gh api repos/gisaf22/.github/contents/AGENT_WORKFLOW.md -H "Accept: application/vnd.github.raw"
gh api repos/gisaf22/.github/contents/playbooks --jq '.[].path'
```

---

## 9. Rules — never break these

Design before code — always design in Claude UI first, no code until design is agreed
This overrides the global default of making a reasonable assumption and proceeding when ambiguity
does not materially affect the outcome — here, design agreement is required regardless.

Every design document must include a capabilities table (Determinism, Observability, Contracts,
Lineage, Idempotency, Testability, Operability, Evolvability) before the changes section —
see `docs/architecture/platform-capabilities.md` for definitions and status symbols

No SQL outside `dal/`

No study runs without a LENS_DESIGN.md agreed in Claude UI first

No signals enter the signal registry without a confirmed lens status

No signals enter SYNTH-01 without a confirmed registry entry

DAL contracts are code-enforced — `dal/fct/fct_contracts.py`, `dal/feat/feat_contracts.py`, `dal/validation/`

The governed registry must have real promotion_class values before any lens study design begins — this gate is now met

Code tests live in tests/, mirroring the package path; statistical analysis is not pytest.

No production or workflow logic in `tests/` — it holds only thin software-engineering tests plus
the fixtures they need; anything the product runs moves to a real layer and the original is deleted

Clean break on every refactor — no shims, aliases, re-export wrappers, deprecation layers, or
old→new glossaries; repoint every caller, delete the old, and prune redundant tests rather than
porting them 1:1
For refactors specifically, this overrides the global default of identifying the smallest correct
change — the full clean break is the correct change here.
Pruning redundant tests overrides the global default of treating existing tests as part of the
specification — a test that only pins the deleted shape is deleted with it.

No worktree agents for targeted refactors — mechanical, well-defined sweeps (column removals,
renames, contract updates) are done with direct edits; worktrees are only for genuinely
exploratory work that may be thrown away

No bare `git stash` / `git stash pop` — never use the stash as a "does this change belong to me"
probe; establish provenance with `git diff` / `git status` / `git log` on specific paths

Run `ruff check . && ruff format --check . && mypy` before pushing — `pytest` does not catch
lint, formatting or type errors, and CI gates on all three

---

## 10. How to start a new session

1. Read `CONTEXT.md` — current project state, structure, and the document hierarchy
2. Read `docs/architecture/adlc.md` — the authoritative analysis lifecycle and test contracts
3. Read `docs/implementation-plan.md` — the ADRs still to be written, and the questions gating the `starting_xi` slice
4. Read `dal/pipeline.py` docstring for DAL entry points; read `dal/fct/fct_contracts.py` and `dal/feat/feat_contracts.py` for contract enforcement if any DAL work is planned
5. Read `docs/governance/eng-issues-2026.md` for active engineering issues
6. Read the relevant design document for the current task
7. Do not write code until the design is agreed in Claude UI

---

## 11. Decision-folder documentation

Governed by [`gisaf22/.github` `ANALYSIS_WORKFLOW.md`](https://github.com/gisaf22/.github/blob/main/ANALYSIS_WORKFLOW.md);
where this section and that file disagree, that file wins.

- **One `CARD.md` per decision**, in its `decisions/<name>/` folder. It opens with the status line
  `Stage N — <name>. Gates 0..N-1 passed.` and answers each stage reached, briefly.
- **Decisions and their reasons live as comments on the Epic/Feature issue.** The card links
  them and never copies them.
- **Superseded docs move to `archive/`** with the header `Superseded by CARD.md on <date>.`
  Archived docs are provenance, not authority; cite them by path (`archive/METRIC.md` §5).
- Docs the code still governs from (e.g. `starting_xi/PRE_REGISTRATION.yaml`) stay in
  place, with a one-line pointer to the card at the top.
