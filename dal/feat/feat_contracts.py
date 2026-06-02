"""Feature layer causality contracts — derived from FEATURE_REGISTRY.

STATE_COL_CONTRACTS is the downstream-facing dict representation of causality,
warmup, reliability, and allowed-values metadata for every governed output column.
It is derived from FEATURE_REGISTRY (feat_schema.py) — the single source of truth.
"""

from dal.feat.feat_schema import FEATURE_REGISTRY, FeatureRecord


def _to_state_contract(rec: FeatureRecord) -> dict:
    contract: dict = {
        "causality": rec.causality,
        "null_if_no_obs": rec.null_if_no_obs,
    }
    if rec.warmup_gws is not None:
        contract["warmup_gws"] = rec.warmup_gws
    if rec.min_obs is not None:
        contract["min_obs_for_reliability"] = rec.min_obs
    if rec.values is not None:
        contract["values"] = rec.values
    return contract


STATE_COL_CONTRACTS: dict[str, dict] = {col: _to_state_contract(rec) for col, rec in FEATURE_REGISTRY.items()}
