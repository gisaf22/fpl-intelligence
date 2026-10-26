"""Tests for the `starting_xi` composition root (`operational.starting_xi`).

The pre-run check is tested against `PRE_REGISTRATION.yaml` and a throwaway git repo. The end-to-end
pass (`test_run_study_end_to_end_on_a_small_fixture`) exercises `run_study` for real -- the
sampler's actual rejection sampling and the harness's actual replay -- against fake, cheap rankers
standing in for `rankers.py`'s real rules, on the same small-universe convention
`tests/decisions/starting_xi/test_sampler.py` uses (a feasible, budget-and-club-legal universe small
enough to run a real pilot over).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest
import yaml

from decisions.starting_xi import orderings, rankers, results
from domain.fpl_squad import POSITION_BY_ID
from operational import starting_xi
from operational.starting_xi import run_study
from warehouse import served

pytestmark = pytest.mark.unit

_ID_BY_POSITION = {label: position_id for position_id, label in POSITION_BY_ID.items()}


# ---------------------------------------------------------------------------
# Small, sampler-feasible warehouse frames (convention: tests/decisions/starting_xi/test_sampler.py)
# ---------------------------------------------------------------------------


def _small_frames(n_gw: int = 8, seed: int = 3) -> served.Frames:
    """68 players over GK/DEF/MID/FWD, GW1..`n_gw`, 8 clubs, prices spread so §2.6's uniform
    rejection sampling clears the proceed threshold on a real pilot. A third enter at GW2; as in
    the loader's output, a player has no row before his entry gameweek."""
    rng = np.random.default_rng(seed)
    counts = {"GK": 10, "DEF": 22, "MID": 24, "FWD": 12}
    rows: list[dict[str, object]] = []
    player_id = 0
    for position, n in counts.items():
        for slot in range(n):
            player_id += 1
            # A narrower band than the real price range keeps a 2/5/5/3 squad affordable under
            # the 100.0 cap on this small a universe; a wider one red-lines the pilot (§2.6).
            price = float(np.round(rng.uniform(4.0, 8.0), 1))
            team = (player_id % 8) + 1
            debut = 1 if slot % 3 else 2
            for gw in range(debut, n_gw + 1):
                rows.append(
                    {
                        "player_id": player_id,
                        "gw": gw,
                        "fixture_count": 1,
                        "deadline_fixture_count": 1,
                        "deadline_count_is_realised": False,
                        "total_points": float(rng.integers(0, 12)),
                        "minutes": 90.0,
                        "team_id": team,
                        "position_id": _ID_BY_POSITION[position],
                        "price": price,
                        "entry_gw": debut,
                    }
                )
    gameweek = pd.DataFrame(rows)
    return served.Frames(fixture=pd.DataFrame(), gameweek=gameweek, pin=_warehouse_pin())


@dataclass(frozen=True)
class _FakeRanker:
    """A stand-in for §6.1's `RankerOutput`, satisfying the harness's protocol structurally."""

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


def _fake_rank_fns(seed: int) -> dict[str, Callable[[served.Frames], _FakeRanker]]:
    """One fake rule per name in `rankers.rules(seed)`, at `rankers.RULE_WINDOW`.

    Cheap and deterministic, standing in for the real rules -- `test_rules.py` covers those; this
    module's job is the wiring around them, not the rules themselves.
    """

    def _make(name: str) -> Callable[[served.Frames], _FakeRanker]:
        def _rank(frames: served.Frames) -> _FakeRanker:
            gameweek = frames.gameweek
            scores = gameweek.loc[:, ["player_id", "gw"]].copy()
            scores["score"] = gameweek["total_points"].fillna(0.0) - gameweek["player_id"].astype(float) * 0.001
            return _FakeRanker(name=name, window=rankers.RULE_WINDOW, scores=scores)

        return _rank

    return {name: _make(name) for name in rankers.rules(seed)}


def _git_repo(root, *, dirty: bool = False):
    """A throwaway one-commit repository; `dirty` leaves an untracked file in it."""
    root.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "init", "-q"], check=True)
    (root / "a.txt").write_text("a\n")
    subprocess.run([*git, "add", "a.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)
    if dirty:
        (root / "b.txt").write_text("b\n")
    return root


def _warehouse_pin() -> served.Pin:
    return served.Pin(run_id="39064033745", sha256={"fct_player_fixture.parquet": "e" * 64})


def _off_registration_flags(tmp_path) -> dict[str, object]:
    """What the small-fixture runs need: they are off-registration by construction (5 squads,
    GW2-8, seed != 0), so they run forced and land non-canonical."""
    return dict(
        repo_root=_git_repo(tmp_path / "repo"),
        allow_off_registration=True,
    )


# ---------------------------------------------------------------------------
# Run hygiene: the pre-run check against PRE_REGISTRATION.yaml, and the git tree
# ---------------------------------------------------------------------------

_REGISTERED = dict(
    bench_order=orderings.PRE_REGISTERED_ORDERINGS,
    rank_fns=rankers.rules(0),
    gameweeks=range(4, 39),
    n_squads=300,
    seed=0,
)


def _pre_registration() -> dict[str, object]:
    payload: dict[str, object] = yaml.safe_load(starting_xi.PRE_REGISTRATION_PATH.read_text())
    return payload


@pytest.mark.covers("#33 AC3 (proposed)")
def test_the_registered_configuration_has_no_mismatches() -> None:
    assert starting_xi.pre_registration_mismatches(**_REGISTERED, pre_registration=_pre_registration()) == []


def test_every_off_registration_field_is_named() -> None:
    by_weighted = (orderings.PRE_REGISTERED_ORDERINGS[0], ("by_weighted_score", lambda *_: None))
    rules_minus_one = {name: fn for name, fn in rankers.rules(0).items() if name != "random"}
    mismatches = starting_xi.pre_registration_mismatches(
        bench_order=by_weighted,
        rank_fns=rules_minus_one,
        gameweeks=range(2, 9),
        n_squads=5,
        seed=7,
        pre_registration=_pre_registration(),
    )
    assert {m.split(":")[0] for m in mismatches} == {
        "bench_ordering",
        "rules",
        "scored_gameweeks",
        "squads_per_gameweek",
        "master_seed",
    }


@pytest.mark.covers("#33 AC3 (proposed)")
def test_preflight_on_a_clean_tree_and_registered_configuration_is_canonical(tmp_path) -> None:
    repo = _git_repo(tmp_path / "repo")
    data = _warehouse_pin()
    provenance = starting_xi.preflight(**_REGISTERED, warehouse_pin=data, repo_root=repo)

    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    assert provenance.git_sha == head.stdout.strip()
    assert provenance.clean_tree is True
    assert provenance.canonical is True
    assert provenance.non_canonical_reasons == ()
    assert provenance.warehouse_run_id == data.run_id
    assert provenance.warehouse_sha256 == data.sha256
    expected_pre_registration = hashlib.sha256(starting_xi.PRE_REGISTRATION_PATH.read_bytes()).hexdigest()
    assert provenance.pre_registration_sha256 == expected_pre_registration


def test_preflight_refuses_a_dirty_tree_unless_allowed_and_then_marks_it_non_canonical(tmp_path) -> None:
    repo = _git_repo(tmp_path / "repo", dirty=True)
    data = _warehouse_pin()
    with pytest.raises(starting_xi.RunRefused, match="dirty"):
        starting_xi.preflight(**_REGISTERED, warehouse_pin=data, repo_root=repo)

    provenance = starting_xi.preflight(**_REGISTERED, warehouse_pin=data, repo_root=repo, allow_dirty=True)
    assert provenance.clean_tree is False
    assert provenance.canonical is False
    assert provenance.non_canonical_reasons == ("dirty_tree",)


def test_preflight_refuses_off_registration_unless_forced_and_then_marks_it_non_canonical(tmp_path) -> None:
    repo = _git_repo(tmp_path / "repo")
    data = _warehouse_pin()
    off = {**_REGISTERED, "n_squads": 5}
    with pytest.raises(starting_xi.RunRefused, match="squads_per_gameweek"):
        starting_xi.preflight(**off, warehouse_pin=data, repo_root=repo)

    provenance = starting_xi.preflight(**off, warehouse_pin=data, repo_root=repo, allow_off_registration=True)
    assert provenance.canonical is False
    assert provenance.non_canonical_reasons == ("off_registration:squads_per_gameweek",)


def test_run_study_refuses_before_writing_anything(tmp_path) -> None:
    with pytest.raises(starting_xi.RunRefused):
        run_study(
            _small_frames(n_gw=8),
            rank_fns=_fake_rank_fns(7),
            gameweeks=range(2, 9),
            n_squads=5,
            seed=7,
            squad_mode="uniform",
            results_root=tmp_path / "results",
            repo_root=_git_repo(tmp_path / "repo"),
        )
    assert not (tmp_path / "results").exists()


# ---------------------------------------------------------------------------
# §5.1.2's end-to-end pass: the DB-free core, on a small fixture
# ---------------------------------------------------------------------------


def test_run_study_end_to_end_on_a_small_fixture(tmp_path) -> None:
    rank_fns = _fake_rank_fns(7)

    run = run_study(
        _small_frames(n_gw=8),
        rank_fns=rank_fns,
        gameweeks=range(2, 9),
        n_squads=5,
        seed=7,
        squad_mode="uniform",
        results_root=tmp_path / "results",
        **_off_registration_flags(tmp_path),
    )

    assert run.n_squad_weeks > 0
    assert run.results_dir == tmp_path / "results" / run.run_id

    read_back = results.read(tmp_path / "results", run.run_id)
    assert len(read_back["squad_weeks"]) == run.n_squad_weeks
    assert set(read_back) == {"squad_weeks", "ordering_replays", "manifest"}
    assert set(read_back["squad_weeks"]["ranker"]) == set(rankers.rules(7))
    manifest = read_back["manifest"]
    assert manifest["provenance"]["canonical"] is False
    assert "off_registration:squads_per_gameweek" in manifest["provenance"]["non_canonical_reasons"]
    assert manifest["identity"]["construction"] == starting_xi.CONSTRUCTION


def test_same_seed_reproduces_run_id_and_squad_set_id(tmp_path) -> None:
    frames = _small_frames(n_gw=8)
    kwargs = dict(
        rank_fns=_fake_rank_fns(11),
        gameweeks=range(2, 9),
        n_squads=5,
        seed=11,
        squad_mode="uniform",
        **_off_registration_flags(tmp_path),
    )

    first = run_study(frames, results_root=tmp_path / "a", **kwargs)
    second = run_study(frames, results_root=tmp_path / "b", **kwargs)

    assert first.run_id == second.run_id
    manifest_a = json.loads((tmp_path / "a" / first.run_id / "manifest.json").read_text())
    manifest_b = json.loads((tmp_path / "b" / second.run_id / "manifest.json").read_text())
    assert manifest_a["identity"]["squad_set_id"] == manifest_b["identity"]["squad_set_id"]


def test_importing_the_composition_root_reaches_model_and_warehouse_and_not_research() -> None:
    """§3.8: the composition root is the one legal place Tier A and Tier B meet, so `model` (via
    `rankers.py`) and `warehouse` (via `served.load`) are expected. `research` is not needed by
    anything this module imports and must not leak in -- §3.9 excludes it from both tiers.

    `serve` is *not* asserted absent: `operational/__init__.py` eagerly re-exports
    `operational.recommend`, which imports `serve`, so `import operational.starting_xi` always
    executes that package `__init__` first and pulls `serve` in regardless of what
    `starting_xi.py` itself imports (§5.6's re-export hazard, pre-existing and unrelated to this
    module). Asserting its absence would be asserting something false about this repository.
    """
    program = (
        "import sys; import operational.starting_xi; "
        "reached = {m.split('.')[0] for m in sys.modules}; "
        "assert 'model' in reached, reached; "
        "assert 'warehouse' in reached, reached; "
        "assert 'research' not in reached, reached"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0
