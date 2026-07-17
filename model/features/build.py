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
        if spec.known_future or spec.name not in mart.columns:
            continue
        if bool(first_rows[spec.name].notna().any()):
            raise AssertionError(
                f"leakage: strictly-prior feature {spec.name!r} is defined on a player's first appearance"
            )
