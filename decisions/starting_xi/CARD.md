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

- **Rules** (unfitted, one idea each), each × windows {season, last 3}. Inputs per [`DATA.md`](DATA.md).
  - D1: plain points per gameweek elapsed since entry (blanks count as 0, a double counts once); prediction = the rate, unscaled.
  - D2–D4: per-fixture points rates over {team fixtures, appearances (minutes > 0), starts}; prediction = rate × the coming gameweek's `fixture_count`.
  - Last 3: D1 over the last 3 gameweeks elapsed; D2–D4 over the last 3 past gameweeks holding the unit (a double is one gameweek, 2 in the denominator). Fewer than 3: NULL.
  - Decomposition: starts rate (last 3 gameweeks with a fixture) × season points per appearance × the coming `fixture_count`; NULL if either half is.
  - Floor: a random legal XI (a seeded random score per player, `master_seed` via `seeding.week_seed`).
  - Decisions and reasons: [#30](https://github.com/gisaf22/fpl-intelligence/issues/30).
- **Ranking:** unscored players (no score yet — not enough history) rank below all scored players; no-fixture players rank last; ties go to lowest `player_id` ([`harness.py:234`](harness.py#L234)); formation limits then apply.
- **Metric:** XI regret primary; bench-order regret secondary; no-subs regret as sensitivity (§1).
- **Report per rule:** mean, median, 95% paired block-bootstrap range and P90 of regret; position on a random (0%) → hindsight-ideal (100%) scale. Segments: position (ideal-XI minus chosen-XI points at that position; may be negative; positions sum to total regret), and season phase GW 4–12 / 13–26 / 27–38 (the lens scheme, starting at the first scored gameweek; the characterisation scheme ≤14/≤24 is not used here). DGWs not segmented.
- **Scored gameweeks:** GW4–38. At GW3 every last-3 rule is NULL for everyone ([#30](https://github.com/gisaf22/fpl-intelligence/issues/30)). A zero-information squad-week (every rule picks the same XI) is flagged `is_zero_information`, excluded from reporting and counted in the manifest ([#31](https://github.com/gisaf22/fpl-intelligence/issues/31)).
- **Squads:** synthetic 2025-26, uniform and ownership-weighted. Ownership weights use `fct_player_gameweek.selected` by [`DATA.md`](DATA.md)'s price rule (the most recent known value before the gameweek; with none, as at GW1 or a player's entry week, that gameweek's own value), since no pre-deadline snapshot exists for 2025-26. One run per squad mode ([#31](https://github.com/gisaf22/fpl-intelligence/issues/31)). This is a realism assumption, read only alongside the uniform view. Ownership-weighted squads are ownership-weighted among budget-feasible squads, not the real field: the budget check removes expensive popular players, so top premiums appear ~30–40% less often than ownership alone implies (snapshot 39064033745, e.g. player 430 GW38 0.54 → 0.34). Weighted squads also have ~half the distinct players of uniform. Read weighted results with this in mind; real squads (Stage 5) settle realism.
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
