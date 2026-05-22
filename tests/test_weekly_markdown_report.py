import pandas as pd

from signals.lifecycle import load_registry
from intelligence.reporting.insights import build_insight_cards
from intelligence.reporting.reports import (
    build_signal_summary,
    build_stable_performance_signals,
    build_summary_by_layer,
    build_summary_by_position,
    build_weekly_markdown_report,
    write_weekly_markdown_report,
)


def _marts():
    signal_summary = build_signal_summary(load_registry(), gw=36)
    summary_by_position = build_summary_by_position(signal_summary)
    summary_by_layer = build_summary_by_layer(signal_summary)
    stable_performance_signals = build_stable_performance_signals(signal_summary)
    insight_cards = build_insight_cards(
        signal_summary=signal_summary,
        summary_by_position=summary_by_position,
        summary_by_layer=summary_by_layer,
        stable_performance_signals=stable_performance_signals,
    )
    return {
        "signal_summary": signal_summary,
        "summary_by_position": summary_by_position,
        "summary_by_layer": summary_by_layer,
        "stable_performance_signals": stable_performance_signals,
        "insight_cards": insight_cards,
    }


def test_build_weekly_markdown_report_has_required_sections_and_caveats():
    report = build_weekly_markdown_report(**_marts())

    required_text = [
        "# GW36 Signal Intelligence Report",
        "## Executive Summary",
        "## What Not To Over-Interpret",
        "## Stable Performance Signals",
        "## Exposure Controls",
        "## Context Signals",
        "## Market Behavior Signals",
        "## Blocked And Caveated Signals",
        "## Position Notes",
        "## Caveats",
        "descriptive, not predictive",
        "Stable scoring-adjacent signals are descriptive",
        "Fixture and match-environment signals are context",
    ]
    for text in required_text:
        assert text in report


def test_weekly_markdown_report_contains_concrete_signal_evidence():
    report = build_weekly_markdown_report(**_marts())

    assert "bps.GK" in report or "| GK" in report
    assert "ict_index" in report
    assert "14" in report
    assert "registry_snapshot.csv" in report
    assert "snapshot_changes.csv" in report


def test_write_weekly_markdown_report(tmp_path):
    output_path = write_weekly_markdown_report(**_marts(), output_dir=tmp_path)

    assert output_path.exists()
    assert output_path.name == "weekly_report.md"
    text = output_path.read_text(encoding="utf-8")
    assert "# GW36 Signal Intelligence Report" in text
