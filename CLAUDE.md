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
