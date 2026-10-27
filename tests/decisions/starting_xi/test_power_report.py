"""Tests for `power_report.py`: the lab's acceptance gate, MDE table and labels (#60 P10, P11, U-U4).

Every test builds its power table by hand; nothing here runs a simulation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace

import pytest

from decisions.starting_xi import power_lab, power_report

pytestmark = pytest.mark.unit

SHARES = power_lab.TRUE_WIN_SHARES  # (0.51, 0.52, 0.53, 0.55, 0.58, 0.60)
HEADLINE = power_report.HEADLINE_EDGE
SECONDARY = power_report.SECONDARY_EDGE
CORNER = power_lab.WORST_CASE_CORNER


def _curve(**by_share: float) -> dict[float, float]:
    """Power by swept share; unnamed shares interpolate as a flat 0.0 so only the named points matter."""
    named = {float(k.replace("p", "0.")): v for k, v in by_share.items()}
    return {s: named.get(s, 0.0) for s in SHARES}


def _rising(low: float, high: float) -> dict[float, float]:
    step = (high - low) / (len(SHARES) - 1)
    return {s: round(low + i * step, 4) for i, s in enumerate(SHARES)}


def _results(
    settings: tuple[power_lab.Setting, ...],
    power: Callable[[power_lab.Setting, float], float],
    *,
    firings: Mapping[str, int] | None = None,
    sensitivity: float = 1.0,
    is_pilot: bool = False,
) -> power_lab.PowerResults:
    return power_lab.PowerResults(
        settings=settings,
        power={(s.name, share): power(s, share) for s in settings for share in SHARES},
        false_alarm_firings={s.name: (firings or {}).get(s.name, 30) for s in settings},
        sensitivity_power=sensitivity,
        fake_studies=1_000,
        inner_resamples=10_000,
        is_pilot=is_pilot,
    )


def _corner_sweep(curves: Mapping[int, Mapping[float, float]]) -> power_lab.PowerResults:
    settings = tuple(replace(CORNER, name=f"corner_gameweeks_{g}", gameweeks=g) for g in curves)
    by_gw = {s.name: curves[s.gameweeks] for s in settings}
    return _results(settings, lambda s, share: by_gw[s.name][share])


ALL_REACHABLE: Mapping[int, bool] = {g: True for g in power_lab.GAMEWEEK_SWEEP}


def _full_grid(**kwargs: object) -> power_lab.PowerResults:
    """The frozen grid with power 0.9 everywhere -- what `build_report` needs before it reports at all."""
    return _results(power_lab.SETTINGS, lambda s, share: 0.9, **kwargs)  # type: ignore[arg-type]


# --- AC3: both acceptance checks gate the table --------------------------------------------------


@pytest.mark.covers("#60 AC3")
def test_the_false_alarm_count_is_63_of_1000() -> None:
    assert power_report.false_alarm_max_firings(1_000) == 63


@pytest.mark.covers("#60 AC3")
@pytest.mark.parametrize(("firings", "passes"), [(30, True), (63, True), (64, False), (90, False)])
def test_a_failed_false_alarm_check_is_named_and_blocks_the_power_table(firings: int, passes: bool) -> None:
    report = power_report.build_report(_full_grid(firings={CORNER.name: firings}), reachable=ALL_REACHABLE)

    if passes:
        assert report.failed_checks == []
        assert report.power_table is not None
    else:
        assert report.power_table is None
        assert report.failed_checks == [f"false-alarm check failed: {CORNER.name} fired in {firings} of 1000"]


@pytest.mark.covers("#60 AC3")
def test_a_failed_sensitivity_check_is_named_and_blocks_the_power_table() -> None:
    report = power_report.build_report(_full_grid(sensitivity=0.95), reachable=ALL_REACHABLE)
    assert report.power_table is None
    assert report.failed_checks == ["sensitivity check failed: power 0.95 at a true 65%, below 0.99"]


# --- AC4: the MDE, read at the lowest-power setting ----------------------------------------------


@pytest.mark.covers("#60 AC4")
def test_the_mde_is_read_at_the_lowest_power_setting_and_names_it() -> None:
    strong = replace(power_lab.BASELINE, name="strong")
    weak = replace(CORNER, name="weak")
    curves = {"strong": dict.fromkeys(SHARES, 0.9), "weak": _curve(p58=0.79, p60=0.81)}
    reading = power_report.mde_reading(_results((strong, weak), lambda s, share: curves[s.name][share]), ALL_REACHABLE)

    assert reading.setting == "weak"
    assert reading.label.mde == 0.60
    assert reading.label.status == "underpowered"
    assert reading.label.mde_beyond_sweep is False


@pytest.mark.covers("#60 AC4")
def test_power_exactly_at_the_pass_mark_passes() -> None:
    label = power_report.label_row(_curve(p55=0.80, p58=0.9, p60=0.95), threshold_reachable=True)
    assert label.mde == 0.55
    assert label.status is None


@pytest.mark.covers("#60 AC4")
def test_nothing_at_the_pass_mark_reads_underpowered_and_mde_beyond_the_sweep() -> None:
    label = power_report.label_row(_rising(0.40, 0.75), threshold_reachable=True)
    assert (label.status, label.mde, label.mde_beyond_sweep) == ("underpowered", None, True)


@pytest.mark.covers("#60 AC4")
def test_a_pilot_runs_numbers_are_refused() -> None:
    with pytest.raises(power_report.ReportRefused, match="pilot"):
        power_report.build_report(_full_grid(is_pilot=True), reachable=ALL_REACHABLE)


@pytest.mark.covers("#60 AC6c")
def test_a_partial_grid_is_refused_and_its_missing_settings_named() -> None:
    partial = _results(power_lab.SETTINGS[:-1], lambda s, share: 0.9)
    with pytest.raises(power_report.ReportRefused, match=power_lab.SETTINGS[-1].name):
        power_report.build_report(partial, reachable=ALL_REACHABLE)


@pytest.mark.covers("#60 AC4")
def test_the_report_labels_its_assumptions_and_states_its_repeat_counts() -> None:
    text = power_report.render(power_report.build_report(_full_grid(), reachable=ALL_REACHABLE))
    assert "assumption" in text.lower()
    for size in ("small", "medium", "large"):
        assert size in text
    assert "1,000 fake studies per setting" in text
    assert "10,000 inner bootstrap repeats" in text


# --- AC8: gameweeks needed at the worst-case corner, both edges ----------------------------------


@pytest.mark.covers("#60 AC8")
def test_gameweeks_needed_is_the_smallest_swept_count_reaching_the_pass_mark() -> None:
    results = _corner_sweep(
        {
            5: _curve(p55=0.2),
            8: _curve(p55=0.4),
            12: _curve(p55=0.6),
            16: _curve(p55=0.78),
            24: _curve(p55=0.83),
            38: _curve(p55=0.95),
        }
    )
    assert power_report.gameweeks_needed(results, HEADLINE).count == 24


@pytest.mark.covers("#60 AC8")
def test_gameweeks_needed_counts_exactly_the_pass_mark() -> None:
    results = _corner_sweep(
        {5: _curve(), 8: _curve(), 12: _curve(p55=0.80), 16: _curve(p55=0.9), 24: _curve(p55=0.9), 38: _curve(p55=0.9)}
    )
    assert power_report.gameweeks_needed(results, HEADLINE).count == 12


@pytest.mark.covers("#60 AC8")
def test_an_edge_no_swept_count_reaches_says_so_and_names_38() -> None:
    curves = {g: _curve(p53=0.5, p55=0.9 if g >= 24 else 0.5) for g in power_lab.GAMEWEEK_SWEEP}
    results = _corner_sweep(curves)

    secondary = power_report.gameweeks_needed(results, SECONDARY)
    assert secondary.count is None
    assert secondary.largest_tried == 38
    assert "more gameweeks than the season has" in secondary.text
    assert power_report.gameweeks_needed(results, HEADLINE).count == 24


@pytest.mark.covers("#60 AC8")
def test_gameweeks_needed_is_labelled_conditional_on_its_assumptions() -> None:
    results = _corner_sweep({g: _curve(p53=0.9, p55=0.9) for g in power_lab.GAMEWEEK_SWEEP})
    text = power_report.gameweeks_needed(results, HEADLINE).text
    assert "conditional on the assumed edge, shock size, manager effect and tie rate" in text


# --- AC9: MDE per gameweek count, in U3's order with U4's rules ----------------------------------


@pytest.mark.covers("#60 AC9")
def test_a_reachable_count_where_nothing_reaches_the_mark_reads_underpowered_and_beyond_the_sweep() -> None:
    label = power_report.label_row(_rising(0.10, 0.60), threshold_reachable=True)
    assert label.status == "underpowered"
    assert label.mde_beyond_sweep is True


@pytest.mark.covers("#60 AC9")
def test_a_reachable_count_with_an_mde_above_the_headline_reads_underpowered_with_that_mde() -> None:
    label = power_report.label_row(_curve(p55=0.74, p58=0.82, p60=0.9), threshold_reachable=True)
    assert (label.status, label.mde, label.mde_beyond_sweep) == ("underpowered", 0.58, False)


@pytest.mark.covers("#60 AC9")
def test_mde_beyond_the_sweep_comes_with_underpowered_and_exactly_80_at_the_headline_carries_neither() -> None:
    both = power_report.label_row(_rising(0.40, 0.75), threshold_reachable=True)
    neither = power_report.label_row(_curve(p55=0.80, p58=0.9, p60=0.9), threshold_reachable=True)
    assert (both.status, both.mde_beyond_sweep) == ("underpowered", True)
    assert (neither.status, neither.mde_beyond_sweep) == (None, False)


@pytest.mark.covers("#60 AC9")
def test_an_unreachable_count_reads_undetermined_with_its_power_shown_and_no_mde() -> None:
    label = power_report.label_row(_rising(0.10, 0.60), threshold_reachable=False)
    assert label.status == "undetermined by construction"
    assert label.power_at_headline == _rising(0.10, 0.60)[HEADLINE]
    assert label.mde == "not defined at this count"
    assert label.mde_beyond_sweep is False


@pytest.mark.covers("#60 AC9")
def test_a_secondary_edge_below_the_mark_is_a_report_not_a_verdict() -> None:
    label = power_report.label_row(_curve(p53=0.6, p55=0.85, p58=0.9, p60=0.9), threshold_reachable=True)
    assert label.status is None
    assert (label.headline_detectable, label.secondary_detectable) == (True, False)


@pytest.mark.covers("#60 AC9")
def test_every_swept_gameweek_count_gets_a_row_naming_its_setting_and_no_reachable_row_breaks_u4() -> None:
    curves = {
        5: _rising(0.1, 0.6),
        8: _rising(0.2, 0.7),
        12: _curve(p55=0.74, p58=0.82, p60=0.9),
        16: _curve(p55=0.8, p58=0.9, p60=0.9),
        24: _curve(p53=0.8, p55=0.9, p58=0.9, p60=0.9),
        38: _rising(0.9, 1.0),
    }
    reachable = {**ALL_REACHABLE, 5: False}
    rows = power_report.mde_by_gameweeks(_corner_sweep(curves), reachable)

    assert [r.gameweeks for r in rows] == list(power_lab.GAMEWEEK_SWEEP)
    assert all(r.setting == f"corner_gameweeks_{r.gameweeks}" for r in rows)
    assert rows[0].label.status == "undetermined by construction"
    for row in rows[1:]:
        assert not (row.label.mde_beyond_sweep and row.label.status != "underpowered"), row.gameweeks
    assert power_report.U4_VIOLATION in power_report.check_row(
        power_report.RowLabel(
            status=None,
            mde=None,
            mde_beyond_sweep=True,
            power_at_headline=0.5,
            headline_detectable=False,
            secondary_detectable=False,
        )
    )


# --- AC10: power against manager count, and the rows implied ------------------------------------


@pytest.mark.covers("#60 AC10")
def test_the_manager_sweep_shows_power_and_managers_times_gameweeks_rows() -> None:
    settings = (
        replace(power_lab.BASELINE, name="m2000_g5"),
        replace(power_lab.BASELINE, name="m500_g38", managers=500, gameweeks=38),
        replace(power_lab.BASELINE, name="m1000_g5", managers=1_000),
    )
    power = {"m2000_g5": 0.5, "m500_g38": 0.9, "m1000_g5": 0.45}
    rows = power_report.manager_sweep(_results(settings, lambda s, share: power[s.name]))

    by_name = {r.setting: r for r in rows}
    assert by_name["m2000_g5"].rows == 10_000
    assert by_name["m500_g38"].rows == 19_000
    assert {r.managers for r in rows} == {500, 1_000, 2_000}
    assert by_name["m1000_g5"].power_at_headline == 0.45


# --- AC11: p-value resolution per gameweek count ------------------------------------------------


@pytest.mark.covers("#60 AC11")
def test_the_resolution_at_5_gameweeks_is_126_resamples_and_reaches_holms_strictest_threshold() -> None:
    row = power_report.resolution(5, n_resamples=10_000)
    assert row.distinct_resamples == 126
    assert row.smallest_step == pytest.approx(2 / 5**5)
    assert row.threshold_reachable is True
    assert row.method


@pytest.mark.covers("#60 AC11")
def test_the_resolution_table_covers_every_swept_count() -> None:
    table = power_report.resolution_table(power_lab.GAMEWEEK_SWEEP, n_resamples=10_000)
    assert [r.gameweeks for r in table] == list(power_lab.GAMEWEEK_SWEEP)


@pytest.mark.covers("#60 AC11")
def test_a_count_whose_resampling_cannot_reach_the_threshold_is_reported_unreachable() -> None:
    row = power_report.resolution(3, n_resamples=10_000)  # smallest step 2/27, above 0.0125
    assert row.threshold_reachable is False
