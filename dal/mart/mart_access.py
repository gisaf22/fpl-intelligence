"""Mart access interface — single-call entry point for analytics consumers.

get_analytics_dataset() is the canonical replacement for the deleted dal.access module.
Callers do not need to know the internal layer sequence (staging → intermediate → fct → feat → mart).

Callers that want the persisted artifact (after a pipeline run) should use dal.pipeline.load().
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dal.config import DB_PATH
from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.feat.feat_player_gameweek import build_player_gameweek_state
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.mart.mart_analytical import GOVERNED_SIGNAL_COLUMNS, build_prepared_dataset
from dal.staging import load_staged_entities


@dataclass(frozen=True)
class MartResult:
    """Typed result returned by get_analytics_dataset().

    mart            : full analytical dataset at (player_id, gw) grain
    signals         : governed signal columns present in mart (keyed from FEATURE_REGISTRY)
    gw_range        : (min_gw, max_gw) inclusive bounds present in mart
    data_cutoff_gw  : GW at which the mart was cut off (rows with gw > cutoff are excluded)
    """

    mart: pd.DataFrame
    signals: tuple[str, ...]
    gw_range: tuple[int, int]
    data_cutoff_gw: int


def get_analytics_dataset(
    db_path: Path = DB_PATH,
    data_cutoff_gw: int | None = None,
) -> MartResult:
    """Run the full pipeline and return the governed analytical dataset.

    This is the canonical consumer interface — the single-call replacement for the
    deleted dal.access.get_state_features(). Callers import from dal directly.

    db_path         : path to the FPL SQLite database (defaults to FPL_DB_PATH env var)
    data_cutoff_gw  : if None, defaults to the max GW present in the FCT spine
    """
    staged = load_staged_entities(db_path)
    player_fixture = get_player_fixture_base(staged)
    spine = build_player_gameweek_spine(player_fixture, staged.events)
    features = build_player_gameweek_state(spine)
    cutoff = data_cutoff_gw if data_cutoff_gw is not None else int(spine["gw"].max())
    mart = build_prepared_dataset(features, cutoff)
    return MartResult(
        mart=mart,
        signals=GOVERNED_SIGNAL_COLUMNS,
        gw_range=(int(mart["gw"].min()), int(mart["gw"].max())),
        data_cutoff_gw=cutoff,
    )
