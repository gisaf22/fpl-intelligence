"""Tests for `realism.py`: the Stage 5 realism check's measuring function and `REALISM.md` writer (#66).

Every feed is built by hand; nothing here reads a data layer or runs the lab.
"""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pandas as pd
import pytest
import yaml

from decisions.starting_xi import power_lab, realism, verdict
from decisions.starting_xi.power_report import ShockLevel
from operational import starting_xi_power_lab

pytestmark = pytest.mark.unit

RESULTS_DIR = Path(__file__).resolve().parents[3] / "decisions" / "starting_xi" / "power_lab_results"
PRE_REGISTRATION_PATH = RESULTS_DIR.parent / "PRE_REGISTRATION.yaml"
# REPORT.md's SHA-256 as recorded in https://github.com/gisaf22/fpl-intelligence/pull/68.
REPORT_SHA256 = "8db7a7cf5b004a4974cffcaec4df5678935296224d83d2de4b1dc002d8ebf668"

VERDICT_WINDOW = tuple(range(4, 16))  # GW4-GW15, #55 D-N3
# The levels #65 prints: 9 points at 8, 12 and 16 gameweeks; 6 at 24 and 38; none at 5.
LEVELS_65 = [
    ShockLevel(5, None, None),
    ShockLevel(8, 9, None),
    ShockLevel(12, 9, None),
    ShockLevel(16, 9, None),
    ShockLevel(24, 6, "not probed at 9"),
    ShockLevel(38, 6, "not probed at 9"),
]


def _feed(shares: dict[int, float], managers: int = 10, band: str = "top") -> pd.DataFrame:
    """One row per manager-week: the first round(share x managers) managers win, the rest lose."""
    rows = []
    for gameweek, share in shares.items():
        wins = round(share * managers)
        for manager in range(managers):
            rows.append((manager + 1, gameweek, 1.0 if manager < wins else 0.0, band))
    return pd.DataFrame(rows, columns=list(verdict.COLUMNS))


def _window_feed(spread_shares: tuple[float, ...] = (0.4, 0.5, 0.6), managers: int = 10) -> pd.DataFrame:
    """A feed over the verdict window whose weekly shares cycle through `spread_shares`."""
    return _feed({g: spread_shares[i % len(spread_shares)] for i, g in enumerate(VERDICT_WINDOW)}, managers)


def _measurement(
    spread: float, gameweeks: tuple[int, ...] = VERDICT_WINDOW, managers: int = 1_900
) -> realism.Measurement:
    return realism.Measurement(
        gameweeks=gameweeks,
        spread_points=spread,
        panel_managers=managers,
        managers_per_gameweek=(managers,) * len(gameweeks),
    )


def _row_label(text: str, gameweeks: int) -> str:
    """The rendered table row for one gameweek count."""
    matches = [line for line in text.splitlines() if line.startswith(f"| {gameweeks} |")]
    assert len(matches) == 1, f"expected one row for {gameweeks} gameweeks, got {matches}"
    return matches[0]


def _labels(rows: list[realism.RowCheck]) -> dict[int, bool | None]:
    return {row.gameweeks: row.applies for row in rows}


# --- AC1: each gameweek count is labelled against its own level --------------------------------------


@pytest.mark.covers("#66 AC1")
def test_a_spread_of_7_against_a_level_of_6_labels_the_24_and_38_rows_only() -> None:
    labels = _labels(realism.label_rows(7.0, LEVELS_65))
    assert labels == {5: None, 8: True, 12: True, 16: True, 24: False, 38: False}


@pytest.mark.covers("#66 AC1")
def test_each_count_is_compared_with_its_own_level_not_another_counts() -> None:
    levels = [
        ShockLevel(5, None, None),
        *(ShockLevel(g, lvl, None) for g, lvl in ((8, 3), (12, 5), (16, 7), (24, 9), (38, 11))),
    ]
    labels = _labels(realism.label_rows(6.0, levels))
    assert labels == {5: None, 8: False, 12: False, 16: True, 24: True, 38: True}


@pytest.mark.covers("#66 AC1")
@pytest.mark.parametrize(("spread", "expected"), [(5.0, True), (10.0, False)])
def test_a_spread_within_or_beyond_every_level_labels_every_compared_row_alike(spread: float, expected: bool) -> None:
    labels = _labels(realism.label_rows(spread, LEVELS_65))
    assert labels == {5: None, **{g: expected for g in (8, 12, 16, 24, 38)}}


@pytest.mark.covers("#66 AC1")
def test_two_levels_for_one_count_are_refused() -> None:
    with pytest.raises(realism.RealismRefused, match="two levels for 24"):
        realism.label_rows(7.0, [*LEVELS_65, ShockLevel(24, 9, None)])


@pytest.mark.covers("#66 AC1")
def test_a_spread_equal_to_a_level_is_within_it() -> None:
    # "Beyond" is strictly greater: a count stays within the limit at its level (proposed at pick-up).
    assert _labels(realism.label_rows(6.0, LEVELS_65))[24] is True


@pytest.mark.covers("#66 AC1")
def test_the_invalid_count_has_no_level_no_comparison_and_no_label() -> None:
    text = realism.render(_measurement(50.0), LEVELS_65)
    row = _row_label(text, 5)
    assert "no level" in row
    assert "not applicable" not in row
    assert "not compared" in row


@pytest.mark.covers("#66 AC1")
def test_a_not_applicable_row_names_the_spread_and_the_level_it_is_beyond() -> None:
    row = _row_label(realism.render(_measurement(7.0), LEVELS_65), 24)
    assert "not applicable" in row
    assert "7.00" in row
    assert "6 points" in row


@pytest.mark.covers("#66 AC1")
def test_the_rough_uncertainty_is_printed_beside_the_estimate() -> None:
    text = realism.render(_measurement(7.0), LEVELS_65)
    relative = 1 / math.sqrt(2 * (len(VERDICT_WINDOW) - 1))
    assert realism.relative_uncertainty(12) == pytest.approx(relative)
    assert f"{relative:.0%}" in text  # about 21% at 12 gameweeks
    assert f"{7.0 * relative:.2f}" in text
    assert "1/sqrt(2(n-1))" in text


@pytest.mark.covers("#66 AC1")
def test_the_uncertainty_gates_no_label() -> None:
    # The same spread with far fewer gameweeks (a much wider uncertainty) labels the same rows.
    few = realism.render(_measurement(7.0, gameweeks=(4, 5, 6)), LEVELS_65)
    many = realism.render(_measurement(7.0), LEVELS_65)
    for gameweeks in (5, 8, 12, 16, 24, 38):
        assert _row_label(few, gameweeks) == _row_label(many, gameweeks)


# --- AC2: the 12-gameweek row is always stated --------------------------------------------------------


@pytest.mark.covers("#66 AC2")
@pytest.mark.parametrize(
    "measurement",
    [_measurement(3.0), _measurement(12.0), _measurement(7.0, gameweeks=(4, 5, 6, 7, 8, 9, 10))],
    ids=["within_its_level", "beyond_its_level", "fewer_than_12_scored_gameweeks"],
)
def test_the_12_gameweek_row_is_stated_in_every_case(measurement: realism.Measurement) -> None:
    _row_label(realism.render(measurement, LEVELS_65), 12)


@pytest.mark.covers("#66 AC2")
def test_levels_without_a_swept_count_are_refused_rather_than_leaving_its_row_out() -> None:
    without_12 = [level for level in LEVELS_65 if level.gameweeks != 12]
    with pytest.raises(realism.RealismRefused, match="12"):
        realism.render(_measurement(7.0), without_12)


# --- AC3: the weekly win share and its spread across gameweeks, no conversion ------------------------


@pytest.mark.covers("#66 AC3")
def test_weekly_shares_of_40_50_and_60_percent_give_a_spread_of_10_points() -> None:
    measured = realism.measure(_feed({4: 0.4, 5: 0.5, 6: 0.6}), gameweeks=(4, 5, 6))
    assert measured.spread_points == pytest.approx(10.0)


@pytest.mark.covers("#66 AC3")
def test_the_spread_follows_the_registered_ddof(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = _feed({4: 0.4, 5: 0.5, 6: 0.6})
    assert realism.SPREAD_DDOF == 1
    monkeypatch.setattr(realism, "SPREAD_DDOF", 0)
    assert realism.measure(feed, gameweeks=(4, 5, 6)).spread_points == pytest.approx(10 * math.sqrt(2 / 3))


@pytest.mark.covers("#66 AC3")
def test_ties_count_as_the_verdict_counts_them() -> None:
    # Week 4: all ties, a share of 50%. Week 5: half win, half lose, 50%. Week 6: all win, 100%.
    ties = pd.DataFrame(
        [(m, 4, 0.5, "top") for m in range(1, 11)]
        + [(m, 5, 1.0 if m <= 5 else 0.0, "top") for m in range(1, 11)]
        + [(m, 6, 1.0, "top") for m in range(1, 11)],
        columns=list(verdict.COLUMNS),
    )
    expected = pd.Series([50.0, 50.0, 100.0]).std(ddof=1)
    assert realism.measure(ties, gameweeks=(4, 5, 6)).spread_points == pytest.approx(expected)


@pytest.mark.covers("#66 AC3")
def test_a_feed_carrying_points_or_any_column_beyond_the_verdicts_is_refused() -> None:
    feed = _feed({4: 0.4, 5: 0.5}).assign(points=60)
    with pytest.raises(realism.RealismRefused, match="points"):
        realism.measure(feed, gameweeks=(4, 5))


@pytest.mark.covers("#66 AC3")
def test_a_feed_missing_a_verdict_column_is_refused() -> None:
    with pytest.raises(realism.RealismRefused, match="band"):
        realism.measure(_feed({4: 0.4, 5: 0.5}).drop(columns="band"), gameweeks=(4, 5))


@pytest.mark.covers("#66 AC3")
def test_an_outcome_the_verdict_would_not_count_is_refused() -> None:
    feed = _feed({4: 0.4, 5: 0.5})
    feed.loc[0, "outcome"] = 0.25
    with pytest.raises(realism.RealismRefused, match="outcome"):
        realism.measure(feed, gameweeks=(4, 5))


@pytest.mark.covers("#66 AC3")
def test_the_output_states_the_statistic_in_win_share_points_with_no_conversion() -> None:
    text = realism.render(_measurement(7.0), LEVELS_65)
    assert "spread across gameweeks of the weekly win share" in text
    assert "win-share points" in text
    assert "no conversion" in text


# --- AC5: the verdict window only; the lab stays free of data ----------------------------------------


@pytest.mark.covers("#66 AC5")
def test_the_verdict_window_is_gw4_to_gw15() -> None:
    assert realism.VERDICT_GAMEWEEKS == VERDICT_WINDOW


@pytest.mark.covers("#66 AC5")
def test_rows_outside_the_requested_gameweeks_do_not_move_the_spread() -> None:
    inside = _window_feed()
    outside = pd.concat([_feed({3: 1.0, 16: 0.0, 20: 1.0}), inside], ignore_index=True)
    assert realism.measure(outside, gameweeks=VERDICT_WINDOW) == realism.measure(inside, gameweeks=VERDICT_WINDOW)


@pytest.mark.covers("#66 AC5")
def test_the_lab_modules_do_not_import_the_realism_module() -> None:
    program = (
        "import sys\n"
        "from decisions.starting_xi import power_lab, power_report\n"
        "print('decisions.starting_xi.realism' in sys.modules)\n"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    assert child.stdout.strip() == "False"


@pytest.mark.covers("#66 AC5")
def test_the_realism_module_reaches_no_data_layer() -> None:
    program = (
        "import sys\n"
        "import decisions.starting_xi.realism\n"
        "roots = ('dal', 'warehouse', 'model', 'serve')\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in roots))\n"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    assert child.stdout.strip() == "[]"


@pytest.mark.covers("#66 AC5")
def test_running_the_check_changes_no_registered_setting(tmp_path: Path) -> None:
    realism.write(tmp_path, realism.measure(_window_feed(), gameweeks=VERDICT_WINDOW), LEVELS_65)
    registered = yaml.safe_load(PRE_REGISTRATION_PATH.read_text())
    assert starting_xi_power_lab.pre_registration_mismatches(registered) == []


# --- AC6: the realism module writes REALISM.md; REPORT.md stays byte-identical -----------------------


@pytest.mark.covers("#66 AC6")
def test_the_committed_levels_are_read_from_the_labs_committed_cells() -> None:
    assert realism.committed_levels(RESULTS_DIR / "cells") == LEVELS_65


@pytest.mark.covers("#66 AC6")
def test_the_writer_puts_realism_md_next_to_the_report(tmp_path: Path) -> None:
    path = realism.write(tmp_path, _measurement(7.0), LEVELS_65)
    assert path == tmp_path / "REALISM.md"
    assert path.read_text() == realism.render(_measurement(7.0), LEVELS_65)


@pytest.mark.covers("#66 AC6")
def test_realism_md_states_every_required_item() -> None:
    measurement = _measurement(7.0)
    text = realism.render(measurement, LEVELS_65)
    assert "spread across gameweeks of the weekly win share" in text  # the statistic
    for gameweeks in power_lab.GAMEWEEK_SWEEP:  # per count, whether the lab's row applies
        row = _row_label(text, gameweeks)
        assert "7.00" in row  # the compared values: the spread beside each level
    assert "applies" in _row_label(text, 8)
    assert "9 points" in _row_label(text, 8)
    assert "uncertainty" in text
    assert "sampling noise" in text
    assert all(re.search(rf"\bGW{g}\b", text) for g in VERDICT_WINDOW)  # the gameweeks used


@pytest.mark.covers("#66 AC6")
def test_the_committed_report_is_byte_identical_to_the_one_recorded_in_pr_68() -> None:
    assert hashlib.sha256((RESULTS_DIR / "REPORT.md").read_bytes()).hexdigest() == REPORT_SHA256


@pytest.mark.covers("#66 AC6")
def test_writing_realism_md_leaves_the_report_and_probe_untouched(tmp_path: Path) -> None:
    for name in ("REPORT.md", "PROBE.md"):
        shutil.copy(RESULTS_DIR / name, tmp_path / name)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    realism.write(tmp_path, _measurement(7.0), LEVELS_65)
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert set(after) == {*before, "REALISM.md"}
    assert {name: after[name] for name in before} == before


# --- AC8: no mean, and nothing it could be rebuilt from ----------------------------------------------


@pytest.mark.covers("#66 AC8")
def test_the_return_value_holds_the_spread_and_the_counts_and_no_mean() -> None:
    assert {f.name for f in fields(realism.Measurement)} == {
        "gameweeks",
        "spread_points",
        "panel_managers",
        "managers_per_gameweek",
    }


@pytest.mark.covers("#66 AC8")
def test_feeds_whose_weekly_shares_differ_by_a_constant_give_the_same_measurement_and_file(tmp_path: Path) -> None:
    low = realism.measure(_window_feed((0.2, 0.3, 0.4)), gameweeks=VERDICT_WINDOW)
    high = realism.measure(_window_feed((0.5, 0.6, 0.7)), gameweeks=VERDICT_WINDOW)
    assert low == high
    (tmp_path / "low").mkdir()
    (tmp_path / "high").mkdir()
    a = realism.write(tmp_path / "low", low, LEVELS_65).read_bytes()
    b = realism.write(tmp_path / "high", high, LEVELS_65).read_bytes()
    assert a == b


@pytest.mark.covers("#66 AC8")
def test_the_counts_are_the_distinct_panel_managers_and_each_gameweeks_own_count() -> None:
    feed = pd.concat([_window_feed(managers=10), _feed({20: 0.5}, managers=30)], ignore_index=True)
    feed = feed.loc[~((feed["gameweek"] == 4) & (feed["manager_id"] > 6))]  # GW4: 6 managers
    measured = realism.measure(feed, gameweeks=VERDICT_WINDOW)
    assert measured.gameweeks == VERDICT_WINDOW
    assert measured.panel_managers == 10
    assert measured.managers_per_gameweek == (6, *(10,) * 11)


# --- AC9: the sampling noise is printed and not subtracted -------------------------------------------


@pytest.mark.covers("#66 AC9")
def test_the_sampling_noise_at_1900_managers_a_gameweek_is_about_1_1_points() -> None:
    assert realism.sampling_noise_points((1_900,) * 12) == pytest.approx(100 * math.sqrt(0.25 / 1_900))
    assert round(realism.sampling_noise_points((1_900,) * 12), 1) == 1.1


@pytest.mark.covers("#66 AC9")
def test_the_sampling_noise_averages_each_gameweeks_own_variance_not_the_distinct_count() -> None:
    # 100 x sqrt(mean of 0.25 / n_g): with n_g of 100 and 400, sqrt((0.0025 + 0.000625) / 2) x 100.
    assert realism.sampling_noise_points((100, 400)) == pytest.approx(100 * math.sqrt((0.25 / 100 + 0.25 / 400) / 2))
    assert realism.sampling_noise_points((100, 400)) != pytest.approx(100 * math.sqrt(0.25 / 400))


@pytest.mark.covers("#66 AC9")
def test_the_measured_noise_uses_the_feeds_per_gameweek_counts() -> None:
    feed = _window_feed(managers=10)
    feed = feed.loc[~((feed["gameweek"] == 4) & (feed["manager_id"] > 5))]  # GW4: 5 managers
    measured = realism.measure(feed, gameweeks=VERDICT_WINDOW)
    text = realism.render(measured, LEVELS_65)
    expected = 100 * math.sqrt((0.25 / 5 + 11 * 0.25 / 10) / 12)
    assert realism.sampling_noise_points(measured.managers_per_gameweek) == pytest.approx(expected)
    assert f"{expected:.2f}" in text


@pytest.mark.covers("#66 AC9")
def test_the_sampling_noise_is_printed_and_stated_as_not_subtracted() -> None:
    text = realism.render(_measurement(7.0, managers=1_900), LEVELS_65)
    noise_lines = [line for line in text.splitlines() if "sampling noise" in line.lower()]
    assert len(noise_lines) == 1
    assert f"{realism.sampling_noise_points((1_900,) * 12):.2f}" in noise_lines[0]
    assert "not subtracted" in noise_lines[0]
    assert "1,900" in noise_lines[0]


@pytest.mark.covers("#66 AC9")
def test_the_sampling_noise_gates_no_label() -> None:
    few = realism.render(_measurement(7.0, managers=20), LEVELS_65)
    many = realism.render(_measurement(7.0, managers=2_000), LEVELS_65)
    for gameweeks in power_lab.GAMEWEEK_SWEEP:
        assert _row_label(few, gameweeks) == _row_label(many, gameweeks)


@pytest.mark.covers("#66 AC9")
def test_the_noise_is_not_subtracted_from_the_spread() -> None:
    # The same weekly shares over 10 or 40 managers: different noise, the same spread.
    few = realism.measure(_window_feed(managers=10), gameweeks=VERDICT_WINDOW)
    many = realism.measure(_window_feed(managers=40), gameweeks=VERDICT_WINDOW)
    assert few.spread_points == pytest.approx(many.spread_points)
    assert few.spread_points == pytest.approx(pd.Series([40.0, 50.0, 60.0] * 4).std(ddof=1))


# --- AC10: a run on other gameweeks is a labelled preview --------------------------------------------


@pytest.mark.covers("#66 AC10")
def test_a_run_on_other_gameweeks_is_labelled_a_preview_and_names_them() -> None:
    text = realism.render(_measurement(7.0, gameweeks=(4, 5, 6, 7, 8)), LEVELS_65)
    first = text.splitlines()[2]
    assert first.startswith("Preview")
    assert all(re.search(rf"\bGW{g}\b", first) for g in (4, 5, 6, 7, 8))
    assert not re.search(r"\bGW9\b", first)


@pytest.mark.covers("#66 AC10")
def test_the_run_on_the_verdict_gameweeks_is_the_record_not_a_preview() -> None:
    text = realism.render(_measurement(7.0), LEVELS_65)
    assert "Preview" not in text
    assert text.splitlines()[2].startswith("Record")


# --- AC11: the writer is deterministic ----------------------------------------------------------------


@pytest.mark.covers("#66 AC11")
def test_writing_twice_from_one_feed_gives_identical_bytes(tmp_path: Path) -> None:
    feed = _window_feed()
    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()
    first = realism.write(tmp_path / "first", realism.measure(feed, gameweeks=VERDICT_WINDOW), LEVELS_65)
    second = realism.write(tmp_path / "second", realism.measure(feed, gameweeks=VERDICT_WINDOW), LEVELS_65)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.covers("#66 AC11")
def test_shuffled_feed_rows_and_levels_give_identical_bytes() -> None:
    feed = _window_feed()
    shuffled = feed.sample(frac=1.0, random_state=1).reset_index(drop=True)
    a = realism.render(realism.measure(feed, gameweeks=VERDICT_WINDOW), LEVELS_65)
    b = realism.render(realism.measure(shuffled, gameweeks=tuple(reversed(VERDICT_WINDOW))), list(reversed(LEVELS_65)))
    assert a == b


@pytest.mark.covers("#66 AC11")
def test_no_timestamp_reaches_the_file() -> None:
    text = realism.render(_measurement(7.0), LEVELS_65)
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}", text)


# --- Proposed AC12: a gameweek the check cannot measure fails loud -----------------------------------


@pytest.mark.covers("#66 AC12")
def test_a_requested_gameweek_with_no_rows_is_refused_by_name() -> None:
    with pytest.raises(realism.RealismRefused, match="GW6"):
        realism.measure(_feed({4: 0.4, 5: 0.5}), gameweeks=(4, 5, 6))


@pytest.mark.covers("#66 AC12")
def test_fewer_than_two_gameweeks_is_refused() -> None:
    with pytest.raises(realism.RealismRefused, match="two gameweeks"):
        realism.measure(_feed({4: 0.4}), gameweeks=(4,))
