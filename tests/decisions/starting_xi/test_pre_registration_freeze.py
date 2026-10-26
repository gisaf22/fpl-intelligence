"""Freeze test for `PRE_REGISTRATION.yaml`: the Stage 3 test design frozen on 2026-10-17 (CARD.md §3).

The file is a mirror, not a config: the code owns each value, and the pre-run check
(`operational.starting_xi.pre_registration_mismatches`) compares a run and the code against it.
This test pins the file to the frozen design and shows that the check catches a change to any one
pinned value.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from decisions.starting_xi import orderings, rankers
from operational import starting_xi

pytestmark = pytest.mark.unit

PRE_REGISTRATION_PATH = Path(__file__).resolve().parents[3] / "decisions" / "starting_xi" / "PRE_REGISTRATION.yaml"

FROZEN_DESIGN: dict[str, Any] = {
    "rules": [
        "ppg_appearance_last3",
        "ppg_appearance_season",
        "ppg_fixture_last3",
        "ppg_fixture_season",
        "ppg_gameweek_last3",
        "ppg_gameweek_season",
        "ppg_start_last3",
        "ppg_start_season",
        "random",
        "starts_rate_x_points_per_appearance",
    ],
    "scored_gameweeks": {"first_gw": 4, "last_gw": 38},
    "phases": {"4-12": [4, 12], "13-26": [13, 26], "27-38": [27, 38]},
    "squad_modes": ["uniform", "ownership"],
    "squads_per_gameweek": 300,
    "construction": "weekly",
    "master_seed": 0,
    "bench_ordering": ["by_rank"],
    "gameweek_interval": {"n": 10000, "block": 4, "ci_level": 0.95, "seed": 0},
    "deadline_fallback_sensitivity": {
        "run": "excluding_deadline_fallback_weeks",
        "excludes": "deadline_count_is_realised",
        "holm_family": False,
    },
}

CANONICAL_RUN: dict[str, Any] = {
    "bench_order": orderings.PRE_REGISTERED_ORDERINGS,
    "rank_fns": rankers.rules(0),
    "gameweeks": range(4, 39),
    "n_squads": 300,
    "seed": 0,
}


def _mutate(path: tuple[str, ...], value: object) -> dict[str, Any]:
    changed = copy.deepcopy(FROZEN_DESIGN)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


@pytest.mark.covers("#33 AC1")
def test_the_file_holds_the_frozen_stage_3_design() -> None:
    assert yaml.safe_load(PRE_REGISTRATION_PATH.read_text()) == FROZEN_DESIGN


@pytest.mark.covers("#33 AC1")
def test_a_canonical_run_matches_the_file() -> None:
    registered = yaml.safe_load(PRE_REGISTRATION_PATH.read_text())
    assert starting_xi.pre_registration_mismatches(**CANONICAL_RUN, pre_registration=registered) == []


@pytest.mark.covers("#33 AC1")
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("rules",), FROZEN_DESIGN["rules"][:-1]),
        (("rules",), [*FROZEN_DESIGN["rules"][:-1], "starts_rate"]),
        (("scored_gameweeks", "first_gw"), 3),
        (("scored_gameweeks", "last_gw"), 37),
        (("phases", "4-12"), [4, 13]),
        (("squad_modes",), ["uniform"]),
        (("squads_per_gameweek",), 299),
        (("construction",), "build_once"),
        (("master_seed",), 1),
        (("bench_ordering",), ["by_weighted_score"]),
        (("gameweek_interval", "n"), 1000),
        (("gameweek_interval", "block"), 3),
        (("gameweek_interval", "ci_level"), 0.9),
        (("gameweek_interval", "seed"), 1),
    ],
    ids=lambda part: "/".join(part) if isinstance(part, tuple) else None,
)
def test_changing_any_one_pinned_value_is_a_named_mismatch(path: tuple[str, ...], value: object) -> None:
    mismatches = starting_xi.pre_registration_mismatches(**CANONICAL_RUN, pre_registration=_mutate(path, value))
    assert [m.split(":")[0] for m in mismatches] == [path[0]]


@pytest.mark.covers("#59 AC4a")
def test_the_file_declares_the_deadline_fallback_sensitivity_run() -> None:
    registered = yaml.safe_load(PRE_REGISTRATION_PATH.read_text())
    assert registered["deadline_fallback_sensitivity"] == FROZEN_DESIGN["deadline_fallback_sensitivity"]


@pytest.mark.covers("#59 AC4a")
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("run", "headline"),
        ("excludes", "uncovered_blank"),
        ("holm_family", True),
    ],
)
def test_changing_the_sensitivity_run_its_exclusion_or_its_holm_place_is_a_named_mismatch(
    key: str, value: object
) -> None:
    mismatches = starting_xi.pre_registration_mismatches(
        **CANONICAL_RUN, pre_registration=_mutate(("deadline_fallback_sensitivity", key), value)
    )
    assert [m.split(":")[0] for m in mismatches] == ["deadline_fallback_sensitivity"]
