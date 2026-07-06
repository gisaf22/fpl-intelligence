# Phase 2.1 Design — Count models for the point components

**Status:** design (resolves open decisions before build)
**Date:** 2026-07-06
**Authority:** [predictive-layer-plan.md](predictive-layer-plan.md) §Phase 2.1
**Preconditions:** Phase 0 harness frozen; Phase 1 checkpoint merged (identity is a thin,
low-ceiling slice — motivates features); `statsmodels` + `scikit-learn` installed;
component columns verified present in the mart (below).
**Strategy context:** [analysis-strategy-review.md](analysis-strategy-review.md) — Phase 2 is the
"land it, don't widen" phase; the lagged/form read is folded in here (§7); a second season is a
Phase 3 prerequisite, **not** needed for 2.1.

---

## 1. Purpose & where it sits

Phase 0/1 established that a player's own points history ranks weakly (ICC ~6–10% outfield, ~0 GK).
Phase 2.1 is the **first model with features (X)** and the first to **model the target's true shape**.
FPL weekly points are a *deterministic function of underlying counts* (goals, assists, clean sheets,
cards, saves, bonus). Those counts are **zero-inflated and over-dispersed** — Poisson is wrong.
The maturity move is to (a) diagnose that, (b) fit the right count family per component, and (c) map
fitted components back to expected points via the FPL scoring rule. Statistical **Rung 4 (predictive)**;
Pearl rung 1 (association) throughout; single-season; **conditional on appearance** (inherited from
Phase 0 — we forecast points *given the player featured*, not whether he will).

## 2. Decision — model components, then map to points (not total_points directly)

Two options were considered:

| | **A — component models → points map** (chosen) | **B — one model on `total_points`** |
|---|---|---|
| Fit | goals, assists, clean sheets separately, each with its right family | one count family on total_points |
| Zero-inflation | handled *naturally* per component (most players don't score) | must be modeled on a lumpy mixture |
| Interpretability | high — "his points come from expected goals" | low — a black-ish box |
| Maps to FPL rules | yes — position-aware scoring applied to E[counts] | no — ignores the known scoring structure |
| Recruiter signal | strong — decomposition + GLM families + exposure | weaker |

**Chosen: A.** Model the point-driving components and compose them through the known FPL scoring rule.
This respects the data-generating process instead of flattening it, and each component's zero-inflation
is modeled where it lives.

## 3. Components, families, and how minutes enter

Per position, the components that carry the points (start with the big three; expand only if the gate needs it):

| Component | Column | Family (to be confirmed by §5 test) | Positions |
|---|---|---|---|
| Goals | `goals_scored` | NB or ZIP (rare, over-dispersed) | MID, FWD (DEF secondary) |
| Assists | `assists` | NB or ZIP | MID, FWD, DEF |
| Clean sheet | `clean_sheets` | Bernoulli (logistic) | GK, DEF, (MID) |

Clean sheet is a **binary** outcome (a team either conceded 0 or it didn't — no "rate"), so it is
Bernoulli/logistic and yields `P(clean sheet)` directly; only the *count* components (goals, assists,
goals-conceded) take a Poisson/NB family. Match the family to the outcome's support.

**Minutes — a validated decision, NOT a hard-coded offset.** The tempting move is a log-minutes
*offset* (coefficient forced to 1), which asserts a *constant per-minute scoring rate* — "3× minutes
⇒ 3× goals". That proportionality is an **unvalidated assumption and is probably false**: goals cluster
late in matches (fatigue, chasing, opening up), substitutes are a selected population correlated with
game state, and FPL's own rules kink the curve at 60' (appearance 1→2 pts; clean-sheet needs 60'). So
proportional exposure must **earn** offset status, per position:

1. **Estimate, don't assert.** Enter `log(minutes)` as a covariate with a *freely estimated*
   coefficient β. Only if β ≈ 1 (proportional) do we lock it as an offset; otherwise keep the free term.
2. **Inspect the empirical shape.** Plot the per-minute component rate across minutes bands
   (0–30 / 30–60 / 60–90) per position — does the rate actually hold constant, or rise late / differ for subs?
3. **Escalate to non-linear if the data demands it.** Minutes-band dummies or a spline to capture the
   60' kink and late-game effect, rather than a single log term.

Proportional exposure is a reasonable *starting hypothesis* and clean baseline — but it clears its own
check (β test + band inspection) before it is trusted. Clean sheet is not a rate at all; minutes enters
there as a covariate / played-60 gate.

Saves, bonus, cards, goals-conceded deductions are **out of scope for 2.1's fit** — folded in as
fixed scoring arithmetic or deferred, so the first build stays legible. Documented, not hidden.

## 4. Features (X) — minimal, lagged, leakage-safe

Start deliberately small; the elastic-net breadth is Phase 2.2, not here.

- Goals rate: **lagged** `xgi_roll3` / `xg` (strictly prior, `.shift(1)` before use).
- Assists rate: lagged `xa` / `creativity`.
- Clean sheet: opponent/fixture context (`fixture_context`, lagged `goals_conceded_roll3`), `was_home`.

Every feature is **strictly prior** — same leakage discipline as Phase 0 (`_assert_no_leakage`-style
guard). The walk-forward harness is reused unchanged; only the predictor column changes.

## 5. Overdispersion diagnosis (the gate-1 test)

Before choosing NB vs Poisson vs ZIP, **test it**, per component per position:
- Fit Poisson GLM; compute the **dispersion statistic** (Pearson χ²/df) and a formal
  **over-dispersion test** (e.g. Cameron–Trivedi / LRT Poisson vs NB).
- If dispersion ≫ 1 → NB. If excess zeros beyond NB → ZIP/hurdle. The **test picks the family**, not taste.
This is the "fits distributions to data, not habit" recruiter signal, and Phase 2's hard gate.

## 6. Placement & dedup

- **Module:** `model/forecast/count_models.py` (new) — GLM fits, dispersion test, component→points map.
- **Score:** reuse the Phase-0 per-position walk-forward harness (`model/eval/walkforward.py`); the
  count model produces an `E[points]` column scored exactly like a baseline. No harness changes.
- **Notebook:** `model/forecast/phase2_count_models.ipynb` — diagnostic rubric, `fpl-intelligence`
  kernel; renders the dispersion diagnosis, per-position gate bars, and the lagged-form read (§7).
- Do **not** modify Phase-0/1 modules or the locked designs. Kernels stay in `research`; the model in `model`.

## 7. Folded-in: lagged / form-persistence read (the open autocorrelation question)

The never-run autocorrelation study (Q4/Q5) is folded in here, where the predictive framing is
legitimate and gated. Using the existing `research/kernels/diagnostic/serial.py`:
- report **within-player lag-1 autocorrelation** of the components/points per position (does form
  cluster beyond level?), and
- test whether a **lagged-form feature earns its place** over the level-only baseline in the model.
This answers "do form features add signal?" as a *gated* modeling question, not an orphan diagnostic.

## 8. How to run & read

- Fit per position; render the dispersion test (Poisson vs NB vs ZIP verdict per component).
- Compose E[points] via the FPL scoring rule; score on the walk-forward harness per position.
- Read the **per-position gate bars**: E[points] vs (a) the Phase-0 best baseline and (b) the best
  single signal. Report Spearman / precision@k / NDCG, within position, conditional on appearance.

## 9. Gate (promotion criteria — all must pass)

1. **Family justified:** the over-dispersion test rejects Poisson in favor of NB (or ZIP/hurdle) for
   the components where it matters — the family is chosen by evidence.
2. **Beats the floor:** composed E[points] beats the **Phase-0 best baseline** on the walk-forward
   harness, **per position** (materially where identity was weak: DEF/GK less certain, MID/FWD the test).
3. **Beats the best single signal:** the model beats the single strongest signal alone — i.e. the
   composition adds value over "just use xGI."

If (2)/(3) fail, Phase 2.1 ships the **dispersion diagnosis + honest null** (same discipline as D2):
the target-shape finding is kept; the feature model is recorded as not-yet-beating baseline.

## 10. Constraints honored

Rung boundaries (predictive in `model`, kernels in `research`); lag/leakage discipline (all features
strictly prior); within-position ranking only; notebooks-don't-emit; import-linter; extend-not-rebuild
(reuse the Phase-0 harness). Single-season; conditional on appearance. Availability ("will he play")
is the survival family's job (Phase 6), explicitly out of scope.

## 11. Risks & scope limits

- **Component→points map approximations** — saves/bonus/cards deferred; the composed points is an
  approximation, stated. Refine only if the gate needs it.
- **Minutes proportionality is not assumed** — the constant per-minute-rate (offset) hypothesis is
  tested (§3), not baked in; if β ≠ 1 or the band rates are non-constant, a free coefficient or spline
  is used instead. A recorded finding either way.
- **Conditional on appearance** — inherited; the model ranks players who played.
- **Thin positions** — GK clean-sheet and DEF goals are sparse; per-position floors apply, and a null
  for a thin position is reported, not forced.
- **Single season** — no drift/cohort validation; deferred to Phase 3 once a second season lands.
