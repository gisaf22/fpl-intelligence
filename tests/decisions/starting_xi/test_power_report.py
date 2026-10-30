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


def _probe(
    corner: tuple[int, int, int] = (30, 30, 30), baseline: tuple[int, int, int] = (30, 30, 30)
) -> dict[str, int]:
    """Probe firings at 8, 12 and 16 gameweeks, by anchor."""
    return {
        power_lab.probe_setting(anchor, g).name: n
        for anchor, by_count in ((CORNER, corner), (power_lab.BASELINE, baseline))
        for g, n in zip((8, 12, 16), by_count, strict=True)
    }


def _results(
    settings: tuple[power_lab.Setting, ...],
    power: Callable[[power_lab.Setting, float], float],
    *,
    firings: Mapping[str, int] | None = None,
    sensitivity: float = 1.0,
    is_pilot: bool = False,
    probe_firings: Mapping[str, int] | None = None,
) -> power_lab.PowerResults:
    return power_lab.PowerResults(
        settings=settings,
        power={(s.name, share): power(s, share) for s in settings for share in SHARES},
        false_alarm_firings={s.name: (firings or {}).get(s.name, 30) for s in settings},
        sensitivity_power=sensitivity,
        fake_studies=1_000,
        inner_resamples=10_000,
        is_pilot=is_pilot,
        probe_firings=_probe() if probe_firings is None else probe_firings,
    )


def _corner_sweep(curves: Mapping[int, Mapping[float, float]]) -> power_lab.PowerResults:
    settings = tuple(replace(CORNER, name=f"corner_gameweeks_{g}", gameweeks=g) for g in curves)
    by_gw = {s.name: curves[s.gameweeks] for s in settings}
    return _results(settings, lambda s, share: by_gw[s.name][share])


ALL_REACHABLE: Mapping[int, bool] = {g: True for g in power_lab.GAMEWEEK_SWEEP}


def _full_grid(**kwargs: object) -> power_lab.PowerResults:
    """The frozen grid with power 0.9 everywhere -- what `build_report` needs before it reports at all."""
    return _results(power_lab.SETTINGS, lambda s, share: 0.9, **kwargs)  # type: ignore[arg-type]


# --- AC3 (amended by U5): the false-alarm check gates per gameweek count; sensitivity gates all ----


@pytest.mark.covers("#60 AC3")
def test_the_false_alarm_count_is_63_of_1000() -> None:
    assert power_report.false_alarm_max_firings(1_000) == 63


@pytest.mark.covers("#60 AC3")
@pytest.mark.parametrize(("firings", "passes"), [(30, True), (63, True), (64, False), (90, False)])
def test_a_failed_false_alarm_check_is_named_and_invalidates_only_its_gameweek_count(
    firings: int, passes: bool
) -> None:
    report = power_report.build_report(_full_grid(firings={CORNER.name: firings}), reachable=ALL_REACHABLE)

    assert report.power_table is not None
    at_5 = [row for row in report.power_table if row.gameweeks == CORNER.gameweeks]
    elsewhere = [row for row in report.power_table if row.gameweeks != CORNER.gameweeks]
    assert all(row.power is not None for row in elsewhere)
    gw5 = next(r for r in report.gameweek_rows if r.gameweeks == CORNER.gameweeks)
    if passes:
        assert report.failed_checks == []
        assert all(row.power is not None for row in at_5)
        assert gw5.label.status != power_report.INVALID
    else:
        assert report.failed_checks == [f"false-alarm check failed: {CORNER.name} fired in {firings} of 1000"]
        assert all(row.power is None for row in at_5)  # no power claimed at that count
        assert gw5.label.status == power_report.INVALID


@pytest.mark.covers("#60 AC3")
def test_the_report_still_refuses_a_partial_grid_when_a_count_is_invalid() -> None:
    partial = _results(power_lab.SETTINGS[:-1], lambda s, share: 0.9, firings={CORNER.name: 90})
    with pytest.raises(power_report.ReportRefused, match="partial grid"):
        power_report.build_report(partial, reachable=ALL_REACHABLE)


@pytest.mark.covers("#60 AC3")
def test_an_invalid_count_claims_no_power_and_has_no_mde() -> None:
    label = power_report.label_row(_rising(0.9, 1.0), threshold_reachable=True, false_alarm_ok=False)
    assert label.status == power_report.INVALID
    assert label.status == "verdict procedure invalid at this count (false-alarm check failed)"
    assert (label.power_at_headline, label.mde, label.mde_beyond_sweep) == (None, "not defined at this count", False)
    assert power_report.check_row(label) == []


@pytest.mark.covers("#60 AC3")
def test_an_invalid_count_takes_precedence_over_an_unreachable_threshold() -> None:
    label = power_report.label_row(_rising(0.1, 0.6), threshold_reachable=False, false_alarm_ok=False)
    assert label.status == power_report.INVALID


@pytest.mark.covers("#60 AC3")
def test_check_row_catches_power_claimed_at_an_invalid_count() -> None:
    bad = power_report.RowLabel(
        status=power_report.INVALID,
        mde=power_report.NOT_DEFINED,
        mde_beyond_sweep=False,
        power_at_headline=0.9,
        headline_detectable=None,
        secondary_detectable=None,
    )
    assert power_report.check_row(bad) == ["power claimed at an invalid count"]


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
def test_gameweeks_needed_skips_a_count_whose_false_alarm_check_failed() -> None:
    curves = {g: _curve(p55=0.9 if g >= 12 else 0.5) for g in power_lab.GAMEWEEK_SWEEP}
    results = _corner_sweep(curves)
    results = replace(results, false_alarm_firings={**results.false_alarm_firings, "corner_gameweeks_12": 64})
    assert power_report.gameweeks_needed(results, HEADLINE).count == 16


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


# --- #65 AC3: the probe, reported alongside, with the largest tolerable shock per count ----------

FIVE_INVALID = {power_lab.BASELINE.name: 68}  # 5 gameweeks fails the false-alarm check (U5), as on the full grid


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start : end if end != -1 else len(text)]


@pytest.mark.covers("#65 AC3")
def test_each_probe_cell_is_reported_against_63_by_anchor_and_count() -> None:
    probe = power_report.probe_report(_full_grid(probe_firings=_probe(corner=(64, 40, 20), baseline=(41, 38, 20))))

    assert probe.limit == 63
    by_cell = {(c.anchor, c.gameweeks): (c.firings, c.over_limit) for c in probe.cells}
    assert by_cell == {
        (CORNER.name, 8): (64, True),
        (CORNER.name, 12): (40, False),
        (CORNER.name, 16): (20, False),
        (power_lab.BASELINE.name, 8): (41, False),
        (power_lab.BASELINE.name, 12): (38, False),
        (power_lab.BASELINE.name, 16): (20, False),
    }
    assert probe.smallest_over == {CORNER.name: 8, power_lab.BASELINE.name: None}


@pytest.mark.covers("#65 AC3")
def test_63_firings_are_not_over_the_limit_and_no_count_over_it_is_stated() -> None:
    probe = power_report.probe_report(_full_grid(probe_firings=_probe(corner=(63, 63, 63), baseline=(63, 63, 63))))
    assert not any(c.over_limit for c in probe.cells)
    assert probe.smallest_over == {CORNER.name: None, power_lab.BASELINE.name: None}
    assert "no probed count over the limit" in power_report.render_probe(probe)


@pytest.mark.covers("#65 AC3")
def test_each_count_carries_the_largest_shock_level_at_which_it_stays_within_the_limit() -> None:
    results = _full_grid(firings=FIVE_INVALID, probe_firings=_probe(corner=(64, 40, 20), baseline=(41, 38, 20)))
    levels = {s.gameweeks: (s.level, s.note) for s in power_report.probe_report(results).shock_levels}
    assert levels == {
        5: (None, None),  # invalid under U5: no level
        8: (6, None),  # a probe cell over 63 at the corner
        12: (9, None),
        16: (9, None),
        24: (6, "not probed at 9"),
        38: (6, "not probed at 9"),
    }


@pytest.mark.covers("#65 AC3")
def test_a_count_over_the_limit_at_either_anchor_reads_6_points() -> None:
    results = _full_grid(probe_firings=_probe(corner=(30, 30, 30), baseline=(30, 70, 30)))
    levels = {s.gameweeks: s.level for s in power_report.probe_report(results).shock_levels}
    assert levels[12] == 6
    assert levels[8] == levels[16] == 9


@pytest.mark.covers("#65 AC3")
def test_a_missing_probe_cell_is_named_and_refused() -> None:
    firings = _probe()
    missing = power_lab.probe_setting(power_lab.BASELINE, 16).name
    del firings[missing]
    with pytest.raises(power_report.ReportRefused, match=missing):
        power_report.probe_report(_full_grid(probe_firings=firings))
    with pytest.raises(power_report.ReportRefused, match=missing):
        power_report.build_report(_full_grid(probe_firings=firings), reachable=ALL_REACHABLE)


@pytest.mark.covers("#65 AC3")
def test_a_probe_cell_over_the_limit_leaves_the_grids_u5_labels_unchanged() -> None:
    report = power_report.build_report(_full_grid(probe_firings=_probe(corner=(64, 30, 30))), reachable=ALL_REACHABLE)
    gw8 = next(r for r in report.gameweek_rows if r.gameweeks == 8)
    assert gw8.label.status != power_report.INVALID
    assert report.failed_checks == []
    assert report.power_table is not None
    assert all(row.power is not None for row in report.power_table if row.gameweeks == 8)


@pytest.mark.covers("#65 AC3")
def test_the_shock_levels_are_printed_beside_the_gameweeks_needed_lines() -> None:
    results = _full_grid(firings=FIVE_INVALID, probe_firings=_probe(corner=(64, 40, 20), baseline=(41, 38, 20)))
    section = _section(
        power_report.render(power_report.build_report(results, reachable=ALL_REACHABLE)), "## Gameweeks needed"
    )
    assert "- 5 gameweeks: no level" in section
    assert "- 8 gameweeks: 6 points" in section
    assert "- 12 gameweeks: 9 points" in section
    assert "- 24 gameweeks: 6 points, not probed at 9" in section


@pytest.mark.covers("#65 AC3")
def test_a_saved_probe_cell_is_read_as_a_probe_firing_not_a_grid_one() -> None:
    probe = power_lab.probe_setting(CORNER, 8)
    saved = {
        "probe": power_lab.CellResult(power_lab.cell_id(probe, 0.5), probe.name, 0.5, 1_000, 0, 64, (0, 0, 0), 0),
    }
    results = power_lab.assemble_results(saved, fake_studies=1_000)
    assert results.probe_firings == {probe.name: 64}
    assert probe.name not in results.false_alarm_firings


# --- #65 AC6: the conditional line, verbatim, on every rendered output ---------------------------

CONDITIONAL_LINE = (
    "Conditional on assumed settings (shock, manager spread, tie rate, independence beyond the weekly shock); "
    "not measured from real data."
)
RETIRED_LABEL = "conditional on the assumed edge, shock size, manager effect and tie rate"


def _every_rendered_output() -> dict[str, str]:
    probe_results = _full_grid(probe_firings=_probe(corner=(64, 40, 20)))
    return {
        "report": power_report.render(power_report.build_report(_full_grid(), reachable=ALL_REACHABLE)),
        "report stopped by a failed sensitivity check": power_report.render(
            power_report.build_report(_full_grid(sensitivity=0.95), reachable=ALL_REACHABLE)
        ),
        "probe": power_report.render_probe(power_report.probe_report(probe_results)),
    }


@pytest.mark.covers("#65 AC6")
def test_the_conditional_line_is_the_registered_wording() -> None:
    assert power_report.CONDITIONAL == CONDITIONAL_LINE


@pytest.mark.covers("#65 AC6")
@pytest.mark.parametrize("output", ["report", "report stopped by a failed sensitivity check", "probe"])
def test_every_rendered_output_carries_the_conditional_line_verbatim(output: str) -> None:
    text = _every_rendered_output()[output]
    assert CONDITIONAL_LINE in text
    assert RETIRED_LABEL not in text


@pytest.mark.covers("#65 AC6")
def test_a_report_stopped_by_a_failed_sensitivity_check_has_no_table_but_carries_the_line() -> None:
    text = _every_rendered_output()["report stopped by a failed sensitivity check"]
    assert "No power table" in text
    assert CONDITIONAL_LINE in text


# --- #65 AC7 (D-GATE): no power in the managers table at a count U5 marks invalid ---------------


def _five_invalid_with_marked_power() -> power_lab.PowerResults:
    # 0.777 marks power at 5 gameweeks, so the test can see whether the managers table prints it.
    return _results(power_lab.SETTINGS, lambda s, share: 0.777 if s.gameweeks == 5 else 0.9, firings=FIVE_INVALID)


@pytest.mark.covers("#65 AC7")
def test_a_manager_row_at_an_invalid_count_claims_no_power() -> None:
    rows = power_report.build_report(_five_invalid_with_marked_power(), reachable=ALL_REACHABLE).managers
    at_5 = [r for r in rows if r.gameweeks == 5]
    assert at_5
    assert all(r.power_at_headline is None for r in at_5)
    assert all(r.power_at_headline == 0.9 for r in rows if r.gameweeks != 5)


@pytest.mark.covers("#65 AC7")
def test_the_rendered_managers_table_prints_invalid_never_a_power_number_at_an_invalid_count() -> None:
    text = power_report.render(power_report.build_report(_five_invalid_with_marked_power(), reachable=ALL_REACHABLE))
    table = _section(text, "## Power against managers")
    rows_at_5 = [line for line in table.splitlines() if line.startswith("| ") and "| 5 |" in line]
    assert rows_at_5
    assert all(line.rstrip().endswith("| invalid |") for line in rows_at_5)
    assert "0.777" not in table
    assert any(line.rstrip().endswith("| 0.900 |") for line in table.splitlines())


# --- #65 AC8 (D-P10): the headline MDE at the smallest valid count ------------------------------


def _five_invalid_and_weakest() -> power_lab.PowerResults:
    """5 gameweeks invalid and weakest; at 8 the corner is weakest, with an MDE of 55%; 12 is weaker than 8."""

    def power(s: power_lab.Setting, share: float) -> float:
        if s.gameweeks == 5:
            return 0.3
        if s.name == "worst_case_corner_gameweeks_8":
            return 0.821 if share >= 0.55 else 0.4
        if s.gameweeks == 12:
            return 0.85 if share >= 0.55 else 0.35
        return 0.9

    return _results(power_lab.SETTINGS, power, firings=FIVE_INVALID)


@pytest.mark.covers("#65 AC8")
def test_the_headline_mde_is_read_at_the_smallest_valid_counts_weakest_setting() -> None:
    reading = power_report.mde_reading(_five_invalid_and_weakest(), ALL_REACHABLE)
    assert reading.gameweeks == 8
    assert reading.setting == "worst_case_corner_gameweeks_8"
    assert reading.label.mde == 0.55
    assert reading.label.status is None


@pytest.mark.covers("#65 AC8")
def test_the_rendered_headline_mde_is_labelled_with_its_count() -> None:
    text = power_report.render(power_report.build_report(_five_invalid_and_weakest(), reachable=ALL_REACHABLE))
    section = _section(text, "## MDE")
    assert "MDE 55% at 8 gameweeks" in section
    assert "worst_case_corner_gameweeks_8" in section
    assert power_report.NOT_DEFINED not in section


@pytest.mark.covers("#65 AC8")
def test_the_headline_mde_is_not_defined_only_when_no_count_is_valid() -> None:
    every_count_invalid = {s.name: 90 for s in power_lab.SETTINGS}
    results = _results(power_lab.SETTINGS, lambda s, share: 0.9, firings=every_count_invalid)
    reading = power_report.mde_reading(results, ALL_REACHABLE)
    assert reading.gameweeks is None
    assert reading.label.mde == power_report.NOT_DEFINED
    text = power_report.render(power_report.build_report(results, reachable=ALL_REACHABLE))
    assert "MDE not defined: no gameweek count is valid" in _section(text, "## MDE")
