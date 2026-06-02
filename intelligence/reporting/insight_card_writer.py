"""Structured weekly insight cards generated from analytical marts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

INSIGHT_COLUMNS: tuple[str, ...] = (
    "insight_id",
    "gw",
    "title",
    "category",
    "position",
    "signals",
    "evidence",
    "interpretation",
    "confidence",
    "actionability",
    "caveat",
)

DIRECT_SCORING_SIGNALS: frozenset[str] = frozenset({"bonus", "bps", "goals_scored", "assists", "clean_sheets"})


def _csv(values: list[str]) -> str:
    return ",".join(sorted(dict.fromkeys(values)))


def _card(
    insight_id: str,
    gw: int,
    title: str,
    category: str,
    position: str,
    signals: list[str],
    evidence: str,
    interpretation: str,
    confidence: str,
    actionability: str,
    caveat: str,
) -> dict[str, object]:
    return {
        "insight_id": insight_id,
        "gw": gw,
        "title": title,
        "category": category,
        "position": position,
        "signals": _csv(signals),
        "evidence": evidence,
        "interpretation": interpretation,
        "confidence": confidence,
        "actionability": actionability,
        "caveat": caveat,
    }


def _gw(signal_summary: pd.DataFrame) -> int:
    return int(signal_summary["gw"].iloc[0])


def _status_counts(group: pd.DataFrame) -> dict[str, int]:
    return {
        "eligible": int((group["downstream_status"] == "eligible").sum()),
        "caveated": int((group["downstream_status"] == "caveated").sum()),
        "blocked": int((group["downstream_status"] == "blocked").sum()),
    }


def build_insight_cards(
    signal_summary: pd.DataFrame,
    summary_by_position: pd.DataFrame,
    summary_by_layer: pd.DataFrame,
    stable_performance_signals: pd.DataFrame,
) -> pd.DataFrame:
    """Build deterministic insight cards focused on interpretation guardrails."""
    gw = _gw(signal_summary)
    cards: list[dict[str, object]] = []

    direct = signal_summary[signal_summary["signal"].isin(DIRECT_SCORING_SIGNALS)]
    direct_stable = stable_performance_signals[stable_performance_signals["signal"].isin(DIRECT_SCORING_SIGNALS)]
    if not direct.empty:
        cards.append(
            _card(
                insight_id="DO_NOT_OVERINTERPRET_DIRECT_SCORING",
                gw=gw,
                title="Stable scoring-adjacent signals are descriptive, not independent predictors",
                category="DO_NOT_OVERINTERPRET",
                position="ALL",
                signals=direct["signal"].tolist(),
                evidence=(
                    f"{len(direct_stable)} stable descriptive rows among "
                    f"{len(direct)} scoring-adjacent signal-position rows"
                ),
                interpretation=(
                    "Rows such as bonus, BPS, goals, assists, and clean sheets can "
                    "explain total points because they are close to the scoring system."
                ),
                confidence="high",
                actionability=(
                    "Use these rows to explain where points came from, not as raw independent feature candidates."
                ),
                caveat=(
                    "Predictive use requires lagging or leakage controls because these "
                    "signals are mechanically related to the target."
                ),
            )
        )

    context = signal_summary[signal_summary["signal_layer"] == "context"]
    if not context.empty:
        counts = _status_counts(context)
        cards.append(
            _card(
                insight_id="CONTEXT_ONLY_MATCH_ENVIRONMENT",
                gw=gw,
                title="Fixture and match-environment signals are context, not player quality",
                category="CONTEXT_ONLY",
                position="ALL",
                signals=context["signal"].tolist(),
                evidence=(
                    f"{counts['eligible']} eligible, {counts['caveated']} caveated, "
                    f"{counts['blocked']} blocked context rows"
                ),
                interpretation=("Context signals should condition interpretation rather than rank players directly."),
                confidence="high",
                actionability="Use as segmentation or conditioning axes.",
                caveat=(
                    "Weak or caveated FDR relationships do not mean fixtures are irrelevant; "
                    "they mean direct player-quality interpretation is unsafe."
                ),
            )
        )

    market = signal_summary[signal_summary["signal_layer"] == "market_behavior"]
    if not market.empty:
        counts = _status_counts(market)
        cards.append(
            _card(
                insight_id="MARKET_BEHAVIOR_NOT_ABILITY",
                gw=gw,
                title="Market behavior should not be read as player ability",
                category="MARKET_BEHAVIOR",
                position="ALL",
                signals=market["signal"].tolist(),
                evidence=(
                    f"{counts['eligible']} eligible, {counts['caveated']} caveated, "
                    f"{counts['blocked']} blocked market-behavior rows"
                ),
                interpretation=(
                    "Ownership and transfer signals describe manager behavior and demand, "
                    "not intrinsic player performance."
                ),
                confidence="high",
                actionability="Use for sentiment, demand, or popularity context.",
                caveat=(
                    "Market signals may still be useful, but direct performance inference "
                    "would be an over-interpretation."
                ),
            )
        )

    exposure = signal_summary[signal_summary["signal_layer"] == "exposure"]
    if not exposure.empty:
        counts = _status_counts(exposure)
        cards.append(
            _card(
                insight_id="EXPOSURE_NOT_QUALITY",
                gw=gw,
                title="Minutes and starts measure access to points, not performance quality",
                category="EXPOSURE_NOT_QUALITY",
                position="ALL",
                signals=exposure["signal"].tolist(),
                evidence=(
                    f"{counts['eligible']} eligible, {counts['caveated']} caveated, "
                    f"{counts['blocked']} blocked exposure rows"
                ),
                interpretation=(
                    "Exposure controls whether a player can accumulate points; it does "
                    "not measure how well they perform."
                ),
                confidence="high",
                actionability="Use for filtering, eligibility, and availability context.",
                caveat="Do not use exposure rows as player-quality rankings.",
            )
        )

    low_conf = signal_summary[signal_summary["low_confidence"].astype(bool)]
    if not low_conf.empty:
        cards.append(
            _card(
                insight_id="LOW_CONFIDENCE_DIRECTIONAL_PATTERNS",
                gw=gw,
                title="Low-confidence monotonic rows should stay caveated",
                category="LOW_CONFIDENCE",
                position="ALL",
                signals=low_conf["signal"].tolist(),
                evidence=f"{len(low_conf)} rows have low_confidence=true",
                interpretation=(
                    "These rows retain directional geometry but do not have enough bootstrap stability for promotion."
                ),
                confidence="medium",
                actionability="Review as watchlist signals only.",
                caveat="Do not treat low-confidence monotonicity as a stable signal.",
            )
        )

    blocked = signal_summary[signal_summary["downstream_status"] == "blocked"]
    if not blocked.empty:
        cards.append(
            _card(
                insight_id="BLOCKED_SUPPORT_ROWS",
                gw=gw,
                title="Blocked rows should not be interpreted downstream",
                category="BLOCKED_SUPPORT",
                position="ALL",
                signals=blocked["signal"].tolist(),
                evidence=f"{len(blocked)} rows are blocked by support or geometry rules",
                interpretation=("Blocked rows failed minimum support, degeneracy, or unassessable geometry checks."),
                confidence="high",
                actionability="Exclude from weekly interpretation except as data-quality notes.",
                caveat="A blocked row is not evidence that the underlying football concept is useless.",
            )
        )

    for _, row in summary_by_position.sort_values("position").iterrows():
        position = str(row["position"])
        position_signals = stable_performance_signals[stable_performance_signals["position"] == position][
            "signal"
        ].tolist()
        cards.append(
            _card(
                insight_id=f"POSITION_SUMMARY_{position}",
                gw=int(row["gw"]),
                title=f"{position} signal health summary",
                category="POSITION_SUMMARY",
                position=position,
                signals=position_signals,
                evidence=(
                    f"{int(row['eligible'])} eligible, {int(row['caveated'])} caveated, "
                    f"{int(row['blocked'])} blocked, "
                    f"{int(row['stable_performance_count'])} stable performance rows"
                ),
                interpretation=(
                    "Position-level signal health should guide where analysis is more or less structurally reliable."
                ),
                confidence="medium",
                actionability="Use to prioritize review depth by position.",
                caveat="Position summaries are descriptive and do not rank individual players.",
            )
        )

    layer_counts = summary_by_layer.set_index("signal_layer")
    if "performance" in layer_counts.index:
        perf = layer_counts.loc["performance"]
        cards.append(
            _card(
                insight_id="PERFORMANCE_LAYER_HEALTH",
                gw=gw,
                title="Performance layer contains the main stable descriptive signal spine",
                category="DO_NOT_OVERINTERPRET",
                position="ALL",
                signals=stable_performance_signals["signal"].tolist(),
                evidence=(
                    f"{int(perf['eligible'])} eligible, {int(perf['caveated'])} caveated, "
                    f"{int(perf['blocked'])} blocked performance rows; "
                    f"{int(perf['stable_performance_count'])} stable performance rows"
                ),
                interpretation=(
                    "Stable performance rows are useful descriptive anchors, but they "
                    "are not automatically model-safe independent features."
                ),
                confidence="medium",
                actionability="Use stable rows as governed descriptive anchors.",
                caveat=("Separate descriptive stability from predictive usefulness and target-proximity risk."),
            )
        )

    insight_cards = pd.DataFrame(cards, columns=INSIGHT_COLUMNS)
    return insight_cards.sort_values(["category", "insight_id"], kind="stable").reset_index(drop=True)


def write_insight_cards(
    signal_summary: pd.DataFrame,
    summary_by_position: pd.DataFrame,
    summary_by_layer: pd.DataFrame,
    stable_performance_signals: pd.DataFrame,
    output_dir: str | Path,
) -> Path:
    """Write weekly insight cards CSV."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / "insight_cards.csv"
    build_insight_cards(
        signal_summary=signal_summary,
        summary_by_position=summary_by_position,
        summary_by_layer=summary_by_layer,
        stable_performance_signals=stable_performance_signals,
    ).to_csv(output_path, index=False)
    return output_path
