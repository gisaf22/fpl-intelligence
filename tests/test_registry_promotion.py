"""Unit tests for promotion class assignment."""

import pandas as pd
import pytest

from research.registry.promotion import assign_promotion_class
from signals.governance.schema import PROMOTION_CLASS_VALUES
from signals.governance.schema import RESEARCH_REGISTRY_PATH as DEFAULT_REGISTRY_PATH

pytestmark = pytest.mark.unit

# --- integration: counts locked against the governed registry CSV ---


def test_promotion_class_counts_match_governed_registry():
    df = pd.read_csv(DEFAULT_REGISTRY_PATH)
    non_null_counts = df["promotion_class"].dropna().value_counts().to_dict()
    assert non_null_counts == {
        "review_signal": 47,
        "market_context": 13,
        "context_control": 10,
        "core_signal": 8,
        "exposure_control": 2,
    }
    assert df["promotion_class"].isna().sum() == 24  # blocked rows


def test_blocked_rows_have_null_promotion_class_in_registry():
    df = pd.read_csv(DEFAULT_REGISTRY_PATH)
    blocked = df[df["downstream_status"] == "blocked"]
    assert blocked["promotion_class"].isna().all()


def test_core_signals_are_all_eligible_stable_continuous_monotonic():
    df = pd.read_csv(DEFAULT_REGISTRY_PATH)
    core = df[df["promotion_class"] == "core_signal"]
    assert (core["downstream_status"] == "eligible").all()
    assert (core["temporal_stability"] == "stable").all()
    assert (core["association_class"] == "continuous_monotonic").all()


def _row(
    signal_layer: str = "performance",
    downstream_status: str = "eligible",
    temporal_stability: str = "stable",
    association_class: str = "continuous_monotonic",
    signal: str = "bps",
    position: str = "MID",
) -> dict:
    return {
        "signal": signal,
        "position": position,
        "signal_layer": signal_layer,
        "downstream_status": downstream_status,
        "temporal_stability": temporal_stability,
        "association_class": association_class,
    }


# --- vocabulary ---


def test_promotion_class_values_are_complete():
    assert PROMOTION_CLASS_VALUES == {
        "core_signal",
        "review_signal",
        "context_control",
        "exposure_control",
        "market_context",
    }


# --- layer-mapped classes ---


def test_exposure_layer_always_exposure_control():
    assert assign_promotion_class(_row(signal_layer="exposure", downstream_status="caveated")) == "exposure_control"


def test_context_layer_always_context_control():
    assert assign_promotion_class(_row(signal_layer="context", downstream_status="caveated")) == "context_control"


def test_market_behavior_layer_always_market_context():
    result = assign_promotion_class(_row(signal_layer="market_behavior", downstream_status="caveated"))
    assert result == "market_context"


def test_layer_mapping_ignores_downstream_status():
    # context_control even if downstream_status were somehow eligible
    assert assign_promotion_class(_row(signal_layer="context", downstream_status="eligible")) == "context_control"


# --- core_signal ---


def test_eligible_stable_continuous_monotonic_is_core_signal():
    assert (
        assign_promotion_class(
            _row(
                signal_layer="performance",
                downstream_status="eligible",
                temporal_stability="stable",
                association_class="continuous_monotonic",
            )
        )
        == "core_signal"
    )


def test_eligible_but_moderate_shift_is_review_signal():
    assert (
        assign_promotion_class(
            _row(
                downstream_status="eligible",
                temporal_stability="moderate_shift",
                association_class="continuous_monotonic",
            )
        )
        == "review_signal"
    )


def test_eligible_but_insufficient_data_is_review_signal():
    assert (
        assign_promotion_class(
            _row(
                downstream_status="eligible",
                temporal_stability="insufficient_data",
                association_class="continuous_monotonic",
            )
        )
        == "review_signal"
    )


def test_eligible_but_weak_association_is_review_signal():
    assert (
        assign_promotion_class(
            _row(
                downstream_status="eligible",
                temporal_stability="stable",
                association_class="weak_association",
            )
        )
        == "review_signal"
    )


# --- review_signal ---


def test_caveated_performance_is_review_signal():
    assert (
        assign_promotion_class(
            _row(
                signal_layer="performance",
                downstream_status="caveated",
            )
        )
        == "review_signal"
    )


def test_caveated_defensive_context_is_review_signal():
    assert (
        assign_promotion_class(
            _row(
                signal_layer="defensive_context",
                downstream_status="caveated",
            )
        )
        == "review_signal"
    )


def test_caveated_discipline_is_review_signal():
    assert (
        assign_promotion_class(
            _row(
                signal_layer="discipline",
                downstream_status="caveated",
            )
        )
        == "review_signal"
    )


def test_caveated_valuation_is_review_signal():
    assert (
        assign_promotion_class(
            _row(
                signal_layer="valuation",
                downstream_status="caveated",
            )
        )
        == "review_signal"
    )


# --- blocked rows are excluded ---


def test_blocked_row_raises():
    with pytest.raises(ValueError, match="blocked rows are excluded"):
        assign_promotion_class(_row(downstream_status="blocked"))


def test_blocked_row_error_includes_signal_and_position():
    with pytest.raises(ValueError, match=r"bps.*MID"):
        assign_promotion_class(_row(signal="bps", position="MID", downstream_status="blocked"))


# --- output is always a governed value ---


@pytest.mark.parametrize(
    "layer,status,temporal,assoc",
    [
        ("performance", "eligible", "stable", "continuous_monotonic"),
        ("performance", "eligible", "moderate_shift", "continuous_monotonic"),
        ("performance", "caveated", "stable", "weak_association"),
        ("defensive_context", "caveated", "insufficient_data", "weak_association"),
        ("exposure", "caveated", "stable", "weak_association"),
        ("context", "caveated", "insufficient_data", "weak_association"),
        ("market_behavior", "caveated", "stable", "weak_association"),
        ("discipline", "caveated", "stable", "weak_association"),
        ("valuation", "caveated", "stable", "weak_association"),
    ],
)
def test_output_is_always_governed_vocabulary(layer, status, temporal, assoc):
    result = assign_promotion_class(
        _row(
            signal_layer=layer,
            downstream_status=status,
            temporal_stability=temporal,
            association_class=assoc,
        )
    )
    assert result in PROMOTION_CLASS_VALUES
