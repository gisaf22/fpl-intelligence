import pandas as pd
import pytest

from signals.governance import (
    enrich_signal_layers,
    load_registry,
    validate_registry_contract,
)
from signals.governance.promotion import enrich_promotion_class


SEMANTIC_COLUMNS = {
    "signal_layer",
    "layer_role",
    "feature_candidate_eligible",
    "downstream_status",
    "interpretation_caveat",
}


def _full_enrich(registry: pd.DataFrame) -> pd.DataFrame:
    """Apply the full enrichment pipeline: semantic layers then promotion class."""
    return enrich_promotion_class(enrich_signal_layers(registry))


def test_enrich_signal_layers_adds_semantic_columns_to_raw_registry():
    registry = load_registry().drop(columns=list(SEMANTIC_COLUMNS) + ["promotion_class"])

    enriched = _full_enrich(registry)
    validate_registry_contract(enriched)

    assert SEMANTIC_COLUMNS.issubset(enriched.columns)
    assert enriched["downstream_status"].value_counts().to_dict() == {
        "caveated": 71,
        "blocked": 24,
        "eligible": 9,
    }


def test_enrich_signal_layers_replaces_stale_semantic_columns():
    registry = load_registry()
    registry["signal_layer"] = "performance"
    registry["downstream_status"] = "eligible"

    enriched = enrich_signal_layers(registry)

    assert (
        enriched.loc[enriched["signal"].eq("fdr_avg"), "signal_layer"]
        .eq("context")
        .all()
    )
    assert (
        enriched.loc[enriched["signal"].eq("fdr_avg"), "downstream_status"]
        .eq("caveated")
        .all()
    )


def test_enrich_signal_layers_fails_on_unmapped_signal():
    registry = pd.DataFrame(
        {
            "signal": ["unknown_signal"],
            "position": ["MID"],
            "relationship_geometry": ["monotonic_positive"],
        }
    )

    with pytest.raises(ValueError, match="unknown_signal"):
        enrich_signal_layers(registry)


def test_low_confidence_status_is_caveated_when_re_enriched():
    registry = load_registry().drop(columns=list(SEMANTIC_COLUMNS) + ["promotion_class"])
    idx = registry[registry["signal"].eq("xgi") & registry["position"].eq("MID")].index[0]
    registry.loc[idx, "low_confidence"] = True

    enriched = enrich_signal_layers(registry)

    row = enriched.loc[idx]
    assert row["feature_candidate_eligible"] == True  # noqa: E712
    assert row["downstream_status"] == "caveated"


def test_insufficient_support_status_is_blocked_when_re_enriched():
    registry = load_registry().drop(columns=list(SEMANTIC_COLUMNS) + ["promotion_class"])
    idx = registry[
        registry["support_flags"].str.contains("insufficient_support", na=False)
    ].index[0]

    enriched = enrich_signal_layers(registry)

    assert enriched.loc[idx, "downstream_status"] == "blocked"


def test_enrich_promotion_class_assigns_null_to_blocked_rows():
    registry = load_registry().drop(columns=["promotion_class"])
    enriched = _full_enrich(registry)

    blocked = enriched[enriched["downstream_status"] == "blocked"]
    assert blocked["promotion_class"].isna().all()


def test_enrich_promotion_class_assigns_governed_value_to_non_blocked_rows():
    from signals.governance.promotion import PROMOTION_CLASS_VALUES

    registry = load_registry().drop(columns=["promotion_class"])
    enriched = _full_enrich(registry)

    non_blocked = enriched[enriched["downstream_status"] != "blocked"]
    assert non_blocked["promotion_class"].notna().all()
    assert set(non_blocked["promotion_class"].unique()).issubset(PROMOTION_CLASS_VALUES)
