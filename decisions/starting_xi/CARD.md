# Starting XI — card

**Stage 3 — Explore. Test design frozen 2026-10-17. Gates 0–2 passed.**

Process: [ANALYSIS_WORKFLOW](https://github.com/gisaf22/.github/blob/main/ANALYSIS_WORKFLOW.md).
Decisions and their reasons are recorded on the Epic issue; this card summarises them.
Still governing the harness code: [`DESIGN.md`](DESIGN.md) and [`PRE_REGISTRATION.yaml`](PRE_REGISTRATION.yaml). Data mapping: [`DATA.md`](DATA.md).
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

- **Source and mapping:** fpl-warehouse served parquet, season 2025-26 — see [`DATA.md`](DATA.md).
- **Known-when:** each rule sees only data from gameweeks before the one being scored.
- **Population:** exploration uses 2025-26; confirmation uses 2026-27, which is unseen because it comes later in time.
- The two existing runs (3821cc93, 4b348fe0) are **dry runs, not results**.

## 3 Explore (current) — test design, frozen 2026-10-17

- **Rules** (unfitted, one idea each). Per-fixture points rates from warehouse `fct_player_fixture`; prediction = rate × the coming gameweek's `fixture_count`.
  - D1–D4: points ÷ {gameweeks elapsed since entry, team fixtures, appearances (minutes > 0), starts} × windows {season, last 3}.
  - Decomposition: starts rate (last 3 team fixtures) × season points per appearance.
  - Floor: a random legal XI.
- **Ranking:** unscored players (no score yet — not enough history) rank below all scored players; no-fixture players rank last; ties go to lowest `player_id` ([`harness.py:234`](harness.py#L234)); formation limits then apply.
- **Metric:** XI regret primary; bench-order regret secondary; no-subs regret as sensitivity (§1).
- **Report per rule:** mean, median, 95% paired block-bootstrap range and P90 of regret; position on a random (0%) → hindsight-ideal (100%) scale. Segments: position, and season phase GW 3–12 / 13–26 / 27–38 (the lens scheme; the characterisation scheme ≤14/≤24 is not used here). DGWs not segmented.
- **Squads:** synthetic 2025-26, uniform and ownership-weighted. Zero-information weeks are excluded and counted. Ownership weights use the previous gameweek's `fct_player_gameweek.selected` (lag 1), since no pre-deadline snapshot exists for 2025-26; GW1 falls back to uniform. This is a realism assumption, read only alongside the uniform view.
- Real managers' squads and the human baseline are **not** used here (Stage 5 only), so that data stays unseen.
- Claims at this stage are descriptive only. `p_play` is its own exercise, later.

## 4 Decide (next)

- **Go/no-go:** go to Stage 4 only if there is a clear margin over random, a material spread between rules, and losses cluster in an explainable segment.
- No threshold against hindsight: the hindsight ideal is a reference only. Failure patterns become hypotheses.

## 5 Confirm (to pre-register before 2026-27)

- **Squads:** real managers, a random sample by manager ID, excluding Free Hit and Bench Boost weeks. Captured through an fpl-ingest story (not yet created).
- **Human baseline:** each manager's own XI regret.
- **To write and commit before looking:** reference, threshold, power simulation (sample size), Holm correction, guardrails, and the decision rule per outcome.

## 6–8

Not started. Promote only confirmed winners to the warehouse. Model only if confirmed headroom remains. Deliver with live regret monitoring.
