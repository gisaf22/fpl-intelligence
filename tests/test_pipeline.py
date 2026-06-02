"""Unit tests for dal/pipeline.py — manifest, caching, and freshness validation.

Capabilities tested: Observability, Idempotency, Operability, Lineage.
Freshness tests use mocks. Build/manifest tests use the test.db fixture.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from dal.exceptions import DataFreshnessError
from dal.pipeline import _hash_db, _manifest_path
from dal.staging import validate_data_freshness

# ---------------------------------------------------------------------------
# validate_data_freshness — mocked staging layer
# ---------------------------------------------------------------------------


def _events_df(gws: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"gw": gws})


def _histories_df(gws: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"player_id": list(range(len(gws))), "gw": gws})


@pytest.mark.unit
def test_validate_data_freshness_raises_on_missing_gw(tmp_path: Path) -> None:
    """DataFreshnessError raised when target GW is absent from events."""
    db = tmp_path / "fpl.db"
    db.write_bytes(b"x")
    with (
        patch("dal.staging.stg_freshness.get_staged_events", return_value=_events_df([1, 2])),
        patch("dal.staging.stg_freshness.get_staged_player_histories", return_value=_histories_df([1])),
    ):
        with pytest.raises(DataFreshnessError) as exc_info:
            validate_data_freshness(db, gw=5)
        assert exc_info.value.gw == 5


@pytest.mark.unit
def test_validate_data_freshness_raises_on_stale_histories(tmp_path: Path) -> None:
    """DataFreshnessError raised when prior-GW player_histories are absent."""
    db = tmp_path / "fpl.db"
    db.write_bytes(b"x")
    with (
        patch("dal.staging.stg_freshness.get_staged_events", return_value=_events_df([1, 2, 3])),
        patch("dal.staging.stg_freshness.get_staged_player_histories", return_value=_histories_df([1])),
    ):
        with pytest.raises(DataFreshnessError) as exc_info:
            validate_data_freshness(db, gw=3)
        assert exc_info.value.gw == 2


@pytest.mark.unit
def test_validate_data_freshness_gw1_skips_history_check(tmp_path: Path) -> None:
    """GW 1 has no prior GW — the history check must be skipped."""
    db = tmp_path / "fpl.db"
    db.write_bytes(b"x")
    with (
        patch("dal.staging.stg_freshness.get_staged_events", return_value=_events_df([1])),
        patch("dal.staging.stg_freshness.get_staged_player_histories", return_value=_histories_df([])),
    ):
        validate_data_freshness(db, gw=1)  # must not raise


# ---------------------------------------------------------------------------
# _hash_db — determinism
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_manifest_hash_is_stable(tmp_path: Path) -> None:
    """Same file content → same SHA-256 hash on repeated calls."""
    db = tmp_path / "fpl.db"
    db.write_bytes(b"stable content")
    h1 = _hash_db(db)
    h2 = _hash_db(db)
    assert h1 == h2
    assert h1.startswith("sha256:")


@pytest.mark.unit
def test_manifest_hash_differs_on_content_change(tmp_path: Path) -> None:
    """Different file content → different hash."""
    db = tmp_path / "fpl.db"
    db.write_bytes(b"version1")
    h1 = _hash_db(db)
    db.write_bytes(b"version2")
    h2 = _hash_db(db)
    assert h1 != h2


# ---------------------------------------------------------------------------
# build() — manifest written and structured correctly (uses test.db fixture)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_manifest_written_after_successful_build(db_path: Path, tmp_path: Path) -> None:
    """build() must write a manifest JSON file adjacent to the source DB."""
    import shutil

    from dal.pipeline import run as build

    local_db = tmp_path / "fpl.db"
    shutil.copy(db_path, local_db)

    build(db_path=local_db, force=True)

    manifest_file = _manifest_path(local_db)
    assert manifest_file.exists(), "manifest JSON not written after successful build"


@pytest.mark.integration
def test_manifest_contains_required_fields(db_path: Path, tmp_path: Path) -> None:
    """Manifest must include run_id, source_db_hash, gw_range, and layers dict."""
    import shutil

    from dal.pipeline import run as build

    local_db = tmp_path / "fpl.db"
    shutil.copy(db_path, local_db)

    result = build(db_path=local_db, force=True)

    for field in ("run_id", "source_db_hash", "gw_range", "layers"):
        assert field in result, f"Missing required manifest field: {field!r}"


@pytest.mark.integration
def test_manifest_records_per_layer_fingerprint(db_path: Path, tmp_path: Path) -> None:
    """fct layer entry in manifest must include a fingerprint from reproducibility.py."""
    import shutil

    from dal.pipeline import run as build

    local_db = tmp_path / "fpl.db"
    shutil.copy(db_path, local_db)

    result = build(db_path=local_db, force=True)

    fct_entry = result.get("layers", {}).get("fct", {})
    assert "fingerprint" in fct_entry, "fct layer manifest entry missing 'fingerprint'"
    assert fct_entry["fingerprint"], "fct fingerprint is empty"


@pytest.mark.integration
def test_cache_hit_skips_rebuild(db_path: Path, tmp_path: Path) -> None:
    """Second build() call with same source hash must return cached manifest without rebuilding."""
    import shutil

    from dal.pipeline import run as build

    local_db = tmp_path / "fpl.db"
    shutil.copy(db_path, local_db)

    first = build(db_path=local_db, force=True)

    # Wrap build_player_gameweek_spine to detect if it's called again
    with patch("dal.pipeline.build_player_gameweek_spine") as mock_spine:
        second = build(db_path=local_db, force=False)
        mock_spine.assert_not_called()

    assert second["run_id"] == first["run_id"], "Cache miss: run_id changed on second call"


@pytest.mark.integration
def test_force_true_rebuilds_despite_cache(db_path: Path, tmp_path: Path) -> None:
    """force=True must rebuild even when source hash is unchanged."""
    import shutil

    from dal.pipeline import run as build

    local_db = tmp_path / "fpl.db"
    shutil.copy(db_path, local_db)

    build(db_path=local_db, force=True)
    second = build(db_path=local_db, force=True)

    # Both runs complete; run_id will differ (timestamp-based)
    assert second["layers"]["fct"]["status"] == "OK"


@pytest.mark.unit
def test_failed_layer_stops_pipeline(tmp_path: Path) -> None:
    """If fct raises, the manifest records FAIL for fct and feat/mart are not attempted."""
    from dal.pipeline import run as build

    db = tmp_path / "fpl.db"
    db.write_bytes(b"stub")

    from dal.staging import StagedEntities

    mock_staged = StagedEntities(
        player_histories=pd.DataFrame({"gw": [1]}),
        players=pd.DataFrame(),
        fixtures=pd.DataFrame(),
        teams=pd.DataFrame(),
        element_types=pd.DataFrame(),
        events=pd.DataFrame(),
    )
    with (
        patch("dal.pipeline.load_staged_entities", return_value=mock_staged),
        patch("dal.pipeline.get_player_fixture_base", return_value=pd.DataFrame()),
        patch("dal.pipeline.build_player_gameweek_spine", side_effect=RuntimeError("fct boom")),
    ):
        result = build(db_path=db, force=True)

    assert result["layers"]["fct"]["status"] == "FAIL"
    assert "feat" not in result["layers"], "feat must not run after fct failure"
    assert "mart" not in result["layers"], "mart must not run after fct failure"


@pytest.mark.unit
def test_failed_layer_records_error_message(tmp_path: Path) -> None:
    """Manifest must include the exception message when a layer fails."""
    from dal.pipeline import run as build

    db = tmp_path / "fpl.db"
    db.write_bytes(b"stub")

    from dal.staging import StagedEntities

    mock_staged = StagedEntities(
        player_histories=pd.DataFrame({"gw": [1]}),
        players=pd.DataFrame(),
        fixtures=pd.DataFrame(),
        teams=pd.DataFrame(),
        element_types=pd.DataFrame(),
        events=pd.DataFrame(),
    )
    with (
        patch("dal.pipeline.load_staged_entities", return_value=mock_staged),
        patch("dal.pipeline.get_player_fixture_base", return_value=pd.DataFrame()),
        patch("dal.pipeline.build_player_gameweek_spine", side_effect=RuntimeError("grain duplicates detected")),
    ):
        result = build(db_path=db, force=True)

    error_msg = result["layers"]["fct"].get("error", "")
    assert "grain duplicates detected" in error_msg
