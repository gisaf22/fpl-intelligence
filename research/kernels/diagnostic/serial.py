"""Within-player serial-dependence kernel — diagnostic, association-only.

Measures whether a player's own values carry over from one gameweek to the next:
the lag-l rank autocorrelation of a column *within* each player, and the rate at
which an event in one gameweek coincides with an outcome in the next.

To isolate genuine within-player persistence from between-player level differences,
the autocorrelation demeans each value by the player's own season mean before pairing
(the same within-transformation as ``panel.split_between_within_player_rho``). See
``within_player_autocorr`` for the demeaning rationale and its small Nickell-bias caveat.

This is a **diagnostic** (Rung 2) kernel: it characterises observed structure in the
season at hand — "does form cluster within a player?" — and stays on the association
rung. It makes **no predictive claim**: the lag-1 pairing describes serial dependence
already present in the data, not a forecast of future gameweeks. Predictive
generalisation (lagged study + inference + gates) belongs to the families layer.

Pairing is by **gameweek number**, not row order: a row at gw ``t`` is paired with the
same player's row at gw ``t + lag`` only when both rows exist in the supplied frame.
Players who miss the intervening gameweek therefore contribute no spanning pair, so a
gap in appearances never produces a spurious "consecutive" pair.

Vocabulary mirrors the sibling diagnostic kernels (``panel.py``, ``conditioning.py``):
results are dicts with rounded statistics, explicit counts, and a ``support_flag`` that
is non-empty when the slice was too thin to interpret.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from research.kernels.diagnostic._rankcorr import rank_corr as _rank_corr

# Minimum spanning pairs required before a within-player autocorrelation is reported.
# A floor against degenerate spearmanr (constant / tiny samples), not a power threshold.
MIN_N_PAIRS = 30

# Minimum conditioning events required before a transition rate is reported.
MIN_N_EVENTS = 30

# Minimum distinct players that must contribute before a within-player statistic is
# reported. A pooled rho/rate can clear a pair/event floor while resting on a handful of
# players' trajectories, which is leverage, not representativeness. Mirrors the
# ``min_n_players`` guard in ``panel.split_between_within_player_rho``.
MIN_N_PLAYERS = 20

# Sentinel returned when a slice cannot be interpreted.
_INSUFFICIENT = "insufficient_support"


def _require_columns(df: pd.DataFrame, columns: set[str]) -> None:
    """Raise if any required column is absent, naming the offenders.

    Fail-fast guard kept separate so both public functions share one error contract.
    """
    missing = columns - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")


def _require_binary(s: pd.Series, name: str) -> None:
    """Raise unless every non-null value of ``s`` is boolean or 0/1.

    ``transition_rate`` reads ``event``/``outcome`` as rates via ``astype(bool)`` and
    ``mean()``; a stray value like ``2.0`` would coerce to ``True`` and the mean would
    stop being a rate. This makes the "must be boolean (or 0/1)" precondition fail-fast
    rather than silently wrong. All-null columns pass (a support issue, not a contract
    violation). ``True``/``False`` satisfy ``isin([0, 1])`` because ``True == 1``.
    """
    nonnull = s.dropna()
    if not nonnull.isin([0, 1]).all():
        bad = sorted({v for v in nonnull.unique() if v not in (0, 1)}, key=str)
        raise ValueError(f"{name} must be boolean or 0/1; found non-binary values: {bad}")


def _pair_with_future(
    df: pd.DataFrame,
    future_cols: list[str],
    player_col: str,
    gw_col: str,
    lag: int,
) -> pd.DataFrame:
    """Join each (player, gw) row to the same player's row ``lag`` gameweeks later.

    The later row's ``future_cols`` are carried back onto the current row with a
    ``__next`` suffix; all current-row columns are retained. The join is an inner join
    on (player, gw), so only player-gameweeks whose ``+lag`` counterpart is also present
    survive — gaps in a player's appearances are dropped rather than bridged.

    Args:
        df:          Source frame; must contain ``player_col``, ``gw_col`` and
                     every name in ``future_cols``.
        future_cols: Columns to pull from the ``+lag`` row (suffixed ``__next``).
        player_col:  Player identity column.
        gw_col:      Integer gameweek column (the lag axis).
        lag:         Positive gameweek offset to span.

    Returns:
        A frame with one row per spanning pair: the current row's columns plus
        ``<col>__next`` for each ``future_cols`` entry. Empty when no pair spans.
    """
    if lag < 1:
        raise ValueError(f"lag must be a positive gameweek offset, got {lag}")

    # Grain precondition. Serial pairing is a (player, gw) self-join; a duplicate key turns
    # it into a Cartesian product within the key (one row spuriously pairs with several),
    # which silently corrupts both the count and the statistic. The analytical mart is
    # already (player_id, gw)-unique — DGWs arrive pre-collapsed to one summed row — so this
    # never fires in the intended pipeline. It is a fail-fast boundary for off-grain input:
    # a fixture-grain frame, or seasons pooled without a season key so gw numbers collide.
    # Same rationale as dal.feat's entry-time grain check (a dup corrupts the windows it feeds).
    if df.duplicated(subset=[player_col, gw_col]).any():
        n_dup = int(df.duplicated(subset=[player_col, gw_col]).sum())
        raise ValueError(
            f"({player_col}, {gw_col}) must be unique before serial pairing — found {n_dup} "
            "duplicate key(s). Each row must be one player-gameweek (mart grain): collapse "
            "double-gameweeks, or add a season key (pool on season+player_id+gw) before calling."
        )

    future = df[[player_col, gw_col, *future_cols]].copy()
    future = future.rename(columns={col: f"{col}__next" for col in future_cols})
    # Shift the later row back by `lag` so it aligns with the current gw on merge.
    future[gw_col] = future[gw_col] - lag
    return df.merge(future, on=[player_col, gw_col], how="inner")


def within_player_autocorr(
    df: pd.DataFrame,
    col: str,
    player_col: str = "player_id",
    gw_col: str = "gw",
    lag: int = 1,
    min_n_pairs: int = MIN_N_PAIRS,
    min_n_players: int = MIN_N_PLAYERS,
    demean: bool = True,
    method: str = "spearman",
) -> dict[str, Any]:
    """Lag-l within-player rank autocorrelation of ``col`` (serial dependence).

    Pools every (value at gw ``t``, value at gw ``t + lag``) pair for the same player
    and reports their rank correlation. A high positive rho means a player's value tends
    to persist week to week (it "clusters"); near zero means each gameweek is roughly
    independent of the last; negative means it tends to reverse.

    **Player demeaning (``demean=True``, the default).** Each value has its player's
    full-season mean subtracted before pairing, so the correlation reflects within-player
    deviations from a player's own baseline — *state* — rather than between-player level
    differences — *identity*. Without it the pooled correlation is inflated by the fact
    that consistently high players supply (high, high) pairs and low players (low, low)
    pairs, which is between-player identity, not serial dependence. This mirrors the
    within component of ``panel.split_between_within_player_rho``.

    Two consequences of demeaning, stated honestly:
      * It uses the player's whole-season mean (a descriptive within-transformation, not
        a lag-respecting trailing mean). That is correct for a Rung-2 *description* of the
        observed season; a *predictive* use would require a trailing mean to avoid
        look-ahead, which belongs to the families layer, not here.
      * It induces a small downward (Nickell) bias of order -1/(T-1) in the
        autocorrelation. With T ~ 30-38 gameweeks this is ~-0.03 — it can only understate
        persistence, never manufacture it. Set ``demean=False`` for the raw pooled
        persistence (which then *includes* between-player identity).

    Args:
        df:          Analytical slice (e.g. one position, ``minutes > 0``). Filtering is
                     the caller's responsibility — this kernel only pairs and correlates.
        col:         Column whose within-player persistence is measured.
        player_col:  Player identity column.
        gw_col:      Integer gameweek column.
        lag:         Gameweek offset to span (default 1 = adjacent gameweeks).
        min_n_pairs: Floor on spanning pairs below which rho is suppressed.
        min_n_players: Floor on the number of *distinct players* contributing a spanning
                     pair. A pooled rho can clear ``min_n_pairs`` while resting on a few
                     players' trajectories (leverage, not representativeness); this guards
                     it, mirroring ``panel.split_between_within_player_rho``.
        demean:      Subtract each player's full-season mean before pairing (default True).
        method:      Rank-correlation method — ``"spearman"`` (default) or ``"kendall"``
                     (tau-b, tie-corrected sensitivity check). With ``demean=True`` the
                     statistic is no longer invariant to monotone rescaling of ``col``,
                     because demeaning is an affine operation applied before ranking; with
                     ``demean=False`` Spearman's monotone invariance holds.

    Returns:
        ``{"rho", "n_pairs", "n_players", "lag", "support_flag"}``. ``rho`` is rounded to
        4 dp (it carries tau-b when ``method="kendall"``), or ``NaN`` when there are fewer
        than ``min_n_pairs`` spanning pairs, fewer than ``min_n_players`` distinct players
        contribute, or either side of the pair is constant. ``n_pairs`` counts overlapping
        within-player pairs (each interior row enters two), so it is **not** an
        independent-sample size — any inference belongs to the families layer, not here.
        The ``support_flag`` is ``"insufficient_support"`` in those cases, else empty.

    Raises:
        ValueError: if a required column is missing, ``(player_col, gw_col)`` is not unique,
                    ``lag`` is not positive, or ``method`` is unknown.
    """
    _require_columns(df, {col, player_col, gw_col})

    work = df[[player_col, gw_col, col]].copy()
    value_col = col
    if demean:
        baseline = work.groupby(player_col)[col].transform("mean")
        work = work.assign(_dm=work[col].astype(float) - baseline.astype(float))
        value_col = "_dm"

    pairs = _pair_with_future(work, [value_col], player_col, gw_col, lag)
    pairs = pairs[[player_col, value_col, f"{value_col}__next"]].dropna()
    n_pairs = len(pairs)
    n_players = int(pairs[player_col].nunique())

    interpretable = (
        n_pairs >= min_n_pairs
        and n_players >= min_n_players
        and pairs[value_col].nunique() > 1
        and pairs[f"{value_col}__next"].nunique() > 1
    )
    if not interpretable:
        return {"rho": np.nan, "n_pairs": n_pairs, "n_players": n_players, "lag": lag, "support_flag": _INSUFFICIENT}

    rho = _rank_corr(pairs[value_col], pairs[f"{value_col}__next"], method)
    return {"rho": round(rho, 4), "n_pairs": n_pairs, "n_players": n_players, "lag": lag, "support_flag": ""}


def post_event_outcome_rate(
    df: pd.DataFrame,
    event_col: str,
    outcome_col: str,
    player_col: str = "player_id",
    gw_col: str = "gw",
    lag: int = 1,
    min_n_events: int = MIN_N_EVENTS,
    min_n_players: int = MIN_N_PLAYERS,
) -> dict[str, Any]:
    """Observed outcome rate the gameweek after an event, against the base rate.

    Answers "given this happened (e.g. a haul), how often did the player return the
    next gameweek — versus how often they return in general?" Both ``event_col`` and
    ``outcome_col`` must be boolean (or 0/1). The conditional rate is computed over the
    ``+lag`` row of player-gameweeks where the event fired; the base rate is the
    unconditional outcome rate over every paired current row, so the two are measured on
    the same pairable population and are directly comparable.

    This is a descriptive coincidence rate within the observed season — not a predictive
    probability. ``lift`` is the additive gap (conditional minus base) in rate points; note
    that ``base_rate`` is the *grand* rate over all paired rows (it includes the event rows
    themselves), so the contrast is "after the event vs. overall", not "after the event vs.
    after a non-event". For a rare outcome read ``lift`` against ``base_rate``: +0.05 on a
    base of 0.02 is a much larger relative shift than +0.05 on a base of 0.40.

    Args:
        df:           Analytical slice. Filtering is the caller's responsibility.
        event_col:    Boolean conditioning event observed at gw ``t``.
        outcome_col:  Boolean outcome whose rate is measured at gw ``t + lag``.
        player_col:   Player identity column.
        gw_col:       Integer gameweek column.
        lag:          Gameweek offset between event and outcome (default 1).
        min_n_events: Floor on conditioning events below which rates are suppressed.
        min_n_players: Floor on the number of *distinct players* firing the event, so a
                      rate cannot rest on a handful of players (leverage, not support).

    Returns:
        ``{"base_rate", "conditional_rate", "lift", "n_event", "n_paired", "n_players",
        "lag", "support_flag"}``. Rates and ``lift`` are rounded to 4 dp, or ``NaN`` with
        ``support_flag = "insufficient_support"`` when fewer than ``min_n_events`` events
        have a ``+lag`` counterpart, or fewer than ``min_n_players`` distinct players fire
        the event. ``n_players`` counts distinct players supplying a conditioning event.

    Raises:
        ValueError: if a required column is missing, ``(player_col, gw_col)`` is not unique,
                    ``event_col``/``outcome_col`` are not boolean/0-1, or ``lag`` is not
                    positive.
    """
    _require_columns(df, {event_col, outcome_col, player_col, gw_col})
    _require_binary(df[event_col], event_col)
    _require_binary(df[outcome_col], outcome_col)

    paired = _pair_with_future(df, [outcome_col], player_col, gw_col, lag)
    next_outcome = paired[f"{outcome_col}__next"]
    # Restrict to pairs whose outcome and event are both observed (non-null).
    paired = paired[next_outcome.notna() & paired[event_col].notna()]
    n_paired = len(paired)

    event_mask = paired[event_col].astype(bool)
    n_event = int(event_mask.sum())
    n_players = int(paired.loc[event_mask, player_col].nunique())

    if n_event < min_n_events or n_players < min_n_players:
        return {
            "base_rate": np.nan,
            "conditional_rate": np.nan,
            "lift": np.nan,
            "n_event": n_event,
            "n_paired": n_paired,
            "n_players": n_players,
            "lag": lag,
            "support_flag": _INSUFFICIENT,
        }

    base_rate = float(paired[f"{outcome_col}__next"].astype(float).mean())
    conditional_rate = float(paired.loc[event_mask, f"{outcome_col}__next"].astype(float).mean())
    return {
        "base_rate": round(base_rate, 4),
        "conditional_rate": round(conditional_rate, 4),
        "lift": round(conditional_rate - base_rate, 4),
        "n_event": n_event,
        "n_paired": n_paired,
        "n_players": n_players,
        "lag": lag,
        "support_flag": "",
    }
