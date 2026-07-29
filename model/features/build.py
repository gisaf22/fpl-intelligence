"""spec -> lag-safe column, with the leakage property assertion (spec §4 stage 0).

Two responsibilities, kept small:

* :func:`materialize` — resolve a :class:`~model.features.spec.FeatureSpec` to its column on the
  mart. Today every declared feature is an already-frozen, lag-safe mart column (``*_roll3``,
  ``was_home``); this is the seam where a spec-driven build (roll/ewma/slope over ``source``) will
  land as the §3 axes are opened, so callers depend on *the spec*, never on a raw column name.
* :func:`assert_lag_safe` — the leakage property: a strictly-prior feature must be **NaN on every
  player's first appearance** (the one row with zero legitimate history). Any construction that
  leaks — a missing shift, a forward window, a window bleeding across the player boundary — is
  forced to surface a spurious non-NaN there. Known-future features (venue) are exempt by design.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from model.features.spec import FeaturePool, FeatureSpec


def materialize(mart: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    """The lag-safe column for ``spec``, as a Series aligned to ``mart``'s index.

    Currently a validated pass-through to the frozen mart column named ``spec.name`` (the mart's
    ``*_roll`` columns are already lag-safe — verified to exclude the current GW). The indirection is
    deliberate: terms declare features by spec, so opening a new §3 aggregation axis is a change here,
    not in every term.
    """
    if spec.name not in mart.columns:
        raise KeyError(f"feature {spec.name!r} not present on mart (source={spec.source!r})")
    return mart[spec.name]


def add_lagged_rolls(
    df: pd.DataFrame,
    sources: Sequence[str],
    windows: Sequence[int] = (3, 5),
    *,
    group: str = "player_id",
) -> pd.DataFrame:
    """Materialize strictly-prior rolling-mean features ``{source}_roll{w}`` (spec §3 aggregation axis).

    For each present ``source`` and window ``w``, builds ``{source}_roll{w}`` as the per-``group`` mean of
    the prior ``w`` appearances — ``shift(1)`` **before** rolling, so the current GW never enters its own
    feature (lag-safe by construction; asserted by :func:`assert_lag_safe`). Absent sources are skipped, so
    the same call is a no-op on a mart that lacks them. ``min_periods=1`` matches the frozen construction
    the shipped points model uses, so ``selected`` draws reproduce it.
    """
    out = df.copy()
    for src in sources:
        if src not in out.columns:
            continue
        out[src] = pd.to_numeric(out[src], errors="coerce")
        grouped = out.groupby(group)[src]
        for w in windows:
            out[f"{src}_roll{w}"] = grouped.transform(
                lambda s, w=w: s.shift(1).rolling(w, min_periods=1).mean()
            )
    return out


def add_opponent_xgc_forward(
    df: pd.DataFrame,
    window: int = 5,
    *,
    feature: str = "opp_xgc_forward",
    src: str = "xgc",
    opp_key: str = "opponent_team_id",
) -> pd.DataFrame:
    """Materialize ``opp_xgc_forward`` — the upcoming opponent's strictly-prior rolling conceded-xG.

    The dynamic, defence-side replacement for FPL's static one-number-per-team ``fdr_avg``: how leaky
    the *specific* opponent has been, updated week to week. Built at TEAM grain then broadcast onto
    player rows keyed on the **opponent's** identity (spec §3 #4, the same fan-out ``team_goals_against``
    uses, but keyed on ``opponent_team_id`` rather than the player's own ``team_id``):

    1. aggregate ``src`` (a team's own conceded-xG, ``xgc``) to a team-fixture frame — the mean over the
       team's appeared players (``minutes > 0``), mirroring ``team_goals_against.population``'s ``team_xgc``;
    2. lag-roll at team grain — ``shift(1).rolling(window)`` — so a team's row carries only its *strictly
       prior* conceded-xG (lag-safe by construction; asserted by :func:`assert_lag_safe_team`, and its
       first team-fixture is therefore NaN — the correct grain, since a debuting player faces an opponent
       that already has history);
    3. broadcast that team roll onto players keyed on ``opp_key`` — each player gets *their opponent's*
       leakiness.

    **Not leakage:** the opponent is fixed once the schedule is out (a known-future entity), and the roll
    uses only the opponent's matches strictly before gw ``t``. This is a strictly-prior roll of a
    known-future opponent, so it is checked at opponent-team grain, not at the player's first appearance.

    **Coverage.** A team that has no team-fixture row for gw ``t`` — an opponent playing a *double*
    gameweek there (its rows are DGW-excluded) or an as-yet-history-less side — leaves the broadcast NaN.
    Rather than let those attacking rows silently drop out of the scored population (``fdr_avg`` has no
    such holes, so the beats-fdr comparison must be same-``n``), they are filled with the strictly-prior
    **league-average** conceded-xG (an expanding mean over all prior team-fixtures — itself lag-safe): the
    honest "no opponent history yet" prior, exactly the role ``fdr_avg``'s static tier plays.

    A no-op (returns ``df`` unchanged) when ``opp_key`` or ``src`` is absent — mirroring
    :func:`add_lagged_rolls`, so a mart not enriched with the opponent identity simply does not draw it.
    """
    if opp_key not in df.columns or src not in df.columns:
        return df
    out = df.copy()
    out[src] = pd.to_numeric(out[src], errors="coerce")
    played = out[pd.to_numeric(out["minutes"], errors="coerce") > 0]
    team = (
        played.groupby(["team_id", "gw"], as_index=False)[src].mean()
        .rename(columns={src: "team_xgc"})
        .sort_values(["team_id", "gw"])
    )
    team[feature] = team.groupby("team_id")["team_xgc"].transform(
        lambda s: s.shift(1).rolling(window, min_periods=1).mean()
    )
    assert_lag_safe_team(team, feature)  # strictly-prior at opponent-team grain (first fixture is NaN)

    # Fan out keyed on the OPPONENT (rename team_id -> opp_key so broadcast joins opponent-to-player).
    opp_frame = team[["team_id", "gw", feature]].rename(columns={"team_id": opp_key})
    work = out[[opp_key, "gw"]].copy()
    work[opp_key] = pd.to_numeric(work[opp_key], errors="coerce")  # NaN opp (no fixture) -> league prior
    opp_frame[opp_key] = pd.to_numeric(opp_frame[opp_key], errors="coerce")
    broadcast_vals = broadcast(work, opp_frame, [feature], keys=(opp_key, "gw"))[feature]

    # Coverage fill: strictly-prior league-average conceded-xG where the opponent has no team row this gw.
    league_prior = _expanding_league_prior(team, "team_xgc")
    fill = out["gw"].map(league_prior)
    out[feature] = broadcast_vals.to_numpy()
    out[feature] = out[feature].fillna(fill)
    return out


def _expanding_league_prior(team: pd.DataFrame, col: str) -> pd.Series:
    """Per-gw strictly-prior league mean of ``col`` (expanding over all team-fixtures with gw < t).

    Lag-safe: the value for gw ``t`` averages only fixtures strictly before ``t`` (``cumsum().shift(1)``),
    so filling a coverage hole with it never sees the current gameweek. NaN at the first gw (no prior).
    """
    per_gw = team.groupby("gw")[col].agg(["sum", "count"]).sort_index()
    prior_sum = per_gw["sum"].cumsum().shift(1)
    prior_cnt = per_gw["count"].cumsum().shift(1)
    return prior_sum / prior_cnt


def broadcast(
    mart: pd.DataFrame,
    team_frame: pd.DataFrame,
    cols: Sequence[str],
    *,
    keys: Sequence[str] = ("team_id", "gw"),
) -> pd.DataFrame:
    """Broadcast ``team_gw`` columns onto ``player_gw`` rows via a checked left-join (spec §3 #4).

    A joint model fits at ``team_gw`` (one row per team-fixture) but its terms are consumed at
    ``player_gw`` (many players per fixture), so its output must fan **out**, once per player — the
    exact join at ``points_model.walk_forward_points``. This makes that step explicit and checked
    rather than an inline merge.

    Args:
        mart:       the player-grain frame to broadcast onto (carries ``keys``).
        team_frame: the team-grain frame carrying ``keys`` + ``cols``; **must be unique on ``keys``**.
        cols:       the team-grain columns to attach.
        keys:       the join grain (default the team-fixture key).

    Returns:
        A DataFrame indexed like ``mart``, one column per ``cols``, NaN where a team-fixture is absent.

    Raises:
        AssertionError: if ``team_frame`` has duplicate ``keys`` — a left-join would **multiply**
            player rows (the silent bug this guards), so the fan-out must be strictly one-to-many.
        KeyError: if a key or requested column is missing.
    """
    keys, cols = list(keys), list(cols)
    missing_keys = [k for k in keys if k not in mart.columns or k not in team_frame.columns]
    if missing_keys:
        raise KeyError(f"broadcast keys absent from mart or team_frame: {missing_keys}")
    missing_cols = [c for c in cols if c not in team_frame.columns]
    if missing_cols:
        raise KeyError(f"broadcast columns absent from team_frame: {missing_cols}")
    if bool(team_frame.duplicated(subset=keys).any()):
        raise AssertionError(f"broadcast: team_frame is not unique on {keys} — a left-join would multiply rows")

    merged = mart[keys].merge(team_frame[[*keys, *cols]], on=keys, how="left")
    # A left-join on a right side that is unique over `keys` preserves left row order and count, so the
    # merged frame realigns to mart's index positionally (asserted, not assumed).
    assert len(merged) == len(mart), "broadcast changed the row count — right side was not unique"
    merged.index = mart.index
    return merged[cols]


def assert_lag_safe(mart: pd.DataFrame, pool: FeaturePool) -> None:
    """Leakage property: every strictly-prior feature is NaN on each player's first appearance.

    Raises ``AssertionError`` naming the offending feature. Known-future features (``known_future``)
    are skipped — the upcoming fixture's venue is legitimately known before kickoff. Mirrors the
    harness canary in :mod:`model.eval.walkforward`, but scoped to a term's declared pool.
    """
    if "player_id" not in mart.columns or "gw" not in mart.columns:
        raise KeyError("mart must carry player_id + gw to check lag-safety")
    first_rows = mart.sort_values(["player_id", "gw"]).groupby("player_id").head(1)
    for spec in pool.candidates:
        # Known-future (venue) is exempt; a team-grain feature broadcast onto players (e.g.
        # opp_xgc_forward) is NOT NaN on a player's debut — the opponent already has history — so the
        # player-first-appearance canary is the wrong grain and would false-flag it. Team-grain features
        # are lag-checked at their own grain by :func:`assert_lag_safe_team` inside their build step.
        if spec.known_future or spec.grain != "player_gw" or spec.name not in mart.columns:
            continue
        if bool(first_rows[spec.name].notna().any()):
            raise AssertionError(
                f"leakage: strictly-prior feature {spec.name!r} is defined on a player's first appearance"
            )


def assert_lag_safe_team(
    team_frame: pd.DataFrame, feature: str, *, group: str = "team_id", gw_col: str = "gw"
) -> None:
    """Team-grain leakage property: a strictly-prior team roll is NaN on each team's first fixture.

    The opponent-team analogue of :func:`assert_lag_safe`. ``opp_xgc_forward`` is a ``shift(1).rolling``
    of a team's own conceded-xG, so a team's *first* fixture — the one row with zero legitimate prior —
    must be NaN. Any construction that leaks the present (a missing ``shift``, a forward/centred window,
    a window bleeding across the team boundary) forces a spurious non-NaN there, which this catches.
    Asserted on the team frame *before* the opponent broadcast (and before any coverage fill), so it
    tests the roll itself rather than the fanned-out, prior-filled column consumers see.
    """
    if group not in team_frame.columns or gw_col not in team_frame.columns:
        raise KeyError(f"team frame must carry {group} + {gw_col} to check team-grain lag-safety")
    first_rows = team_frame.sort_values([group, gw_col]).groupby(group).head(1)
    if bool(first_rows[feature].notna().any()):
        raise AssertionError(
            f"leakage: team-grain feature {feature!r} is defined on a team's first fixture"
        )
