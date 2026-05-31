import pandas as pd

from intelligence.reporting.reports import (
    build_signal_summary,
    build_stable_performance_signals,
    build_summary_by_layer,
    build_summary_by_position,
    write_weekly_report_tables,
)
from signals.governance import load_registry


def test_signal_summary_is_compact_weekly_mart():
    registry = load_registry()

    summary = build_signal_summary(registry, gw=36)

    assert len(summary) == 104
    assert summary["gw"].eq(36).all()
    assert "n_records" not in summary.columns
    assert {
        "gw",
        "position",
        "signal",
        "signal_layer",
        "downstream_status",
        "relationship_geometry",
        "association_class",
        "interpretation_caveat",
    }.issubset(summary.columns)


def test_summary_by_position_matches_status_counts():
    summary = build_signal_summary(load_registry(), gw=36)

    by_position = build_summary_by_position(summary)

    assert set(by_position["position"]) == {"GK", "DEF", "MID", "FWD"}
    assert int(by_position["total_signals"].sum()) == 104
    assert int(by_position["eligible"].sum()) == 9
    assert int(by_position["caveated"].sum()) == 71
    assert int(by_position["blocked"].sum()) == 24


def test_summary_by_layer_matches_status_counts():
    summary = build_signal_summary(load_registry(), gw=36)

    by_layer = build_summary_by_layer(summary)

    assert int(by_layer["total_signals"].sum()) == 104
    assert int(by_layer["eligible"].sum()) == 9
    assert int(by_layer["caveated"].sum()) == 71
    assert int(by_layer["blocked"].sum()) == 24


def test_stable_performance_signals_follow_v1_rule():
    summary = build_signal_summary(load_registry(), gw=36)

    stable = build_stable_performance_signals(summary)

    assert len(stable) == 9
    assert stable["signal_layer"].eq("performance").all()
    assert stable["downstream_status"].eq("eligible").all()
    assert stable["association_class"].eq("continuous_monotonic").all()
    assert stable["low_confidence"].eq(False).all()


def test_write_weekly_report_tables(tmp_path):
    outputs = write_weekly_report_tables(load_registry(), gw=36, output_dir=tmp_path)

    assert set(outputs) == {
        "signal_summary",
        "summary_by_position",
        "summary_by_layer",
        "stable_performance_signals",
    }
    for path in outputs.values():
        assert path.exists()

    signal_summary = pd.read_csv(outputs["signal_summary"])
    stable = pd.read_csv(outputs["stable_performance_signals"])
    assert len(signal_summary) == 104
    assert len(stable) == 9

