"""Tests for the Phase 2.1 over-dispersion diagnosis (model.forecast.count_models)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.forecast.count_models import (
    COUNT_COMPONENTS,
    diagnose_by_position,
    diagnose_overdispersion,
)

pytestmark = pytest.mark.unit


def test_poisson_data_reads_as_poisson() -> None:
    rng = np.random.default_rng(0)
    y = rng.poisson(0.3, size=4000)
    d = diagnose_overdispersion(y)
    assert d["family"] == "poisson"
    assert 0.85 < d["dispersion_index"] < 1.2
    assert not d["material_overdispersion"]


def test_overdispersed_data_reads_as_nb() -> None:
    # Negative-binomial-like: Poisson mixed over a Gamma rate → Var >> Mean.
    rng = np.random.default_rng(1)
    lam = rng.gamma(shape=0.5, scale=1.0, size=4000)  # heterogeneous rate
    y = rng.poisson(lam)
    d = diagnose_overdispersion(y)
    assert d["dispersion_index"] > 1.5
    assert d["material_overdispersion"]
    assert d["family"] in ("negative_binomial", "zero_inflated")
    assert d["lrt_p"] < 0.05


def test_insufficient_rows() -> None:
    d = diagnose_overdispersion(np.array([0, 1, 0, 2, 0]))
    assert d["family"] == "insufficient"
    assert np.isnan(d["mean"])


def test_diagnose_by_position_structure() -> None:
    rng = np.random.default_rng(2)
    rows = []
    for p in range(120):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        for gw in range(1, 20):
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "goals_scored": rng.poisson(0.1), "assists": rng.poisson(0.1),
            })
    res = diagnose_by_position(pd.DataFrame(rows))
    assert res.index.names == ["position", "component"]
    # GK is skipped for attacking components.
    assert "GK" not in set(res.index.get_level_values("position"))
    assert set(res.index.get_level_values("component")) == set(COUNT_COMPONENTS)
