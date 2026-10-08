# fpl-intelligence — agent rules

These rules sit on top of the global engineering policy in `~/.claude/CLAUDE.md`.

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

## Before pushing

Run `ruff check . && ruff format --check . && mypy` before pushing — `pytest` does not catch
lint, formatting or type errors, and CI gates on all three
