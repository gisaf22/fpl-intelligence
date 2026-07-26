"""Tests for the scoring-rule conformance guard (model.eval.scoring_conformance).

The guard's job: catch the class of bug the saves gap belonged to — ``compose`` applying a nonlinear
scoring rule to an expectation (``rule(E[X])``) where the expectation of the rule (``E[rule(X)]``) is
required. Ground truth is the simulator's per-component draw mean.
"""

from __future__ import annotations

import numpy as np
import pytest

import model.compose as compose_mod
from model.eval.scoring_conformance import (
    NONCONFORMING_TERMS,
    assert_conformance,
    scoring_conformance,
)
from model.simulate import DECOMP_TERMS
from tests._synthetic_mart import points_panel as _panel

pytestmark = pytest.mark.unit


def test_every_exact_term_conforms_and_bonus_is_the_only_exception() -> None:
    """On a fixed synthetic panel, every asserted term equals the simulator's E[rule] to within MC
    error; ``bonus`` (clip(E) vs E[clip]) is the sole reported non-conformer."""
    table = scoring_conformance(_panel(seed=0), n_sims=2000, seed=0)
    asserted = table[table["asserted"]]
    assert asserted["conforms"].astype(bool).all(), (
        "an exactly-computed term drifted from the simulator:\n"
        + asserted[~asserted["conforms"].astype(bool)].to_string(index=False)
    )
    # bonus is present and flagged not-asserted (its Jensen residual is real, not zero)
    assert set(table.loc[~table["asserted"], "term"]) == set(NONCONFORMING_TERMS)
    assert (table["term"].isin(DECOMP_TERMS)).all()


def test_assert_conformance_passes_on_the_shipped_model() -> None:
    """The guard must be GREEN on the shipped model — otherwise it is not a usable regression gate."""
    table = assert_conformance(_panel(seed=1), n_sims=2000, seed=0)
    assert not table.empty


def test_guard_trips_when_a_nonlinear_rule_is_reduced_to_rule_of_expectation(monkeypatch) -> None:
    """Reintroduce exactly the saves bug — score E[S]/3 instead of E[floor(S/3)] — and the guard must
    catch it. This is the proof the check has teeth: the draw path is untouched (still floors), so only
    compose diverges, which is precisely the rule(E) vs E[rule] failure mode."""
    from domain.fpl_scoring import GK_SAVES_PER_POINT

    # the pre-fix (wrong) conversion: the payout of the expectation, not the expectation of the payout
    monkeypatch.setattr(compose_mod, "saves_points_expectation",
                        lambda e_saves: np.asarray(e_saves, dtype=float) / GK_SAVES_PER_POINT)

    with pytest.raises(AssertionError, match="non-conformance"):
        assert_conformance(_panel(seed=0), n_sims=2000, seed=0)

    # and it must point at the right (position, term): GK saves, not something else
    table = scoring_conformance(_panel(seed=0), n_sims=2000, seed=0)
    broken = table[(table["asserted"]) & (~table["conforms"].astype(bool))]
    assert list(zip(broken["position"], broken["term"], strict=True)) == [("GK", "saves")]
