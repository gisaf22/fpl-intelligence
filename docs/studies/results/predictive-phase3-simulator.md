# Phase 3.1 — Monte-Carlo points simulator (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 3.1.
**Produced:** 2026-07-09 · **Code:** `model/forecast/simulator.py` (`simulate_points`,
`simulate_from_mart`, `simulator_consistency`). Consumes `walk_forward_points` output (Phase 3.0);
`minutes > 0`, DGW-excluded, GW > 3; N = 10,000 draws, seed = 0.

## What it does
Samples each player-GW's components through the real FPL scoring rules to produce a full points
**distribution** — mean, sd, p10/p50/p90, and **P(haul ≥ 10)** — not just the composed mean. Per draw:
`play60 ~ Bern(p60)`, `goals/assists ~ Poisson`, `saves ~ Poisson` (GK), `DC ~ Bern(p_dc)`, and **team
`GA ~ Poisson(λ_ga = −log p_cs)` drawn once per team-fixture and shared** → `clean_sheet = 1{GA=0}·1{≥60'}`
and `conceded = −floor(GA/2)` from that one draw; bonus = proxy applied to the drawn returns. Summed
through the scoring multipliers.

## Internal-correctness gate — PASSED
Phase 3.1 validates *internal correctness only* (distributional quality is Phase 4):

- **Reproducible** under seed (test).
- **Sim mean ≈ analytic `full_pts`:** corr **0.9988**, mean abs diff **0.039** over 9,147 player-GWs.
  The tiny gap is the saves floor (`⌊s/3⌋` vs `E[s]/3`) and the bonus clip — the simulator is if
  anything *more* faithful than the analytic mean. This is a **consistency** check (the sim reproduces
  the composition's known centre), **not** the circular "sim mean predicts points".
- **Coupling invariant:** by construction a draw has `CS=1` iff `GA=0` iff `conceded=0` — CS never
  co-occurs with a conceded penalty (the D-D coupling, enforced by the shared team-GA draw).

## Simulated distributions (mean of per-row stats, per position, 9,147 player-GWs)

| pos | mean | sd | p10 | p50 | p90 | P(haul≥10) |
|---|---|---|---|---|---|---|
| GK | 4.28 | 3.91 | 1.01 | 2.81 | 7.95 | **7.5%** |
| DEF | 3.43 | 3.14 | 0.63 | 2.23 | 7.79 | 3.9% |
| MID | 2.93 | 2.30 | 1.26 | 2.00 | 6.28 | 2.1% |
| FWD | 2.57 | 2.15 | 1.17 | 1.71 | 6.18 | 2.1% |

Sensible shapes: right-skewed (p50 < mean), defenders carry the widest spread (binary CS + occasional
goals), and **GK have the highest haul probability** — a clean sheet, saves, and bonus can stack. The
per-row output also exposes captaincy ceilings (p90) and downside (p10) the point forecast can't.

## Scope limits (carried, first-class)
- **`P(play)` / blank 0-minute tail NOT represented** — distributions are *conditional on appearance*
  (X1 → Phase 5). The single most important caveat for any haul/ceiling number here.
- **Single-player marginals only** — no team goals-for / attacking co-movement, so **team-stacked
  joint hauls are not modelled** (Phase 5). Team-GA sharing is exact for full-90 players, approximate
  for subs (on-pitch GA).
- **Distributional adequacy is unverified** — the Poisson forms/dispersion of GA and goals/assists are
  validated only at the mean; whether the *tails* are calibrated is a **Phase 4** question (PIT,
  haul-rate reliability, CRPS). Bonus is underdispersed (competitive residual not sampled).

## Status
Simulator built and passes internal-correctness gate; 5 hermetic tests. **Next: Phase 4** — trust the
probabilities (calibration / proper scoring), which is where these distributions get validated rather
than asserted. (Phase 3.2 bookmaker-odds benchmark remains data-blocked.)
