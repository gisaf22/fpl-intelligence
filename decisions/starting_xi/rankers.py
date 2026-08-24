"""The three pre-registered floor rankers -- `DESIGN.md` §0.12, §5.1, §6.1, §6.3, §6.4, §8.1, §8.3.

**Three rankers, pre-registered and unconditional.** §0.12 selects F1 (`p_play` alone), F2
(season-long PPG-to-date) and F3 (3-gameweek recent form) as the floor set, and records the gate
that once made F3 conditional as **closed**: the governed mart's `points_roll3` exclusion is
written with its scope attached and does not bind a *baseline ranker*, which is the one role
`research/families/form/LENS_DESIGN.md` makes mandatory. Nothing here is conditional on it. §0.12's
F4 -- the 5-gameweek variant -- is deliberately **not** built: it is excluded from the
pre-registered set so the floor is not half-populated by one family, and a sensitivity check is
built when it is run.

**One signature, panel-producing, called once per run.** §6.1: `rank(mart) -> RankerOutput`, over
the whole mart rather than once per gameweek. The shape is chosen for F1 and not for the cheap two
-- `INVENTORY.md` §2.6 measures `p_play`'s fit as an expanding walk-forward that re-estimates a GLM
per position per gameweek, so a per-gameweek signature would re-run the whole season's walk for
every gameweek's predictions.

**The declared window is a declaration, not an inference** (§0.7). §6.3 fixes the three: F1 GW4-38,
F2 GW2-38, F3 GW2-38, with F1 binding any comparison containing it to GW4-38. The literals live
below; `test_rankers.py` carries the drift test tying F1's GW4 to `WARMUP_GW`, so the constant this
document derived it from cannot move without the declaration failing loudly.

**What each ranker reads, and the two population shapes.**

* **F1** scores the rows `PlayModel.population` keeps. `INVENTORY.md` §2.6 measures that population
  dropping `is_dgw` rows and null-`minutes` rows, so those rows carry no score. That is intended:
  §6.5 governs the double-gameweek hole (unrankable, placed below every scored player) and §0.4
  removes the no-fixture one upstream by ranking such a player last for *every* ranker, so the
  asymmetry never reaches the comparison.
* **F2 and F3** read one frame -- §8.3's population, built here by :func:`population`: the full
  player-gameweek spine restricted to each player's post-registration window, with null
  `total_points` filled to **0**. §0.9 fixes that denominator as gameweeks elapsed rather than
  appearances, and §8.3 is why the two are identical through GW4 (`METRIC.md` §5.3, Appendix A.3):
  two windows over one population.

**The population is built here rather than read or borrowed, and both halves of that are forced.**
`INVENTORY.md` §2.1 measures no `points_roll*` column on the governed mart and records the
enforcement as being over `build_player_gameweek_state`'s output columns, so there is nothing to
read (§6.4, §9.1). And §5.1 forbids this module every Tier A sibling, so `harness.as_of_points`'s
copy of the same construction cannot be imported. The two constructions are therefore duplicated by
contract, and `test_rankers.py` pins them against each other rather than leaving the agreement to
the docstrings -- which is the same move `test_harness.py` makes against the sampler's registration
predicate.

**`min_periods = 1`, via `add_lagged_rolls`** (§6.4). `INVENTORY.md` §2.1 measures two coexisting
conventions and this is a metric-affecting choice between them: `min_periods = k` yields NaN for
any player with fewer than *k* prior observations, which makes coverage a **per-player** property
no declared window can express, and would leave a large share of any uniform-drawn 15 unscoreable
-- degenerate *correlated with price*, the axis §2.2 identifies as the one that tilts comparisons.
The cost is stated rather than hidden: at GW2 F3 is a one-gameweek mean and at GW3 a two-gameweek
mean.

**Import closure: `numpy`, `pandas`, and three `model/` modules.** Tier B (§3.3, §5.1), so `model/`,
`dal/` and `domain/` are permitted and `research/`, `serve/`, `operational/` and every Tier A
sibling -- `harness.py`, `sampler.py`, `formations.py`, `results.py` -- are not. §3.4 records that
the `model/` edge is unavoidable and closed to re-argument: F1 is a fitted GLM with no shallow path
to it, so relocating `expanding_prior_mean` would remove a `model/` import from one of three floor
rankers while F1 keeps the module in `model/` anyway. `test_rankers.py` asserts the closure in a
subprocess, including §5.6's positive assertion that `model` *is* reached.

**What this module must not do** (§6.2): read `status` or `chance_of_playing` (`INVENTORY.md` §2.6
confirms they never reach the mart); read any row at gameweek >= *t* when scoring *t*; read realised
outcomes for the gameweek being scored; read the squad table or anything the sampler produced;
mutate the mart it is handed -- the same frame goes to every ranker in a paired comparison. It also
does not adopt `assert_no_future_leakage`: `INVENTORY.md` §3.7 records it requiring `points_roll3`,
so it fails closed against this very mart. §6.2's instruction is to write a leakage assertion
against the columns actually used, and :func:`_assert_lag_safe` is it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import numpy as np
import pandas as pd

from model.eval.baselines import expanding_prior_mean
from model.features.build import add_lagged_rolls
from model.terms.p_play.p_play import PlayModel

# ---------------------------------------------------------------------------
# The pre-registered constants (§0.12, §6.3, §6.4)
# ---------------------------------------------------------------------------

F1_P_PLAY: Final[str] = "F1_p_play"
F2_SEASON_PPG: Final[str] = "F2_season_ppg"
F3_FORM_ROLL3: Final[str] = "F3_form_roll3"

# §6.4's selection, and the number the name above carries. §0.12 records `METRIC.md` §5.1's grounds:
# short enough to track rotation, long enough that one blank does not dominate, and the window the
# platform already uses for its lag-1 rolling signals.
RECENT_FORM_WINDOW: Final[int] = 3

# §0.7's study-level scope. No repository constant carries it -- it is this slice's own.
STUDY_FIRST_GW: Final[int] = 2
STUDY_LAST_GW: Final[int] = 38

# §6.3's three declarations. F1 starts at GW4 because `INVENTORY.md` §2.6 records `WARMUP_GW = 3` at
# `model/eval/walkforward.py:58` with predictions beginning at GW4. The literal is written out
# rather than derived as `WARMUP_GW + 1`: §0.7 makes the window a *declaration*, and §7.4 freezes it
# in the pre-registration, so it must not silently follow an upstream constant. `WARMUP_GW` is
# therefore not imported here at all -- `test_rankers.py` imports it and asserts the two still
# agree, which is the drift test that makes the literal safe without making it derived.
P_PLAY_FIRST_GW: Final[int] = 4

DECLARED_WINDOWS: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        F1_P_PLAY: (P_PLAY_FIRST_GW, STUDY_LAST_GW),
        F2_SEASON_PPG: (STUDY_FIRST_GW, STUDY_LAST_GW),
        F3_FORM_ROLL3: (STUDY_FIRST_GW, STUDY_LAST_GW),
    }
)
"""Name -> declared window, for `results.py`'s `RunManifest.ranker_windows` (§7.2, §7.3).

Exposed as data so the composition root can record the windows without running a comparison.
"""

# The columns each population reads. F1's is the wider set: `INVENTORY.md` §2.6 records
# `PlayModel.population` filtering on `is_dgw` and `minutes`, coercing `starts`, and drawing
# `minutes_roll{3,5}` from the mart.
_PPG_MART_COLUMNS: Final[tuple[str, ...]] = ("player_id", "gw", "minutes", "total_points")
_P_PLAY_MART_COLUMNS: Final[tuple[str, ...]] = (
    "player_id",
    "gw",
    "position",
    "minutes",
    "starts",
    "is_dgw",
    "minutes_roll3",
    "minutes_roll5",
)

_SCORE_COLUMNS: Final[tuple[str, ...]] = ("player_id", "gw", "score")


# ---------------------------------------------------------------------------
# The interface (§6.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RankerOutput:
    """§6.1's panel-producing output: a name, a declared window, and a score panel.

    Structural, not nominal. `harness.py` consumes this shape as a `Protocol` and never imports
    this module (§3.5, §5.1) -- the composition root is the only place the two meet. The class is
    declared here so the ranker side has a concrete type; `test_rankers.py` asserts it satisfies
    the harness's protocol, so the two cannot drift apart unnoticed.

    `scores` carries exactly (`player_id`, `gw`, `score`), one row per player-gameweek the ranker
    covers inside `window`, sorted by (`player_id`, `gw`). Higher `score` = more preferred. A row
    the ranker cannot score is emitted with a **null** `score` rather than a number (§6.5); a row
    the ranker's population never contained is absent, which the harness reads identically.
    """

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


RankFn = Callable[[pd.DataFrame], RankerOutput]
"""§6.1's `rank(mart) -> RankerOutput`."""


# ---------------------------------------------------------------------------
# §8.3's population, and the two assertions that protect it
# ---------------------------------------------------------------------------


def registration_gw(mart: pd.DataFrame) -> pd.Series:
    """Per player, the first gameweek carrying a non-null `minutes` row.

    §8.3's population is "restricted to each player's post-registration window" and does not
    operationalise *registration*; the predicate used is §2.1's -- the sampler's own, so the squad
    universe and the frame the PPG rankers read agree on who exists when.

    This repeats `harness.registration_gw` and `sampler._registration_gw` verbatim, and the repeat
    is **forced by §5.1**, which forbids this module every Tier A sibling. `test_rankers.py`
    asserts all three agree on the same mart rather than trusting the three copies to stay equal.

    `INVENTORY.md` §2.5 records why the predicate is needed at all: the DAL spine is a full
    player x gameweek cartesian product, so a GW20 debutant *has* GW1-19 rows with NULL
    performance, and counting them would score the DAL's construction rather than the player.
    """
    played = mart.loc[mart["minutes"].notna(), ["player_id", "gw"]]
    return played.groupby("player_id")["gw"].min()


def population(mart: pd.DataFrame) -> pd.DataFrame:
    """§8.3's frame: the post-registration spine with null `total_points` filled to **0**.

    §0.9's denominator, as a population rather than as a divisor: every gameweek from a player's
    registration onward is a row, whether he featured, blanked, or had no fixture. A rolling or
    expanding mean over these rows is therefore denominated in **gameweeks elapsed**, which is the
    quantity §0.9 selects; the same statistic over appearances is a different number, and
    `METRIC.md` §3.2 gives the concrete failure -- it orders an 8-per-appearance player who features
    a third of the time above a nailed 4-per-week one.

    Args:
        mart: the analytical mart, carrying at least `player_id`, `gw`, `minutes`, `total_points`.

    Returns:
        (`player_id`, `gw`, `total_points`), sorted by (`player_id`, `gw`) on a fresh
        `RangeIndex`, `total_points` float and complete. Never a view: the mart is copied, because
        §6.2 forbids mutating the frame every ranker in a paired comparison shares.
    """
    missing = [column for column in _PPG_MART_COLUMNS if column not in mart.columns]
    if missing:
        raise ValueError(f"mart is missing columns the PPG population reads: {missing}")

    frame = mart.loc[:, list(_PPG_MART_COLUMNS)].copy()
    first = registration_gw(frame)
    frame["_registration_gw"] = frame["player_id"].map(first)
    frame = frame.loc[frame["_registration_gw"].notna() & (frame["gw"] >= frame["_registration_gw"])]
    frame = frame.sort_values(["player_id", "gw"], kind="stable").reset_index(drop=True)
    frame["total_points"] = frame["total_points"].fillna(0).astype(float)
    return frame.loc[:, ["player_id", "gw", "total_points"]]


def _assert_points_complete(pop: pd.DataFrame) -> None:
    """§8.3's assertion, at the call site because the precondition is invisible there.

    A pandas rolling or expanding mean **skips** NaN rather than treating it as 0, so a frame whose
    blanks were left null would produce an *appearance*-denominated statistic -- the quantity §0.9
    rejects, and one that would look entirely plausible in the output. Without this the reuse of
    `expanding_prior_mean` and `add_lagged_rolls` is a silent-wrong-answer risk rather than a
    saving.
    """
    if bool(pop["total_points"].isna().any()):
        raise AssertionError(
            "total_points carries nulls across the population; the PPG denominator would be "
            "appearances rather than gameweeks elapsed (DESIGN.md §0.9, §8.3)"
        )


def _assert_lag_safe(rolled: pd.DataFrame, column: str) -> None:
    """§6.2's leakage assertion, written against the column actually used.

    The property is the one `model/features/build.py:190` enforces for governed features: a
    strictly-prior column is **NaN on each player's first row**, because that row has no legitimate
    history. Any construction that leaks -- a missing `shift(1)`, a forward window, a window
    bleeding across the player boundary -- is forced to surface a non-null value there.

    `assert_lag_safe` itself is not called: it takes a `FeaturePool`, and this column is not a
    governed feature and must not be given a spec that suggests it is (`INVENTORY.md` §2.1 records
    the mart's exclusion of `points_roll*`). §6.2 asks for an assertion over the columns the ranker
    uses, which is this.
    """
    first_rows = rolled.groupby("player_id", sort=False).head(1)
    if bool(first_rows[column].notna().any()):
        raise AssertionError(f"leakage: {column!r} is defined on a player's first population row (DESIGN.md §6.2)")


def _panel(name: str, pop: pd.DataFrame, score: pd.Series | np.ndarray) -> RankerOutput:
    """Assemble §6.1's output: the score column beside its keys, clipped to the declared window."""
    first_gw, last_gw = DECLARED_WINDOWS[name]
    frame = pd.DataFrame(
        {
            "player_id": pop["player_id"].to_numpy(dtype=int),
            "gw": pop["gw"].to_numpy(dtype=int),
            "score": np.asarray(score, dtype=float),
        }
    )
    frame = frame.loc[(frame["gw"] >= first_gw) & (frame["gw"] <= last_gw)]
    frame = frame.sort_values(["player_id", "gw"], kind="stable").reset_index(drop=True)
    return RankerOutput(name=name, window=(first_gw, last_gw), scores=frame.loc[:, list(_SCORE_COLUMNS)])


# ---------------------------------------------------------------------------
# F1 -- `p_play` alone (§0.12, §3.4, §8.1)
# ---------------------------------------------------------------------------


def rank_p_play(mart: pd.DataFrame) -> RankerOutput:
    """F1: rank on the probability of featuring, ignoring the scoring rate entirely.

    `PlayModel` is used as it stands (`model/terms/p_play/p_play.py:40`, §8.1) at its default
    variant. `INVENTORY.md` §2.6 measures the fit as an expanding walk-forward re-estimated per
    position per gameweek from strictly prior rows, so the as-of guarantee lives inside the
    ranker's own fit and one call covers the panel (§6.1). *`INVENTORY.md` does not record
    `PlayModel`'s constructor surface -- §11's third gap -- so the default is taken rather than
    configured; §6.1's interface admits a configured object if a later pass wants one.*

    **Coverage is the model's population, and the holes are governed rather than filled.**
    `INVENTORY.md` §2.6 measures `PlayModel.population` dropping `is_dgw` rows and null-`minutes`
    rows. Double-gameweek rows stay unrankable under §6.5 -- P(play) in a double gameweek is not 0
    and is not a fixed number, so no constant can fill the hole. No-fixture rows never reach that
    rule: §0.4 has the harness rank such a player last for *every* ranker, which is what stops F1
    carrying an implicit fixture-awareness the two PPG rankers lack. Rows below GW4 are outside the
    declared window and are not emitted.

    The predictions come back indexed to a population the fit built internally, so the frame is
    re-derived here and the two indices are asserted equal -- `model/terms/_binary_component.py`'s
    own `_scored_rows` re-derives it the same way, and the assertion is what turns that convention
    into something that fails loudly if it stops holding.
    """
    missing = [column for column in _P_PLAY_MART_COLUMNS if column not in mart.columns]
    if missing:
        raise ValueError(f"mart is missing columns the p_play ranker reads: {missing}")

    model = PlayModel()
    fitted = model.fit(mart)
    pop = PlayModel.population(mart)
    if not pop.index.equals(fitted.meta["population_index"]):
        raise AssertionError("PlayModel.population is not reproducible across calls; predictions cannot be aligned")

    return _panel(F1_P_PLAY, pop, fitted.predictions.to_numpy(dtype=float))


# ---------------------------------------------------------------------------
# F2 -- season-long PPG-to-date (§0.12, §8.1, §8.3)
# ---------------------------------------------------------------------------


def rank_season_ppg(mart: pd.DataFrame) -> RankerOutput:
    """F2: mean points per gameweek elapsed since registration, strictly before the scored week.

    `expanding_prior_mean` (`model/eval/baselines.py:58`) is called directly on §8.3's population.
    `INVENTORY.md` §2.1 records it as a one-argument `groupby.transform` with `shift(1)` before
    `expanding()` and **no population of its own** -- its meaning follows the rows passed -- which
    is exactly what makes it reusable for a denominator no wrapper in the repository supplies.
    §3.4 and §8.1 both record why its wrapper `build_baseline_features` must not be used instead:
    it filters `minutes > 0` and `~is_dgw`, which would drop the no-fixture rows §0.4 keeps legal
    to select and make the counterfactual easier than the real decision.

    A player's own registration gameweek carries **no** prior gameweek and therefore no rate, and
    the row is emitted as unrankable (null) rather than as a number -- §6.5's rule, and the same
    value F3 returns there, so the two floor rankers have identical coverage.
    """
    pop = population(mart)
    _assert_points_complete(pop)
    return _panel(F2_SEASON_PPG, pop, expanding_prior_mean(pop))


# ---------------------------------------------------------------------------
# F3 -- 3-gameweek recent form (§0.12, §6.4, §8.1, §8.3, §9.1)
# ---------------------------------------------------------------------------


def rank_recent_form(mart: pd.DataFrame) -> RankerOutput:
    """F3: mean points over the last `RECENT_FORM_WINDOW` gameweeks elapsed, lag-1.

    `add_lagged_rolls` (`model/features/build.py:37`) computes it at `min_periods = 1` over §8.3's
    population -- §6.4's selection, and §9.1 records that deriving over a population the consumer
    supplies is not merely *compatible* with the governance record but the construction it
    **requires**: `INVENTORY.md` §2.1 measures no `points_roll*` column on the governed mart and
    records the enforcement as being over `build_player_gameweek_state`'s output columns, so a
    ranker reading a mart column would have had nothing to read and one adding a column would have
    broken `tests/test_state_architecture.py`.

    `INVENTORY.md` §2.1 records the helper's convention as `shift(1).rolling(N).mean()` with
    `min_periods=1`, which is the same convention `research/families/form/validate/study.py` uses
    for the same two statistics. *The convention is shared; the frame is not* -- §0.9 denominates
    in gameweeks elapsed where the study rolls over its own `minutes >= 60` population, and §6.4 is
    explicit that the population is this slice's choice and not the study's.

    Warmup rows are partial-window means, not nulls: at GW2 the statistic is a one-gameweek mean
    and at GW3 a two-gameweek mean. §6.4 states the cost and requires it visible in the reported
    span rather than hidden behind a minimum-observations cut, and `METRIC.md` §5.3 records the
    consequence -- F2 and F3 return the same number for every player at GW2, GW3 and GW4, first
    diverging at GW5.
    """
    pop = population(mart)
    _assert_points_complete(pop)
    rolled = add_lagged_rolls(pop, sources=["total_points"], windows=(RECENT_FORM_WINDOW,))
    column = f"total_points_roll{RECENT_FORM_WINDOW}"
    _assert_lag_safe(rolled, column)
    return _panel(F3_FORM_ROLL3, pop, rolled[column])


# ---------------------------------------------------------------------------
# The pre-registered set (§0.12, §0.13)
# ---------------------------------------------------------------------------

FLOOR_RANKERS: Final[Mapping[str, RankFn]] = MappingProxyType(
    {
        F1_P_PLAY: rank_p_play,
        F2_SEASON_PPG: rank_season_ppg,
        F3_FORM_ROLL3: rank_recent_form,
    }
)
"""§0.12's pre-registered floor set -- all three, unconditionally.

§0.13 determines *which* of them is the floor per comparison, on the intersection of every window
involved; that is a property of a run's results and not of this module. A set rather than one
nominated ranker because `METRIC.md` §5.3 records that which naive ranker wins is itself a result:
if F1 is hard to beat, that says something about the decision no candidate's score would reveal.
"""
