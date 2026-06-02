import pandas as pd
import pytest

from signals.characterisation.registry_build_contracts import (
    PreparedDatasetContract,
    normalize_signal_config,
    validate_prepared_dataset,
)

pytestmark = pytest.mark.unit


def _prepared_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": [1, 1, 2, 2],
            "position": ["MID", "MID", "FWD", "FWD"],
            "gw": [1, 2, 1, 3],
            "bps": [10, 12, 6, 9],
            "xgi": [0.3, 0.4, 0.1, 0.2],
            "total_points": [5, 7, 2, 4],
        }
    )


def test_validate_prepared_dataset_requires_core_columns():
    data = _prepared_data().drop(columns=["player_id"])

    with pytest.raises(ValueError, match="prepared data missing required columns"):
        validate_prepared_dataset(data, signals=["bps"], data_cutoff_gw=2)


def test_normalize_signal_config_rejects_invalid_signals():
    with pytest.raises(ValueError, match="at least one signal"):
        normalize_signal_config([])

    with pytest.raises(ValueError, match="non-empty signal"):
        normalize_signal_config(["bps", " "])

    with pytest.raises(ValueError, match="duplicate signals"):
        normalize_signal_config(["bps", "bps"])


def test_validate_prepared_dataset_rejects_missing_signal_columns():
    with pytest.raises(ValueError, match="prepared data missing required columns"):
        validate_prepared_dataset(_prepared_data(), signals=["missing"], data_cutoff_gw=2)


def test_validate_prepared_dataset_requires_valid_gameweek_values():
    data = _prepared_data()
    data["gw"] = data["gw"].astype(object)
    data.loc[0, "gw"] = "future"

    with pytest.raises(ValueError, match="non-numeric gameweek values"):
        validate_prepared_dataset(data, signals=["bps"], data_cutoff_gw=2)


def test_validate_prepared_dataset_filters_future_rows():
    result = validate_prepared_dataset(
        _prepared_data(),
        signals=["bps", "xgi"],
        data_cutoff_gw=2,
    )

    assert len(result) == 3
    assert result["gw"].max() == 2
    assert set(result["player_id"]) == {1, 2}


def test_validate_prepared_dataset_rejects_invalid_positions():
    data = _prepared_data()
    data.loc[0, "position"] = "MANAGER"

    with pytest.raises(ValueError, match="invalid positions"):
        validate_prepared_dataset(data, signals=["bps"], data_cutoff_gw=2)


def test_validate_prepared_dataset_rejects_invalid_population_scope():
    contract = PreparedDatasetContract(population_scope="experimental")

    with pytest.raises(ValueError, match="invalid population_scope"):
        validate_prepared_dataset(
            _prepared_data(),
            signals=["bps"],
            data_cutoff_gw=2,
            contract=contract,
        )


def test_validate_prepared_dataset_enforces_minimum_cutoff_support():
    data = _prepared_data()
    data["gw"] = 3

    with pytest.raises(ValueError, match="insufficient rows"):
        validate_prepared_dataset(data, signals=["bps"], data_cutoff_gw=2)

    contract = PreparedDatasetContract(min_non_null_signal_rows=4)
    with pytest.raises(ValueError, match="insufficient non-null signal rows"):
        validate_prepared_dataset(
            _prepared_data(),
            signals=["bps"],
            data_cutoff_gw=2,
            contract=contract,
        )
