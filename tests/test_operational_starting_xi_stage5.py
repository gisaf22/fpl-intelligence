"""Acceptance tests for the Stage 5 runner, `operational/starting_xi_stage5.py` (#73).

Every pin here is constructed (`tests/_stage5_publish.py`): no test reads the real pin or compares
D2 with a real manager. The outcomes are hand-computed from that publish's fixed points.

The runner's surface these tests assume is the proposal at the Stage 2 pause: `look` returns a
`Look` (its printed `text` plus the numbers behind it), `verdict` writes `VERDICT.md` and
`FEED.csv` into one directory and `REALISM.md` into another, `scan_outputs` and `check_feed` are the
two helper commands, and `pre_registration_mismatches` is the pre-run check against the `look` key.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from decisions.starting_xi import realism, verdict
from operational import starting_xi_stage5 as stage5
from tests import _stage5_publish as fx
from warehouse import served

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO_ROOT / "decisions" / "starting_xi" / "stage5_look.ipynb"
VERDICT_ENTRY_POINTS = ("crossed_share", "two_sided_p", "raw_p_values", "needs_rerun", "primary_verdict")
# Wording the look must never print: a p-value, an interval, or a pass or fail call.
VERDICT_WORDING = re.compile(r"p[- ]?value|interval|\bCI\b|confidence|\bpass(es|ed)?\b|\bfail|reject|significan", re.I)
LOOK_GWS = (4, 5, 6, 7, 8)
VERDICT_GWS = tuple(range(4, 12))


def _publish(tmp_path: Path, last_gw: int, **manifest: str | None) -> tuple[served.Pin, Path]:
    root = tmp_path / f"publish-{last_gw}"
    return fx.write(root, last_gw, **manifest), root


def _verdict(tmp_path: Path, last_gw: int = 11) -> tuple[Path, Path, served.Pin]:
    pin, root = _publish(tmp_path, last_gw)
    results, lab = tmp_path / "stage5_results", tmp_path / "power_lab_results"
    results.mkdir()
    lab.mkdir()
    stage5.verdict(pin, snapshot_root=root, results_dir=results, realism_dir=lab)
    return results, lab, pin


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raise(*_: object, **__: object) -> None:
    raise AssertionError("verdict code was called")


# --- AC1: the look prints descriptive numbers per gameweek and nothing of a verdict ---


@pytest.mark.integration
@pytest.mark.covers("#73 AC1")
def test_the_look_prints_each_gameweeks_panel_share_and_mean_difference_and_its_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in VERDICT_ENTRY_POINTS:
        monkeypatch.setattr(verdict, name, _raise)
    pin, root = _publish(tmp_path, 10)  # ratified past GW8, so used and ratified differ

    look = stage5.look(pin, snapshot_root=root)

    rows = look.rows.set_index("gameweek")
    assert list(rows.index) == list(LOOK_GWS)
    for gw in LOOK_GWS:
        outcomes = []
        differences = []
        for manager in fx.PANEL:
            d2, theirs = fx.d2_points(gw), fx.eleven_points(manager, gw)
            outcomes.append(1.0 if d2 > theirs else 0.5 if d2 == theirs else 0.0)
            differences.append(d2 - theirs)
        assert rows.at[gw, "panel_size"] == len(fx.PANEL)
        assert rows.at[gw, "d2_share"] == pytest.approx(sum(outcomes) / len(outcomes))
        assert rows.at[gw, "mean_points_difference"] == pytest.approx(sum(differences) / len(differences))
    # The tie counts 0.5: TIED ties every week, so GW4's share is (0.5 + 1 + 1) / 3, not 2/3 or 1.
    assert rows.at[4, "d2_share"] == pytest.approx(2.5 / 3)

    assert look.run_id == pin.run_id
    assert look.ratified_gameweeks == tuple(range(1, 11))
    assert look.gameweeks_used == LOOK_GWS
    assert look.managers_per_gameweek == {gw: len(fx.MANAGERS) for gw in range(1, 11)}
    assert look.panel_size == len(fx.PANEL)
    assert pin.run_id in look.text
    assert "GW10" in look.text, "the header omits the ratified gameweeks"
    assert not VERDICT_WORDING.search(look.text)


@pytest.mark.integration
@pytest.mark.covers("#73 AC1")
def test_the_look_header_does_not_show_the_used_gameweeks_as_the_ratified_ones(tmp_path: Path) -> None:
    pin, root = _publish(tmp_path, 10)
    look = stage5.look(pin, snapshot_root=root)
    assert look.ratified_gameweeks != look.gameweeks_used


# --- AC2: the verdict needs 8 scorable ratified gameweeks and uses exactly GW4-GW11 ---


@pytest.mark.integration
@pytest.mark.covers("#73 AC2")
@pytest.mark.covers("#76 AC9")
def test_the_verdict_refuses_a_pin_with_seven_scorable_gameweeks(tmp_path: Path) -> None:
    pin, root = _publish(tmp_path, 10)  # GW4-GW10
    with pytest.raises(ValueError, match="the 8 scorable ratified gameweeks"):
        stage5.verdict(pin, snapshot_root=root, results_dir=tmp_path, realism_dir=tmp_path)
    assert not list(tmp_path.glob("*.md")) and not list(tmp_path.glob("*.csv"))


@pytest.mark.integration
@pytest.mark.covers("#73 AC2")
@pytest.mark.covers("#76 AC9")
@pytest.mark.parametrize("last_gw", [11, 12])
def test_the_verdict_runs_on_exactly_gw4_to_gw11(tmp_path: Path, last_gw: int) -> None:
    results, _, _ = _verdict(tmp_path, last_gw)
    feed = pd.read_csv(results / "FEED.csv")
    assert tuple(sorted(feed["gameweek"].unique())) == VERDICT_GWS


# --- AC3: three files in two places, from one feed and pin, identified by what is committed ---


@pytest.mark.integration
@pytest.mark.covers("#73 AC3")
def test_the_verdict_writes_its_three_files_and_records_the_feed_and_realism_hashes(tmp_path: Path) -> None:
    results, lab, _ = _verdict(tmp_path)

    assert sorted(p.name for p in results.iterdir()) == ["FEED.csv", "VERDICT.md"]
    assert sorted(p.name for p in lab.iterdir()) == ["REALISM.md"]
    header = (results / "VERDICT.md").read_text(encoding="utf-8")
    feed = pd.read_csv(results / "FEED.csv")
    assert len(feed) == len(fx.PANEL) * len(VERDICT_GWS)
    assert str(len(feed)) in header
    assert _sha256(results / "FEED.csv") in header
    assert _sha256(lab / "REALISM.md") in header


@pytest.mark.integration
@pytest.mark.covers("#73 AC3")
def test_the_local_feed_is_git_ignored_and_the_verdict_beside_it_is_not() -> None:
    def ignored(path: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO_ROOT).returncode == 0

    assert ignored("decisions/starting_xi/stage5_results/FEED.csv")
    assert not ignored("decisions/starting_xi/stage5_results/VERDICT.md")


@pytest.mark.integration
@pytest.mark.covers("#73 AC3")
def test_a_realism_error_stops_the_run_and_leaves_no_verdict_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> Path:
        raise realism.RealismRefused("forced")

    monkeypatch.setattr(realism, "write", broken)
    pin, root = _publish(tmp_path, 15)
    results, lab = tmp_path / "results", tmp_path / "lab"
    results.mkdir()
    lab.mkdir()
    with pytest.raises(realism.RealismRefused):
        stage5.verdict(pin, snapshot_root=root, results_dir=results, realism_dir=lab)
    assert list(results.iterdir()) == [] and list(lab.iterdir()) == []


@pytest.mark.integration
@pytest.mark.covers("#73 AC3")
def test_a_second_verdict_run_on_the_pin_is_byte_identical(tmp_path: Path) -> None:
    first, first_lab, pin = _verdict(tmp_path / "first")
    root = tmp_path / "first" / "publish-15"
    second, second_lab = tmp_path / "second", tmp_path / "second_lab"
    second.mkdir()
    second_lab.mkdir()
    stage5.verdict(pin, snapshot_root=root, results_dir=second, realism_dir=second_lab)
    for name in ("VERDICT.md", "FEED.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert (first_lab / "REALISM.md").read_bytes() == (second_lab / "REALISM.md").read_bytes()


# --- AC4: one shared feed builder, so the two modes agree on who was scored ---


@pytest.mark.integration
@pytest.mark.covers("#73 AC4")
def test_the_look_and_the_verdict_have_the_same_panel_and_outcomes_in_each_gameweek(tmp_path: Path) -> None:
    results, _, pin = _verdict(tmp_path)
    look = stage5.look(pin, snapshot_root=tmp_path / "publish-15")

    from_verdict = pd.read_csv(results / "FEED.csv")
    from_verdict = from_verdict[from_verdict["gameweek"].isin(LOOK_GWS)].reset_index(drop=True)
    from_look = look.feed.loc[:, list(verdict.COLUMNS)].reset_index(drop=True)
    assert set(from_look["manager_id"]) == set(fx.PANEL), "a self-cohort or screened-out manager was scored"
    pd.testing.assert_frame_equal(from_look, from_verdict, check_dtype=False)


# --- AC5: the verdict header identifies the pin, and a missing field stops the run first ---

HEADER_FIELDS = ("run_id", "built_at", "git_sha", "ratified_gameweeks", "managers_per_gameweek")


@pytest.mark.unit
@pytest.mark.covers("#73 AC5")
@pytest.mark.parametrize("field", HEADER_FIELDS)
def test_a_verdict_header_missing_a_field_raises_and_names_it(tmp_path: Path, field: str) -> None:
    pin, root = _publish(tmp_path, 15)
    header = stage5.verdict_header(pin, snapshot_root=root)
    with pytest.raises(ValueError, match=field):
        stage5.render_verdict_header(dataclasses.replace(header, **{field: None}))


@pytest.mark.unit
@pytest.mark.covers("#73 AC5")
def test_a_verdict_whose_header_lacks_a_field_writes_no_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin, root = _publish(tmp_path, 15)
    complete = stage5.verdict_header(pin, snapshot_root=root)
    monkeypatch.setattr(stage5, "verdict_header", lambda *_, **__: dataclasses.replace(complete, git_sha=None))
    results, lab = tmp_path / "results", tmp_path / "lab"
    results.mkdir()
    lab.mkdir()
    with pytest.raises(ValueError, match="git_sha"):
        stage5.verdict(pin, snapshot_root=root, results_dir=results, realism_dir=lab)
    assert list(results.iterdir()) == [] and list(lab.iterdir()) == []


@pytest.mark.integration
@pytest.mark.covers("#73 AC5")
def test_the_verdict_header_records_the_pins_identity_ratified_gameweeks_and_manager_counts(tmp_path: Path) -> None:
    results, _, pin = _verdict(tmp_path)
    header = (results / "VERDICT.md").read_text(encoding="utf-8")
    assert pin.run_id in header
    assert fx.BUILT_AT in header
    assert fx.GIT_SHA in header
    assert "- Verdict gameweeks: GW4-GW11 (8)\n" in header
    assert str(len(fx.MANAGERS)) in header


# --- AC6: the look can reach no verdict number, shown by what it does ---

_LOOK_IN_A_FRESH_INTERPRETER = """
import sys
from pathlib import Path
from decisions.starting_xi import verdict
def _raise(*args, **kwargs):
    raise AssertionError("verdict code was called")
for name in {names!r}:
    setattr(verdict, name, _raise)
from operational import starting_xi_stage5
from warehouse import served
root = Path(sys.argv[1])
print(starting_xi_stage5.look(served.pin_of(root / sys.argv[2]), snapshot_root=root).text)
"""


@pytest.mark.integration
@pytest.mark.covers("#73 AC6")
def test_the_look_runs_to_completion_with_every_verdict_entry_point_patched_to_raise(tmp_path: Path) -> None:
    pin, root = _publish(tmp_path, 8)
    script = _LOOK_IN_A_FRESH_INTERPRETER.format(names=VERDICT_ENTRY_POINTS)
    run = subprocess.run(
        [sys.executable, "-c", script, str(root), pin.run_id], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    assert pin.run_id in run.stdout
    assert not VERDICT_WORDING.search(run.stdout)


def _code_cells(notebook: Path) -> list[str]:
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    return ["".join(cell["source"]) for cell in cells if cell["cell_type"] == "code"]


@pytest.mark.integration
@pytest.mark.covers("#73 AC6")
def test_the_look_notebook_imports_only_the_look_function_and_its_first_cell_prints_the_header() -> None:
    cells = _code_cells(NOTEBOOK)
    imports = [line.strip() for cell in cells for line in cell.splitlines() if re.match(r"\s*(import|from)\s", line)]
    assert imports == ["from operational.starting_xi_stage5 import look"]
    first = cells[0]
    for shown in ("run_id", "gameweeks_used", "panel_size"):
        assert shown in first, f"the first cell does not print {shown}"
    assert "print(" in first


# --- AC7: the committed outputs regenerate byte for byte, and the local feed matches its record ---

_VERDICT_IN_A_FRESH_INTERPRETER = """
import sys
from pathlib import Path
from operational import starting_xi_stage5
from warehouse import served
root = Path(sys.argv[1])
starting_xi_stage5.verdict(
    served.pin_of(root / sys.argv[2]), snapshot_root=root, results_dir=Path(sys.argv[3]), realism_dir=Path(sys.argv[4])
)
"""


@pytest.mark.integration
@pytest.mark.covers("#73 AC7")
def test_two_verdict_runs_in_separate_processes_are_byte_identical_and_the_feed_matches_its_record(
    tmp_path: Path,
) -> None:
    pin, root = _publish(tmp_path, 15)
    outputs = []
    for name in ("one", "two"):
        results, lab = tmp_path / name / "results", tmp_path / name / "lab"
        results.mkdir(parents=True)
        lab.mkdir()
        run = subprocess.run(
            [sys.executable, "-c", _VERDICT_IN_A_FRESH_INTERPRETER, str(root), pin.run_id, str(results), str(lab)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
        outputs.append((results, lab))
    (one, one_lab), (two, two_lab) = outputs
    assert (one / "VERDICT.md").read_bytes() == (two / "VERDICT.md").read_bytes()
    assert (one_lab / "REALISM.md").read_bytes() == (two_lab / "REALISM.md").read_bytes()
    assert stage5.check_feed(two / "FEED.csv", one / "VERDICT.md") == []


@pytest.mark.integration
@pytest.mark.covers("#73 AC7")
def test_the_feed_keeps_the_verdicts_column_order_and_a_sorted_row_order(tmp_path: Path) -> None:
    results, _, _ = _verdict(tmp_path)
    feed = pd.read_csv(results / "FEED.csv")
    assert list(feed.columns) == list(verdict.COLUMNS)
    assert feed.equals(feed.sort_values(["manager_id", "gameweek"], ignore_index=True))


@pytest.mark.integration
@pytest.mark.covers("#73 AC7")
@pytest.mark.parametrize("change", ["drop_a_row", "shuffle_rows", "swap_columns"])
def test_the_feed_check_names_a_feed_that_differs_from_its_record(tmp_path: Path, change: str) -> None:
    results, _, _ = _verdict(tmp_path)
    path = results / "FEED.csv"
    feed = pd.read_csv(path)
    if change == "drop_a_row":
        feed = feed.iloc[1:]
    elif change == "shuffle_rows":
        feed = feed.iloc[::-1]
    else:
        feed = feed.loc[:, list(reversed(feed.columns))]
    feed.to_csv(path, index=False)
    assert stage5.check_feed(path, results / "VERDICT.md") != []


# --- AC8: nothing committed holds a manager's id or a per-manager row ---


def _look_notebook_with_outputs(tmp_path: Path, text: str) -> Path:
    notebook = tmp_path / "stage5_look.ipynb"
    cell = {"cell_type": "code", "source": ["print(look)"], "outputs": [{"output_type": "stream", "text": [text]}]}
    notebook.write_text(json.dumps({"cells": [cell], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}))
    return notebook


@pytest.mark.integration
@pytest.mark.covers("#73 AC8")
def test_the_committed_outputs_hold_no_manager_id_and_no_per_manager_row(tmp_path: Path) -> None:
    results, lab, pin = _verdict(tmp_path)
    look = stage5.look(pin, snapshot_root=tmp_path / "publish-15")
    notebook = _look_notebook_with_outputs(tmp_path, look.text)
    outputs = [results / "VERDICT.md", lab / "REALISM.md", notebook]
    assert stage5.scan_outputs(outputs, manager_ids=fx.MANAGERS) == []


@pytest.mark.integration
@pytest.mark.covers("#73 AC8")
def test_the_scan_names_one_leaked_manager_id(tmp_path: Path) -> None:
    results, lab, _ = _verdict(tmp_path)
    path = results / "VERDICT.md"
    path.write_text(path.read_text(encoding="utf-8") + f"\nbest manager: {fx.BEATEN}\n", encoding="utf-8")
    findings = stage5.scan_outputs([path, lab / "REALISM.md"], manager_ids=fx.MANAGERS)
    assert len(findings) == 1 and str(fx.BEATEN) in findings[0]


@pytest.mark.integration
@pytest.mark.covers("#73 AC8")
def test_the_scan_names_a_per_manager_row_without_an_id(tmp_path: Path) -> None:
    # A row keyed on anything but a gameweek, a group or a gameweek count is a per-manager row
    # (the rule proposed at the Stage 2 pause).
    results, _, _ = _verdict(tmp_path)
    path = results / "VERDICT.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n| manager 3 | 0.5 |\n", encoding="utf-8")
    assert stage5.scan_outputs([path], manager_ids=fx.MANAGERS) != []


@pytest.mark.integration
@pytest.mark.covers("#73 AC8")
def test_the_scan_reads_a_notebooks_saved_outputs(tmp_path: Path) -> None:
    notebook = _look_notebook_with_outputs(tmp_path, f"GW4 panel 3; {fx.TIED} tied\n")
    assert stage5.scan_outputs([notebook], manager_ids=fx.MANAGERS) != []


# --- AC10: the verdict header's build time and git sha are the pin's ---


@pytest.mark.integration
@pytest.mark.covers("#73 AC10")
def test_the_verdict_header_takes_its_build_time_and_git_sha_from_the_pin(tmp_path: Path) -> None:
    pin, root = _publish(tmp_path, 15, built_at="2026-11-02T00:00:00+00:00", git_sha="f" * 40)
    header = stage5.verdict_header(pin, snapshot_root=root)
    assert (header.built_at, header.git_sha) == ("2026-11-02T00:00:00+00:00", "f" * 40)
    assert (header.built_at, header.git_sha) == (pin.built_at, pin.git_sha)


@pytest.mark.unit
@pytest.mark.covers("#73 AC10")
@pytest.mark.parametrize("field", ["built_at", "git_sha"])
@pytest.mark.parametrize("mode", ["look", "verdict"])
def test_the_runner_refuses_a_pin_without_a_build_field_and_names_it(tmp_path: Path, field: str, mode: str) -> None:
    pin, root = _publish(tmp_path, 15, **{field: None})
    assert getattr(pin, field) is None
    results, lab = tmp_path / "results", tmp_path / "lab"
    results.mkdir()
    lab.mkdir()
    with pytest.raises(served.ServedContractError, match=field):
        if mode == "look":
            stage5.look(pin, snapshot_root=root)
        else:
            stage5.verdict(pin, snapshot_root=root, results_dir=results, realism_dir=lab)
    assert list(results.iterdir()) == [] and list(lab.iterdir()) == []


@pytest.mark.unit
@pytest.mark.covers("#73 AC10")
def test_a_pin_without_the_build_fields_still_loads_outside_the_runner(tmp_path: Path) -> None:
    pin, root = _publish(tmp_path, 15, built_at=None, git_sha=None)
    assert not served.load(fx.SEASON, pin=pin, snapshot_root=root).gameweek.empty
    assert not served.load_managers(fx.SEASON, pin=pin, snapshot_root=root).picks.empty


# --- AC11: the look stops at GW8 and never pads a shorter pin ---


@pytest.mark.unit
@pytest.mark.covers("#73 AC11")
def test_a_pin_ratified_past_gw8_gives_a_look_at_gw4_to_gw8_only(tmp_path: Path) -> None:
    pin, root = _publish(tmp_path, 10)
    look = stage5.look(pin, snapshot_root=root)
    assert look.gameweeks_used == LOOK_GWS
    assert tuple(look.rows["gameweek"]) == LOOK_GWS
    assert set(look.feed["gameweek"]) == set(LOOK_GWS)
    assert look.ceiling_gw == stage5.LOOK_CEILING_GW == 8
    assert "GW8" in look.text and "ceiling" in look.text.lower()


@pytest.mark.unit
@pytest.mark.covers("#73 AC11")
def test_a_pin_ratified_to_gw6_gives_a_look_at_gw4_to_gw6_without_padding_or_error(tmp_path: Path) -> None:
    pin, root = _publish(tmp_path, 6)
    look = stage5.look(pin, snapshot_root=root)
    assert look.gameweeks_used == (4, 5, 6)
    assert tuple(look.rows["gameweek"]) == (4, 5, 6)
    assert set(look.feed["gameweek"]) == {4, 5, 6}
    assert look.ratified_gameweeks == tuple(range(1, 7))
    assert "GW8" in look.text and "ceiling" in look.text.lower()


# --- AC12: the runner's pre-run check holds the `look` key and its constants together ---


@pytest.mark.unit
@pytest.mark.covers("#73 AC12")
def test_the_runner_code_matches_the_registered_look_key() -> None:
    registered = yaml.safe_load(stage5.PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
    assert stage5.pre_registration_mismatches(registered) == []


@pytest.mark.unit
@pytest.mark.covers("#73 AC12")
@pytest.mark.parametrize(("constant", "value"), [("LOOK_CEILING_GW", 9), ("ONCE_PER_PURPOSE", False)])
def test_a_drifted_look_constant_is_a_named_mismatch(
    monkeypatch: pytest.MonkeyPatch, constant: str, value: object
) -> None:
    registered = yaml.safe_load(stage5.PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
    monkeypatch.setattr(stage5, constant, value)
    assert [m.split(":")[0] for m in stage5.pre_registration_mismatches(registered)] == ["look"]


@pytest.mark.unit
@pytest.mark.covers("#73 AC12")
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("ceiling_gw",), 9),
        (("overlap", "look", "last_gw"), 9),
        (("overlap", "look", "first_gw"), 5),
        (("overlap", "verdict", "last_gw"), 16),
        (("once_per_purpose",), False),
    ],
)
def test_a_changed_look_value_in_the_file_is_a_named_mismatch(path: tuple[str, ...], value: object) -> None:
    registered = yaml.safe_load(stage5.PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
    target = registered["look"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert [m.split(":")[0] for m in stage5.pre_registration_mismatches(registered)] == ["look"]


@pytest.mark.unit
@pytest.mark.covers("#73 AC12")
def test_a_registration_without_the_look_key_is_a_named_mismatch() -> None:
    registered = yaml.safe_load(stage5.PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
    del registered["look"]
    assert [m.split(":")[0] for m in stage5.pre_registration_mismatches(registered)] == ["look"]


@pytest.mark.unit
@pytest.mark.covers("#73 AC12")
@pytest.mark.parametrize("mode", ["look", "verdict"])
def test_both_modes_refuse_to_run_off_the_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    registered = yaml.safe_load(stage5.PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
    del registered["look"]
    off = tmp_path / "PRE_REGISTRATION.yaml"
    off.write_text(yaml.safe_dump(registered), encoding="utf-8")
    monkeypatch.setattr(stage5, "PRE_REGISTRATION_PATH", off)
    pin, root = _publish(tmp_path, 15)
    with pytest.raises(stage5.OffRegistration, match="look"):
        if mode == "look":
            stage5.look(pin, snapshot_root=root)
        else:
            stage5.verdict(pin, snapshot_root=root, results_dir=tmp_path, realism_dir=tmp_path)
    assert not list(tmp_path.glob("*.md")) and not list(tmp_path.glob("*.csv"))


# --- #76 AC6: the committed pin and registration clear the runner's pre-run checks ---


@pytest.mark.integration
@pytest.mark.covers("#76 AC6")
@pytest.mark.parametrize("mode", ["look", "verdict"])
def test_the_committed_pin_clears_the_registration_and_build_identity_checks(tmp_path: Path, mode: str) -> None:
    # No snapshot is synced here, so a run past both checks stops at the first file's bytes instead.
    with pytest.raises(served.ServedContractError, match=r"sha256 None does not match pin"):
        if mode == "look":
            stage5.look(snapshot_root=tmp_path)
        else:
            stage5.verdict(snapshot_root=tmp_path, results_dir=tmp_path, realism_dir=tmp_path)
    assert "look_pin" in yaml.safe_load(stage5.PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
