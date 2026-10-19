"""Drift guard: domain/fpl_squad.py's STAGED constants match FPL's own element_types declaration.

The squad constants live in `domain/`, sourced from element_types with a drift test rather than
hardcoded in the slice. This is that test. It reads the staged frame through
`dal/staging` rather than the YAML contract, because the contract maps columns while the *values*
live in the database.

The GKP→GK mapping is performed here, explicitly: `element_types` declares `position_label`
(GKP/DEF/MID/FWD) while the constants are keyed on `position` (GK/DEF/MID/FWD), the vocabulary
the slice uses. Doing the mapping in the test rather than in the module
keeps the module's keys the ones its consumers use.

MAX_PER_CLUB and BUDGET_CAP are not asserted: no table in this repository carries either, which
is why both are annotated UNVERIFIED at their definitions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dal.staging.stg_entities import get_staged_element_types
from domain import fpl_squad

pytestmark = pytest.mark.unit

# element_types' own vocabulary -> the vocabulary the constants are keyed on.
LABEL_TO_POSITION = {"GKP": "GK", "DEF": "DEF", "MID": "MID", "FWD": "FWD"}


def _declared(db_path: Path, column: str) -> dict[str, int]:
    staged = get_staged_element_types(db_path)
    return {LABEL_TO_POSITION[row.position_label]: int(getattr(row, column)) for row in staged.itertuples()}


def test_squad_select_matches_element_types(db_path: Path) -> None:
    assert dict(fpl_squad.SQUAD_SELECT) == _declared(db_path, "squad_select")


def test_xi_bounds_match_element_types(db_path: Path) -> None:
    assert dict(fpl_squad.XI_MIN_PLAY) == _declared(db_path, "squad_min_play")
    assert dict(fpl_squad.XI_MAX_PLAY) == _declared(db_path, "squad_max_play")


@pytest.mark.covers("#43 AC2")
def test_position_ids_match_element_types(db_path: Path) -> None:
    staged = get_staged_element_types(db_path)
    declared = {int(row.position_code): LABEL_TO_POSITION[row.position_label] for row in staged.itertuples()}
    assert dict(fpl_squad.POSITION_BY_ID) == declared


def test_sizes_are_consistent_with_the_quota_and_bounds() -> None:
    assert fpl_squad.SQUAD_SIZE == sum(fpl_squad.SQUAD_SELECT.values())
    assert set(fpl_squad.POSITIONS) == set(fpl_squad.SQUAD_SELECT)
    assert sum(fpl_squad.XI_MIN_PLAY.values()) <= fpl_squad.XI_SIZE <= sum(fpl_squad.XI_MAX_PLAY.values())
    # Every 2/5/5/3 squad admits at least one legal XI, which is why the sampler needs no
    # formation check at draw time.
    for position, quota in fpl_squad.SQUAD_SELECT.items():
        assert quota >= fpl_squad.XI_MIN_PLAY[position]


def test_budget_cap_tenths_matches_the_float_cap() -> None:
    assert fpl_squad.BUDGET_CAP_TENTHS == round(fpl_squad.BUDGET_CAP * 10)


def test_the_constants_are_immutable() -> None:
    with pytest.raises(TypeError):
        fpl_squad.SQUAD_SELECT["GK"] = 3  # type: ignore[index]


@pytest.mark.covers("#33 AC4 (proposed)")
def test_prices_convert_to_exact_integer_tenths() -> None:
    assert fpl_squad.price_in_tenths(np.array([4.5, 10.0, 14.1])).tolist() == [45, 100, 141]
    assert int(fpl_squad.price_in_tenths(5.5)) == 55


@pytest.mark.covers("#33 AC4 (proposed)")
@pytest.mark.parametrize("price", [5.55, float("nan")])
def test_a_price_not_quoted_in_tenths_is_refused(price: float) -> None:
    with pytest.raises(ValueError, match="tenths"):
        fpl_squad.price_in_tenths(np.array([5.0, price]))
