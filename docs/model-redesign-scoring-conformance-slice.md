# Scoring-rule conformance — plan + decision doc

**Status:** DONE (forks ruled: A=simulator decomposition, B1=accept+document bonus, C=assert+report,
D=`model/eval/`) · **Type:** spec + result
**Verdict (real mart, n_sims=4000):** every exactly-computed term conforms to within Monte-Carlo error;
`bonus` is the **sole** non-conformer and its gap **is** the entire residual measured up front (GK −0.043,
DEF −0.017, MID −0.027, FWD −0.006) — proof that after the position + saves fixes, `compose` is exact
everywhere except the one accepted bonus-clip approximation. Guard added (`assert_conformance`), and a
test proves it trips (pointing at exactly `(GK, saves)`) when the old `E[S]/3` bug is reintroduced.

---

**Original plan below.**
**Parent:** [position-specification results](model-redesign-position-specification-results.md) §open items
**Goal:** a standing guard that `compose`'s point estimate for each scoring term equals the expectation
of the **actual FPL rule** under the fitted distribution — `E[rule(X)]`, not `rule(E[X])`. This is the
class of bug the saves gap belonged to (`E[floor(S/3)]` vs `E[S]/3`), which no existing gate could see.

## Honest framing (measured first — this is a guardrail, not a win)

After the saves fix, the residual non-conformance is **small and already located**. Ground truth is the
simulator (it draws each component then applies the rule per draw), so `compose − sim_mean` per position:

| position | gap (compose − sim) |
|---|---|
| GK | −0.044 |
| DEF | −0.017 |
| MID | −0.027 |
| FWD | −0.006 |

All ≤0.044 pt/GW and all negative — the sign of the **bonus clip** Jensen effect (near `returns≈0` the
lower clip at 0 makes `E[clip] ≥ clip(E)`, so compose slightly *under*-states). So this slice does **not**
find a new material bug. Its value is: (1) a **regression guard** so the next refactor cannot silently
reintroduce a `rule(E)` bug on saves/conceded/etc., and (2) a **quantified decision** on the one term
that does not conform — bonus.

FPL has exactly **three** nonlinear scoring rules; everything else is linear (per-goal/assist multipliers,
binary indicators) and conforms trivially:

| rule | term | status |
|---|---|---|
| `floor(S/3)` | saves | exact (just fixed) |
| `-floor(GA/2)` | conceded | exact (always was) |
| `clip(·, 0, 3)` | bonus | **`clip(E[returns])` — the residual** |

## Forks (proposed)

- **A — where does ground-truth `E[rule]` come from?** The **simulator's per-component draw means**,
  reusing `iter_sample_blocks` (the single home of the draw loop). The simulator already computes the
  full per-component decomposition internally (`goal_pts, assists, cs, conceded, saves_pts, dc_pts,
  bonus, appearance`) and then sums it — expose those component means and diff against compose's
  `DECOMP_COLUMNS` (compose already emits the same decomposition). **Not** a re-derived analytic
  expectation (that is what we are checking — circular) and **not** a duplicated draw loop (Phase-4
  deliberately removed the duplicated loop; re-adding one here would undo that).
- **B — the bonus residual: fix or accept?** It is ~0.02–0.04 pt/GW and the simulator already carries the
  honest `E[clip]` for the *distribution* (p10/p90/p_haul are right). Two options:
  - **B1 (recommend): accept + document.** Report the bonus gap under a tolerance; do not "fix" compose's
    point bonus. Fixing it would couple `compose_points` to a Monte-Carlo run (compose currently needs no
    draws), a large architectural cost for <0.05 pt. The point estimate stays the analytic
    `clip(E[returns])`; its ~0.03 pt understatement is documented as an accepted approximation.
  - **B2:** replace compose's point bonus with the simulator's `E[clip]` mean. Removes the gap but makes
    the mean depend on a stochastic draw (seed, n_sims) — trades a known 0.03 pt bias for MC noise and a
    compose→simulate dependency.
- **C — assert or report?** **Both.** The exactly-computed terms (goals, assists, clean_sheet, conceded,
  saves, DC, appearance) are **asserted** to conform within an MC tolerance — that is the regression
  guard. The bonus gap is **reported** under a looser tolerance (it is a known non-zero Jensen residual;
  asserting it to 0 would be a lie). Tolerance sized from MC error at the check's `n_sims`.
- **D — home.** `model/eval/` — this is measurement of a fitted model (like `calibration`,
  `simulator_consistency`). Concretely it **generalizes `simulator_consistency`**, which today compares
  only aggregate `e_points` and **excludes GK** — the exclusion that hid the saves gap. The new check is
  per-term and includes GK.

## Sequence (one reviewable commit each)

1. **Expose the decomposition from the draw primitive.** `iter_sample_blocks` (or a thin sibling) yields
   per-component draws, not only the summed points. Gate: `simulate_points`' seed-pinned golden stays
   **bit-identical** (the summation path is unchanged; the decomposition is additional output).
2. **`scoring_conformance(mart)`** in `model/eval/`: per (position, term), compose's decomposition mean
   vs the simulator's per-component mean, with the MC tolerance. Asserts the exact terms, reports bonus.
   Retire/subsume `simulator_consistency`'s GK exclusion.
3. **Test + freeze:** a seed-pinned conformance vector; a synthetic-panel unit test that a deliberately
   broken rule (e.g. `E[S]/3` reintroduced) trips the guard. Record the real-mart verdict in a results
   doc, including the accepted bonus residual (Fork B1).

## Stress-test constraints

1. **Golden safety:** step 1 must keep `simulate_points`' 4dp golden bit-identical — the decomposition is
   additive output, the summed path is untouched.
2. **No duplicated draw loop:** reuse `iter_sample_blocks`. If the check re-implements the draws, the
   design is wrong (it re-creates the exact duplication Phase-4 removed).
3. **Tolerance honesty:** the assert tolerance is MC error at the chosen `n_sims`, not a number picked to
   make it pass. Bonus is reported, not asserted to zero.
4. **Ground-truth discipline:** the simulator is ground truth for `E[rule]` **only** because it
   draws-then-applies. If a term's *draw* is itself wrong, this check cannot see it (it checks compose
   against sim, not sim against reality — that is calibration's job).

## Invariant
`simulate` golden bit-identical · import-linter 6/6 · ruff clean · full `pytest` green · the guard trips
on a reintroduced `rule(E)` bug.

## Open question for ruling
Fork B (bonus: **accept+document** vs **fix**) is the one real decision — the rest are mechanical. Recommend B1.
