"""Tests for `power_lab.py`: the Stage 5 power simulation lab's fake data, guards and run loop (#60).

The lab generates fake manager-week tables and runs the real Stage 5 verdict on each (L). Its run
loop carries P13's guards: an estimate printed first, checkpoint/resume, a progress line per cell
and a wall-clock budget. AC16 is proposed on #60 (the fake data must hit the target win share).
"""

from __future__ import annotations

import ast
import inspect
import json
import types
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi import power_lab, verdict

pytestmark = pytest.mark.unit

# A tiny setting so a cell runs in milliseconds; the verdict's counts are cut to match.
TINY = replace(power_lab.BASELINE, name="tiny", managers=30, gameweeks=5)
TINY_VERDICT: dict[str, Any] = {"n_resamples": 100, "seed": 0, "rerun_resamples": 200, "rerun_seed": 1}


class FakeClock:
    """Wall-clock that advances only when a progress line is logged: one finished cell = `per_cell` seconds."""

    def __init__(self, per_cell: float) -> None:
        self.now = 0.0
        self.per_cell = per_cell
        self.lines: list[str] = []

    def __call__(self) -> float:
        return self.now

    def log(self, line: str) -> None:
        self.lines.append(line)
        if line.startswith(power_lab.PROGRESS_PREFIX):
            self.now += self.per_cell


def _run(
    out_dir: Path,
    cells: list[tuple[power_lab.Setting, float]],
    *,
    budget_seconds: float,
    clock: FakeClock,
    fake_studies: int = 2,
) -> power_lab.LabRun:
    return power_lab.run_lab(
        cells=cells,
        fake_studies=fake_studies,
        out_dir=out_dir,
        budget_seconds=budget_seconds,
        seconds_per_study={(TINY.managers, TINY.gameweeks): clock.per_cell / fake_studies},
        clock=clock,
        log=clock.log,
        verdict_kwargs=TINY_VERDICT,
    )


def _cells(n: int) -> list[tuple[power_lab.Setting, float]]:
    return [(replace(TINY, name=f"tiny_{i}"), 0.55) for i in range(n)]


# --- AC6a / AC12: the estimate comes first, and prices each setting at its own cost ---------------


@pytest.mark.covers("#60 AC6a")
def test_the_whole_grid_estimate_is_printed_before_the_first_cell_runs(tmp_path: Path) -> None:
    clock = FakeClock(per_cell=10.0)
    _run(tmp_path, _cells(3), budget_seconds=1_000, clock=clock)

    estimate_at = next(i for i, line in enumerate(clock.lines) if line.startswith(power_lab.ESTIMATE_PREFIX))
    first_progress_at = next(i for i, line in enumerate(clock.lines) if line.startswith(power_lab.PROGRESS_PREFIX))
    assert estimate_at < first_progress_at
    assert "30" in clock.lines[estimate_at]  # 3 cells x 10 s


@pytest.mark.covers("#60 AC12")
def test_the_estimate_prices_each_setting_at_its_own_measured_cost() -> None:
    baseline = power_lab.BASELINE
    long_season = replace(baseline, name="gameweeks_38", gameweeks=38)
    timings = {(2_000, 5): 0.1, (2_000, 38): 0.76}

    estimate = power_lab.estimate_grid_seconds(
        cells=[(baseline, 0.55), (long_season, 0.55)], fake_studies=1_000, seconds_per_study=timings
    )

    assert estimate == pytest.approx(1_000 * 0.1 + 1_000 * 0.76)
    assert estimate != pytest.approx(2 * 1_000 * 0.1)  # not the baseline's cost times the cell count


@pytest.mark.covers("#60 AC12")
def test_the_estimate_refuses_a_setting_the_pilot_did_not_time() -> None:
    with pytest.raises(KeyError, match="2000"):
        power_lab.estimate_grid_seconds(cells=[(power_lab.BASELINE, 0.55)], fake_studies=10, seconds_per_study={})


@pytest.mark.covers("#60 AC12")
def test_the_pilot_times_every_distinct_size_in_the_frozen_grid() -> None:
    sizes = {(s.managers, s.gameweeks) for s in power_lab.SETTINGS}
    assert set(power_lab.pilot_sizes(power_lab.SETTINGS)) == sizes


# --- AC6b: resume ----------------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.covers("#60 AC6b")
def test_a_resumed_run_recomputes_nothing_saved_and_matches_an_uninterrupted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cells = _cells(4)
    whole = _run(tmp_path / "whole", cells, budget_seconds=1_000, clock=FakeClock(10.0))

    stopped = _run(tmp_path / "resumed", cells, budget_seconds=25, clock=FakeClock(10.0))
    assert len(stopped.finished) == 2

    calls: list[str] = []
    real = power_lab.run_fake_study

    def counting(setting: power_lab.Setting, *args: object, **kwargs: object) -> object:
        calls.append(setting.name)
        return real(setting, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(power_lab, "run_fake_study", counting)
    resumed = _run(tmp_path / "resumed", cells, budget_seconds=1_000, clock=FakeClock(10.0))

    assert set(calls) == {"tiny_2", "tiny_3"}  # the two saved cells are not recomputed
    assert resumed.cell_results == whole.cell_results


# --- AC6c: budget stop and progress log -----------------------------------------------------------


@pytest.mark.covers("#60 AC6c")
def test_a_budget_stop_lists_finished_and_unfinished_cells_and_logs_progress_per_cell(tmp_path: Path) -> None:
    clock = FakeClock(per_cell=10.0)
    run = _run(tmp_path, _cells(20), budget_seconds=35, clock=clock, fake_studies=1)

    assert run.finished == ["tiny_0|0.55", "tiny_1|0.55", "tiny_2|0.55"]
    assert len(run.not_run) == 17
    assert run.complete is False
    assert sum(line.startswith(power_lab.PROGRESS_PREFIX) for line in clock.lines) == 3
    assert any("17" in line for line in clock.lines if line.startswith(power_lab.BUDGET_STOP_PREFIX))


@pytest.mark.covers("#60 AC6c")
def test_a_budget_stop_leaves_no_partly_written_checkpoint(tmp_path: Path) -> None:
    _run(tmp_path, _cells(5), budget_seconds=25, clock=FakeClock(10.0), fake_studies=1)
    for path in tmp_path.iterdir():
        assert path.suffix == ".json", f"stray file {path.name}"
        json.loads(path.read_text())


# --- AC7: the lab never reads D2's scores against managers ----------------------------------------


@pytest.mark.covers("#60 AC7")
@pytest.mark.parametrize(
    ("frame", "offender"),
    [
        (pd.DataFrame({"manager_id": [1], "gameweek": [4], "outcome": [1.0]}), "outcome"),
        (pd.DataFrame({"manager_id": [1], "gameweek": [4], "rule_xi_points": [61]}), "rule_xi_points"),
        (pd.DataFrame({"manager_id": [1], "d2_minus_manager": [3.0]}), "d2_minus_manager"),
    ],
    ids=["stage5_result_frame", "d2_score_column", "derived_column"],
)
def test_an_input_carrying_anything_beyond_the_panel_structure_is_refused_by_name(
    frame: pd.DataFrame, offender: str
) -> None:
    with pytest.raises(power_lab.LabInputRefused, match=rf"stage5_panel.*{offender}"):
        power_lab.check_lab_inputs({"stage5_panel": frame})


@pytest.mark.covers("#60 AC7")
def test_the_panel_structure_alone_passes_the_input_check() -> None:
    power_lab.check_lab_inputs(
        {"stage5_panel": pd.DataFrame({"manager_id": [1], "gameweek": [4], "band": ["top"]}), "fake_studies": 10}
    )


@pytest.mark.covers("#60 AC7")
def test_the_lab_entry_point_calls_the_input_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(power_lab, "check_lab_inputs", lambda inputs: seen.append(dict(inputs)))
    _run(tmp_path, _cells(1), budget_seconds=1_000, clock=FakeClock(10.0), fake_studies=1)
    assert len(seen) == 1


# --- AC13: the lab calls the real verdict, not a copy ---------------------------------------------


@pytest.mark.covers("#60 AC13")
def test_the_lab_resolves_the_shared_verdict_function_itself() -> None:
    assert power_lab.primary_verdict is verdict.primary_verdict


@pytest.mark.covers("#60 AC13")
def test_a_fake_study_goes_through_the_resolved_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[pd.DataFrame] = []
    real: Callable[..., verdict.Verdict] = verdict.primary_verdict

    def spy(table: pd.DataFrame, **kwargs: object) -> verdict.Verdict:
        calls.append(table)
        return real(table, **kwargs)

    monkeypatch.setattr(power_lab, "primary_verdict", spy)
    power_lab.run_fake_study(TINY, 0.55, np.random.default_rng(0), **TINY_VERDICT)
    assert len(calls) == 1


@pytest.mark.covers("#60 AC13")
def test_the_lab_module_defines_no_verdict_machinery_of_its_own() -> None:
    tree = ast.parse(inspect.getsource(power_lab))
    defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}
    machinery = {"primary_verdict", "raw_p_values", "crossed_share", "two_sided_p", "needs_rerun", "holm_bonferroni"}
    assert defined.isdisjoint(machinery)


@pytest.mark.covers("#60 AC13")
def test_the_identity_check_fails_for_a_lab_calling_a_byte_for_byte_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    real = verdict.primary_verdict
    copy = types.FunctionType(real.__code__, real.__globals__, real.__name__, real.__defaults__, real.__closure__)
    copy.__kwdefaults__ = real.__kwdefaults__
    monkeypatch.setattr(power_lab, "primary_verdict", copy)

    table = power_lab.generate_fake_table(TINY, 0.55, np.random.default_rng(0))
    assert np.array_equal(copy(table, **TINY_VERDICT).p_raw, real(table, **TINY_VERDICT).p_raw)  # same numbers
    assert power_lab.primary_verdict is not verdict.primary_verdict  # yet the identity check rejects it


# --- AC16 (proposed): the fake data hits its target ------------------------------------------------


@pytest.mark.covers("#60 AC16")
@pytest.mark.parametrize("tie_rate", [0.2, 0.4, 0.6])
@pytest.mark.parametrize("share", [0.5, 0.55, 0.60])
def test_fake_data_hits_the_target_win_share_and_tie_rate(share: float, tie_rate: float) -> None:
    setting = replace(power_lab.WORST_CASE_CORNER, name="big", managers=4_000, gameweeks=38, tie_rate=tie_rate)
    table = power_lab.generate_fake_table(setting, share, np.random.default_rng(0))

    assert set(table.columns) == {"manager_id", "gameweek", "outcome", "band"}
    assert len(table) == setting.managers * setting.gameweeks
    assert table["outcome"].isin([0.0, 0.5, 1.0]).all()
    assert (table["outcome"] == 0.5).mean() == pytest.approx(tie_rate, abs=0.01)
    # The target holds in expectation over the shocks; 38 large shocks leave ~1 point of noise (3.5 SE here).
    assert table["outcome"].mean() == pytest.approx(share, abs=0.035)


@pytest.mark.covers("#60 AC16")
def test_the_decided_week_win_rate_reaches_each_target_share_exactly_in_expectation() -> None:
    for setting in power_lab.SETTINGS:
        for share in (power_lab.NULL_SHARE, *power_lab.TRUE_WIN_SHARES):
            assert power_lab.expected_share(setting, share) == pytest.approx(share, abs=1e-9), setting.name


# --- AC17 (proposed): the runtime constraint -- tiers, per-tier estimate, re-run counted, parallel ---


@pytest.mark.covers("#60 AC17")
def test_the_three_tiers_partition_the_whole_grid() -> None:
    tiers = [[power_lab.cell_id(s, w) for s, w in power_lab.tier_cells(t)] for t in power_lab.TIERS]
    every = [
        *(power_lab.cell_id(s, w) for s in power_lab.SETTINGS for w in (0.5, *power_lab.TRUE_WIN_SHARES)),
        power_lab.cell_id(power_lab.WORST_CASE_CORNER, power_lab.SENSITIVITY_SHARE),
    ]
    flat = [c for tier in tiers for c in tier]
    assert len(flat) == len(set(flat)) == len(every) == 155
    assert set(flat) == set(every)


@pytest.mark.covers("#60 AC17")
def test_tier_1_holds_every_false_alarm_cell_and_both_edges_on_the_gameweek_sweep() -> None:
    tier1 = {power_lab.cell_id(s, w) for s, w in power_lab.tier_cells(1)}
    assert {power_lab.cell_id(s, 0.5) for s in power_lab.SETTINGS} <= tier1
    for setting in power_lab.GAMEWEEK_SWEEP_SETTINGS:
        assert {power_lab.cell_id(setting, 0.55), power_lab.cell_id(setting, 0.53)} <= tier1
    assert power_lab.cell_id(power_lab.WORST_CASE_CORNER, 0.65) in tier1
    assert {s.gameweeks for s in power_lab.GAMEWEEK_SWEEP_SETTINGS} == set(power_lab.GAMEWEEK_SWEEP)


@pytest.mark.covers("#60 AC17")
def test_the_per_tier_estimate_flags_a_tier_over_one_sitting() -> None:
    sizes = power_lab.pilot_sizes(power_lab.SETTINGS)
    fast = power_lab.estimate_by_tier(dict.fromkeys(sizes, 0.001), fake_studies=1_000)
    slow = power_lab.estimate_by_tier(dict.fromkeys(sizes, 0.2), fake_studies=1_000)
    assert [e.tier for e in fast] == [1, 2, 3]
    assert not any(e.over_sitting_limit for e in fast)
    tier1 = slow[0]
    assert tier1.seconds == pytest.approx(len(power_lab.tier_cells(1)) * 1_000 * 0.2)
    assert tier1.over_sitting_limit is (tier1.seconds > 90 * 60)
    assert tier1.over_sitting_limit


@pytest.mark.covers("#60 AC17")
def test_the_lab_counts_a_needed_rerun_and_never_applies_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verdict, "needs_rerun", lambda p_raw, *, n_resamples, alpha: True)
    study = power_lab.run_fake_study(TINY, 0.55, np.random.default_rng(0), **TINY_VERDICT)
    assert (study.rerun_needed, study.rerun) == (True, False)
    assert power_lab.run_cell(TINY, 0.55, 3, TINY_VERDICT).rerun_triggers == 3


@pytest.mark.integration
@pytest.mark.covers("#60 AC17")
def test_a_parallel_run_gives_the_same_cells_as_a_serial_one(tmp_path: Path) -> None:
    cells = _cells(3)
    timings = {(TINY.managers, TINY.gameweeks): 0.0}

    def run(out: str, workers: int) -> power_lab.LabRun:
        return power_lab.run_lab(
            cells=cells,
            fake_studies=2,
            out_dir=tmp_path / out,
            budget_seconds=1_000,
            seconds_per_study=timings,
            log=lambda _: None,
            verdict_kwargs=TINY_VERDICT,
            workers=workers,
        )

    serial, parallel = run("serial", 1), run("parallel", 2)
    assert parallel.complete and serial.complete
    assert parallel.cell_results == serial.cell_results
