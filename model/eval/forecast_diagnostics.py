"""Render-for-humans forecast diagnostics (relocated from the strangled god-files, spec §10.5).

Two per-position diagnostics that fit no model — they measure properties of the model's *inputs* and its
*accuracy ceiling*, so they live in ``model/eval`` (measurement of models), alongside
``captaincy_diagnostics``. They were the last live functions in ``component_forecast`` /
``points_model`` that were not extracted into the term registry; moved here so the god-files can be
deleted without losing them. Diagnostic only (no findings emission) — consumed by the eval notebooks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from domain.fpl_scoring import GK_SAVES_PER_POINT
from model.eval.metrics import grouped_spearman
from model.eval.population import canonical
from model.eval.walkforward import MIN_ROWS_PER_POS, POSITIONS, WARMUP_GW


def xg_vs_goals_forecast_skill(mart: pd.DataFrame) -> pd.DataFrame:
    """Within-position rank skill of lagged xG vs lagged goals at forecasting next-GW goals.

    Justifies feeding the goals term lagged process stats (xG/xA) rather than lagged realized
    components. Findings: docs/studies/results/predictive-phase2-component-model.md.
    """
    pop = canonical(mart)
    g = pop.groupby("player_id")
    # strictly-prior expanding means only — leakage-safe, mirrors the goals term's inputs.
    pop["xg_prior"] = g["xg"].transform(lambda s: s.expanding().mean().shift(1))
    pop["goals_prior"] = g["goals_scored"].transform(lambda s: s.expanding().mean().shift(1))
    ev = pop[pop["gw"] > WARMUP_GW].dropna(subset=["xg_prior", "goals_prior"])
    rows = []
    for pos in ("DEF", "MID", "FWD"):
        sub = ev[ev["position"] == pos]
        rx = grouped_spearman(sub, "xg_prior", "goals_scored", ["gw"], MIN_ROWS_PER_POS)
        rg = grouped_spearman(sub, "goals_prior", "goals_scored", ["gw"], MIN_ROWS_PER_POS)
        rows.append({"position": pos, "xg_prior": round(rx, 4), "goals_prior": round(rg, 4),
                     "delta": round(rx - rg, 4), "winner": "xG" if rx > rg else "goals"})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values("position").set_index("position")


def unmodeled_points_share(mart: pd.DataFrame) -> pd.DataFrame:
    """Per-position share of total points DEFERRED by the component map (bonus, and GK saves).

    Quantifies the accuracy ceiling the component ranking model cannot reach and motivates closing
    the points equation. Findings: docs/studies/results/predictive-phase3-scoring-diagnostics.md.
    """
    pop = canonical(mart)
    rows = []
    for pos in POSITIONS:
        sub = pop[pop["position"] == pos]
        tp = float(pd.to_numeric(sub["total_points"], errors="coerce").sum())
        bonus_pct = 100 * float(pd.to_numeric(sub["bonus"], errors="coerce").sum()) / tp
        saves = np.floor(pd.to_numeric(sub["saves"], errors="coerce").fillna(0) / GK_SAVES_PER_POINT)
        saves_pct = 100 * float(saves.sum()) / tp if pos == "GK" else 0.0
        rows.append({"position": pos, "total_points": round(tp),
                     "bonus_pct": round(bonus_pct, 1), "gk_saves_pct": round(saves_pct, 1)})
    out = pd.DataFrame(rows)
    out["position"] = pd.Categorical(out["position"], categories=POSITIONS, ordered=True)
    return out.sort_values("position").set_index("position")
