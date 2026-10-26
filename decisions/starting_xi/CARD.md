# Starting XI — card

**Stage 4 — Decided 2026-10-18. Next: Stage 5 (real squads).**

Process: [ANALYSIS_WORKFLOW](https://github.com/gisaf22/.github/blob/main/ANALYSIS_WORKFLOW.md).
Decisions and their reasons are recorded on the Epic issue; this card summarises them.
Still governing the harness code: [`PRE_REGISTRATION.yaml`](PRE_REGISTRATION.yaml) and the modules' docstrings. Data mapping: [`DATA.md`](DATA.md).

## 0 Decision

- **Who / action:** a manager picks the legal 11 to start from a settled 15-man squad.
- **When:** before the gameweek deadline, after transfers and chips have resolved. Only data known at the deadline is used.
- **Goal:** maximise expected points. Bench order is secondary.
- **Why it matters:** the decision comes up every gameweek. The cost of a wrong pick is the gap between what the chosen XI scored and what the best available XI would have scored, not the benched player's score.
- **Out of scope:** captaincy, Free Hit, Bench Boost, transfers and squad building, predicting hauls directly, and rival or template context as an input.
- **Assumptions:** the squad is given. In exploration it is synthetic, because the repo holds no manager picks. Note that `starts` means the player started for their club, not in an FPL XI.

## 1 Metric

- **Primary in Stage 3 (synthetic squads, against a random XI) — XI regret:** points from the best legal 11 in the same 15, without auto-subs, minus points from the chosen XI with our own auto-subs. Minimising regret is the same as maximising points.
- **Primary in Stage 5 (real managers) — win share** (amended 2026-10-23, [#55](https://github.com/gisaf22/fpl-intelligence/issues/55) decisions 8–12): the share of evaluation-panel manager-weeks in which D2's chosen eleven outscores the manager's chosen eleven, ties as half, with a per-manager share beside it. Both elevens are scored with plain player points and no auto-subs, so it measures the selection of the starting eleven, not the outcome after FPL's substitutions.

<details><summary>Superseded 2026-10-23</summary>

- **Primary — XI regret:** points from the best legal 11 in the same 15, without auto-subs, minus points from the chosen XI with auto-subs. Minimising regret is the same as maximising points.
</details>

- **Secondary — bench-order regret,** given the chosen XI. Reported separately and never folded into the primary.
- **Sensitivity:** both sides scored without subs.

## 2 Data

- **Source and mapping:** fpl-warehouse served parquet, season 2025-26 — see [`DATA.md`](DATA.md).
- **Known-when:** each rule sees only data from gameweeks before the one being scored.
- **Population:** exploration uses 2025-26; confirmation uses 2026-27, which is unseen because it comes later in time.
- Stage 3 runs: `7d0882b01554c1cb` (uniform) and `bdcc8b3f54f937b0` (ownership), see §3 Results.

## 3 Explore — test design, frozen 2026-10-17

- **Rules** (unfitted, one idea each), each × windows {season, last 3}. Inputs per [`DATA.md`](DATA.md).
  - D1: plain points per gameweek elapsed since entry (blanks count as 0, a double counts once); prediction = the rate, unscaled.
  - D2–D4: per-fixture points rates over {team fixtures, appearances (minutes > 0), starts}; prediction = rate × the coming gameweek's `fixture_count`.
  - Last 3: D1 over the last 3 gameweeks elapsed; D2–D4 over the last 3 past gameweeks holding the unit (a double is one gameweek, 2 in the denominator). Fewer than 3: NULL.
  - Decomposition: starts rate (last 3 gameweeks with a fixture) × season points per appearance × the coming `fixture_count`; NULL if either half is.
  - Floor: a random legal XI (a seeded random score per player, `master_seed` via `seeding.week_seed`).
  - Decisions and reasons: [#30](https://github.com/gisaf22/fpl-intelligence/issues/30).
- **Ranking:** unscored players (no score yet — not enough history) rank below all scored players; no-fixture players rank last; ties go to lowest `player_id` ([`harness.rank_squad`](harness.py#L221)); formation limits then apply.
- **Metric:** XI regret primary; bench-order regret secondary; no-subs regret as sensitivity (§1).
- **Report per rule:** mean, median, 95% paired block-bootstrap range and P90 of regret; position on a random (0%) → hindsight-ideal (100%) scale. Segments: position (ideal-XI minus chosen-XI points at that position; may be negative; positions sum to total regret), and season phase GW 4–12 / 13–26 / 27–38 (the lens scheme, starting at the first scored gameweek; the characterisation scheme ≤14/≤24 is not used here). DGWs not segmented.
- **Scored gameweeks:** GW4–38. At GW3 every last-3 rule is NULL for everyone ([#30](https://github.com/gisaf22/fpl-intelligence/issues/30)). A zero-information squad-week (every rule picks the same XI) is flagged `is_zero_information`, excluded from reporting and counted in the manifest ([#31](https://github.com/gisaf22/fpl-intelligence/issues/31)).
- **Squads:** synthetic 2025-26, uniform and ownership-weighted. Ownership weights use `fct_player_gameweek.selected` by [`DATA.md`](DATA.md)'s price rule (the most recent known value before the gameweek; with none, as at GW1 or a player's entry week, that gameweek's own value), since no pre-deadline snapshot exists for 2025-26. One run per squad mode ([#31](https://github.com/gisaf22/fpl-intelligence/issues/31)). This is a realism assumption, read only alongside the uniform view. Ownership-weighted squads are ownership-weighted among budget-feasible squads, not the real field: the budget check removes expensive popular players, so top premiums appear ~30–40% less often than ownership alone implies (snapshot 39064033745, e.g. player 430 GW38 0.54 → 0.34). Weighted squads also have ~half the distinct players of uniform. Read weighted results with this in mind; real squads (Stage 5) settle realism.
- Real managers' squads and the human baseline are **not** used here (Stage 5 only), so that data stays unseen.
- Claims at this stage are descriptive only. `p_play` is its own exercise, later.

### Results (2026-10-18, [#34](https://github.com/gisaf22/fpl-intelligence/issues/34)) — [`results.ipynb`](results.ipynb)

- Two canonical runs at git `9e1e222`, warehouse `39064033745`, 300 squads × GW4–38: uniform `7d0882b01554c1cb`, ownership `bdcc8b3f54f937b0`.
- Ownership squads: the best rule, `ppg_fixture_season`, misses 2.56 points per squad-week (25.8% of the way from random to the hindsight ideal) and beats random by 0.89 [0.40, 1.40]. Season windows beat last-3 windows; among season rules only D4 is clearly worse than D2.
- Uniform squads are degenerate: ~6 playing players per squad, so every rule fields nearly the same XI.
- Caveats: synthetic GK regret is inflated (both keepers played in 64% of ownership squad-weeks), weighted squads under-include premiums, and managers see team news.
- Caveat (2026-10-26, [#59](https://github.com/gisaf22/fpl-intelligence/issues/59) D5): the per-unit rules (D2–D4 and the decomposition) multiply by the coming gameweek's **realised** fixture count, because no capture precedes any 2025-26 deadline, so no as-of-deadline count can exist for 2025-26. A fixture postponed after a deadline therefore demotes its players with hindsight. The leak can only favour those rules, and its size is unmeasured. From 2026-27 GW3 on, the multiplier is the count scheduled at the deadline.

## 4 Decide — decided 2026-10-18

- **Gate:** go only if there is a clear margin over random, a material spread between rules, and losses cluster in an explainable segment. No threshold against hindsight: the hindsight ideal is a reference only.
- **Decision (Fred, 2026-10-18, [#28](https://github.com/gisaf22/fpl-intelligence/issues/28#issuecomment-6256944201)):** adopt `ppg_fixture_season` (D2: season points per team fixture × the coming fixture count). Uniform mode set aside as evidence (degenerate). Next (Stage 5): compare D2's XI with real managers' own XIs on their 2026-27 squads — reported cumulatively with a confidence band; managers see team news, so the comparison favours them.

## 5 Confirm (next; to pre-register before 2026-27)

- **Squads:** real managers, a random sample by manager ID, excluding Free Hit and Bench Boost weeks. Captured through an fpl-ingest story (not yet created).
- **Human baseline** (amended 2026-10-23): each manager's own chosen eleven, compared with D2's chosen eleven from the same 15 by the Stage 5 win share (§1).
- **Stage 3 vs Stage 5** (2026-10-23): Stage 3 selected the rule on XI regret against synthetic squads; Stage 5 tests it on win share against real managers, a different statistic against different opponents.
- **Auto-subs** (amended 2026-10-23): not applied to either eleven, so matching FPL's `automatic_subs` is not a requirement of this comparison; kept only as a validation of our own substitution logic, if one is built.

<details><summary>Superseded 2026-10-23</summary>

- **Human baseline:** each manager's own XI regret.
</details>

- **Data profile (2026-10-22, [#55](https://github.com/gisaf22/fpl-intelligence/issues/55)):** [`picks_profile.ipynb`](picks_profile.ipynb) describes the captured 2026-27 panel (GW1–7) and scores nothing; the comparison's definitions are recorded on #55 before it is run.
- **To write and commit before looking:** reference, threshold, power simulation (sample size), Holm correction, guardrails, and the decision rule per outcome.

## 6–8

Not started. Promote only confirmed winners to the warehouse. Model only if confirmed headroom remains. Deliver with live regret monitoring.
