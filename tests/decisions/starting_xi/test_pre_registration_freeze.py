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
    "stage5_verdict": {
        "groups": ["overall", "top", "middle", "bottom"],
        "sides": 2,
        "null_share": 0.5,
        "family_wise_alpha": 0.05,
        "p_value": "one_plus_k_over_one_plus_b",
        "n_resamples": 10000,
        "seed": 0,
        "rerun_resamples": 100000,
        "rerun_seed": 1,
    },
    "power_lab": {
        "true_win_shares": [0.51, 0.52, 0.53, 0.55, 0.58, 0.60],
        "tie_rates": [0.2, 0.4, 0.6],
        "effect_levels": ["small", "medium", "large"],
        "shock_sd_points": {"small": 2, "medium": 4, "large": 6},
        "manager_effect_sd_points": {"small": 5, "medium": 10, "large": 15},
        "gameweek_sweep": [5, 8, 12, 16, 24, 38],
        "manager_sweep": [500, 1000, 2000],
        "baseline": {"shock": "medium", "manager_effect": "medium", "tie_rate": 0.4, "gameweeks": 5, "managers": 2000},
        "worst_case_corner": {
            "shock": "large",
            "manager_effect": "large",
            "tie_rate": 0.6,
            "gameweeks": 5,
            "managers": 2000,
        },
        "settings": [
            "baseline",
            "shock_small",
            "shock_large",
            "manager_effect_small",
            "manager_effect_large",
            "ties_20",
            "ties_60",
            "gameweeks_8",
            "gameweeks_12",
            "gameweeks_16",
            "gameweeks_24",
            "gameweeks_38",
            "managers_500",
            "managers_1000",
            "worst_case_corner",
            "worst_case_corner_gameweeks_8",
            "worst_case_corner_gameweeks_12",
            "worst_case_corner_gameweeks_16",
            "worst_case_corner_gameweeks_24",
            "worst_case_corner_gameweeks_38",
            "worst_case_corner_managers_500",
            "worst_case_corner_managers_1000",
        ],
        "fake_studies": 1000,
        "inner_resamples": 10000,
        "false_alarm_max_firings": 63,
        "sensitivity": {"setting": "worst_case_corner", "share": 0.65, "min_power": 0.99},
        "pass_mark": 0.8,
        "headline_edge": 0.55,
        "secondary_edge": 0.53,
        "master_seed": 60,
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


@pytest.mark.covers("#60 AC5")
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("stage5_verdict", "family_wise_alpha"), 0.1),
        (("stage5_verdict", "sides"), 1),
        (("stage5_verdict", "groups"), ["overall", "top", "bottom"]),
        (("stage5_verdict", "n_resamples"), 5000),
        (("stage5_verdict", "seed"), 7),
        (("stage5_verdict", "rerun_resamples"), 10000),
        (("stage5_verdict", "rerun_seed"), 0),
        (("power_lab", "true_win_shares"), [0.51, 0.52, 0.53, 0.55, 0.58]),
        (("power_lab", "tie_rates"), [0.2, 0.4]),
        (("power_lab", "shock_sd_points"), {"small": 2, "medium": 3, "large": 6}),
        (("power_lab", "manager_effect_sd_points"), {"small": 5, "medium": 10, "large": 20}),
        (("power_lab", "gameweek_sweep"), [5, 8, 12, 16, 24, 36]),
        (("power_lab", "manager_sweep"), [500, 1000, 1998]),
        (("power_lab", "baseline"), {**FROZEN_DESIGN["power_lab"]["baseline"], "managers": 1998}),
        (("power_lab", "worst_case_corner"), {**FROZEN_DESIGN["power_lab"]["worst_case_corner"], "tie_rate": 0.4}),
        (("power_lab", "settings"), FROZEN_DESIGN["power_lab"]["settings"][:-1]),
        (("power_lab", "fake_studies"), 2000),
        (("power_lab", "inner_resamples"), 2000),
        (("power_lab", "false_alarm_max_firings"), 64),
        (("power_lab", "sensitivity"), {**FROZEN_DESIGN["power_lab"]["sensitivity"], "min_power": 0.95}),
        (("power_lab", "pass_mark"), 0.9),
        (("power_lab", "headline_edge"), 0.58),
        (("power_lab", "master_seed"), 0),
    ],
    ids=lambda part: "/".join(part) if isinstance(part, tuple) else None,
)
def test_changing_any_one_stage5_verdict_or_lab_value_is_a_named_mismatch(path: tuple[str, ...], value: object) -> None:
    mismatches = starting_xi.pre_registration_mismatches(**CANONICAL_RUN, pre_registration=_mutate(path, value))
    assert [m.split(":")[0] for m in mismatches] == [path[0]]


@pytest.mark.covers("#60 AC5")
def test_the_lab_grid_is_one_dimension_at_a_time_around_the_baseline_plus_the_corner_sweeps() -> None:
    from decisions.starting_xi import power_lab

    base, corner = power_lab.BASELINE, power_lab.WORST_CASE_CORNER
    for setting in power_lab.SETTINGS:
        anchor = corner if setting.name.startswith("worst_case_corner") else base
        fields = ("shock", "manager_effect", "tie_rate", "gameweeks", "managers")
        differing = [f for f in fields if getattr(setting, f) != getattr(anchor, f)]
        assert len(differing) <= 1, (setting.name, differing)
        if anchor is corner:
            assert differing in ([], ["gameweeks"], ["managers"]), setting.name


@pytest.mark.covers("#60 AC5")
def test_the_false_alarm_count_is_recomputed_for_the_registered_number_of_fake_studies() -> None:
    from decisions.starting_xi import power_report

    lab = yaml.safe_load(PRE_REGISTRATION_PATH.read_text())["power_lab"]
    assert power_report.false_alarm_max_firings(lab["fake_studies"]) == lab["false_alarm_max_firings"]


@pytest.mark.covers("#60 AC5")
def test_the_stage5_window_is_the_frozen_scored_gameweeks_from_gw4() -> None:
    registered = yaml.safe_load(PRE_REGISTRATION_PATH.read_text())
    assert registered["scored_gameweeks"]["first_gw"] == 4 == rankers.RULE_WINDOW[0]
