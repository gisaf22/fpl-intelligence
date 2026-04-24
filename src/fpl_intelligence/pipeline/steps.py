from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, TypedDict

from analysis.dal import player_repo
from fpl_intelligence.config import DGW_DIVERGENCE_WEIGHT, MINUTES_FILTER_LOOKBACK, OVR_TOP_N
from fpl_intelligence.context import GameweekContext
from fpl_intelligence.eligibility import is_player_eligible
from fpl_intelligence.models.briefing import (
    AnalystStatus,
    Briefing,
    BriefingContext,
    BriefingMeta,
    GwType,
    MinutesFilter,
    OvrSignalOutput,
    SignalStatus,
    Signals,
    SignalOutput,
    SignalItem,
    DataCeiling
)
from fpl_intelligence.datasets import FeatureRecord, PlayerFeatures, PlayerMetrics
from fpl_intelligence.models.pipeline import (
    BaseSignalOutputs,
    FeaturesDataset,
    FilteredPool,
    GwContext,
    MetricsDataset,
    RunResult,
    WeightedSignalOutputs,
)

_ELEMENT_TYPE_TO_POSITION = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# FPL points are right-skewed and ownership is power-law distributed.
# Mean-based z-score is distorted by outliers like high-ownership premium assets.
# Uses median as center and MAD scaled by 1.4826 (normal-distribution consistency
# factor) for outlier-resistant standardization.
def robust_zscore(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [0.0] * len(values)
    med = median(values)
    mad = median([abs(v - med) for v in values])
    scaled_mad = mad * 1.4826
    if scaled_mad == 0:
        return [0.0] * len(values)
    return [(v - med) / scaled_mad for v in values]


# -------------------------
# DATA VALIDATION
# -------------------------
# SQL moved to repository layer — computation layer must remain I/O-free
def validate_data_freshness(
    conn: sqlite3.Connection,
    gw: int,
    max_age_hours: int = 6,
) -> None:
    from fpl_intelligence.db import player_repo
    player_repo.validate_data_freshness(conn, gw, max_age_hours)


# -------------------------
# CONTEXT
# -------------------------
def load_gw_context(db_path: Path) -> GwContext:
    # SQL moved to repository layer — computation layer must remain I/O-free
    from fpl_intelligence.db import player_repo
    gw = player_repo.fetch_current_gw(db_path)

    # deadline_time intentionally not sourced from DB — upstream event data is stale
    # this system does not rely on event deadlines for analytical correctness
    deadline_time = None

    return GwContext(
        gw=gw,
        gw_type=GwType.normal,
        double_teams=[],
        blank_teams=[],
        deadline_time=deadline_time,
    )


# -------------------------
# METRICS
# -------------------------
# DGW handling:
# This aggregation assumes player_histories contains one row per fixture.
# SUM(...) correctly aggregates across multiple fixtures in a DGW.
# If ingest provides only one row per player per GW, DGW under-counting
# occurs upstream and is not fixable at the pipeline layer.
# eligibility enforced at feature stage via PlayerFeatures.is_eligible
def compute_metrics_batch(db_path: Path, context: GwContext) -> MetricsDataset:
    gw = context.gw
    lookback = MINUTES_FILTER_LOOKBACK

    # SQL moved to repository layer — computation layer must remain I/O-free
    from fpl_intelligence.db import player_repo
    rows = player_repo.fetch_player_metrics(db_path, gw, lookback)

    records = []
    for eid, name, team, etype, pts, starts, selected in rows:
        records.append(PlayerMetrics(
            entity_id=int(eid),
            entity_name=str(name),
            team_id=int(team),
            position=_ELEMENT_TYPE_TO_POSITION.get(etype),
            points_last_n=float(pts),
            starts_last_n=float(starts),
            selected_count_gw=float(selected or 0),
        ))

    return MetricsDataset(gw=gw, records=records)


# -------------------------
# FEATURES
# -------------------------
def compute_features_batch(
    metrics: MetricsDataset,
    context: GwContext,
    gw_contexts: dict[int, GameweekContext],
) -> FeaturesDataset:
    records = metrics.records

    # NOTE: start_rate is an exposure-normalized rate over the fixed lookback window
    # (starts / window_length), not a participation-conditional rate. Denominator is
    # always MINUTES_FILTER_LOOKBACK regardless of games played.
    # TODO: this is really a lookback window, not a filter, rename?
    start_rates = [r.starts_last_n / MINUTES_FILTER_LOOKBACK for r in records]

    returns = {}
    for pos in {r.position for r in records if r.position}:
        # TODO: cleaner and faster?
        # arr = np.array([r.points_last_n for r in group])
        # z = (arr - arr.mean()) / arr.std(ddof=0)
        group = [r for r in records if r.position == pos]
        scores = robust_zscore([r.points_last_n for r in group])
        for r, z in zip(group, scores):
            returns[r.entity_id] = z

    # Both signals share the same positional reference population so that
    # mispricing_score reflects positional undervaluation, not global market
    # divergence. This is a one-off semantic correction specific to ownership_z
    # alignment — do not treat as an approved pattern for other normalizations.
    ownership = {}
    for pos in {r.position for r in records if r.position}:
        group = [r for r in records if r.position == pos]
        scores = robust_zscore([r.selected_count_gw for r in group])
        for r, z in zip(group, scores):
            ownership[r.entity_id] = z

    # Minimum starts in the lookback window for eligibility.
    # Derived from the rotation threshold used in apply_minutes_filter (0.40):
    #   starts_last_n / MINUTES_FILTER_LOOKBACK >= 0.40
    #   ⟺ starts_last_n >= math.ceil(0.40 * MINUTES_FILTER_LOOKBACK)  (= 3 for lookback=6)
    _min_starts: int = math.ceil(0.40 * MINUTES_FILTER_LOOKBACK)

    enriched = []
    for rec, sr in zip(records, start_rates):
        eid = rec.entity_id

        if eid not in gw_contexts:
            raise RuntimeError(f"Missing GameweekContext for player_id={eid}")
        ctx = gw_contexts[eid]

        player_dict = {"minutes_lookback": rec.starts_last_n}
        eligibility_new = is_player_eligible(player_dict, ctx, _min_starts)

        # Validation: assert new centralized eligibility matches pre-refactor inline logic
        # for all non-BGW players (the only population where the two must agree).
        # KNOWN DIVERGENCE: BGW players — old code had no is_bgw gate so a BGW player
        # with high start_rate would have been eligible. New code always returns False
        # for is_bgw=True. This is the documented conflict from the audit; skip assertion
        # for BGW players.
        if not ctx.is_bgw:
            eligibility_old = sr >= 0.40
            if eligibility_old != eligibility_new:
                raise RuntimeError(
                    f"Eligibility mismatch for player_id={eid}: "
                    f"old={eligibility_old} new={eligibility_new} "
                    f"(start_rate={sr:.4f}, starts_last_n={rec.starts_last_n}, "
                    f"min_starts={_min_starts})"
                )

        enriched.append(PlayerFeatures(
            entity_id=rec.entity_id,
            entity_name=rec.entity_name,
            team_id=rec.team_id,
            position=rec.position,
            points_last_n=rec.points_last_n,
            starts_last_n=rec.starts_last_n,
            selected_count_gw=rec.selected_count_gw,
            start_rate=sr,
            returns_z=returns.get(eid, 0.0),
            ownership_z=ownership.get(eid, 0.0),
            mispricing_score=returns.get(eid, 0.0) - ownership.get(eid, 0.0),
            is_eligible=eligibility_new,
        ))

    assert len(enriched) == len({f.entity_id for f in enriched})

    return FeaturesDataset(gw=metrics.gw, records=enriched)


# -------------------------
# FILTER
# -------------------------
# TODO: why bucket? 0.74 is same as 0.4, big gap, any models or viz using buckets?
def apply_minutes_filter(features: FeaturesDataset, context: GwContext) -> FilteredPool:
    nailed, rotation, doubt = [], [], []

    for r in features.records:
        eid = r.entity_id
        if r.start_rate >= 0.75:
            nailed.append(eid)
        elif r.start_rate >= 0.40:
            rotation.append(eid)
        else:
            doubt.append(eid)

    return FilteredPool(
        gw=context.gw,
        nailed=nailed,
        rotation=rotation,
        doubt=doubt,
    )


# -------------------------
# SIGNALS
# -------------------------

class _SignalItemDict(TypedDict):
    entity_id: int
    entity_name: str
    team_id: int | None
    position: str | None
    value: float
    components: FeatureRecord
    context_flags: dict[str, bool]


# reads: FeatureRecord (static contract) — do not access undeclared attributes
def compute_signals_base(
    features: list[FeatureRecord],
    pool: FilteredPool,
    context: GwContext,
    gw_contexts: dict[int, GameweekContext],
) -> BaseSignalOutputs:
    all_items: list[_SignalItemDict] = []

    for r in features:
        if not r.is_eligible:
            continue

        value = r.mispricing_score
        if r.entity_id not in gw_contexts:
            raise RuntimeError(f"Missing GameweekContext for player_id={r.entity_id}")
        ctx = gw_contexts[r.entity_id]

        # direction is not set here; it is derived from the final post-weighted
        # value in assemble_briefing so DGW adjustments are reflected correctly.
        all_items.append({
            "entity_id": r.entity_id,
            "entity_name": r.entity_name,
            "team_id": ctx.team_id,
            "position": r.position,
            "value": value,
            "components": r,
            "context_flags": {
                "is_double_team": ctx.is_dgw,   # removed: was hardcoded, now derived from DB
                "is_blank_team": ctx.is_bgw,    # removed: was hardcoded, now derived from DB
                "context_weight_applied": False,
            }
        })

    # Lists are not sliced to OVR_TOP_N here; truncation happens in
    # apply_context_weighting after DGW weighting so players are ranked on
    # their final values before truncation. Pre-weighting lists may therefore
    # exceed OVR_TOP_N in size — this is expected and intentional.
    undervalued = sorted(
        [i for i in all_items if i["value"] > 0],
        key=lambda x: x["value"],
        reverse=True,
    )

    overvalued = sorted(
        [i for i in all_items if i["value"] <= 0],
        key=lambda x: x["value"],
    )

    return BaseSignalOutputs(
        gw=context.gw,
        signals={
            "minutes_filter": {
                "nailed_count": len(pool.nailed),
                "rotation_count": len(pool.rotation),
                "doubt_count": len(pool.doubt),
                "status": SignalStatus.complete,
            },
            "ownership_vs_returns": {
                "status": SignalStatus.complete,
                "undervalued": undervalued,
                "overvalued": overvalued,
            }
        }
    )


# -------------------------
# CONTEXT WEIGHTING
# -------------------------
# TODO: unify context weighting logic into shared post-signal policy layer (DGW/BGW/blank weeks),
# currently duplicated across signal builders as ad-hoc transformations
def apply_context_weighting(
    base_outputs: BaseSignalOutputs,
    context: GwContext,
    gw_contexts: dict[int, GameweekContext],
) -> WeightedSignalOutputs:
    signals = dict(base_outputs.signals)

    if "ownership_vs_returns" in signals:
        ovr = dict(signals["ownership_vs_returns"])

        # TODO: why inner function
        def _scale_item(item: _SignalItemDict) -> _SignalItemDict:
            ctx = gw_contexts[item["entity_id"]]
            if ctx.is_dgw:  # removed: was hardcoded, now derived from DB
                scaled = dict(item)
                scaled["value"] = item["value"] * DGW_DIVERGENCE_WEIGHT
                scaled["context_flags"] = {
                    **item["context_flags"],
                    "context_weight_applied": True,
                }
                return scaled
            return item

        # Sort is stable: equal post-weighting values preserve pre-weighting order.
        # Truncate to OVR_TOP_N after sorting so DGW-boosted players are ranked
        # on their final values before the list is capped.
        undervalued = [_scale_item(i) for i in ovr["undervalued"]]
        undervalued.sort(key=lambda x: x["value"], reverse=True)
        undervalued = undervalued[:OVR_TOP_N]

        overvalued = [_scale_item(i) for i in ovr["overvalued"]]
        overvalued.sort(key=lambda x: x["value"])
        overvalued = overvalued[:OVR_TOP_N]

        ovr["undervalued"] = undervalued
        ovr["overvalued"] = overvalued
        signals["ownership_vs_returns"] = ovr

    return WeightedSignalOutputs(
        gw=context.gw,
        signals=signals,
    )


# -------------------------
# BRIEFING
# -------------------------
# TODO: remove defensive coercions by enforcing strict signal schema upstream,
# current mapping layer compensates for inconsistent dict structure in WeightedSignalOutputs
def assemble_briefing(
    context: GwContext,
    weighted_outputs: WeightedSignalOutputs,
) -> Briefing:

    minutes = weighted_outputs.signals["minutes_filter"]

    ownership = weighted_outputs.signals["ownership_vs_returns"]

    def _build_signal_items(raw_items: list) -> list[SignalItem]:
        result = []
        for r in raw_items:
            result.append(
                SignalItem(
                    entity_id=r["entity_id"],
                    entity_name=r["entity_name"],
                    team_id=int(r["team_id"]),
                    position=r["position"],
                    value=r["value"],
                    components={
                        "returns_z": float(r["components"].returns_z),
                        "ownership_z": float(r["components"].ownership_z),
                    },
                    context_flags=r["context_flags"],
                    data_ceiling=DataCeiling.outcome_only,
                    # Derived from the final post-weighted value so DGW adjustments
                    # are reflected in the direction label.
                    direction="undervalued" if r["value"] > 0 else "overvalued",
                )
            )
        return result

    signals = Signals(
        minutes_filter=MinutesFilter(
            nailed_count=minutes["nailed_count"],
            rotation_count=minutes["rotation_count"],
            doubt_count=minutes["doubt_count"],
            status=SignalStatus.complete,
        ),
        ownership_vs_returns=OvrSignalOutput(
            status=SignalStatus.complete,
            undervalued=_build_signal_items(ownership["undervalued"]),
            overvalued=_build_signal_items(ownership["overvalued"]),
        ),
    )

    return Briefing(
        meta=BriefingMeta(
            gw=context.gw,
            generated_at=datetime.now(timezone.utc),
            schema_version="1.0",
            config_version="1.0",
            prompt_version="1.0",
            data_sources=["fpl-ingest"],
            analyst_status=AnalystStatus.complete,
        ),
        context=BriefingContext(**context.model_dump()),
        signals=signals,
    )


# -------------------------
# EDITORIAL STUB
# -------------------------

def generate_editorial_brief(
    briefing: Briefing,
    output_path: Path,
) -> Path:
    raise NotImplementedError


# -------------------------
# LOGGING
# -------------------------

def log_run(context: GwContext, result: RunResult, log_path: Path) -> None:
    raise NotImplementedError