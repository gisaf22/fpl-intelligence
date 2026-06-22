"""Compute registry relationship sections from prepared analytical data.

Mode: diagnostic · Stage: explore · Status: framework helper (no standalone verdict)
Population: registry relationship sections over prepared analytical data.
Not a §4 audit row — supports the explore-stage registry build.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.kernels.descriptive.binning import (
    BLOCK_ORDER,
    MATCH_LEVEL_SIGNALS,
    POSITIONS,
    bin_analysis,
    select_bucketing_scheme,
)
from research.kernels.diagnostic.panel import split_between_within_player_rho
from research.kernels.diagnostic.shape import (
    MONO_CONF_HIGH,
    MONO_CONF_LOW,
    MONOTONIC_GEOMETRIES,
    classify_geometry,
)
from research.kernels.diagnostic.stability import stability_classify
from research.kernels.diagnostic.tail import measure_tail_event_dependence
from research.kernels.inferential.monotonicity import monotonicity_confidence


def _require_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    frame_name: str,
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{frame_name} missing required columns: {missing}")


@dataclass(frozen=True)
class SectionBuildConfig:
    """Column and iteration settings for relationship-section computation."""

    target_column: str = "total_points"
    position_column: str = "position"
    player_column: str = "player_id"
    block_column: str = "gw_block"
    positions: tuple[str, ...] = tuple(POSITIONS)
    population_scope: str = "primary"
    population_robustness: str = "untested"
    default_preferred_population: str = "both"
    n_bootstrap: int = 200


@dataclass(frozen=True)
class RelationshipSections:
    """Computed section outputs consumed by registry assembly."""

    geometry: pd.DataFrame
    stability: pd.DataFrame
    decomposition: pd.DataFrame
    haul: pd.DataFrame


def _preferred_population_lookup(
    signal_metadata: pd.DataFrame | None,
) -> dict[tuple[str, str], str]:
    if signal_metadata is None or signal_metadata.empty:
        return {}

    required = {"signal", "position", "preferred_population"}
    missing = sorted(required - set(signal_metadata.columns))
    if missing:
        raise ValueError(f"signal metadata missing required columns: {missing}")

    duplicates = int(signal_metadata[["signal", "position"]].duplicated().sum())
    if duplicates:
        raise ValueError(f"signal metadata has {duplicates} duplicate signal-position keys")

    return {
        (str(row["signal"]), str(row["position"])): str(row["preferred_population"])
        for row in signal_metadata.to_dict(orient="records")
    }


def _support_type_for_failure(signal: str, flag: str) -> str:
    if "insufficient_support:insufficient_n" in flag:
        return "insufficient_n"
    if "insufficient_support:bin_density" in flag and signal.startswith("fdr_"):
        return "ordinal_scheme_mismatch"
    if flag == "degenerate":
        return "near_constant_position"
    return ""


def _q_gap(bin_stats: pd.DataFrame, geometry: str) -> float:
    if geometry not in MONOTONIC_GEOMETRIES:
        return np.nan
    occupied = bin_stats[bin_stats["count"] > 0]
    if len(occupied) < 2:
        return np.nan
    return round(float(occupied["mean"].iloc[-1] - occupied["mean"].iloc[0]), 3)


def _effective_n_per_bin(bin_stats: pd.DataFrame) -> float:
    occupied = bin_stats[bin_stats["count"] > 0]
    if occupied.empty:
        return np.nan
    return round(float(occupied["count"].mean()), 1)


def _geometry_row(
    data: pd.DataFrame,
    signal: str,
    position: str,
    config: SectionBuildConfig,
    preferred_population: str,
) -> dict[str, object]:
    subset = data[data[config.position_column] == position][[signal, config.target_column]].dropna()
    n_records = len(subset)
    zero_fraction = round(float((subset[signal].astype(float) == 0).mean()), 3) if n_records else np.nan

    base = {
        "signal": signal,
        "position": position,
        "population_scope": config.population_scope,
        "population_robustness": config.population_robustness,
        "variable_level": "match_level" if signal in MATCH_LEVEL_SIGNALS else "player_level",
        "preferred_population": preferred_population,
        "n_records": n_records,
        "zero_fraction": zero_fraction,
    }

    scheme = select_bucketing_scheme(subset[signal], signal_name=signal)
    scheme_type, _ = scheme
    if scheme_type == "insufficient":
        return {
            **base,
            "bucketing_scheme": scheme_type,
            "active_bin_count": 0,
            "effective_n_per_bin": np.nan,
            "q1_q5_mean_gap": np.nan,
            "relationship_geometry": "unassessable",
            "monotonicity_confidence": np.nan,
            "low_confidence": False,
            "support_flags": "insufficient_support:insufficient_n",
            "support_type": "insufficient_n",
        }

    work = data.rename(columns={config.position_column: "position"})
    bin_stats, flag = bin_analysis(
        work,
        signal=signal,
        target=config.target_column,
        position=position,
        scheme=scheme,
    )
    if bin_stats is None:
        relationship_geometry = "unassessable" if flag.startswith("insufficient_support") else "indeterminate"
        return {
            **base,
            "bucketing_scheme": scheme_type,
            "active_bin_count": 0,
            "effective_n_per_bin": np.nan,
            "q1_q5_mean_gap": np.nan,
            "relationship_geometry": relationship_geometry,
            "monotonicity_confidence": np.nan,
            "low_confidence": False,
            "support_flags": flag,
            "support_type": _support_type_for_failure(signal, flag),
        }

    active_bin_count = int((bin_stats["count"] > 0).sum())
    relationship_geometry = "unassessable" if flag.startswith("insufficient_support") else classify_geometry(bin_stats)
    q1_q5_mean_gap = _q_gap(bin_stats, relationship_geometry)
    mono_confidence = np.nan
    if relationship_geometry in MONOTONIC_GEOMETRIES:
        mono_confidence = monotonicity_confidence(
            work,
            signal=signal,
            target=config.target_column,
            position=position,
            original_bin_stats=bin_stats,
            scheme=scheme,
            n_bootstrap=config.n_bootstrap,
        )
        if pd.notna(mono_confidence) and mono_confidence < MONO_CONF_LOW:
            relationship_geometry = "indeterminate"
            q1_q5_mean_gap = np.nan
            mono_confidence = np.nan

    return {
        **base,
        "bucketing_scheme": scheme_type,
        "active_bin_count": active_bin_count,
        "effective_n_per_bin": _effective_n_per_bin(bin_stats),
        "q1_q5_mean_gap": q1_q5_mean_gap,
        "relationship_geometry": relationship_geometry,
        "monotonicity_confidence": mono_confidence,
        "low_confidence": bool(pd.notna(mono_confidence) and mono_confidence < MONO_CONF_HIGH),
        "support_flags": flag,
        "support_type": _support_type_for_failure(signal, flag),
    }


def _stability_row(
    data: pd.DataFrame,
    signal: str,
    position: str,
    geometry_row: dict[str, object],
    config: SectionBuildConfig,
) -> dict[str, object]:
    if geometry_row["relationship_geometry"] == "unassessable":
        stability = "unassessable"
    elif config.block_column not in data.columns:
        stability = "insufficient_data"
    else:
        work = data.rename(columns={config.position_column: "position"})
        scheme = select_bucketing_scheme(
            work.loc[work["position"].eq(position), signal],
            signal_name=signal,
        )
        block_gaps: dict[str, float | None] = {}
        for block in BLOCK_ORDER:
            block_data = work[work[config.block_column].eq(block)]
            block_stats, _ = bin_analysis(
                block_data,
                signal=signal,
                target=config.target_column,
                position=position,
                scheme=scheme,
            )
            if block_stats is None:
                block_gaps[block] = None
                continue
            block_geometry = classify_geometry(block_stats)
            block_gaps[block] = _q_gap(block_stats, block_geometry)

        pooled_gap = float(geometry_row["q1_q5_mean_gap"])  # type: ignore[arg-type]
        stability = stability_classify(pooled_gap, block_gaps)

    return {
        "signal": signal,
        "position": position,
        "temporal_stability": stability,
    }


def compute_relationship_sections(
    data: pd.DataFrame,
    signals: Iterable[str],
    config: SectionBuildConfig | None = None,
    signal_metadata: pd.DataFrame | None = None,
) -> RelationshipSections:
    """Compute all relationship sections for configured signal-position pairs."""
    cfg = config or SectionBuildConfig()
    signal_list = tuple(dict.fromkeys(signals))
    _require_columns(
        data,
        (
            cfg.target_column,
            cfg.position_column,
            cfg.player_column,
            *signal_list,
        ),
        "prepared data",
    )
    preferred_lookup = _preferred_population_lookup(signal_metadata)

    geometry_rows: list[dict[str, object]] = []
    stability_rows: list[dict[str, object]] = []
    decomposition_rows: list[dict[str, object]] = []
    haul_rows: list[dict[str, object]] = []

    work = data.rename(columns={cfg.position_column: "position"})
    for signal in signal_list:
        for position in cfg.positions:
            preferred_population = preferred_lookup.get(
                (signal, position),
                cfg.default_preferred_population,
            )
            geom_row = _geometry_row(
                data=data,
                signal=signal,
                position=position,
                config=cfg,
                preferred_population=preferred_population,
            )
            geometry_rows.append(geom_row)
            stability_rows.append(
                _stability_row(
                    data=data,
                    signal=signal,
                    position=position,
                    geometry_row=geom_row,
                    config=cfg,
                )
            )

            decomp = split_between_within_player_rho(
                work,
                signal=signal,
                target=cfg.target_column,
                position=position,
                player_col=cfg.player_column,
            )
            decomposition_rows.append({"signal": signal, "position": position, **decomp})

            haul = measure_tail_event_dependence(
                work,
                signal=signal,
                target=cfg.target_column,
                position=position,
            )
            haul_rows.append({"signal": signal, "position": position, **haul})

    return RelationshipSections(
        geometry=pd.DataFrame(geometry_rows),
        stability=pd.DataFrame(stability_rows),
        decomposition=pd.DataFrame(decomposition_rows),
        haul=pd.DataFrame(haul_rows),
    )
