# Starting XI — card

**Stage 3 — Explore. Gates 0–2 passed (Data: partial — warehouse mapping pending).**

Process: [ANALYSIS_WORKFLOW](https://github.com/gisaf22/.github/blob/main/ANALYSIS_WORKFLOW.md).
Decisions and their reasons are recorded on the Epic issue; this card summarises them.
Still governing the harness code: [`DESIGN.md`](DESIGN.md) and [`PRE_REGISTRATION.yaml`](PRE_REGISTRATION.yaml).
Superseded docs: [`archive/`](archive/).

## 0 Decision

- **Who / action:** a manager picks the legal 11 to start from a settled 15-man squad.
- **When:** before the gameweek deadline, after transfers and chips have resolved. Only data known at the deadline is used.
- **Goal:** maximise expected points. Bench order is secondary.
- **Why it matters:** the decision comes up every gameweek. The cost of a wrong pick is the gap between what the chosen XI scored and what the best available XI would have scored, not the benched player's score.
- **Out of scope:** captaincy, Free Hit, Bench Boost, transfers and squad building, predicting hauls directly, and rival or template context as an input.
- **Assumptions:** the squad is given. In exploration it is synthetic, because the repo holds no manager picks. Note that `starts` means the player started for their club, not in an FPL XI.

## 1 Metric

- **Primary — XI regret:** points from the best legal 11 in the same 15, without auto-subs, minus points from the chosen XI with auto-subs. Minimising regret is the same as maximising points.
- **Secondary — bench-order regret,** given the chosen XI. Reported separately and never folded into the primary.
- **Sensitivity:** both sides scored without subs.

## 2 Data

- **Source:** warehouse served v2 is the primary source. The mapping is pending: minutes NULL semantics, price ÷ 10, club as-of the gameweek, season filter, and naming.
- **Known-when:** each rule sees only data from gameweeks before the one being scored.
- **Population:** exploration uses 2025-26; confirmation uses 2026-27, which is unseen because it comes later in time.
- The two existing runs (3821cc93, 4b348fe0) are **dry runs, not results**.
- `archive/METRIC.md` Appendix A.4 (38.6% season/3-GW PPG ties across GW5–38) is **unverified**.

## 3 Explore (current)

- **Baselines:** a grid of points-averages, with denominators {gameweeks elapsed, team had a fixture, appeared, started} × windows {season, last 3}. Plus a decomposition: starts rate × points per appearance. All are unfitted, one idea per rule, and their definitions are frozen before running.
- `p_play` is its own exercise, later.
- **Squads:** synthetic, drawn both uniformly and weighted by ownership. Rules must not use any signal the ranker uses.
- Claims at this stage are descriptive only.

## 4 Decide (next)

- Headroom = best baseline's regret vs zero (the ideal). Failure patterns become hypotheses.
- Go/no-go threshold to be set before exploring.

## 5 Confirm (to pre-register before 2026-27)

- **Squads:** real managers, a random sample by manager ID, excluding Free Hit and Bench Boost weeks.
- **Human baseline:** each manager's own XI regret.
- **To write and commit before looking:** reference, threshold, power simulation (sample size), Holm correction, guardrails, and the decision rule per outcome.

## 6–8

Not started. Promote only confirmed winners to the warehouse. Model only if confirmed headroom remains. Deliver with live regret monitoring.
