"""Scoring engine — pure computation, no I/O.

Inputs:
  state    — DataFrame from dal.build_player_gameweek_state(spine)
  manifest — SignalManifest from intelligence.scoring.signals.load_manifest()
  gw       — target gameweek integer

Output:
  ScorerOutput  — complete scored result ready for the renderer
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from dal.mart import POSITION_CODE_MAP
from intelligence.scoring.contracts import PlayerScore, ScorerOutput, SignalManifest


class NoDataForGameweek(Exception):
    """Raised when the state DataFrame has no rows for the requested gameweek."""


def _normalise(series: pd.Series) -> pd.Series:
    """Normalise a numeric series to [0, 1]. Constant series → 0.5 for all rows."""
    lo = series.min()
    hi = series.max()
    if hi == lo:
        return pd.Series(0.5, index=series.index, dtype=float)
    return (series - lo) / (hi - lo)


def score(
    state: pd.DataFrame,
    manifest: SignalManifest,
    gw: int,
) -> ScorerOutput:
    """Score all players for the target gameweek.

    Steps:
    1. Filter state to target GW. Raise NoDataForGameweek if empty.
    2. For each position, resolve confirmed signals for that position.
    3. Apply direction (negative rho → negate raw values before normalisation).
    4. Normalise each signal to [0, 1] within position.
    5. Compute composite as weighted mean (weight = abs(rho_pooled)).
    6. Rank players within position by composite score descending.
    7. Return ScorerOutput with one PlayerScore per player.
    """
    gw_data = state[state["gw"] == gw].copy()
    if gw_data.empty:
        raise NoDataForGameweek(
            f"No data found for gameweek {gw}. "
            "Ensure the database has been populated for this gameweek."
        )

    # Derive registry-compatible position string from position_code (GKP→GK etc.)
    gw_data["_position"] = gw_data["position_code"].map(POSITION_CODE_MAP)

    # Group confirmed signals by position for fast lookup
    confirmed_by_position: dict[str, list] = {}
    for sig in manifest.confirmed:
        confirmed_by_position.setdefault(sig.position, []).append(sig)

    player_scores: list[PlayerScore] = []

    for position, signals in confirmed_by_position.items():
        pos_data = gw_data[gw_data["_position"] == position].copy()
        if pos_data.empty:
            continue

        signal_names = [s.signal for s in signals]
        rho_weights = {s.signal: abs(s.rho_pooled) for s in signals}
        directions = {s.signal: s.direction for s in signals}

        # Collect raw values; NaN where the column is missing or null
        raw: dict[str, pd.Series] = {}
        for sig_name in signal_names:
            if sig_name in pos_data.columns:
                raw[sig_name] = pos_data[sig_name].astype(float)
            else:
                raw[sig_name] = pd.Series(np.nan, index=pos_data.index)

        # Normalise each signal within position (direction-adjusted)
        normalised: dict[str, pd.Series] = {}
        for sig_name in signal_names:
            directed = raw[sig_name] * directions[sig_name]
            # Fill NaN with the directed mean so missing players aren't penalised or rewarded
            col_mean = directed.mean()
            if pd.isna(col_mean):
                col_mean = 0.0
            directed_filled = directed.fillna(col_mean)
            normalised[sig_name] = _normalise(directed_filled)

        # Composite: weighted mean of normalised values
        total_weight = sum(rho_weights[s] for s in signal_names)
        if total_weight == 0.0:
            total_weight = 1.0  # guard; weights are abs(rho) so this only fires on empty

        composite = pd.Series(0.0, index=pos_data.index)
        for sig_name in signal_names:
            composite += normalised[sig_name] * rho_weights[sig_name]
        composite /= total_weight

        # Rank descending (rank 1 = highest composite)
        ranks = composite.rank(method="min", ascending=False).astype(int)

        for idx in pos_data.index:
            row = pos_data.loc[idx]
            player_scores.append(
                PlayerScore(
                    player_id=int(row["player_id"]),
                    player_name=str(row.get("player_name", row["player_id"])),
                    position=position,   # registry-canonical position (GK not GKP)
                    rank=int(ranks[idx]),
                    composite_score=float(composite[idx]),
                    signal_values={
                        s: (float(raw[s][idx]) if not pd.isna(raw[s][idx]) else None)
                        for s in signal_names
                    },
                    signal_normalised={
                        s: float(normalised[s][idx])
                        for s in signal_names
                    },
                )
            )

    scored_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return ScorerOutput(
        gw=gw,
        scored_at=scored_at,
        players=player_scores,
        manifest=manifest,
    )
