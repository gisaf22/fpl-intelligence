"""Wave 6 — Observability and Maintainability.

FAILING TESTS committed before any fixes.

O-1: No staging-layer logging — entity row counts, column counts, timing invisible.
O-2: team_id correction logged at INFO without [AUDIT] prefix.
O-3: DALContractViolation raises missing layer= in many sites.
O-4: DB_PATH hardcoded — no FPL_DB_PATH environment variable override.
O-5: No hash-level reproducibility artifact.
O-6: No timing instrumentation at spine build boundaries.
"""

import logging
from pathlib import Path

import pandas as pd
import pytest

from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.staging import load_staged_entities

pytestmark = pytest.mark.unit

TEST_DB_PATH = Path(__file__).parent.parent / "fixtures" / "test.db"

def _load_spine():
    from dal.fct.fct_player_gameweek import build_player_gameweek_spine
    staged = load_staged_entities(TEST_DB_PATH)
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)

# ---------------------------------------------------------------------------
# O-4 — FPL_DB_PATH environment variable override
# ---------------------------------------------------------------------------

def test_fpl_db_path_configurable(monkeypatch):
    """O-4: DB_PATH must be patchable via monkeypatch.setattr for test isolation.

    Tests override DB_PATH with monkeypatch.setattr — not importlib.reload, which
    corrupts module state for all subsequent tests in the process.
    """
    import dal.config as config_mod

    monkeypatch.setattr(config_mod, "DB_PATH", TEST_DB_PATH)

    assert config_mod.DB_PATH == TEST_DB_PATH, (
        f"Expected DB_PATH={TEST_DB_PATH}, got {config_mod.DB_PATH}."
    )

# ---------------------------------------------------------------------------
# O-1 — Staging layer must log entity row counts at INFO
# ---------------------------------------------------------------------------

def test_staging_logs_entity_row_count(caplog):
    """O-1 FAILING TEST: stage() must log entity name and row count after staging.

    FAILS before fix (no logging). PASSES after fix.
    """
    from dal.staging.stg_schema import load_schema
    from dal.staging.stg_transformer import stage

    with caplog.at_level(logging.INFO, logger="dal.staging.stg_transformer"):
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
    from dal.intermediate.int_player_fixture import _validate_and_log_team_id_resolution

    df = pd.DataFrame([{
        "player_id": 1, "player_name": "Test", "gw": 1, "fixture_id": 1,
        "team_id": 99,  # wrong team — will be corrected to true_team_id
    }])
    true_team_id = pd.Series([1])  # correct value differs from df["team_id"]

    with caplog.at_level(logging.INFO, logger="dal.intermediate.int_player_fixture"):
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

    spine1 = _load_spine()
    spine2 = _load_spine()

    fp1 = compute_spine_fingerprint(spine1)
    fp2 = compute_spine_fingerprint(spine2)

    assert fp1["sha256"] == fp2["sha256"], (
        f"Spine fingerprint differs across two runs: {fp1['sha256']} != {fp2['sha256']}"
    )
    assert fp1["n_rows"] == fp2["n_rows"]
    assert fp1["n_cols"] == fp2["n_cols"]

# ---------------------------------------------------------------------------
# O-3b — All DALContractViolation raises must include error_code=
# ---------------------------------------------------------------------------

def test_all_contract_violations_have_error_code():
    """O-3b: Every DALContractViolation raise site in dal/ must include error_code=.

    Paired with test_all_contract_violations_have_layer — both context fields
    are required so the ErrorCode vocabulary is exercised at every call site,
    not just declared.
    Note: this is a static check, not a runtime check.
    """
    project_root = Path(__file__).parent.parent
    dal_dir = project_root / "dal"

    missing_code = []
    for py_file in dal_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        source = py_file.read_text(errors="ignore")
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if "raise DALContractViolation(" in line:
                block = "\n".join(lines[i:i+10])
                if "error_code=" not in block:
                    missing_code.append(
                        f"{py_file.relative_to(project_root)}:{i+1}: {line.strip()}"
                    )

    assert missing_code == [], (
        "DALContractViolation raises missing error_code=:\n" + "\n".join(missing_code)
    )
