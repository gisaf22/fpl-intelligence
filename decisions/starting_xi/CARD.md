# Starting XI — card

**Stage 3 — Explore. Test design frozen 2026-10-17; results recorded 2026-10-18. Gates 0–2 passed.**

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
- Stage 3 runs: `7d0882b01554c1cb` (uniform) and `bdcc8b3f54f937b0` (ownership), see §3 Results.

## 3 Explore (current) — test design, frozen 2026-10-17

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

### Results (2026-10-18, [#34](https://github.com/gisaf22/fpl-intelligence/issues/34)) — descriptive only

- **Runs:** two canonical runs at git `9e1e222`, clean tree, warehouse snapshot `39064033745` (pinned sha256s in each manifest), seed 0, 300 squads × GW4–38. Uniform `7d0882b01554c1cb` (61.7 s); ownership `bdcc8b3f54f937b0` (63.8 s). Full tables: [`STAGE3_TABLES.md`](STAGE3_TABLES.md).
- **Zero-information squad-weeks** (excluded): uniform 100, ownership 71, of 10,500 each.
- **XI regret** (points; mean, median, P90, 95% range of the mean):

  | Rule | Uniform mean [range] | Uniform med / P90 | Uniform scale | Ownership mean [range] | Ownership med / P90 | Ownership scale |
  |---|---|---|---|---|---|---|
  | ppg_fixture_season | 0.104 [0.088, 0.121] | 0 / 0 | 11.5% | 2.562 [2.244, 2.933] | 1 / 8 | 25.8% |
  | ppg_appearance_season | 0.106 [0.090, 0.125] | 0 / 0 | 9.9% | 2.576 [2.257, 2.969] | 1 / 8 | 25.4% |
  | starts_rate_x_points_per_appearance | 0.102 [0.084, 0.120] | 0 / 0 | 13.9% | 2.586 [2.300, 2.943] | 1 / 8 | 25.1% |
  | ppg_gameweek_season | 0.105 [0.088, 0.121] | 0 / 0 | 11.3% | 2.594 [2.312, 2.944] | 1 / 8 | 24.9% |
  | ppg_start_season | 0.107 [0.091, 0.126] | 0 / 0 | 9.5% | 2.664 [2.337, 3.077] | 1 / 8 | 22.9% |
  | ppg_fixture_last3 | 0.108 [0.093, 0.128] | 0 / 0 | 8.7% | 2.797 [2.444, 3.233] | 1 / 9 | 19.0% |
  | ppg_appearance_last3 | 0.110 [0.095, 0.130] | 0 / 0 | 6.4% | 2.852 [2.460, 3.340] | 1 / 9 | 17.4% |
  | ppg_gameweek_last3 | 0.111 [0.097, 0.131] | 0 / 0 | 5.5% | 2.891 [2.582, 3.277] | 1 / 9 | 16.3% |
  | ppg_start_last3 | 0.109 [0.094, 0.128] | 0 / 0 | 7.5% | 2.916 [2.556, 3.408] | 1 / 9 | 15.6% |
  | random | 0.118 [0.104, 0.133] | 0 / 0 | 0% | 3.454 [2.932, 4.128] | 1 / 10 | 0% |

  Scale = position from random (0%) to hindsight ideal (100%). Uniform-squad regret is near 0 for every rule, random included, while no-subs regret is not (below). The sanity diagnostics confirm why.
- **Bench-order regret** (mean, all weeks / when a sub fired): uniform ≤ 0.002 / ≤ 0.005 for every rule. Ownership: rules 0.32–0.54 / 0.60–0.78; random 0.885 / 1.024. Per-rule ranges are in the tables.
- **No-subs sensitivity** (mean): uniform, rules 0.31–1.05 vs random 4.27; ownership, rules 4.67–6.41 vs random 10.15. Season windows sit below last-3 windows in both modes.
- **Segments by position** (mean XI regret at that position, range across the 9 non-random rules; random in brackets). Uniform: GK 0.05–0.06 (0.065), DEF 0.04 (0.044), MID ≤ 0.01, FWD ≤ 0.002. Ownership: GK 0.80–0.85 (0.92), DEF 0.41–0.84 (0.62), MID 0.56–0.74 (1.18), FWD 0.44–0.63 (0.73).
- **Segments by phase** (same layout). Uniform: 4–12 0.11–0.13 (0.125), 13–26 0.10–0.13 (0.123), 27–38 0.08–0.09 (0.107). Ownership: 4–12 2.81–3.44 (4.59), 13–26 2.80–3.05 (3.10), 27–38 1.99–2.40 (3.00).
- **Rule agreement** (mean share of the XI two rules have in common): between non-random rules 0.91–1.00 for uniform and 0.85–0.99 for ownership; with random 0.75 in both.
- **Uniform sanity diagnostics** (both modes; tables in [`STAGE3_TABLES.md`](STAGE3_TABLES.md)). Players with minutes > 0 per squad-week: uniform mean 5.7 (median 6), with 99.9% of squad-weeks having ≤ 11; ownership 11.9 (median 12), 36.8% ≤ 11. Playing players in the chosen XI before subs: uniform 5.4 (rules) / 4.3 (random); ownership 9.6 / 8.8. Mean best-XI points against chosen-XI points: uniform 17.25 vs 17.15 (rules) / 17.13 (random); ownership 44.87 vs 42.15 / 41.41. All 10 rules realise equal XI points in 97.5% of uniform squad-weeks and 33.8% of ownership ones. **This confirms the reading:** uniform squads are dominated by non-playing players. Auto-subs bring in every player who played whatever the pick, so uniform XI regret measures almost nothing about the rules.
- **Paired-difference ranges** (mean XI-regret difference, rule_a − rule_b, with its 95% range from `gameweek_block_ci` on the per-gameweek difference series; negative means rule_a has lower regret). D1–D4 are the season windows of gameweek, fixture, appearance and start rates.

  | Comparison | Uniform | Ownership |
  |---|---|---|
  | best rule − random | −0.016 [−0.027, −0.004] (starts_rate × ppa) | −0.892 [−1.402, −0.404] (ppg_fixture_season) |
  | best season − best last-3 (ppg_fixture_season − ppg_fixture_last3) | −0.003 [−0.014, 0.004] | −0.235 [−0.461, −0.031] |
  | D1 − D2 | 0.000 [0.000, 0.001] | 0.032 [−0.006, 0.099] |
  | D1 − D3 | −0.002 [−0.014, 0.008] | 0.019 [−0.072, 0.093] |
  | D1 − D4 | −0.002 [−0.015, 0.007] | −0.070 [−0.188, 0.024] |
  | D2 − D3 | −0.002 [−0.014, 0.008] | −0.014 [−0.088, 0.037] |
  | D2 − D4 | −0.002 [−0.015, 0.007] | −0.102 [−0.203, −0.030] |
  | D3 − D4 | −0.000 [−0.003, 0.001] | −0.088 [−0.140, −0.041] |
- **Outfield-only sensitivity** (XI regret without the GK slot, i.e. regret_def + regret_mid + regret_fwd). Uniform: 0.053–0.054 for every rule, random included. Ownership: rules 1.76–2.10, random 2.54. The season windows (1.76–1.85) and the decomposition (1.77) sit below the last-3 windows (1.98–2.10). GK regret is nearly flat across rules (ownership 0.80–0.85, random 0.92). In 63.6% of ownership squad-weeks (4.3% uniform) both keepers played, so the GK slot is a live choice far more often than for real managers, who usually hold one nailed starter plus bench fodder, or a rotating cheap pair. Synthetic GK regret is therefore inflated relative to real squads.
- **Formation usage** (chosen XI before subs; share of squad-weeks). Ownership: rules use 4-4-2 most (27–31%), then 3-4-3 (16–23%), with 5-2-3 rarest (1–2%); random 4-4-2 28%, 3-4-3 16%. Hindsight ideal: 3-4-3 50%, 3-5-2 / 4-3-3 / 4-4-2 14–15% each. Uniform: rules and random have near-identical mixes (4-4-2 27–29%); the ideal is 3-4-3 93%, mostly ties broken to 3-4-3 by the harness's tie rule. The ideal's 3-4-3 share is inflated by that tie rule in both modes.
- **Weighted-squad premium caveat:** as stated under Squads above. Ownership-weighted squads under-represent top premiums by ~30–40% against ownership and hold ~half the distinct players of uniform squads, so the ownership numbers do not describe the real field.

### Stage 4 evidence (no verdict)

Differences are paired, with 95% ranges on the per-gameweek difference series (table above).

- **Margin over random:** ownership, the best rule (ppg_fixture_season) has 0.89 points less mean XI regret than random, range [0.40, 1.40], 25.8% of the way to ideal. Outfield-only, the rules sit 0.44–0.77 points below random. Uniform, the margin is 0.016 points [0.004, 0.027]. The range excludes 0, but uniform squads have about 6 playing players, so the margin carries little information.
- **Spread between rules:** ownership, the best season rule beats the best last-3 rule by 0.24 points [0.03, 0.46]. Among season windows, D4 (start rate) has more regret than D2 (fixture), by 0.10 [0.03, 0.20], and than D3 (appearance), by 0.09 [0.04, 0.14]. The D1/D2/D3 pairs' ranges all include 0. Non-random rules share 85–99% of their XI picks. Uniform: every season-pair and season-vs-last-3 range includes 0 or lies within ±0.015.
- **Loss clustering:** ownership regret is spread across positions. GK carries 0.80–0.85 per rule from one slot, nearly flat across rules and inflated by two-playing-keeper squads (63.6%). With GK removed, the rule ordering above holds. By phase, rules' regret is lowest in GW27–38 (1.99–2.40, against 2.80–3.44 earlier). Random's excess over the rules is concentrated in MID (1.18 vs ≤ 0.74) and GW4–12 (4.59 vs ≤ 3.44). Uniform regret is almost all GK and DEF, from squads with few playing players.

## 4 Decide (next)

- **Go/no-go:** go to Stage 4 only if there is a clear margin over random, a material spread between rules, and losses cluster in an explainable segment.
- No threshold against hindsight: the hindsight ideal is a reference only. Failure patterns become hypotheses.

## 5 Confirm (to pre-register before 2026-27)

- **Squads:** real managers, a random sample by manager ID, excluding Free Hit and Bench Boost weeks. Captured through an fpl-ingest story (not yet created).
- **Human baseline:** each manager's own XI regret.
- **To write and commit before looking:** reference, threshold, power simulation (sample size), Holm correction, guardrails, and the decision rule per outcome.

## 6–8

Not started. Promote only confirmed winners to the warehouse. Model only if confirmed headroom remains. Deliver with live regret monitoring.
