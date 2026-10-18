"""Module-shape tests for `rankers.py`: the harness protocol, the leakage assertion and the import
closure. The rules' definitions are tested in `test_rules.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi import rankers
from decisions.starting_xi.harness import RankerOutput as HarnessRankerOutput
from decisions.starting_xi.rankers import _assert_lag_safe
from warehouse import served

pytestmark = pytest.mark.unit

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "warehouse" / "fixtures"
RUN_ID = "39064033745"


def test_every_rule_output_satisfies_the_protocol_the_harness_consumes() -> None:
    """The harness never imports this module, so the two meet structurally at the composition root.
    If they drifted apart, nothing else would notice."""
    frames = served.load("2025-26", pin=served.pin_of(FIXTURE_ROOT / RUN_ID), snapshot_root=FIXTURE_ROOT)
    for rank in rankers.rules(0).values():
        assert isinstance(rank(frames), HarnessRankerOutput)


def test_the_lag_safety_assertion_fires_on_a_leaking_column() -> None:
    frame = pd.DataFrame({"player_id": [1, 1, 2, 2], "gw": [1, 2, 1, 2], "score": [np.nan, 1.0, np.nan, 3.0]})
    _assert_lag_safe(frame, "score")

    leaking = frame.copy()
    leaking.loc[0, "score"] = 5.0
    with pytest.raises(AssertionError, match="first population row"):
        _assert_lag_safe(leaking, "score", rule="ppg_gameweek_season")


def test_the_import_closure_reaches_model_and_no_harness_side_sibling() -> None:
    """Run as a subprocess: the test session has already imported `model`, so an in-process
    `sys.modules` check would pass against any module."""
    program = (
        "import sys;"
        "import decisions.starting_xi.rankers;"
        "banned = ('research', 'serve', 'operational',"
        " 'decisions.starting_xi.harness', 'decisions.starting_xi.sampler',"
        " 'decisions.starting_xi.formations', 'decisions.starting_xi.results',"
        " 'decisions.starting_xi.uncertainty');"
        "reached = sorted(m for m in sys.modules if m.startswith(banned));"
        "print(repr(reached));"
        "print('model.eval.baselines' in sys.modules)"
    )
    child = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, check=True)
    reached, baselines = child.stdout.splitlines()
    assert reached == "[]"
    assert baselines == "True"
