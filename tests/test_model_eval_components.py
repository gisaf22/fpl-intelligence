"""Tests for the reusable eval components (population, metrics, baselines.expanding_prior_mean, scorer)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval import baselines, metrics, population
from model.eval.scorer import GateResult, score_gate, score_gates

pytestmark = pytest.mark.unit


def _mart(n_players: int = 40, n_gw: int = 12, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        skill = rng.uniform(0, 4)
        for gw in range(1, n_gw + 1):
            played = rng.random() < 0.85
            rows.append({
                "player_id": p, "gw": gw, "position": ["GK", "DEF", "MID", "FWD"][p % 4],
                "minutes": 90 if played else 0, "is_dgw": False,
                "total_points": max(0, int(rng.normal(skill, 2))) if played else 0,
            })
    return pd.DataFrame(rows)


def test_population_canonical_and_full_universe() -> None:
    m = _mart()
    cano = population.canonical(m)
    assert (cano["minutes"] > 0).all() and (~cano["is_dgw"]).all()
    full = population.full_universe(m)
    assert len(full) >= len(cano)                                  # full retains blanks
    assert (full["minutes"] == 0).any()


def test_expanding_prior_mean_matches_inline_lambda() -> None:
    cano = population.canonical(_mart())
    new = baselines.expanding_prior_mean(cano)
    old = cano.groupby("player_id")["total_points"].transform(lambda s: s.expanding().mean().shift(1))
    assert np.allclose(new.fillna(-999), old.fillna(-999))          # single source == the old inline form


def test_grouped_spearman_and_series() -> None:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"gw": np.repeat([1, 2, 3], 30), "pred": rng.normal(size=90)})
    df["tgt"] = df["pred"] + rng.normal(0, 0.1, size=90)            # strong positive rank corr
    series = metrics.grouped_spearman_series(df, "pred", "tgt", ["gw"], min_n=10)
    assert len(series) == 3 and (series > 0.8).all()
    assert abs(metrics.grouped_spearman(df, "pred", "tgt", ["gw"], 10) - series.mean()) < 1e-12


def test_block_bootstrap_ci_brackets_and_degenerate() -> None:
    lo, hi = metrics.block_bootstrap_ci(np.full(20, 0.3))
    assert lo == pytest.approx(0.3) and hi == pytest.approx(0.3)    # constant series -> point interval
    lo2, hi2 = metrics.block_bootstrap_ci(np.arange(20.0))
    assert lo2 <= np.arange(20.0).mean() <= hi2
    assert np.isnan(metrics.block_bootstrap_ci(np.array([1.0, 2.0]))).all()  # too short -> nan


def test_precision_and_ndcg_perfect_and_bounds() -> None:
    actual = np.array([10.0, 8, 6, 4, 2, 0])
    assert metrics.precision_at_k(actual, actual, 3) == 1.0         # perfect prediction
    assert metrics.ndcg_at_k(actual, actual, 3) == pytest.approx(1.0)
    assert 0 <= metrics.precision_at_k(actual[::-1], actual, 3) <= 1


def test_score_gate_preserves_estimate_and_adds_ci_coverage() -> None:
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "gw": np.repeat(np.arange(1, 9), 20), "position": "DEF",
        "pred": rng.normal(size=160),
    })
    df["total_points"] = df["pred"] + rng.normal(0, 0.5, size=160)
    out = score_gate(df, "pred", "model A")
    r = out.iloc[0]
    # estimate equals the underlying grouped_spearman; CI brackets it; coverage full
    assert abs(r["spearman"] - round(metrics.grouped_spearman(df, "pred", "total_points", ["gw"], 10), 4)) < 1e-9
    assert r["ci_lo"] <= r["spearman"] <= r["ci_hi"]
    assert r["coverage"] == 1.0 and set(out.columns) >= {"ci_lo", "ci_hi", "coverage", "n_gw"}
    assert GateResult.__dataclass_params__.frozen


def test_score_gates_stacks_and_sorts() -> None:
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"gw": np.repeat(np.arange(1, 7), 20), "position": "MID",
                       "good": rng.normal(size=120)})
    df["total_points"] = df["good"] + rng.normal(0, 0.3, size=120)
    df["noise"] = rng.normal(size=120)
    out = score_gates(df, {"good": "signal", "noise": "noise"})
    assert set(out["model"]) == {"signal", "noise"}
    # within MID, the signal ranks above the noise (sorted by spearman desc)
    assert out.iloc[0]["model"] == "signal"


# --------------------------------------------------------------------------------------------
# Level (calibration) metrics — the gate criterion that ranking metrics are structurally blind to
# --------------------------------------------------------------------------------------------

def test_clustered_ci_is_wider_than_iid_when_errors_repeat_within_player() -> None:
    """The reason to cluster: a player the model misjudges is misjudged EVERY week, so the
    effective sample is players, not player-GWs. An i.i.d. interval would overstate precision."""
    rng = np.random.default_rng(0)
    n_players, n_gw = 30, 20
    player_effect = rng.normal(0, 1.0, n_players)          # persistent per-player error
    values, clusters = [], []
    for p in range(n_players):
        values.extend(player_effect[p] + rng.normal(0, 0.1, n_gw))
        clusters.extend([p] * n_gw)
    values, clusters = np.asarray(values), np.asarray(clusters)

    _, lo, hi = metrics.clustered_mean_ci(values, clusters)
    clustered_width = hi - lo
    # pretend every row is independent
    _, lo_i, hi_i = metrics.clustered_mean_ci(values, np.arange(len(values)))
    iid_width = hi_i - lo_i
    assert clustered_width > 2 * iid_width, (
        f"clustering must widen the interval materially: {clustered_width:.3f} vs {iid_width:.3f}")


def test_position_bias_flags_a_material_bias_and_clears_an_honest_model() -> None:
    rng = np.random.default_rng(1)
    n = 600
    target = rng.poisson(0.5, n).astype(float)
    df = pd.DataFrame({
        "player_id": np.repeat(np.arange(n // 10), 10),
        "position": "FWD",
        "target": target,
        "honest": np.full(n, target.mean()),          # right level
        "biased": np.full(n, target.mean() * 1.6),    # 60% too high — well past the 10% floor
    })
    ok = metrics.position_bias(df, "honest", "target").iloc[0]
    bad = metrics.position_bias(df, "biased", "target").iloc[0]
    assert ok["ok"] and not ok["material"]
    assert not bad["ok"] and bad["material"] and bad["detectable"]
    assert bad["rel_bias"] == pytest.approx(0.6, abs=0.05)


def test_position_bias_treats_a_structurally_zero_target_as_material() -> None:
    """A position whose target is structurally zero (keepers and goals) does not belong in the
    model's population at all — ANY non-zero prediction is material, and relative bias is undefined."""
    df = pd.DataFrame({
        "player_id": np.arange(200) // 5,
        "position": "GK",
        "target": np.zeros(200),
        "pred": np.full(200, 0.06),
    })
    row = metrics.position_bias(df, "pred", "target").iloc[0]
    assert row["material"] and not row["ok"]
    assert np.isnan(row["rel_bias"])


def test_gate_result_passed_all_requires_both_criteria() -> None:
    """A term is only sound where it ranks AND levels — ranking alone must not carry a position."""
    from model.terms._base import GateResult as TermGateResult
    g = TermGateResult(
        term="t", table=pd.DataFrame(), passed={"DEF": True, "MID": True},
        calibration=pd.DataFrame(), passed_calibration={"DEF": False, "MID": True},
    )
    assert g.passed_all == {"DEF": False, "MID": True}
