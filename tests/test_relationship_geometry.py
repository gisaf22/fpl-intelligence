import numpy as np
import pandas as pd
import pytest

from research.foundation.joint import _joint_helpers
from research.kernels.geometry import (
    FDR_ORDINAL_BINS,
    FDR_ORDINAL_LABELS,
    bin_analysis,
    classify_geometry,
    select_bucketing_scheme,
    stability_classify,
)

pytestmark = pytest.mark.unit


def _bin_stats(means: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bin": [f"b{i}" for i in range(len(means))],
            "mean": means,
            "count": [25] * len(means),
        }
    )


def test_select_bucketing_scheme_routes_fdr_to_ordinal_before_discrete():
    series = pd.Series([1, 2, 3, 4, 5] * 25)

    scheme_type, param = select_bucketing_scheme(series, signal_name="fdr_avg")

    assert scheme_type == "ordinal"
    assert param == (FDR_ORDINAL_BINS, FDR_ORDINAL_LABELS)


def test_select_bucketing_scheme_handles_sparse_and_quantile_cases():
    sparse = pd.Series([0, 1, 2] * 40)
    continuous = pd.Series(np.arange(120))

    assert select_bucketing_scheme(sparse)[0] == "discrete"
    assert select_bucketing_scheme(continuous)[0] == "quantile"


def test_bin_analysis_uses_scheme_specific_active_bin_thresholds():
    df = pd.DataFrame(
        {
            "position": ["MID"] * 120,
            "signal": [0] * 40 + [1] * 40 + [2] * 40,
            "target": [1] * 40 + [2] * 40 + [3] * 40,
        }
    )

    bin_stats, flag = bin_analysis(
        df,
        signal="signal",
        target="target",
        position="MID",
        scheme=select_bucketing_scheme(df["signal"]),
    )

    assert flag == ""
    assert bin_stats is not None
    assert len(bin_stats) == 3


def test_classify_geometry_controlled_shapes():
    assert classify_geometry(_bin_stats([1, 2, 3, 4])) == "monotonic_positive"
    assert classify_geometry(_bin_stats([4, 3, 2, 1])) == "monotonic_negative"
    assert classify_geometry(_bin_stats([1, 1, 1, 4])) == "threshold_positive"
    assert classify_geometry(_bin_stats([1, 4, 4, 4])) == "threshold_negative"
    assert classify_geometry(_bin_stats([1, 4, 2, 5])) == "non_monotonic"


def test_stability_classify_gap_patterns():
    assert stability_classify(2.0, {"early": 2.0, "mid": 1.5, "late": 2.5}) == "stable"
    assert stability_classify(2.0, {"early": 2.0, "mid": 0.5, "late": 2.5}) == "moderate_shift"
    assert stability_classify(2.0, {"early": 2.0, "mid": -1.0, "late": 2.5}) == "unstable"
    assert stability_classify(np.nan, {"early": 2.0, "mid": None, "late": None}) == "insufficient_data"


def test_notebook_helper_imports_shared_geometry_functions():
    import research.foundation.joint.association as association
    import research.kernels.correlation.panel as panel
    import research.kernels.correlation.tail as tail
    import research.kernels.geometry as geometry

    assert _joint_helpers.select_bucketing_scheme is geometry.select_bucketing_scheme
    assert _joint_helpers.bin_analysis is geometry.bin_analysis
    assert _joint_helpers.classify_geometry is geometry.classify_geometry
    assert _joint_helpers.stability_classify is geometry.stability_classify
    assert _joint_helpers.decompose_rho is panel.decompose_rho
    assert _joint_helpers.haul_concentration is tail.haul_concentration
    assert _joint_helpers.assign_association_class is association.assign_association_class
    assert _joint_helpers.consolidate_flags is association.consolidate_flags
