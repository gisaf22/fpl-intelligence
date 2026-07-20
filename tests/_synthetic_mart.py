"""Shared synthetic player-GW panel for the eval tests (calibration + captaincy backtest).

Extracted verbatim from the now-deleted ``test_model_forecast_points_model`` so the two surviving eval
tests keep a realistic mart-like fixture. Not a test module (no ``test_`` prefix) — imported as a helper.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def points_panel(n_teams: int = 20, n_gw: int = 16, seed: int = 0) -> pd.DataFrame:
    """Synthetic player-GW panel: per-team defensive strength drives goals-against, and each player
    has a stable defensive-action propensity driving ``defensive_contribution`` (so lags predict)."""
    rng = np.random.default_rng(seed)
    rows = []
    for tm in range(n_teams):
        strength = rng.uniform(0.3, 2.2)  # team's mean goals-against
        dc_prop = {slot: rng.uniform(3, 13) for slot in range(5)}  # per-player DC-action mean
        p60 = {slot: rng.uniform(0.4, 0.98) for slot in range(5)}   # per-player start propensity
        for gw in range(1, n_gw + 1):
            ga = rng.poisson(strength)
            home = int(rng.random() < 0.5)
            for slot, pos in enumerate(["GK", "DEF", "DEF", "MID", "FWD"]):
                started = int(rng.random() < (0.99 if pos == "GK" else p60[slot]))
                mins = 90 if started else int(rng.integers(1, 60))
                goals = rng.poisson(0.3 if pos in ("MID", "FWD") else 0.05)
                assists = rng.poisson(0.15)
                cs = int(ga == 0) if pos != "FWD" else 0
                # bonus tracks returns (more goals/assists/CS -> more likely top-3 BPS)
                bonus = min(3, rng.poisson(0.4 * goals + 0.2 * assists + 0.1 * cs))
                gmult = {"GK": 10, "DEF": 6, "MID": 5, "FWD": 4}[pos]
                cmult = {"GK": 4, "DEF": 4, "MID": 1, "FWD": 0}[pos]
                total_points = 2 + goals * gmult + assists * 3 + cs * cmult + bonus
                rows.append({
                    "player_id": tm * 5 + slot, "team_id": tm, "gw": gw, "position": pos,
                    "minutes": mins, "is_dgw": False, "starts": started,
                    "goals_scored": goals, "assists": assists, "saves": rng.poisson(1.0) if pos == "GK" else 0,
                    "goals_conceded": ga, "xgc": strength + rng.normal(0, 0.1),
                    "xgc_roll3": strength, "goals_conceded_roll3": strength,
                    "clean_sheets": cs, "clean_sheets_roll3": rng.uniform(0, 1),
                    "xg": max(0.0, 0.15 + rng.normal(0, 0.05)), "xa": max(0.0, 0.1 + rng.normal(0, 0.03)),
                    "xgi_roll3": rng.uniform(0, 0.5), "xgi_roll5": rng.uniform(0, 0.5),
                    "defensive_contribution": rng.poisson(dc_prop[slot]),
                    "minutes_roll3": 70.0 + 20 * p60[slot], "minutes_roll5": 70.0 + 20 * p60[slot],
                    "minutes_roll8": 70.0 + 20 * p60[slot], "bonus": bonus, "total_points": total_points,
                    "was_home": home, "fdr_avg": rng.uniform(2, 4),
                })
    return pd.DataFrame(rows)
