# fpl-intelligence — agent rules

These rules sit on top of the global engineering policy in `~/.claude/CLAUDE.md`.

---

## Working on board items

Items on the [FPL Platform board](https://github.com/users/gisaf22/projects/3) follow
[AGENT_WORKFLOW.md](https://github.com/gisaf22/.github/blob/main/AGENT_WORKFLOW.md) in
`gisaf22/.github`. "Pick up #N" means: run that procedure for #N — pick up → tests →
implement → PR → close. Read it before starting. This section is identical in fpl-ingest,
fpl-warehouse and fpl-intelligence; change all three together.

Fetch it into context with:

```sh
gh api repos/gisaf22/.github/contents/AGENT_WORKFLOW.md -H "Accept: application/vnd.github.raw"
```

Must-follow rules:

- **Design decisions:** run AGENT_WORKFLOW.md step 0 before writing any story's ACs.
- **No acceptance criteria table → stop.** Add the `needs-spec` label and ask.
- **Move the item to In Progress** when you pick it up. Bigger than its Size → stop and
  propose a split.
- **Tests come from the acceptance criteria only**, at each AC's test tier, with
  plain-English names. An AC may have several test cases (boundaries, negatives,
  parametrized variants), all marked with its `covers("#<issue> AC<n>")`. No test for
  behaviour no AC describes; flag any you think are missing. Manual/e2e tiers: record the
  result on the PR or issue.
- **Pause for approval before implementing.** Commit the tests first (failing), then stop
  and report. Size XS with every AC manual: skip the pause; the PR is the review point.
  Size S: always pause; if every AC is manual, report a verification plan instead.
- **Stay inside Out of scope.** Spec wrong or ambiguous → stop and ask; don't improvise.
- **PR body says `Closes #N`; post AC results (pass/fail per AC, with evidence) as a PR
  comment; tick the Definition of Done** (N/A with reason where it doesn't apply).
- **Never merge.** The human merges.
- **After merge:** confirm the item is Done, then move every item it was blocking that has
  no other open blocker from Blocked to Todo. Then remove the item's worktrees and delete
  its merged local branches.
- **New items:** use the `gisaf22/.github` templates, create with `--body-file`, and set
  Work Item Type, Epic, Size, Status and parent.
- **Public board:** no account IDs, ARNs or secrets in any issue, PR or comment.
