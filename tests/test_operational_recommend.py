"""Tests for the operational composition root (operational.recommend).

Exercises the wiring — enrich the mart with the forecast, run every registered decision, write the
outputs — without a database or the Monte-Carlo simulator: ``assemble_forecast`` is stubbed, since the
forecast itself is covered by tests/test_model_predictions.py. This isolates the composition root's
job (join → dispatch → write) from the forecast internals.
"""

from __future__ import annotations

import pandas as pd
import pytest

from dal.mart import GOVERNED_SIGNAL_COLUMNS
from operational import recommend
from operational.recommend import (
    DECISIONS,
    enrich_with_forecast,
    recommend_from_mart,
)

pytestmark = pytest.mark.unit


def _mart_row(
    player_id: int,
    gw: int,
    *,
    position_label: str = "MID",
    purchase_price: float = 7.5,
    minutes_roll3: float = 90.0,
    minutes_roll5: float = 85.0,
    p_haul: float = 0.20,
    p90: float = 8.0,
    e_points_uncond: float = 6.0,
) -> dict:
    """A single mart row carrying every governed + spine column the rankers require, pre-enriched
    with the model forecast columns (as the composition root would merge them)."""
    row: dict = {c: 0.0 for c in GOVERNED_SIGNAL_COLUMNS}
    row.update(
        {
            "is_warmup_gw": False,
            "minutes_trend": "stable",
            "fixture_context": "SGW",
            "minutes_roll3": minutes_roll3,
            "minutes_roll5": minutes_roll5,
            # spine
            "player_id": player_id,
            "gw": gw,
            "player_name": f"Player_{player_id}",
            "position_label": position_label,
            "position_code": 3,
            "team_id": player_id * 10,
            "purchase_price": purchase_price,
            "fdr_avg": 3.0,
            "is_bgw": False,
            "goals_scored": 0.5,
            # model forecast (enriched onto the mart by the runner)
            "p_haul": p_haul,
            "p90": p90,
            "e_points_uncond": e_points_uncond,
        }
    )
    return row


@pytest.fixture
def mart() -> pd.DataFrame:
    # Player 1 dominates on all three objectives, including per-£ value (7.0/6.0 > 4.0/5.0), so it ranks
    # first for captain, transfers, AND value — an unambiguous fixture for the ranking assertion.
    return pd.DataFrame(
        [
            _mart_row(1, 5, p_haul=0.30, p90=11.0, e_points_uncond=7.0, purchase_price=6.0),
            _mart_row(2, 5, p_haul=0.10, p90=6.0, e_points_uncond=4.0, purchase_price=5.0),
        ]
    )


def test_enrich_with_forecast_merges_forecast_only_columns(monkeypatch):
    """enrich merges forecast columns not already on the mart, left-joined on (player_id, gw)."""
    base = pd.DataFrame({"player_id": [1, 2], "gw": [5, 5], "purchase_price": [9.0, 5.0]})

    def _fake_forecast(mart: pd.DataFrame, *, n_sims: int, seed: int) -> pd.DataFrame:
        # includes a key col AND an overlapping col (purchase_price) that must NOT clobber the mart.
        return pd.DataFrame(
            {"player_id": [1, 2], "gw": [5, 5], "e_points_uncond": [7.0, 4.0], "purchase_price": [0.0, 0.0]}
        )

    monkeypatch.setattr(recommend, "assemble_forecast", _fake_forecast)
    enriched = enrich_with_forecast(base)

    assert "e_points_uncond" in enriched.columns
    assert len(enriched) == 2  # left join preserves every mart row
    # the mart's own purchase_price is retained, not overwritten by the forecast's overlapping column
    assert enriched["purchase_price"].tolist() == [9.0, 5.0]
    assert enriched.loc[enriched["player_id"] == 1, "e_points_uncond"].iloc[0] == 7.0


def test_recommend_from_mart_writes_all_decisions(monkeypatch, tmp_path, mart):
    """Every registered decision is ranked and written; the summary is produced."""
    # Mart is already forecast-enriched; make assemble_forecast a no-op join (adds no new columns).
    monkeypatch.setattr(recommend, "assemble_forecast", lambda mart, *, n_sims, seed: mart[["player_id", "gw"]].copy())

    result = recommend_from_mart(mart, target_gw=5, output_dir=tmp_path)

    assert set(result.recommendations) == set(DECISIONS)
    for slug in DECISIONS:
        path = result.recommendations[slug]
        assert path.exists(), f"{slug} output not written"
        written = pd.read_csv(path)
        assert len(written) == result.row_counts[slug]
        assert result.row_counts[slug] == 2  # both players eligible
    assert result.summary_path.exists()
    assert "GW5" in result.summary_path.read_text()


def test_recommendations_are_ranked_best_first(monkeypatch, tmp_path, mart):
    """The stronger player (higher p_haul / e_points_uncond) is ranked first in each decision."""
    monkeypatch.setattr(recommend, "assemble_forecast", lambda mart, *, n_sims, seed: mart[["player_id", "gw"]].copy())

    result = recommend_from_mart(mart, target_gw=5, output_dir=tmp_path)

    for slug in DECISIONS:
        written = pd.read_csv(result.recommendations[slug])
        assert written.iloc[0]["player_id"] == 1, f"{slug} did not rank the stronger player first"


def test_target_gw_with_no_rows_still_writes_empty_outputs(monkeypatch, tmp_path, mart):
    """A GW absent from the mart raises inside the ranker — the runner does not silently succeed."""
    from serve.input_contracts import IntelligenceInputError

    monkeypatch.setattr(recommend, "assemble_forecast", lambda mart, *, n_sims, seed: mart[["player_id", "gw"]].copy())
    with pytest.raises(IntelligenceInputError, match="no data for gw=99"):
        recommend_from_mart(mart, target_gw=99, output_dir=tmp_path)
