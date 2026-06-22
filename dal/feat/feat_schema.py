"""Feature layer schema contract — Pandera schema and feature registry.

FEAT_SCHEMA: machine-readable column contract for all governed feature columns.
  strict=False because feat output includes spine columns too; Pandera validates the
  feature subset only.

FEATURE_REGISTRY: single source of truth for every governed output column.
  Carries gate approval, scope, causality, warmup, min_obs, and allowed values.
  Replaces _COLUMN_META (deleted) and _GOVERNED_ROLLING_COLS (derived from this).
  feat_contracts.STATE_COL_CONTRACTS is also derived from this registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandera.pandas as pa

# pa.DataFrameSchema — not pa.DataFrameModel — to avoid inner class Config pattern.
FEAT_SCHEMA = pa.DataFrameSchema(
    columns={
        "player_id": pa.Column(int, nullable=False),
        "gw": pa.Column(int, nullable=False),
        "xgi_roll3": pa.Column(float, nullable=True),
        "xgi_roll5": pa.Column(float, nullable=True),
        "xgc_roll3": pa.Column(float, nullable=True),
        "xgc_roll5": pa.Column(float, nullable=True),
        "clean_sheets_roll3": pa.Column(float, nullable=True),
        "clean_sheets_roll5": pa.Column(float, nullable=True),
        "goals_conceded_roll3": pa.Column(float, nullable=True),
        "goals_conceded_roll5": pa.Column(float, nullable=True),
        "minutes_roll3": pa.Column(float, nullable=True),
        "minutes_roll5": pa.Column(float, nullable=True),
        "minutes_roll8": pa.Column(float, nullable=True),
        "minutes_trend": pa.Column(str, nullable=True),
        "fixture_context": pa.Column(str, pa.Check.isin(["BGW", "SGW", "DGW"])),
        "is_warmup_gw": pa.Column(bool, nullable=False),
    },
    strict=False,
)


@dataclass
class FeatureRecord:
    gate: str  # lens study gate that approved this column
    scope: str  # Individual | Team | Match
    positions: list[str]  # FPL positions for which this column is approved
    status: str  # APPROVED | CONDITIONAL
    causality: str  # lagged | contemporaneous
    note: str = field(default="")
    warmup_gws: int | None = field(default=None)  # first GW where column is non-null
    min_obs: int | None = field(default=None)  # window size at which rolling avg is reliable
    null_if_no_obs: bool | None = field(default=None)
    values: list[str] | None = field(default=None)  # allowed values for categorical columns


# Single source of truth for every governed output column.
# Adding a column requires: an entry here, a column in FEAT_SCHEMA, and a governance record.
FEATURE_REGISTRY: dict[str, FeatureRecord] = {
    "xgi_roll3": FeatureRecord(
        gate="LENS-FORM FORM-001",
        scope="Individual",
        positions=["DEF", "MID"],
        status="APPROVED",
        causality="lagged",
        warmup_gws=1,
        min_obs=3,
        null_if_no_obs=True,
        note="CONDITIONAL at FWD — haul concentration suppresses Q5-Q1 gap",
    ),
    "xgi_roll5": FeatureRecord(
        gate="LENS-FORM FORM-002",
        scope="Individual",
        positions=["DEF", "MID"],
        status="APPROVED",
        causality="lagged",
        warmup_gws=1,
        min_obs=5,
        null_if_no_obs=True,
        note="CONDITIONAL at FWD — same haul concentration caveat as roll3",
    ),
    "xgc_roll3": FeatureRecord(
        gate="G-EDA8-05",
        scope="Team",
        positions=["DEF", "GK"],
        status="CONDITIONAL",
        causality="lagged",
        warmup_gws=1,
        min_obs=3,
        null_if_no_obs=True,
        note="Candidate pending lens study; xgc redundancy with goals_conceded resolved",
    ),
    "xgc_roll5": FeatureRecord(
        gate="G-EDA8-05",
        scope="Team",
        positions=["DEF", "GK"],
        status="CONDITIONAL",
        causality="lagged",
        warmup_gws=1,
        min_obs=5,
        null_if_no_obs=True,
        note="Same basis as xgc_roll3",
    ),
    "clean_sheets_roll3": FeatureRecord(
        gate="G-EDA8-05",
        scope="Team",
        positions=["DEF", "GK"],
        status="CONDITIONAL",
        causality="lagged",
        warmup_gws=1,
        min_obs=3,
        null_if_no_obs=True,
        note="Surviving defensive signal after xgc redundancy resolution",
    ),
    "clean_sheets_roll5": FeatureRecord(
        gate="G-EDA8-05",
        scope="Team",
        positions=["DEF", "GK"],
        status="CONDITIONAL",
        causality="lagged",
        warmup_gws=1,
        min_obs=5,
        null_if_no_obs=True,
        note="Same status as clean_sheets_roll3",
    ),
    "goals_conceded_roll3": FeatureRecord(
        gate="G-EDA5",
        scope="Team",
        positions=["DEF", "GK"],
        status="CONDITIONAL",
        causality="lagged",
        warmup_gws=1,
        min_obs=3,
        null_if_no_obs=True,
        note="Moderate seasonal drift risk at MID",
    ),
    "goals_conceded_roll5": FeatureRecord(
        gate="G-EDA5",
        scope="Team",
        positions=["DEF", "GK"],
        status="CONDITIONAL",
        causality="lagged",
        warmup_gws=1,
        min_obs=5,
        null_if_no_obs=True,
        note="Same status as goals_conceded_roll3",
    ),
    "minutes_roll3": FeatureRecord(
        gate="LENS-AVAIL AVAIL-001",
        scope="Individual",
        positions=["MID"],
        status="APPROVED",
        causality="lagged",
        warmup_gws=1,
        min_obs=3,
        null_if_no_obs=True,
        note="Availability signal only — blocked as form proxy (G-EDA2-02)",
    ),
    "minutes_roll5": FeatureRecord(
        gate="LENS-AVAIL AVAIL-002",
        scope="Individual",
        positions=["MID"],
        status="APPROVED",
        causality="lagged",
        warmup_gws=1,
        min_obs=5,
        null_if_no_obs=True,
        note="Availability signal only; unstable at FWD (1/3 blocks)",
    ),
    "minutes_roll8": FeatureRecord(
        gate="LENS-AVAIL AVAIL-003",
        scope="Individual",
        positions=["DEF", "MID"],
        status="APPROVED",
        causality="lagged",
        warmup_gws=1,
        min_obs=8,
        null_if_no_obs=True,
        note="Strongest availability window; uninformative at FWD and GK",
    ),
    "minutes_trend": FeatureRecord(
        gate="G-EDA2-02",
        scope="Individual",
        positions=["DEF", "MID", "FWD", "GK"],
        status="CONDITIONAL",
        causality="lagged",
        warmup_gws=4,
        min_obs=6,
        null_if_no_obs=True,
        note="Availability domain only; 30-min threshold PROVISIONAL-EDITORIAL (STATE-T-01)",
    ),
    "fixture_context": FeatureRecord(
        gate="Ontology",
        scope="Match",
        positions=["DEF", "MID", "FWD", "GK"],
        status="APPROVED",
        causality="contemporaneous",
        null_if_no_obs=False,
        values=["BGW", "SGW", "DGW"],
        note="Contemporaneous structural label; not a predictive feature",
    ),
    "is_warmup_gw": FeatureRecord(
        gate="DAL-BOUNDARY",
        scope="Individual",
        positions=["DEF", "MID", "FWD", "GK"],
        status="APPROVED",
        causality="contemporaneous",
        null_if_no_obs=False,
        note="True on a player's first GW in the data — rolling signals are NaN (no prior history). "
        "Consumers should filter ~is_warmup_gw before applying rolling signal eligibility thresholds.",
    ),
}
