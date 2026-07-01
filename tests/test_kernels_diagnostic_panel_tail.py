import numpy as np
import pandas as pd
import pytest

from domain.registry.association import assign_association_class, consolidate_flags
from domain.registry.validation import validate_registry_contract
from research.kernels.diagnostic.panel import bootstrap_panel_decomposition, split_between_within_player_rho
from research.kernels.diagnostic.tail import measure_tail_event_dependence
from research.registry.assembler import assemble_registry_from_sections
from research.registry.sections import SectionBuildConfig, compute_relationship_sections

pytestmark = pytest.mark.unit


def test_split_between_within_player_rho_returns_panel_metrics_for_supported_slice():
    rows = []
    for player_id in range(20):
        for gw in range(5):
            rows.append(
                {
                    "player_id": player_id,
                    "position": "MID",
                    "signal": player_id + gw * 0.1,
                    "target": player_id * 0.8 + gw * 0.2,
                }
            )
    df = pd.DataFrame(rows)

    result = split_between_within_player_rho(df, "signal", "target", "MID")

    assert result["support_flag"] == ""
    assert result["n_records"] == 100
    assert result["n_players"] == 20
    assert result["panel_class"] in {
        "state_sensitive",
        "mixed",
        "identity_dominant",
        "indeterminate",
    }
    assert pd.notna(result["rho_pooled"])


def _between_dominated_panel(n_players=30, n_gws=12, noise=0.1, seed=0):
    """Player quality drives both signal and target; within-player variation is independent
    noise -> strong between-player association, ~0 within -> identity_dominant."""
    rng = np.random.default_rng(seed)
    rows = []
    for player_id in range(n_players):
        quality = float(player_id)
        for _ in range(n_gws):
            rows.append(
                {
                    "player_id": player_id,
                    "position": "MID",
                    "signal": quality + rng.normal(0, noise),
                    "target": quality + rng.normal(0, noise),
                }
            )
    return pd.DataFrame(rows)


def test_bootstrap_brackets_point_and_returns_cis():
    out = bootstrap_panel_decomposition(_between_dominated_panel(), "signal", "target", "MID", n_boot=200, seed=0)
    assert out["n_boot"] == 200
    assert out["support_flag"] == ""
    for key in ("rho_pooled_ci", "rho_between_ci", "rho_within_ci", "within_share_ci"):
        assert isinstance(out[key], tuple) and len(out[key]) == 2
        lo, hi = out[key]
        assert lo <= hi  # ordered interval
    # rho_pooled here is near the ceiling (~1.0); percentile CIs are known NOT to bracket a
    # boundary statistic (resamples pile against 1.0), so bracketing is asserted on an interior
    # component instead — rho_within sits near 0.
    wlo, whi = out["rho_within_ci"]
    assert wlo <= out["rho_within"] <= whi  # CI brackets the (interior) point estimate
    plo, phi = out["rho_pooled_ci"]
    assert plo < phi  # player resampling produced genuine spread (clusters vary the result)


def test_bootstrap_identity_dominant_when_between_drives():
    out = bootstrap_panel_decomposition(_between_dominated_panel(), "signal", "target", "MID", n_boot=300, seed=0)
    assert out["within_share"] < 0.20  # within is genuinely small
    assert out["panel_class"] == "identity_dominant"


def test_bootstrap_undecomposable_when_signal_independent_of_target():
    rng = np.random.default_rng(1)
    rows = [
        {"player_id": p, "position": "MID", "signal": rng.normal(), "target": rng.normal()}
        for p in range(30)
        for _ in range(12)
    ]
    out = bootstrap_panel_decomposition(pd.DataFrame(rows), "signal", "target", "MID", n_boot=300, seed=0)
    lo, hi = out["rho_pooled_ci"]
    assert lo <= 0.0 <= hi  # the pooled CI includes zero — no association to split
    assert out["panel_class"] == "undecomposable"


def test_bootstrap_insufficient_support_skips_bootstrap():
    rows = [
        {"player_id": p, "position": "MID", "signal": float(p), "target": float(p)} for p in range(5) for _ in range(3)
    ]
    out = bootstrap_panel_decomposition(pd.DataFrame(rows), "signal", "target", "MID")
    assert out["support_flag"] == "insufficient_support"
    assert out["panel_class"] == "insufficient_support"
    assert out["n_boot"] == 0
    assert np.isnan(out["rho_pooled_ci"][0]) and np.isnan(out["rho_pooled_ci"][1])


def test_bootstrap_point_fields_match_split_between_within():
    df = _between_dominated_panel()
    point = split_between_within_player_rho(df, "signal", "target", "MID")
    out = bootstrap_panel_decomposition(df, "signal", "target", "MID", n_boot=50, seed=0)
    for key in ("rho_pooled", "rho_between", "rho_within", "within_share", "n_records", "n_players"):
        assert out[key] == point[key] or (pd.isna(out[key]) and pd.isna(point[key]))


def test_bootstrap_is_deterministic_given_seed():
    df = _between_dominated_panel()
    a = bootstrap_panel_decomposition(df, "signal", "target", "MID", n_boot=100, seed=7)
    b = bootstrap_panel_decomposition(df, "signal", "target", "MID", n_boot=100, seed=7)
    assert a["panel_class"] == b["panel_class"]
    assert a["rho_pooled_ci"] == b["rho_pooled_ci"]
    assert a["within_share_ci"] == b["within_share_ci"]


def test_split_between_within_supports_kendall_method():
    out = split_between_within_player_rho(_between_dominated_panel(), "signal", "target", "MID", method="kendall")
    assert out["support_flag"] == ""
    assert -1.0 <= out["rho_pooled"] <= 1.0
    assert out["panel_class"] in {"state_sensitive", "mixed", "identity_dominant", "indeterminate"}


def test_bootstrap_supports_kendall_method():
    out = bootstrap_panel_decomposition(
        _between_dominated_panel(), "signal", "target", "MID", n_boot=100, seed=0, method="kendall"
    )
    assert out["n_boot"] == 100
    assert out["panel_class"] in {"identity_dominant", "mixed", "state_sensitive", "indeterminate", "undecomposable"}
    lo, hi = out["rho_pooled_ci"]
    assert -1.0 <= lo <= hi <= 1.0


def test_bootstrap_reports_clustered_pooled_pvalue_for_fdr():
    strong = bootstrap_panel_decomposition(_between_dominated_panel(), "signal", "target", "MID", n_boot=300, seed=0)
    assert 0.0 < strong["rho_pooled_p"] <= 0.05  # strong association -> small (never exactly 0)

    rng = np.random.default_rng(2)
    rows = [
        {"player_id": p, "position": "MID", "signal": rng.normal(), "target": rng.normal()}
        for p in range(30)
        for _ in range(12)
    ]
    indep = bootstrap_panel_decomposition(pd.DataFrame(rows), "signal", "target", "MID", n_boot=300, seed=0)
    assert indep["rho_pooled_p"] > 0.2  # independent -> not significant


def test_split_min_appearances_filters_thin_players_to_share_ceiling_population():
    rng = np.random.default_rng(0)
    rows = []
    for pid in range(25):  # regulars: 12 games each
        for _ in range(12):
            rows.append(
                {
                    "player_id": pid,
                    "position": "MID",
                    "signal": pid + rng.normal(0, 0.1),
                    "target": pid + rng.normal(0, 0.1),
                }
            )
    for pid in range(100, 110):  # cameos: 2 games each
        for _ in range(2):
            rows.append({"player_id": pid, "position": "MID", "signal": rng.normal(), "target": rng.normal()})
    df = pd.DataFrame(rows)

    full = split_between_within_player_rho(df, "signal", "target", "MID", min_appearances=1)
    filtered = split_between_within_player_rho(df, "signal", "target", "MID", min_appearances=10)
    assert full["n_players"] == 35  # 25 regulars + 10 cameos (default: no filter)
    assert filtered["n_players"] == 25  # cameos (2 games < 10) dropped -> only well-sampled players
    # The bootstrap threads the same filter through (point estimate matches the filtered split).
    boot = bootstrap_panel_decomposition(df, "signal", "target", "MID", n_boot=50, seed=0, min_appearances=10)
    assert boot["n_players"] == 25


def test_panel_decomposition_rejects_unknown_method():
    df = _between_dominated_panel()
    with pytest.raises(ValueError, match="method must be one of"):
        split_between_within_player_rho(df, "signal", "target", "MID", method="pearson")
    with pytest.raises(ValueError, match="method must be one of"):
        bootstrap_panel_decomposition(df, "signal", "target", "MID", method="pearson")


def test_measure_tail_event_dependence_uses_fixed_haul_threshold():
    df = pd.DataFrame(
        {
            "position": ["FWD"] * 100,
            "signal": list(range(100)),
            "target": [2] * 60 + [8] * 20 + [14] * 20,
        }
    )

    result = measure_tail_event_dependence(df, "signal", "target", "FWD")

    assert result["support_flag"] == ""
    assert result["n_haul"] == 20
    assert result["haul_pct"] == 20.0
    assert isinstance(result["tail_sensitive"], (bool, type(None)))


def test_association_class_precedence_and_flag_consolidation():
    assert (
        assign_association_class(
            {
                "support_flags": "insufficient_support:bin_density",
                "relationship_geometry": "monotonic_positive",
            }
        )
        == "unassessable"
    )
    assert (
        assign_association_class(
            {
                "support_flags": "",
                "relationship_geometry": "monotonic_positive",
                "temporal_stability": "stable",
                "rho_drop": 0.1,
                "low_confidence": False,
                "panel_class": "mixed",
            }
        )
        == "continuous_monotonic"
    )
    assert (
        assign_association_class(
            {
                "support_flags": "",
                "relationship_geometry": "monotonic_positive",
                "temporal_stability": "stable",
                "rho_drop": 0.1,
                "low_confidence": True,
                "panel_class": "mixed",
            }
        )
        == "weak_association"
    )
    assert (
        consolidate_flags(
            "insufficient_support:bin_density",
            "degenerate",
            "insufficient_support:bin_density",
            "",
        )
        == "insufficient_support:bin_density,degenerate"
    )


def test_compute_relationship_sections_iterates_signal_position_pairs():
    rows = []
    for position_index, position in enumerate(["GK", "DEF", "MID", "FWD"]):
        for player_id in range(20):
            for gw in range(5):
                value = player_id + gw + position_index
                rows.append(
                    {
                        "player_id": f"{position}-{player_id}",
                        "position": position,
                        "gw_block": "early" if gw < 2 else "mid" if gw < 4 else "late",
                        "bps": value,
                        "total_points": value * 0.5 + position_index,
                    }
                )
    data = pd.DataFrame(rows)

    sections = compute_relationship_sections(
        data,
        signals=["bps"],
        config=SectionBuildConfig(n_bootstrap=0),
    )

    assert len(sections.geometry) == 4
    assert len(sections.stability) == 4
    assert len(sections.decomposition) == 4
    assert len(sections.haul) == 4
    assert set(sections.geometry["position"]) == {"GK", "DEF", "MID", "FWD"}
    assert sections.geometry["signal"].eq("bps").all()
    assert sections.geometry["population_scope"].eq("primary").all()
    assert sections.geometry["variable_level"].eq("player_level").all()
    assert sections.geometry["n_records"].eq(100).all()


def test_compute_relationship_sections_can_feed_registry_assembly():
    rows = []
    for player_id in range(20):
        for gw in range(5):
            value = player_id + gw
            rows.append(
                {
                    "player_id": player_id,
                    "position": "MID",
                    "gw_block": "early" if gw < 2 else "mid" if gw < 4 else "late",
                    "bps": value,
                    "total_points": value,
                }
            )
    data = pd.DataFrame(rows)

    sections = compute_relationship_sections(
        data,
        signals=["bps"],
        config=SectionBuildConfig(positions=("MID",), n_bootstrap=0),
    )
    # The build assembles raw evidence; governance enriches at promotion. Mirror
    # that pipeline to obtain a contract-valid governed registry.
    from model.governance.promotion import enrich_promotion_class
    from model.governance.semantics import enrich_signal_layers

    registry = assemble_registry_from_sections(
        geometry=sections.geometry,
        stability=sections.stability,
        decomposition=sections.decomposition,
        haul=sections.haul,
        expected_n=1,
    )
    assert "downstream_status" not in registry.columns  # raw evidence finding
    registry = enrich_promotion_class(enrich_signal_layers(registry))

    validate_registry_contract(registry)
    assert registry.loc[0, "signal"] == "bps"
    assert registry.loc[0, "position"] == "MID"
    assert registry.loc[0, "downstream_status"] in {
        "eligible",
        "caveated",
        "blocked",
    }
