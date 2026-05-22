"""Wave 6 — Observability and Maintainability.

FAILING TESTS committed before any fixes.

O-1: No staging-layer logging — entity row counts, column counts, timing invisible.
O-2: team_id correction logged at INFO without [AUDIT] prefix.
O-3: DALContractViolation raises missing layer= in many sites.
O-4: DB_PATH hardcoded — no FPL_DB_PATH environment variable override.
O-5: No hash-level reproducibility artifact.
O-6: No timing instrumentation at spine build boundaries.
"""

import os
import logging
import hashlib
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

TEST_DB_PATH = Path(__file__).parent.parent / "fixtures" / "test.db"


# ---------------------------------------------------------------------------
# O-4 — FPL_DB_PATH environment variable override
# ---------------------------------------------------------------------------

def test_fpl_db_path_env_override(monkeypatch):
    """O-4 FAILING TEST: DB_PATH must respect FPL_DB_PATH environment variable.

    FAILS before fix (DB_PATH hardcoded, env var ignored). PASSES after fix.
    """
    test_path = str(TEST_DB_PATH)
    monkeypatch.setenv("FPL_DB_PATH", test_path)

    import importlib
    import dal.config as config_mod
    importlib.reload(config_mod)

    assert str(config_mod.DB_PATH) == str(TEST_DB_PATH), (
        f"Expected DB_PATH={TEST_DB_PATH}, got {config_mod.DB_PATH}. "
        f"FPL_DB_PATH env var is not being respected."
    )


# ---------------------------------------------------------------------------
# O-1 — Staging layer must log entity row counts at INFO
# ---------------------------------------------------------------------------

def test_staging_logs_entity_row_count(caplog):
    """O-1 FAILING TEST: stage() must log entity name and row count after staging.

    FAILS before fix (no logging). PASSES after fix.
    """
    from dal.staging.transformer import stage
    from dal.staging.schema import load_schema

    with caplog.at_level(logging.INFO, logger="dal.staging.transformer"):
        stage(TEST_DB_PATH, load_schema("players"))

    logged_messages = [r.message for r in caplog.records]
    assert any("players" in msg and ("rows=" in msg or "staged" in msg)
               for msg in logged_messages), (
        f"Expected INFO log with entity 'players' and row count after staging. "
        f"Got messages: {logged_messages}"
    )


# ---------------------------------------------------------------------------
# O-2 — team_id corrections must use [AUDIT] prefix
# ---------------------------------------------------------------------------

def test_team_id_correction_uses_audit_prefix(caplog):
    """O-2 FAILING TEST: team_id corrections must log with [AUDIT] prefix.

    FAILS before fix (uses plain INFO without [AUDIT]). PASSES after fix.
    """
    from dal.intermediate.player_fixture import _validate_and_log_team_id_resolution

    df = pd.DataFrame([{
        "player_id": 1, "player_name": "Test", "gw": 1, "fixture_id": 1,
        "team_id": 99,  # wrong team — will be corrected to true_team_id
    }])
    true_team_id = pd.Series([1])  # correct value differs from df["team_id"]

    with caplog.at_level(logging.INFO, logger="dal.intermediate.player_fixture"):
        _validate_and_log_team_id_resolution(df, true_team_id)

    audit_messages = [r.message for r in caplog.records if "[AUDIT]" in r.message]
    assert len(audit_messages) >= 1, (
        f"Expected at least one [AUDIT] log message for team_id correction. "
        f"Got messages: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# O-5 — Spine fingerprint reproducibility
# ---------------------------------------------------------------------------

def test_spine_fingerprint_identical_across_runs():
    """O-5 FAILING TEST: spine fingerprint must be identical across two runs.

    FAILS before fix (no fingerprint computed). PASSES after fix.
    """
    from dal.reproducibility import compute_spine_fingerprint
    from dal.curated.player_gameweek_spine import build_player_gameweek_spine

    spine1 = build_player_gameweek_spine(TEST_DB_PATH)
    spine2 = build_player_gameweek_spine(TEST_DB_PATH)

    fp1 = compute_spine_fingerprint(spine1)
    fp2 = compute_spine_fingerprint(spine2)

    assert fp1["sha256"] == fp2["sha256"], (
        f"Spine fingerprint differs across two runs: {fp1['sha256']} != {fp2['sha256']}"
    )
    assert fp1["n_rows"] == fp2["n_rows"]
    assert fp1["n_cols"] == fp2["n_cols"]


# ---------------------------------------------------------------------------
# O-3 — All DALContractViolation raises must include layer=
# ---------------------------------------------------------------------------

def test_all_contract_violations_have_layer():
    """O-3: Every DALContractViolation raise site in dal/ must include layer=.

    Checks source code — if any raise is missing layer=, the test fails.
    Note: this is a static check, not a runtime check.
    """
    import ast
    project_root = Path(__file__).parent.parent
    dal_dir = project_root / "dal"

    missing_layer = []
    for py_file in dal_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        source = py_file.read_text(errors="ignore")
        # Find DALContractViolation raises without layer=
        lines = source.splitlines()
        in_raise = False
        raise_lines = []
        for i, line in enumerate(lines):
            if "raise DALContractViolation(" in line:
                # Check if this raise block contains layer=
                # Look ahead up to 10 lines
                block = "\n".join(lines[i:i+10])
                if "layer=" not in block:
                    missing_layer.append(
                        f"{py_file.relative_to(project_root)}:{i+1}: {line.strip()}"
                    )

    assert missing_layer == [], (
        f"DALContractViolation raises missing layer=:\n" + "\n".join(missing_layer)
    )
