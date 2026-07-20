# p_play term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/p_play/p_play.py` → `PlayModel` / `PlayTerm`
**Shared shape:** `model/terms/_binary_component.py` (the per-position logistic base)
**Spec:** [docs/model-redesign-pplay-blanktail-slice.md](../../../docs/model-redesign-pplay-blanktail-slice.md) · [docs/model-redesign-spec.md](../../../docs/model-redesign-spec.md) X1

The p_play term predicts **P(play) = P(minutes > 0)** one gameweek ahead — the probability a player
features *at all*. It is the appearance gate *before* the `minutes` term's P(>=60' | played), so the two
compose into the appearance ladder: `P(play)` then `p60 = P(>=60' | played)`.

## 1. The unconditional identity — why this term exists

`compose` conditions on appearance: every conditional term scores `E[· | played]`. A player whose
realized minutes turned out **0** therefore has no score, so an *ex-ante* consumer (captaincy over a
lagged-availability pool) that drops blanks only ever ranks players who *turned out* to play —
**hindsight leakage**. P(play) closes that with one factor out front:

```
E[points]_unconditional = P(play) × E[points | played]
```

`compose` (keep_all mode) owns the multiply; this term owns only `P(play)`.

## 2. Population is the WHOLE universe — and TRAIN keeps the blanks

Unlike every conditional-on-appearance term (population `minutes > 0`), P(play)'s population is **all**
rows (DGW excluded), because the target `played = 1{minutes > 0}` is *defined by* the 0-minute rows.
For the same reason it is the one term that **trains on the blank rows** — the base's
`trains_on_appearances_only` flag is set **False**. Filtering TRAIN to `minutes > 0` would leave
`played == 1` for every training row (one class) and collapse the logistic to all-NaN.

## 3. All four positions by logistic — no GK override

The `minutes` (p60) term overrides GK with a robust rate because GK play >=60' ~99% of the time
(near-constant → logistic degenerate). P(play) is **not** degenerate for GK: whether a keeper features
at all is a genuine **starter-vs-backup** split, well described by lagged minutes/start form. So
`logit_positions` is **all four** positions and there is **no `_fill_special` override**.

## 4. Features + lag-safety

`selected` draws lagged minutes at two windows (`minutes_roll3/5`, mart columns) + lagged start rate
(`starts_roll3`, built strictly-prior — `shift(1)` before rolling). `minimal` is `minutes_roll3 +
starts_roll3`. Rotation / availability signals (days-since-start, congestion) are the biggest missing
lever and are declared **unmaterialized** `§3` pool candidates.

## 5. Baseline + validation — no god-file golden (Fork D)

The per-term bar (spec §5) is `minutes_roll3` (lagged minutes level) ranking `played`. There is **no
bit-identical reference**: captaincy's old inline `_p_play` was a *pooled*, crude logistic, so this
per-position term is a deliberate **replacement**, not a reproduction — captaincy numbers shift by design
(same class of change as the GK p60 improvement). P(play) is pinned by **structural + seed** tests
(scores the blanks, learns the availability signal, deterministic), not a frozen vector.
