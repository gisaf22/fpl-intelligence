"""Signal-level weekly intelligence outputs driven by the governed registry.

All observation and note strings are produced from governed template constants.
No free text. No LLM generation. No player-level content.

Output functions:
    build_stable_signal_observations  — one row per (signal, position) for
        core_signal and review_signal promotion classes.
    build_positional_signal_summary   — one row per position with signal-class
        counts derived from promotion_class.
    build_context_condition_notes     — one row per (signal, position) for
        exposure and context layer signals that require conditioning.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Governed vocabularies
# ---------------------------------------------------------------------------

STABLE_PROMOTION_CLASSES: frozenset[str] = frozenset({"core_signal", "review_signal"})

CONTEXT_CONDITION_LAYERS: frozenset[str] = frozenset({"context", "exposure"})

PROMOTION_CLASS_COLUMNS: tuple[str, ...] = (
    "core_signal",
    "review_signal",
    "context_control",
    "exposure_control",
    "market_context",
    "blocked",
)

# ---------------------------------------------------------------------------
# Governed observation templates
# One template per promotion class. No free text outside these constants.
# ---------------------------------------------------------------------------

_STABLE_TEMPLATES: dict[str, str] = {
    "core_signal": (
        "{signal} x {position}: stable continuous-monotonic association "
        "(rho={rho_pooled}). Suitable as a governed descriptive anchor."
    ),
    "review_signal": (
        "{signal} x {position}: association present, under review "
        "(rho={rho_pooled}, temporal stability: {temporal_stability}). "
        "Interpret with caution."
    ),
}

_CONTEXT_NOTE_TEMPLATES: dict[str, str] = {
    "exposure": (
        "{signal} x {position}: exposure control — governs access to point "
        "accumulation, not player quality. Use to filter or condition analysis only."
    ),
    "context": (
        "{signal} x {position}: match-context signal — conditions positional "
        "interpretation. Use as segmentation or conditioning axis only."
    ),
}

# ---------------------------------------------------------------------------
# Output column contracts
# ---------------------------------------------------------------------------

STABLE_OBSERVATION_COLUMNS: tuple[str, ...] = (
    "gw",
    "signal",
    "position",
    "promotion_class",
    "temporal_stability",
    "association_class",
    "rho_pooled",
    "observation",
)

POSITIONAL_SUMMARY_COLUMNS: tuple[str, ...] = (
    "position",
    "core_signal",
    "review_signal",
    "context_control",
    "exposure_control",
    "market_context",
    "blocked",
)

CONTEXT_NOTE_COLUMNS: tuple[str, ...] = (
    "signal",
    "position",
    "signal_layer",
    "association_class",
    "note",
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def build_stable_signal_observations(
    registry: pd.DataFrame,
    gw: int,
) -> pd.DataFrame:
    """Return one row per (signal, position) for core_signal and review_signal rows.

    Observation strings are rendered from governed templates. rho_pooled is
    formatted to 3 decimal places; NaN is rendered as "n/a".

    Args:
        registry: Validated governed registry DataFrame.
        gw:       Current gameweek number.

    Returns:
        DataFrame with columns defined by STABLE_OBSERVATION_COLUMNS.
        Empty if no core_signal or review_signal rows exist.
    """
    stable = registry[
        registry["promotion_class"].isin(STABLE_PROMOTION_CLASSES)
    ].copy()

    rows: list[dict] = []
    for r in stable.to_dict(orient="records"):
        rho_raw = r.get("rho_pooled")
        rho_str = f"{rho_raw:.3f}" if rho_raw is not None and rho_raw == rho_raw else "n/a"
        template = _STABLE_TEMPLATES[str(r["promotion_class"])]
        observation = template.format(
            signal=r["signal"],
            position=r["position"],
            rho_pooled=rho_str,
            temporal_stability=r.get("temporal_stability", "unknown"),
        )
        rows.append(
            {
                "gw": gw,
                "signal": r["signal"],
                "position": r["position"],
                "promotion_class": r["promotion_class"],
                "temporal_stability": r.get("temporal_stability"),
                "association_class": r.get("association_class"),
                "rho_pooled": rho_raw,
                "observation": observation,
            }
        )

    df = pd.DataFrame(rows, columns=list(STABLE_OBSERVATION_COLUMNS))
    return df.sort_values(
        ["promotion_class", "position", "signal"], kind="stable"
    ).reset_index(drop=True)


def build_positional_signal_summary(registry: pd.DataFrame) -> pd.DataFrame:
    """Return one row per position with promotion-class counts.

    Counts blocked rows separately (promotion_class is null for blocked rows).

    Args:
        registry: Validated governed registry DataFrame.

    Returns:
        DataFrame with columns defined by POSITIONAL_SUMMARY_COLUMNS,
        sorted by governed position order (GK, DEF, MID, FWD).
    """
    position_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
    rows: list[dict] = []

    for position, group in registry.groupby("position", sort=False):
        blocked_count = int((group["downstream_status"] == "blocked").sum())
        class_counts = (
            group["promotion_class"]
            .dropna()
            .value_counts()
            .to_dict()
        )
        rows.append(
            {
                "position": position,
                "core_signal": int(class_counts.get("core_signal", 0)),
                "review_signal": int(class_counts.get("review_signal", 0)),
                "context_control": int(class_counts.get("context_control", 0)),
                "exposure_control": int(class_counts.get("exposure_control", 0)),
                "market_context": int(class_counts.get("market_context", 0)),
                "blocked": blocked_count,
            }
        )

    df = pd.DataFrame(rows, columns=list(POSITIONAL_SUMMARY_COLUMNS))
    df["_order"] = df["position"].map(position_order).fillna(99)
    return (
        df.sort_values("_order", kind="stable")
        .drop(columns=["_order"])
        .reset_index(drop=True)
    )


def build_context_condition_notes(registry: pd.DataFrame) -> pd.DataFrame:
    """Return one row per (signal, position) for context and exposure layer signals.

    These signals require conditioning before use. Notes are rendered from
    governed templates keyed on signal_layer.

    Args:
        registry: Validated governed registry DataFrame.

    Returns:
        DataFrame with columns defined by CONTEXT_NOTE_COLUMNS.
        Empty if no context or exposure layer rows exist.
    """
    condition = registry[
        registry["signal_layer"].isin(CONTEXT_CONDITION_LAYERS)
    ].copy()

    rows: list[dict] = []
    for r in condition.to_dict(orient="records"):
        layer = str(r["signal_layer"])
        template = _CONTEXT_NOTE_TEMPLATES.get(layer, "")
        if not template:
            continue
        note = template.format(signal=r["signal"], position=r["position"])
        rows.append(
            {
                "signal": r["signal"],
                "position": r["position"],
                "signal_layer": layer,
                "association_class": r.get("association_class"),
                "note": note,
            }
        )

    df = pd.DataFrame(rows, columns=list(CONTEXT_NOTE_COLUMNS))
    return df.sort_values(
        ["signal_layer", "position", "signal"], kind="stable"
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def write_signal_intelligence(
    registry: pd.DataFrame,
    gw: int,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write all three signal intelligence outputs to CSV.

    Args:
        registry:   Validated governed registry DataFrame.
        gw:         Current gameweek number.
        output_dir: Output directory.

    Returns:
        Dict mapping output name → written Path.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    stable = build_stable_signal_observations(registry, gw)
    positional = build_positional_signal_summary(registry)
    context = build_context_condition_notes(registry)

    paths = {
        "stable_signal_observations": target_dir / "stable_signal_observations.csv",
        "positional_signal_summary": target_dir / "positional_signal_summary.csv",
        "context_condition_notes": target_dir / "context_condition_notes.csv",
    }

    stable.to_csv(paths["stable_signal_observations"], index=False)
    positional.to_csv(paths["positional_signal_summary"], index=False)
    context.to_csv(paths["context_condition_notes"], index=False)

    return paths
