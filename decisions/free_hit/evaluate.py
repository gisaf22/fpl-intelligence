"""Evaluation orchestration -- `METRIC.md` §1's regret series over `DESIGN.md` §2's gameweeks.

The glue between this slice's three construction policies (`candidates.py`) and the **existing,
unchanged** `starting_xi` selection+bench harness (`decisions.starting_xi.harness`), which
`METRIC.md` §1.1 names as a drop-in dependency of every regret definition. Nothing in
`decisions/starting_xi/` is modified or re-implemented here; `harness.run` and
`orderings.order_by_rank` are imported and called as they stand.

**Why this module exists at all.** `DESIGN.md` §1 scopes itself to the gameweek population, the
feasibility primitive and the construction module, and states plainly that "METRIC.md is a separate,
not-yet-written document and is not covered here" -- so no design section ever specified the
evaluation wiring. Three concrete gaps had to be closed to run anything end to end:

1. **Shape.** `harness.run` takes a `squads` frame of (`squad_id`, `gw`, `player_id`), 15 rows per
   squad (`harness.py`'s own docstring, §2.9). A `ConstructionPolicy` returns
   `list[ConstructionCandidate]`. `build_squads` below is that projection and nothing more.
2. **Ranker.** `harness.run` requires a `rank_fn` to pick the XI. Every existing ranker lives in
   `decisions.starting_xi.rankers`, which imports `model.eval.baselines`, `model.features.build`
   and `model.terms.p_play.p_play` at module scope -- importing *any* name from it pulls in 16
   `model/` modules and silently destroys this slice's Tier A property (`DESIGN.md` §4), which
   `.importlinter` cannot currently catch because no contract names `decisions.free_hit.*` yet
   (deferred by `DESIGN.md` §4 to its own falsify-then-revert commit). `rank_season_ppg` below is
   therefore re-derived locally, by the same `shift(1).expanding().mean()` pattern and for the same
   stated reason `candidates.py` re-derives its own signals.
3. **Window.** `rankers.DECLARED_WINDOWS` starts every existing ranker at GW2 or GW4, and
   `harness.run` raises on a window its ranker does not cover. The local ranker declares
   `(2, 38)`: GW1 was in `DESIGN.md` §2's qualifying set when this module was written, but
   `gameweek_population.WARM_UP_EXCLUDED` has since removed it on `METRIC.md` §3.3's resolved
   warm-up axis -- see `STUDY_WINDOW` and `rank_season_ppg`'s own note.

**What this module does not compute.** `METRIC.md` §2's Holm-corrected verdict lives in
`verdict.py`, not here: this module assembles §1.2's per-squad selection series and §1.3/§1.4's
pairwise construction/combined series, and the verdict is a separate reduction over three
specific series drawn from `construction_regret`. Keeping the split means the regret series can
be inspected without the multiplicity correction being implicitly applied to whatever pairs
happen to be present. `Oracle(S, g)` and `SelectionRegret(S, g)` are
**not** recomputed -- the harness already emits both (`best_legal_xi_points` and `regret`), and
§1.1 explicitly defines its oracle as starting_xi's own P1 construct.

No RNG anywhere in this module -- every function here is a pure function of its arguments, matching
`candidates.py`'s own determinism note.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from typing import Final

import pandas as pd

from dal.config import DB_PATH
from dal.pipeline import load
from decisions.free_hit.candidates import (
    ConstructionPolicy,
    build_candidates,
    greedy_by_composite,
    greedy_by_composite_nofdr,
    greedy_by_recent_form,
    greedy_by_season_ppg,
    greedy_by_value,
)
from decisions.free_hit.gameweek_population import qualifying_gameweeks
from decisions.starting_xi.harness import HarnessResult, run
from decisions.starting_xi.orderings import PRE_REGISTERED_ORDERINGS
from domain.fpl_squad import BUDGET_CAP_TENTHS, SQUAD_SELECT

C1_SEASON_PPG: Final[str] = "C1_season_ppg"
C2_VALUE: Final[str] = "C2_value"
C3_RECENT_FORM: Final[str] = "C3_recent_form"
C4_COMPOSITE: Final[str] = "C4_composite"
C4_NOFDR: Final[str] = "C4_composite_nofdr"
"""Policy labels, named rather than left as string literals now that `verdict.py` and the
reporting path both have to refer to specific pairs of them."""

POLICIES: Final[Mapping[str, ConstructionPolicy]] = {
    C1_SEASON_PPG: greedy_by_season_ppg,
    C2_VALUE: greedy_by_value,
    C3_RECENT_FORM: greedy_by_recent_form,
    C4_COMPOSITE: greedy_by_composite,
    C4_NOFDR: greedy_by_composite_nofdr,
}
"""`DECISION.md` §4's three naive baselines (C1/C2/C3, as `DESIGN.md` §6 labels them), plus
`DESIGN.MD` §7's composite candidate C4 and its §7.3 ablation C4-nofdr.

Insertion-ordered, and every frame this module emits is sorted on these names rather than on dict
order, so the output does not depend on this mapping's construction order.

**C4-nofdr is here as a diagnostic, not as a fourth candidate.** `construction_regret` emits every
ordered pair in this mapping, so adding it here gets its regret series computed for free -- but
`DESIGN.MD` §7.3 forbids it entering `METRIC.md` §2's Holm-Bonferroni family, which is
pre-registered as exactly three candidate-vs-baseline comparisons. Membership in this mapping is a
statement about which series get computed, not about which legs the verdict corrects over; that
selection is made where `verdict.verdict` is called.
"""

LOCAL_SEASON_PPG: Final[str] = "local_season_ppg"
"""Name the local ranker reports to the harness -- deliberately *not* `rankers.F2_SEASON_PPG`
(`"F2_season_ppg"`). The two compute the same statistic, but that name is frozen in
`decisions/starting_xi/PRE_REGISTRATION.yaml` against a specific module; reusing it here would let
this slice's results be mistaken for that pre-registered ranker's."""

STUDY_WINDOW: Final[tuple[int, int]] = (2, 38)
"""The local ranker's declared window (`harness.py` §0.7's declaration, not an inference).

Starts at GW2, matching `gameweek_population.qualifying_gameweeks`, which excludes GW1 on
`METRIC.md` §3.3's warm-up axis. The declaration is the ranker's own claim about where it can
score, and GW1 is precisely where it cannot: `shift(1)` has no prior row, so every GW1 score is
NaN. Declaring `(1, 38)` would assert coverage this ranker does not have and let a future caller
widen the run back into the degenerate week without the harness objecting."""


@dataclass(frozen=True)
class _RankerOutput:
    """Structural implementation of `harness.RankerOutput` (a `@runtime_checkable` Protocol).

    Declared here rather than imported from `decisions.starting_xi.rankers`, whose concrete
    `RankerOutput` dataclass is unreachable without that module's `model/` fan-out -- see this
    module's docstring, point 2.
    """

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


@dataclass(frozen=True)
class EvaluationResult:
    """The three frames `METRIC.md` §1 defines, at the two grains it distinguishes.

    `squad_weeks` is the harness's own T2 output, unmodified, one row per (policy, gameweek):
    `chosen_xi_points` is §1.1's `Harness(S, g)`, `best_legal_xi_points` is its `Oracle(S, g)`, and
    `regret` is §1.2's `SelectionRegret(S, g)` -- all three already computed by the harness, none
    recomputed here.

    `selection_regret` is §1.2's per-policy view -- one series per entry in `POLICIES` -- pulled
    out of `squad_weeks` under §1.2's own column names.

    `construction_regret` is §1.3's `ConstructionRegret_{C,B}(g)`, one row per (policy_c, policy_b,
    gameweek) ordered pair. §1.4 resolves Combined regret to *the same computed quantity* under a
    second framing, so it is emitted as a column alias rather than a separately-computed number --
    computing it twice would assert a distinction §1.4 explicitly says does not exist.
    """

    squad_weeks: pd.DataFrame
    selection_regret: pd.DataFrame
    construction_regret: pd.DataFrame
    squads: pd.DataFrame


def rank_season_ppg(mart: pd.DataFrame) -> _RankerOutput:
    """As-of season PPG, re-derived locally -- the `rank_fn` the harness selects its XI with.

    Identical statistic to `decisions.starting_xi.rankers.rank_season_ppg` (F2) and identical
    derivation to `candidates.py`'s own `season_ppg` column: `shift(1).expanding().mean()` over the
    mart's `total_points`, lag-1 so no gameweek's own outcome can inform its own selection. Written
    here rather than imported for the `model/` reason in this module's docstring.

    **Why the window starts at GW2.** `shift(1)` has no prior row at GW1, so every score is NaN
    there. The harness reads a null score as unrankable (`rank_squad`'s `_TIER_UNRANKABLE`) and
    falls back to ascending `player_id` -- so at GW1 both construction *and* selection would be
    decided by player id, not by any signal. That is a real degeneracy, not a defect of this
    function. It was left in the run while `METRIC.md` §3.3's warm-up exclusion was open, so that
    dropping it would not be this module deciding §3.3's question by default; §3.3 has since been
    resolved against the measured live-mart figures and `gameweek_population.WARM_UP_EXCLUDED`
    now carries the exclusion. Scores are still emitted for GW1 -- the frame is not truncated --
    but `STUDY_WINDOW` no longer claims to cover it.
    """
    ordered = mart.sort_values(["player_id", "gw"]).copy()
    ordered["score"] = ordered.groupby("player_id")["total_points"].transform(lambda s: s.shift(1).expanding().mean())
    return _RankerOutput(
        name=LOCAL_SEASON_PPG,
        window=STUDY_WINDOW,
        scores=ordered.loc[:, ["player_id", "gw", "score"]],
    )


def build_squads(
    mart: pd.DataFrame,
    gameweeks: Iterable[int],
    policies: Mapping[str, ConstructionPolicy] = POLICIES,
    *,
    budget_tenths: int = BUDGET_CAP_TENTHS,
) -> pd.DataFrame:
    """Run every policy over every gameweek and project the result into the harness's squad frame.

    `harness.run` consumes (`squad_id`, `gw`, `player_id`) with 15 rows per squad; a
    `ConstructionPolicy` returns `list[ConstructionCandidate]`. This is that projection -- the
    `squad_id` is the policy name, so one `harness.run` call scores all three policies against a
    single ranker pass over the mart (which `harness.py` §6.1 requires: `rank_fn` is called once per
    run, not once per gameweek).

    `build_candidates` is called once per gameweek and its result shared across the three policies:
    the candidate pool is a property of the gameweek, and each policy sets its own `.score` from the
    raw signals the pool already carries (`candidates.py`'s `_scored`).
    """
    rows: list[dict[str, object]] = []
    for gw in sorted(gameweeks):
        pool = build_candidates(mart, gw)
        for name in sorted(policies):
            squad = policies[name](pool, budget_tenths, dict(SQUAD_SELECT))
            rows.extend({"squad_id": name, "gw": gw, "player_id": c.player_id} for c in squad)
    return pd.DataFrame(rows)


def selection_regret(squad_weeks: pd.DataFrame) -> pd.DataFrame:
    """§1.2's `SelectionRegret(S, g) = Oracle(S, g) - Harness(S, g)`, per policy and gameweek.

    A projection of the harness's own output, not a recomputation: `regret` is already
    `best_legal_xi_points - chosen_xi_points` clamped at zero by `harness.run`, which is §1.2's
    formula and its stated lower bound. Renamed to §1.2's vocabulary so the emitted frame reads in
    `METRIC.md`'s terms rather than starting_xi's.
    """
    return (
        squad_weeks.loc[:, ["squad_id", "gw", "best_legal_xi_points", "chosen_xi_points", "regret"]]
        .rename(
            columns={
                "squad_id": "policy",
                "best_legal_xi_points": "oracle",
                "chosen_xi_points": "harness",
                "regret": "selection_regret",
            }
        )
        .sort_values(["policy", "gw"])
        .reset_index(drop=True)
    )


def construction_regret(squad_weeks: pd.DataFrame) -> pd.DataFrame:
    """§1.3's `ConstructionRegret_{C,B}(g)`, one row per ordered (policy_c, policy_b, gameweek).

    Every ordered pair is emitted, not just the upper triangle: §1.3's quantity is signed and
    directional ("positive values favor the candidate"), so `(C1, C2)` and `(C2, C1)` are two
    different readings of the same comparison and `DECISION.md` §4 forbids collapsing them.

    `combined_regret` is the same column under §1.4's second name -- see `EvaluationResult`.
    """
    harness_points = {
        (str(row.squad_id), int(row.gw)): float(row.chosen_xi_points) for row in squad_weeks.itertuples(index=False)
    }
    policies = sorted({str(squad_id) for squad_id in squad_weeks["squad_id"]})
    gameweeks = sorted({int(gw) for gw in squad_weeks["gw"]})

    rows = [
        {
            "policy_c": c,
            "policy_b": b,
            "gw": gw,
            "harness_c": harness_points[(c, gw)],
            "harness_b": harness_points[(b, gw)],
            "construction_regret": harness_points[(c, gw)] - harness_points[(b, gw)],
            "combined_regret": harness_points[(c, gw)] - harness_points[(b, gw)],
        }
        for c, b in permutations(policies, 2)
        for gw in gameweeks
        if (c, gw) in harness_points and (b, gw) in harness_points
    ]
    return pd.DataFrame(rows)


def evaluate(
    mart: pd.DataFrame,
    policies: Mapping[str, ConstructionPolicy] = POLICIES,
) -> EvaluationResult:
    """Construct, replay and assemble every series `METRIC.md` §1 defines, over `DESIGN.md` §2's set.

    The bench order is `orderings.PRE_REGISTERED_ORDERINGS` -- starting_xi's own frozen primary
    (`by_rank`), unchanged, so the selection+bench unit really is the "proven, reused, unchanged"
    one `DECISION.md` §1 and `METRIC.md` §1.1 both name.
    """
    gameweeks = sorted(qualifying_gameweeks(mart))
    squads = build_squads(mart, gameweeks, policies)
    result: HarnessResult = run(squads, rank_season_ppg, PRE_REGISTERED_ORDERINGS, mart, STUDY_WINDOW)
    return EvaluationResult(
        squad_weeks=result.squad_weeks,
        selection_regret=selection_regret(result.squad_weeks),
        construction_regret=construction_regret(result.squad_weeks),
        squads=squads,
    )


def build(db_path: Path = DB_PATH) -> EvaluationResult:
    """Read the mart via `dal/` and evaluate against it.

    The one function in this module that touches the data layer, mirroring
    `gameweek_population.load_qualifying_gameweeks` and `harness.build`.
    """
    return evaluate(load(db_path).mart)
