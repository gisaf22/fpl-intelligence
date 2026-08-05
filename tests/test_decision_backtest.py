"""Behaviour tests for the decision backtest driver (ADR-012 Phase 4).

Legacy-independent: the driver's equivalence to the original tests/helpers evaluators was proven during
the 4a/4b migration; those originals are now deleted, so this tests the driver directly — a small
hand-verifiable case per family, CI determinism, and the empty edge.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dal.mart import GOVERNED_SIGNAL_COLUMNS
from model.eval.decision.backtest import run_backtest
from model.eval.decision.spec import CAPTAIN_EVAL, TRANSFERS_EVAL, VALUE_EVAL
from serve.captain import rank_captain_candidates
from serve.transfers import rank_transfer_targets
from serve.value import rank_value_players

pytestmark = pytest.mark.unit


def _row(pid: int, gw: int, **over: float) -> dict:
    row = {c: 0.0 for c in GOVERNED_SIGNAL_COLUMNS}
    row.update(
        {
            "is_warmup_gw": False,
            "minutes_trend": "stable",
            "fixture_context": "SGW",
            "minutes_roll3": 90.0,
            "minutes_roll5": 88.0,
            "points_roll3": 4.0,
            "xgi_roll3": 0.4,
            "player_id": pid,
            "gw": gw,
            "player_name": f"Player_{pid}",
            "position_label": "MID",
            "position_code": 3,
            "team_id": pid * 10,
            "purchase_price": 7.5,
            "fdr_avg": 3.0,
            "is_bgw": False,
            "goals_scored": 0.0,
            "total_points": 0.0,
            "p_haul": 0.1,
            "p90": 6.0,
            "e_points_uncond": 4.0,
        }
    )
    row.update(over)
    return row


def _captain_pick(f: pd.DataFrame, gw: int) -> pd.DataFrame:
    return rank_captain_candidates(f, target_gw=gw, n=20)


def test_captain_top1_grades_the_highest_haul_pick_against_its_actual_points():
    # Player 2 has the higher haul probability every GW and also outscores player 1 — so the driver
    # should captain player 2, its return should be player 2's actual points (6.0), and since it is the
    # actual best scorer, hit rate is perfect and regret is zero.
    gws = [4, 5, 6, 7, 8]
    rows = []
    for gw in gws:
        rows.append(_row(1, gw, p_haul=0.10, total_points=3.0))
        rows.append(_row(2, gw, p_haul=0.30, total_points=6.0))
    panel = pd.DataFrame(rows)

    result = run_backtest(CAPTAIN_EVAL, panel, gws, pick_fn=_captain_pick)

    assert result.gw_count == 5
    assert result.detail["heuristic_top1_id"].eq(2).all()
    assert result.heuristic_avg_return == pytest.approx(6.0)
    assert result.family_metrics["top1_hit_rate"] == pytest.approx(1.0)
    assert result.family_metrics["mean_regret"] == pytest.approx(0.0)


def test_paired_ci_is_deterministic():
    gws = [4, 5, 6, 7, 8]
    rows = []
    for gw in gws:
        rows.append(_row(1, gw, p_haul=0.10, total_points=float(gw % 4)))
        rows.append(_row(2, gw, p_haul=0.30, total_points=float((gw + 1) % 5)))
    panel = pd.DataFrame(rows)

    r1 = run_backtest(CAPTAIN_EVAL, panel, gws, pick_fn=_captain_pick)
    r2 = run_backtest(CAPTAIN_EVAL, panel, gws, pick_fn=_captain_pick)
    for label in ("recent", "xgi"):
        lo, hi = r1.paired_ci[label]
        assert lo <= hi
        assert (lo, hi) == r2.paired_ci[label]


@pytest.mark.parametrize(
    "spec,ranker,baseline_labels",
    [
        (TRANSFERS_EVAL, rank_transfer_targets, {"recent", "fixture"}),
        (VALUE_EVAL, rank_value_players, {"recent", "fixture"}),
    ],
)
def test_portfolio_families_run_and_report_baseline_relative_structure(spec, ranker, baseline_labels):
    gws = list(range(4, 16))
    rows = [_row(pid, gw, total_points=float((pid * 5 + gw * 7) % 13)) for pid in range(1, 13) for gw in gws]
    panel = pd.DataFrame(rows)

    result = run_backtest(spec, panel, list(range(4, 12)), pick_fn=lambda f, g: ranker(f, target_gw=g, n=spec.n))

    assert result.name == spec.name
    assert result.gw_count >= 1
    assert result.heuristic_avg_return is not None
    assert set(result.baselines) == baseline_labels
    assert set(result.paired_ci) == baseline_labels
    assert "heuristic_variance" in result.family_metrics


def test_empty_eval_window_returns_zero():
    panel = pd.DataFrame([_row(1, 4), _row(2, 4)])
    result = run_backtest(CAPTAIN_EVAL, panel, [], pick_fn=_captain_pick)
    assert result.gw_count == 0
    assert result.heuristic_avg_return is None
