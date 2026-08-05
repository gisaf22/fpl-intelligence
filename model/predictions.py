"""The operational forecast surface — mean + distribution, one row per scored player-GW.

The single place that joins what ``compose`` and ``simulate`` produce into the frame downstream
consumers actually want: the conditional mean ``e_points`` and its decomposition (``compose_points``),
the ex-ante unconditional ``e_points_uncond`` = P(play) x E[points | played], and the distribution
summaries the mean cannot express — ``p90``/``p10`` (captaincy ceiling / downside) and ``p_haul``
(``simulate_points``). This is what an operational layer reads instead of hand-rolling a signal
composite; it is *data*, so it can be handed across the ``serve`` boundary (a column frame or a file)
without ``serve`` importing ``model`` (import-linter ``no_serve_to_research_or_model``).
"""

from __future__ import annotations

import pandas as pd

from model.compose import compose_parameters, compose_points
from model.simulate import simulate_points

# The distribution summaries carried alongside the mean (``position`` is already on the compose panel).
_SIM_CARRY = ["player_id", "gw", "sim_mean", "sim_sd", "p10", "p50", "p90", "p_haul"]


def assemble_forecast(mart: pd.DataFrame, *, n_sims: int = 2000, seed: int = 0, keep_all: bool = True) -> pd.DataFrame:
    """Per player-GW forecast: the compose mean panel left-joined to the simulate distribution.

    Returns ``compose_points(mart, keep_all)`` — ``player_id, team_id, gw, position, minutes``, the
    per-term ``DECOMP_COLUMNS``, ``e_points``, ``base_season`` (and, with ``keep_all``, ``p_play`` +
    ``e_points_uncond``) — with ``sim_mean, sim_sd, p10, p50, p90, p_haul`` merged on ``(player_id, gw)``.
    Distribution columns are NaN on rows the simulator does not score (pre-warmup / non-appearing).

    ``keep_all=True`` (default) is the operational universe: it carries the ex-ante ``e_points_uncond``
    that value/transfer ranking needs, while the ceiling reads (``p90``/``p_haul``) stay the
    conditional-on-appearance simulator draws. The MC is seed-pinned, so a given ``(mart, n_sims, seed)``
    reproduces exactly.
    """
    means = compose_points(mart, keep_all=keep_all)
    params = compose_parameters(mart, keep_all=keep_all)
    sim = simulate_points(params, n_sims=n_sims, seed=seed)[_SIM_CARRY]
    return means.merge(sim, on=["player_id", "gw"], how="left")
