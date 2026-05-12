"""Weekly analytical mart builders for governed signal registries."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


SIGNAL_SUMMARY_COLUMNS: tuple[str, ...] = (
    "gw",
    "position",
    "signal",
    "signal_layer",
    "layer_role",
    "downstream_status",
    "feature_candidate_eligible",
    "relationship_geometry",
    "association_class",
    "rho_pooled",
    "within_share",
    "low_confidence",
    "support_flags",
    "support_type",
    "interpretation_caveat",
)

STATUS_ORDER: dict[str, int] = {
    "eligible": 0,
    "caveated": 1,
    "blocked": 2,
}

POSITION_ORDER: dict[str, int] = {
    "GK": 0,
    "DEF": 1,
    "MID": 2,
    "FWD": 3,
}


def build_signal_summary(registry: pd.DataFrame, gw: int) -> pd.DataFrame:
    """Build the row-level weekly signal summary mart."""
    summary = registry.copy()
    summary.insert(0, "gw", gw)
    summary = summary[[column for column in SIGNAL_SUMMARY_COLUMNS if column in summary.columns]]

    summary["_position_order"] = summary["position"].map(POSITION_ORDER).fillna(99)
    summary["_status_order"] = summary["downstream_status"].map(STATUS_ORDER).fillna(99)
    summary = summary.sort_values(
        ["_position_order", "_status_order", "signal_layer", "signal"],
        kind="stable",
    ).drop(columns=["_position_order", "_status_order"])

    return summary.reset_index(drop=True)


def _count_status(group: pd.DataFrame, status: str) -> int:
    return int((group["downstream_status"] == status).sum())


def _count_stable_performance(group: pd.DataFrame) -> int:
    return int(_stable_performance_mask(group).sum())


def _stable_performance_mask(df: pd.DataFrame) -> pd.Series:
    return (
        (df["signal_layer"] == "performance")
        & (df["downstream_status"] == "eligible")
        & (df["association_class"] == "continuous_monotonic")
        & (df["low_confidence"] == False)  # noqa: E712
    )


def build_summary_by_position(signal_summary: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly signal health by position."""
    rows: list[dict[str, object]] = []
    for position, group in signal_summary.groupby("position", sort=False):
        rows.append(
            {
                "gw": int(group["gw"].iloc[0]),
                "position": position,
                "total_signals": int(len(group)),
                "eligible": _count_status(group, "eligible"),
                "caveated": _count_status(group, "caveated"),
                "blocked": _count_status(group, "blocked"),
                "stable_performance_count": _count_stable_performance(group),
            }
        )
    return pd.DataFrame(rows)


def build_summary_by_layer(signal_summary: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly signal health by semantic layer."""
    rows: list[dict[str, object]] = []
    for layer, group in signal_summary.groupby("signal_layer", sort=True):
        rows.append(
            {
                "gw": int(group["gw"].iloc[0]),
                "signal_layer": layer,
                "total_signals": int(len(group)),
                "eligible": _count_status(group, "eligible"),
                "caveated": _count_status(group, "caveated"),
                "blocked": _count_status(group, "blocked"),
                "stable_performance_count": _count_stable_performance(group),
            }
        )
    return pd.DataFrame(rows)


def build_stable_performance_signals(signal_summary: pd.DataFrame) -> pd.DataFrame:
    """Return stable performance candidates for downstream review."""
    stable = signal_summary[_stable_performance_mask(signal_summary)].copy()
    return stable.sort_values(
        ["position", "rho_pooled", "signal"],
        ascending=[True, False, True],
        kind="stable",
    ).reset_index(drop=True)


def write_weekly_report_tables(
    registry: pd.DataFrame,
    gw: int,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write Phase 4 weekly analytical mart CSVs."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    signal_summary = build_signal_summary(registry, gw)
    summary_by_position = build_summary_by_position(signal_summary)
    summary_by_layer = build_summary_by_layer(signal_summary)
    stable_performance = build_stable_performance_signals(signal_summary)

    outputs = {
        "signal_summary": target_dir / "signal_summary.csv",
        "summary_by_position": target_dir / "summary_by_position.csv",
        "summary_by_layer": target_dir / "summary_by_layer.csv",
        "stable_performance_signals": target_dir / "stable_performance_signals.csv",
    }

    signal_summary.to_csv(outputs["signal_summary"], index=False)
    summary_by_position.to_csv(outputs["summary_by_position"], index=False)
    summary_by_layer.to_csv(outputs["summary_by_layer"], index=False)
    stable_performance.to_csv(outputs["stable_performance_signals"], index=False)

    return outputs


def _fmt_signal_position(df: pd.DataFrame, limit: int = 12) -> str:
    """Format signal-position pairs for compact markdown bullets."""
    if df.empty:
        return "none"
    pairs = [f"{row.signal}.{row.position}" for row in df.itertuples()]
    shown = pairs[:limit]
    suffix = f" (+{len(pairs) - limit} more)" if len(pairs) > limit else ""
    return ", ".join(shown) + suffix


def _markdown_table(df: pd.DataFrame, columns: list[str]) -> list[str]:
    """Render a small markdown table without optional dependencies."""
    if df.empty:
        return ["No rows."]

    rows = df[columns].astype(str).values.tolist()
    widths = [
        max(len(str(column)), *(len(row[i]) for row in rows))
        for i, column in enumerate(columns)
    ]
    header = "| " + " | ".join(
        str(column).ljust(widths[i]) for i, column in enumerate(columns)
    ) + " |"
    divider = "| " + " | ".join("-" * widths[i] for i in range(len(columns))) + " |"
    body = [
        "| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(columns))) + " |"
        for row in rows
    ]
    return [header, divider, *body]


def build_weekly_markdown_report(
    signal_summary: pd.DataFrame,
    summary_by_position: pd.DataFrame,
    summary_by_layer: pd.DataFrame,
    stable_performance_signals: pd.DataFrame,
    insight_cards: pd.DataFrame,
) -> str:
    """Render a manager-readable weekly markdown report from generated marts."""
    gw = int(signal_summary["gw"].iloc[0])
    status_counts = signal_summary["downstream_status"].value_counts().to_dict()
    lines: list[str] = [
        f"# GW{gw} Signal Intelligence Report",
        "",
        "This report is descriptive, not predictive. It summarizes governed signal relationships and highlights interpretation guardrails.",
        "",
        "## Executive Summary",
        "",
        f"- Registry rows reviewed: {len(signal_summary)}",
        f"- Eligible rows: {int(status_counts.get('eligible', 0))}",
        f"- Caveated rows: {int(status_counts.get('caveated', 0))}",
        f"- Blocked rows: {int(status_counts.get('blocked', 0))}",
        f"- Stable descriptive performance rows: {len(stable_performance_signals)}",
        f"- Insight guardrail cards: {len(insight_cards)}",
        "",
    ]

    priority_cards = insight_cards[
        insight_cards["category"].isin(
            [
                "DO_NOT_OVERINTERPRET",
                "CONTEXT_ONLY",
                "MARKET_BEHAVIOR",
                "EXPOSURE_NOT_QUALITY",
            ]
        )
    ]
    lines.extend(["## What Not To Over-Interpret", ""])
    for row in priority_cards.itertuples():
        lines.extend(
            [
                f"- **{row.title}**",
                f"  Evidence: {row.evidence}",
                f"  Interpretation: {row.interpretation}",
                f"  Caveat: {row.caveat}",
            ]
        )
    lines.append("")

    lines.extend(["## Stable Performance Signals", ""])
    if stable_performance_signals.empty:
        lines.append("No stable descriptive performance rows were identified.")
    else:
        stable_cols = [
            "position",
            "signal",
            "rho_pooled",
            "within_share",
            "interpretation_caveat",
        ]
        stable_view = stable_performance_signals[stable_cols].copy()
        for col in ["rho_pooled", "within_share"]:
            stable_view[col] = stable_view[col].round(3)
        lines.extend(_markdown_table(stable_view, stable_cols))
    lines.extend(
        [
            "",
            "These rows are stable descriptive anchors. They are not automatically independent predictive features.",
            "",
        ]
    )

    exposure = signal_summary[signal_summary["signal_layer"] == "exposure"]
    context = signal_summary[signal_summary["signal_layer"] == "context"]
    market = signal_summary[signal_summary["signal_layer"] == "market_behavior"]
    blocked = signal_summary[signal_summary["downstream_status"] == "blocked"]
    caveated = signal_summary[signal_summary["downstream_status"] == "caveated"]

    lines.extend(
        [
            "## Exposure Controls",
            "",
            f"- Exposure signals: {_fmt_signal_position(exposure)}",
            "- Interpretation: exposure controls access to point accumulation, not player quality.",
            "",
            "## Context Signals",
            "",
            f"- Context signals: {_fmt_signal_position(context)}",
            "- Interpretation: context should condition analysis rather than rank players directly.",
            "",
            "## Market Behavior Signals",
            "",
            f"- Market signals: {_fmt_signal_position(market)}",
            "- Interpretation: ownership and transfers describe manager behavior, not intrinsic ability.",
            "",
            "## Blocked And Caveated Signals",
            "",
            f"- Blocked rows: {len(blocked)} ({_fmt_signal_position(blocked, limit=10)})",
            f"- Caveated rows: {len(caveated)}",
            "- Interpretation: blocked rows should be excluded from weekly interpretation; caveated rows require explicit context.",
            "",
            "## Position Notes",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            summary_by_position,
            [
                "position",
                "total_signals",
                "eligible",
                "caveated",
                "blocked",
                "stable_performance_count",
            ],
        )
    )

    lines.extend(["", "## Layer Health", ""])
    lines.extend(
        _markdown_table(
            summary_by_layer,
            [
                "signal_layer",
                "total_signals",
                "eligible",
                "caveated",
                "blocked",
                "stable_performance_count",
            ],
        )
    )

    lines.extend(["", "## Caveats", ""])
    for row in insight_cards.itertuples():
        lines.append(f"- {row.category}: {row.caveat}")
    lines.extend(
        [
            "",
            "## Generated Artifacts",
            "",
            "- `registry_snapshot.csv`",
            "- `snapshot_changes.csv`",
            "- `signal_summary.csv`",
            "- `summary_by_position.csv`",
            "- `summary_by_layer.csv`",
            "- `stable_performance_signals.csv`",
            "- `insight_cards.csv`",
            "- `weekly_report.md`",
            "",
        ]
    )
    return "\n".join(lines)


def write_weekly_markdown_report(
    signal_summary: pd.DataFrame,
    summary_by_position: pd.DataFrame,
    summary_by_layer: pd.DataFrame,
    stable_performance_signals: pd.DataFrame,
    insight_cards: pd.DataFrame,
    output_dir: str | Path,
) -> Path:
    """Write the weekly markdown report."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / "weekly_report.md"
    output_path.write_text(
        build_weekly_markdown_report(
            signal_summary=signal_summary,
            summary_by_position=summary_by_position,
            summary_by_layer=summary_by_layer,
            stable_performance_signals=stable_performance_signals,
            insight_cards=insight_cards,
        ),
        encoding="utf-8",
    )
    return output_path
