"""
Tests for Briefing Pydantic models driven by docs/contracts/test_cases.json.

TC-001, TC-002, TC-006  must succeed (model_validate returns a Briefing instance).
TC-003, TC-004, TC-005  must raise ValidationError, and the error message must
                        contain the field path in violations[0].field.
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fpl_intelligence.models.briefing import Briefing

_TC_PATH = Path(__file__).parent.parent / "docs" / "contracts" / "test_cases.json"


def _load_cases() -> dict:
    with _TC_PATH.open() as f:
        return {tc["id"]: tc for tc in json.load(f)["test_cases"]}


CASES = _load_cases()


# ─── Passing cases ────────────────────────────────────────────────────────────

def test_tc001_valid_full_output():
    tc = CASES["TC-001"]
    result = Briefing.model_validate(tc["input"])
    assert result.meta.gw == 33
    assert result.context.gw_type.value == "dgw"


def test_tc002_valid_partial_one_signal_degraded():
    tc = CASES["TC-002"]
    result = Briefing.model_validate(tc["input"])
    assert result.meta.analyst_status.value == "partial"


def test_tc006_valid_unknown_signal_key():
    tc = CASES["TC-006"]
    result = Briefing.model_validate(tc["input"])
    # unknown signal key must be accepted without rejection
    assert result is not None


# ─── Rejection cases ──────────────────────────────────────────────────────────

def test_tc003_degraded_signal_missing_required_fields():
    tc = CASES["TC-003"]
    with pytest.raises(ValidationError) as exc_info:
        Briefing.model_validate(tc["input"])
    field_path = tc["violations"][0]["field"]
    assert field_path in str(exc_info.value), (
        f"Expected '{field_path}' in error message.\n"
        f"Actual error:\n{exc_info.value}"
    )


def test_tc004_gw_mismatch():
    tc = CASES["TC-004"]
    with pytest.raises(ValidationError) as exc_info:
        Briefing.model_validate(tc["input"])
    field_path = tc["violations"][0]["field"]
    assert field_path in str(exc_info.value), (
        f"Expected '{field_path}' in error message.\n"
        f"Actual error:\n{exc_info.value}"
    )


def test_tc005_minutes_filter_absent():
    tc = CASES["TC-005"]
    with pytest.raises(ValidationError) as exc_info:
        Briefing.model_validate(tc["input"])
    field_path = tc["violations"][0]["field"]
    assert field_path in str(exc_info.value), (
        f"Expected '{field_path}' in error message.\n"
        f"Actual error:\n{exc_info.value}"
    )
