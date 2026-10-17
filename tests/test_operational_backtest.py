"""Thin test for the operational backtest binding (ADR-012 §6).

Confirms the composition root injects each decision's serve ranker into the model/eval driver and
produces a result for every registered decision. The driver's metric correctness is covered by
tests/test_decision_backtest.py; this only checks the wiring.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dal.mart import GOVERNED_SIGNAL_COLUMNS
from operational.backtest import EVAL_SPECS, backtest_decision

pytestmark = pytest.mark.unit


def _row(pid: int, gw: int) -> dict:
    row = {c: 0.0 for c in GOVERNED_SIGNAL_COLUMNS}
    row.update(
        {
            "is_warmup_gw": False,
            "minutes_trend": "stable",
            "fixture_context": "SGW",
            "minutes_roll3": 90.0,
            "minutes_roll5": 88.0,
            "points_roll3": float((pid + gw) % 6),
            "xgi_roll3": float((pid * 2 + gw) % 5) / 10.0,
            "player_id": pid,
            "gw": gw,
            "player_name": f"Player_{pid}",
            "position_label": "MID",
            "position_code": 3,
            "team_id": pid * 10,
            "purchase_price": 5.0 + 0.2 * pid,
            "fdr_avg": float(2 + (pid % 4)),
            "is_bgw": False,
            "goals_scored": 0.0,
            "total_points": float((pid * 5 + gw * 7) % 13),
            "p_haul": 0.1 + 0.01 * pid,
            "p90": 6.0 + pid,
            "e_points_uncond": 2.0 + 0.3 * pid,
        }
    )
    return row


@pytest.fixture
def panel() -> pd.DataFrame:
    return pd.DataFrame([_row(pid, gw) for pid in range(1, 13) for gw in range(4, 13)])


def test_binding_runs_every_registered_decision(panel):
    eval_gws = [4, 5, 6, 7, 8]
    for name, spec in EVAL_SPECS.items():
        result = backtest_decision(spec, panel, eval_gws)
        assert result.name == name
        assert result.gw_count >= 1
        assert set(result.baselines)  # baseline-relative result produced
