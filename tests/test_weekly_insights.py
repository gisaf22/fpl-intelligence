import pandas as pd
import pytest

from domain.registry.operational import load_registry
from serve.reporting.insight_card_writer import INSIGHT_COLUMNS, build_insight_cards, write_insight_cards
from serve.reporting.reports import (
    build_signal_summary,
    build_stable_performance_signals,
    build_summary_by_layer,
    build_summary_by_position,
)

pytestmark = pytest.mark.unit


def _marts():
    signal_summary = build_signal_summary(load_registry(), gw=36)
    return {
        "signal_summary": signal_summary,
        "summary_by_position": build_summary_by_position(signal_summary),
        "summary_by_layer": build_summary_by_layer(signal_summary),
        "stable_performance_signals": build_stable_performance_signals(signal_summary),
    }


def test_build_insight_cards_creates_guardrail_cards():
    marts = _marts()

    cards = build_insight_cards(**marts)

    assert list(cards.columns) == list(INSIGHT_COLUMNS)
    assert 5 <= len(cards) <= 15
    assert cards["gw"].eq(36).all()
    assert cards["evidence"].str.len().gt(0).all()
    assert cards["caveat"].str.len().gt(0).all()
    assert "DO_NOT_OVERINTERPRET" in set(cards["category"])
    assert "CONTEXT_ONLY" in set(cards["category"])
    assert "MARKET_BEHAVIOR" in set(cards["category"])
    assert "EXPOSURE_NOT_QUALITY" in set(cards["category"])
    assert "BLOCKED_SUPPORT" in set(cards["category"])


def test_insight_cards_do_not_make_player_pick_recommendations():
    cards = build_insight_cards(**_marts())
    text = " ".join(cards[["title", "interpretation", "actionability", "caveat"]].fillna("").to_numpy().ravel()).lower()

    banned_terms = ["captain", "buy ", "sell ", "transfer in", "pick "]
    assert not any(term in text for term in banned_terms)


def test_position_summary_cards_exist_for_each_position():
    cards = build_insight_cards(**_marts())
    position_cards = cards[cards["category"] == "POSITION_SUMMARY"]

    assert set(position_cards["position"]) == {"GK", "DEF", "MID", "FWD"}


def test_write_insight_cards(tmp_path):
    output_path = write_insight_cards(**_marts(), output_dir=tmp_path)

    assert output_path.exists()
    cards = pd.read_csv(output_path)
    assert list(cards.columns) == list(INSIGHT_COLUMNS)
    assert 5 <= len(cards) <= 15
