"""Tests for weekly/signal_intelligence.py.

Covers:
- Output schema (column names and types)
- Forbidden-phrase assertions (no player IDs, no ranking language, no predictions)
- Template rendering spot-checks for all three output functions
- Vocabulary membership
- Empty-input safety
"""

from __future__ import annotations

import pandas as pd
import pytest

from signals.lifecycle import load_registry
from intelligence.reporting.signal_intelligence import (
    CONTEXT_NOTE_COLUMNS,
    CONTEXT_CONDITION_LAYERS,
    POSITIONAL_SUMMARY_COLUMNS,
    STABLE_OBSERVATION_COLUMNS,
    STABLE_PROMOTION_CLASSES,
    build_context_condition_notes,
    build_positional_signal_summary,
    build_stable_signal_observations,
    write_signal_intelligence,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry() -> pd.DataFrame:
    return load_registry()


@pytest.fixture(scope="module")
def stable_obs(registry: pd.DataFrame) -> pd.DataFrame:
    return build_stable_signal_observations(registry, gw=36)


@pytest.fixture(scope="module")
def positional_summary(registry: pd.DataFrame) -> pd.DataFrame:
    return build_positional_signal_summary(registry)


@pytest.fixture(scope="module")
def context_notes(registry: pd.DataFrame) -> pd.DataFrame:
    return build_context_condition_notes(registry)


# ---------------------------------------------------------------------------
# Schema: stable_signal_observations
# ---------------------------------------------------------------------------

def test_stable_observations_has_required_columns(stable_obs):
    assert list(stable_obs.columns) == list(STABLE_OBSERVATION_COLUMNS)


def test_stable_observations_gw_column_is_constant(stable_obs):
    if stable_obs.empty:
        pytest.skip("no stable/review rows in registry")
    assert stable_obs["gw"].eq(36).all()


def test_stable_observations_contains_only_governed_promotion_classes(stable_obs):
    unexpected = set(stable_obs["promotion_class"].unique()) - STABLE_PROMOTION_CLASSES
    assert not unexpected, f"unexpected promotion_class values: {unexpected}"


def test_stable_observations_no_null_signals_or_positions(stable_obs):
    if stable_obs.empty:
        pytest.skip("no stable/review rows in registry")
    assert stable_obs["signal"].notna().all()
    assert stable_obs["position"].notna().all()


def test_stable_observations_no_duplicate_signal_position_keys(stable_obs):
    dups = int(stable_obs[["signal", "position"]].duplicated().sum())
    assert dups == 0


def test_stable_observations_observation_column_is_non_empty_string(stable_obs):
    if stable_obs.empty:
        pytest.skip("no stable/review rows in registry")
    assert stable_obs["observation"].notna().all()
    assert (stable_obs["observation"].str.strip() != "").all()


# ---------------------------------------------------------------------------
# Schema: positional_signal_summary
# ---------------------------------------------------------------------------

def test_positional_summary_has_required_columns(positional_summary):
    assert list(positional_summary.columns) == list(POSITIONAL_SUMMARY_COLUMNS)


def test_positional_summary_covers_all_four_positions(positional_summary):
    assert set(positional_summary["position"]) == {"GK", "DEF", "MID", "FWD"}


def test_positional_summary_counts_are_non_negative(positional_summary):
    count_cols = [c for c in POSITIONAL_SUMMARY_COLUMNS if c != "position"]
    for col in count_cols:
        assert (positional_summary[col] >= 0).all(), f"negative count in {col}"


def test_positional_summary_total_matches_registry_rows(positional_summary, registry):
    count_cols = [c for c in POSITIONAL_SUMMARY_COLUMNS if c != "position"]
    total = int(positional_summary[count_cols].sum().sum())
    assert total == len(registry)


def test_positional_summary_blocked_count_matches_registry(positional_summary, registry):
    expected_blocked = (
        registry[registry["downstream_status"] == "blocked"]
        .groupby("position")
        .size()
    )
    for _, row in positional_summary.iterrows():
        pos = row["position"]
        assert row["blocked"] == int(expected_blocked.get(pos, 0))


# ---------------------------------------------------------------------------
# Schema: context_condition_notes
# ---------------------------------------------------------------------------

def test_context_notes_has_required_columns(context_notes):
    assert list(context_notes.columns) == list(CONTEXT_NOTE_COLUMNS)


def test_context_notes_only_contains_governed_layers(context_notes):
    if context_notes.empty:
        pytest.skip("no context/exposure rows in registry")
    unexpected = set(context_notes["signal_layer"].unique()) - CONTEXT_CONDITION_LAYERS
    assert not unexpected, f"unexpected signal_layer values: {unexpected}"


def test_context_notes_no_duplicate_signal_position_keys(context_notes):
    dups = int(context_notes[["signal", "position"]].duplicated().sum())
    assert dups == 0


def test_context_notes_note_column_is_non_empty_string(context_notes):
    if context_notes.empty:
        pytest.skip("no context/exposure rows in registry")
    assert context_notes["note"].notna().all()
    assert (context_notes["note"].str.strip() != "").all()


def test_context_notes_row_count_matches_registry_layer_filter(context_notes, registry):
    expected = registry[registry["signal_layer"].isin(CONTEXT_CONDITION_LAYERS)]
    assert len(context_notes) == len(expected)


# ---------------------------------------------------------------------------
# Forbidden-phrase assertions
# No player-level content, no ranking language, no predicted scores.
# ---------------------------------------------------------------------------

FORBIDDEN_PHRASES: list[str] = [
    "player_id",
    "player id",
    "rank ",
    "ranking",
    "best player",
    "top player",
    "predicted score",
    "will score",
    "probability of scoring",
    "captaincy",
    "transfer recommendation",
]


def _all_text(df: pd.DataFrame) -> str:
    """Concatenate all string columns for phrase scanning."""
    return " ".join(
        df.select_dtypes(include="object").fillna("").values.flatten().tolist()
    ).lower()


def test_stable_observations_contains_no_forbidden_phrases(stable_obs):
    text = _all_text(stable_obs)
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, (
            f"forbidden phrase {phrase!r} found in stable_signal_observations"
        )


def test_positional_summary_contains_no_forbidden_phrases(positional_summary):
    text = _all_text(positional_summary)
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, (
            f"forbidden phrase {phrase!r} found in positional_signal_summary"
        )


def test_context_notes_contains_no_forbidden_phrases(context_notes):
    text = _all_text(context_notes)
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text, (
            f"forbidden phrase {phrase!r} found in context_condition_notes"
        )


# ---------------------------------------------------------------------------
# Template rendering spot-checks
# ---------------------------------------------------------------------------

def _make_registry_row(
    signal: str = "bonus",
    position: str = "MID",
    signal_layer: str = "performance",
    downstream_status: str = "eligible",
    promotion_class: str = "core_signal",
    temporal_stability: str = "stable",
    association_class: str = "continuous_monotonic",
    rho_pooled: float = 0.55,
) -> pd.DataFrame:
    """Build a minimal single-row registry DataFrame for template tests."""
    return pd.DataFrame([{
        "signal": signal,
        "position": position,
        "signal_layer": signal_layer,
        "downstream_status": downstream_status,
        "promotion_class": promotion_class,
        "temporal_stability": temporal_stability,
        "association_class": association_class,
        "rho_pooled": rho_pooled,
        "population_scope": "primary",
        "population_robustness": "untested",
        "preferred_population": "both",
        "layer_role": "points_component",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "",
        "variable_level": "player_level",
        "low_confidence": False,
        "support_flags": "",
        "support_type": "",
    }])


def test_core_signal_observation_contains_signal_position_and_rho():
    row = _make_registry_row(promotion_class="core_signal", rho_pooled=0.55)
    obs = build_stable_signal_observations(row, gw=10)
    assert len(obs) == 1
    text = obs.iloc[0]["observation"]
    assert "bonus" in text
    assert "MID" in text
    assert "0.550" in text
    assert "core" in text.lower() or "stable" in text.lower()


def test_review_signal_observation_contains_temporal_stability():
    row = _make_registry_row(
        promotion_class="review_signal",
        temporal_stability="moderate_shift",
        rho_pooled=0.31,
        downstream_status="caveated",
        signal_layer="performance",
    )
    obs = build_stable_signal_observations(row, gw=10)
    assert len(obs) == 1
    text = obs.iloc[0]["observation"]
    assert "moderate_shift" in text
    assert "0.310" in text


def test_rho_nan_renders_as_n_a():
    import numpy as np
    row = _make_registry_row(promotion_class="review_signal", rho_pooled=float("nan"))
    obs = build_stable_signal_observations(row, gw=10)
    assert "n/a" in obs.iloc[0]["observation"]


def test_context_note_contains_signal_and_position():
    row = _make_registry_row(
        signal="fdr_avg",
        position="DEF",
        signal_layer="context",
        promotion_class=None,
        downstream_status="caveated",
    )
    row["promotion_class"] = None
    notes = build_context_condition_notes(row)
    assert len(notes) == 1
    text = notes.iloc[0]["note"]
    assert "fdr_avg" in text
    assert "DEF" in text


def test_exposure_note_template_differs_from_context_note():
    context_row = _make_registry_row(signal="was_home", position="MID", signal_layer="context", promotion_class=None, downstream_status="caveated")
    context_row["promotion_class"] = None
    exposure_row = _make_registry_row(signal="minutes", position="MID", signal_layer="exposure", promotion_class=None, downstream_status="caveated")
    exposure_row["promotion_class"] = None

    context_note = build_context_condition_notes(context_row).iloc[0]["note"]
    exposure_note = build_context_condition_notes(exposure_row).iloc[0]["note"]
    assert context_note != exposure_note


def test_blocked_rows_excluded_from_stable_observations():
    row = _make_registry_row(
        promotion_class=None,
        downstream_status="blocked",
    )
    row["promotion_class"] = None
    obs = build_stable_signal_observations(row, gw=10)
    assert obs.empty


# ---------------------------------------------------------------------------
# Empty-input safety
# ---------------------------------------------------------------------------

def test_stable_observations_empty_registry_returns_empty_frame():
    empty = pd.DataFrame(columns=load_registry().columns)
    obs = build_stable_signal_observations(empty, gw=1)
    assert obs.empty
    assert list(obs.columns) == list(STABLE_OBSERVATION_COLUMNS)


def test_positional_summary_empty_registry_returns_empty_frame():
    empty = pd.DataFrame(columns=load_registry().columns)
    result = build_positional_signal_summary(empty)
    assert result.empty
    assert list(result.columns) == list(POSITIONAL_SUMMARY_COLUMNS)


def test_context_notes_empty_registry_returns_empty_frame():
    empty = pd.DataFrame(columns=load_registry().columns)
    result = build_context_condition_notes(empty)
    assert result.empty
    assert list(result.columns) == list(CONTEXT_NOTE_COLUMNS)


# ---------------------------------------------------------------------------
# write_signal_intelligence integration
# ---------------------------------------------------------------------------

def test_write_signal_intelligence_creates_all_three_files(tmp_path, registry):
    paths = write_signal_intelligence(registry, gw=36, output_dir=tmp_path)

    assert set(paths.keys()) == {
        "stable_signal_observations",
        "positional_signal_summary",
        "context_condition_notes",
    }
    for path in paths.values():
        assert path.exists(), f"missing output: {path}"

    obs_df = pd.read_csv(paths["stable_signal_observations"])
    pos_df = pd.read_csv(paths["positional_signal_summary"])
    ctx_df = pd.read_csv(paths["context_condition_notes"])

    assert list(obs_df.columns) == list(STABLE_OBSERVATION_COLUMNS)
    assert list(pos_df.columns) == list(POSITIONAL_SUMMARY_COLUMNS)
    assert list(ctx_df.columns) == list(CONTEXT_NOTE_COLUMNS)
