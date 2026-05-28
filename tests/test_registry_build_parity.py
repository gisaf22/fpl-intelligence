"""Sprint D parity gate: computed registry reproducibility test.

The seed registry (eda_03_joint_registry.csv) was produced by running the
computed build pipeline against GW6–33 prepared data (minutes >= 60) and
is the canonical reference for this test.  The exploratory EDA-3 CSV that
predated the governed pipeline is archived as eda_03_joint_registry_exploratory.csv.

This test re-runs the same computed build and asserts that the output is
reproducible within governed tolerances:

- Schema parity: same column set (order is not required)
- Row parity: both seed and computed have exactly 104 rows
- No duplicate (signal, position) keys in computed
- rho_pooled tolerance: absolute difference <= 0.02 for all matched non-null pairs

Marks: @pytest.mark.integration — requires live DB at ~/.fpl/fpl.db.
Skipped automatically when the DB is absent.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from signals.lifecycle import load_registry
from signals.registry.assembly import assemble_registry_from_sections
from signals.registry.config import assign_gw_block
from studies.experiments.registry_sections_study import SectionBuildConfig, compute_relationship_sections

DB_PATH = Path.home() / ".fpl" / "fpl.db"

# Seed registry: produced by the computed build against GW6-33 prepared data.
# This is the reproducibility reference — not the old exploratory EDA-3 CSV.
SEED_REGISTRY_PATH = Path("studies/eda/findings/eda_03_joint_registry.csv")

EXPECTED_REGISTRY_ROWS: int = 104

GW_MIN: int = 6
GW_MAX: int = 33

RHO_TOLERANCE: float = 0.02



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seed_registry() -> pd.DataFrame:
    """Load the seed registry produced by the first governed computed build."""
    return load_registry(SEED_REGISTRY_PATH)


@pytest.fixture(scope="module")
def computed_registry(seed_registry: pd.DataFrame) -> pd.DataFrame:
    """Re-run the computed build against GW6–33 prepared data.

    Skipped when the DB is absent so the suite stays green in CI environments
    that do not have access to the live database.
    """
    if not DB_PATH.exists():
        pytest.skip(f"live DB not found at {DB_PATH}; skipping integration tests")

    from dal.curated.player_gameweek_spine import build_player_gameweek_spine
    from signals.registry.builder import _build_registry_population

    spine = build_player_gameweek_spine(DB_PATH)
    prepared = _build_registry_population(spine, data_cutoff_gw=GW_MAX)

    # Restrict to GW_MIN–GW_MAX window.
    prepared = prepared[prepared["gw"] >= GW_MIN].copy()

    # gw_block is required by _stability_row in sections.py; without it every
    # row receives temporal_stability="insufficient_data".
    prepared["gw_block"] = prepared["gw"].map(assign_gw_block)

    # Use the same signal set as the seed registry.
    signals = tuple(dict.fromkeys(seed_registry["signal"].tolist()))

    sections = compute_relationship_sections(
        data=prepared,
        signals=signals,
        config=SectionBuildConfig(n_bootstrap=200),
    )
    return assemble_registry_from_sections(
        geometry=sections.geometry,
        stability=sections.stability,
        decomposition=sections.decomposition,
        haul=sections.haul,
        expected_n=len(sections.geometry),
    )


# ---------------------------------------------------------------------------
# A. Schema parity
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_schema_parity(
    seed_registry: pd.DataFrame,
    computed_registry: pd.DataFrame,
) -> None:
    """Computed and seed registries must expose the same column set.

    Column ordering is not required — the computed build follows REQUIRED_COLUMNS
    from schema.py while the seed CSV preserves the write order from that build.
    """
    seed_cols = set(seed_registry.columns)
    computed_cols = set(computed_registry.columns)

    only_in_seed = seed_cols - computed_cols
    only_in_computed = computed_cols - seed_cols

    assert not only_in_seed, (
        f"columns present in seed but missing from computed: {sorted(only_in_seed)}"
    )
    assert not only_in_computed, (
        f"columns present in computed but missing from seed: {sorted(only_in_computed)}"
    )


# ---------------------------------------------------------------------------
# B. Row parity
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_seed_registry_has_expected_row_count(
    seed_registry: pd.DataFrame,
) -> None:
    """Seed registry must have exactly 104 rows (26 signals × 4 positions)."""
    assert len(seed_registry) == EXPECTED_REGISTRY_ROWS, (
        f"seed registry row count changed: expected {EXPECTED_REGISTRY_ROWS}, "
        f"got {len(seed_registry)}"
    )


@pytest.mark.integration
def test_computed_registry_row_count(
    computed_registry: pd.DataFrame,
) -> None:
    """Computed registry must produce exactly 104 rows (26 signals × 4 positions)."""
    assert len(computed_registry) == EXPECTED_REGISTRY_ROWS, (
        f"computed registry row count: expected {EXPECTED_REGISTRY_ROWS}, "
        f"got {len(computed_registry)}"
    )


@pytest.mark.integration
def test_no_duplicate_keys_in_computed(
    computed_registry: pd.DataFrame,
) -> None:
    """Computed registry must not have duplicate (signal, position) pairs."""
    dups = int(computed_registry[["signal", "position"]].duplicated().sum())
    assert dups == 0, (
        f"computed registry has {dups} duplicate (signal, position) rows"
    )


# ---------------------------------------------------------------------------
# C. rho_pooled tolerance
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_rho_pooled_tolerance(
    seed_registry: pd.DataFrame,
    computed_registry: pd.DataFrame,
) -> None:
    """rho_pooled must agree within absolute tolerance of 0.02 for all matched pairs.

    Comparison is restricted to rows where both seed and computed rho_pooled
    are non-null. NaN rows in either side are skipped safely.
    """
    merged = seed_registry[["signal", "position", "rho_pooled"]].merge(
        computed_registry[["signal", "position", "rho_pooled"]].rename(
            columns={"rho_pooled": "rho_computed"}
        ),
        on=["signal", "position"],
        how="inner",
    )

    assert len(merged) == EXPECTED_REGISTRY_ROWS, (
        f"inner join on (signal, position) dropped rows: "
        f"expected {EXPECTED_REGISTRY_ROWS}, merged={len(merged)}"
    )

    # Only compare where both values are available.
    valid = merged.dropna(subset=["rho_pooled", "rho_computed"])
    diff = (valid["rho_pooled"] - valid["rho_computed"]).abs()
    failing = valid[diff > RHO_TOLERANCE].copy()
    failing["abs_diff"] = diff[failing.index]

    assert failing.empty, (
        f"{len(failing)} of {len(valid)} comparable (signal, position) pairs exceed "
        f"rho_pooled absolute tolerance of {RHO_TOLERANCE}:\n"
        + failing[["signal", "position", "rho_pooled", "rho_computed", "abs_diff"]]
        .sort_values("abs_diff", ascending=False)
        .to_string(index=False)
    )
