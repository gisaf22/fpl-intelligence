"""Wave 5 — Architecture Cleanup.

FAILING TESTS committed before any fixes.

A-1: pipeline/ contains dead code importing from nonexistent analysis.source.
A-2: GrainViolationError used in opponent_context.py — inconsistent exception hierarchy.
A-3: opponent_context.py lives in state/ but operates on intermediate-layer data.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# A-1 — no imports from pipeline/ in dal/ or research/
# ---------------------------------------------------------------------------

def test_no_import_from_pipeline_in_dal():
    """A-1 FAILING TEST: dal/ must not import from pipeline/.

    FAILS before fix (if any such imports exist). PASSES after fix.
    """
    project_root = Path(__file__).parent.parent
    dal_dir = project_root / "dal"

    violations = []
    for py_file in dal_dir.rglob("*.py"):
        content = py_file.read_text(errors="ignore")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("from ", "import ")) and "pipeline" in stripped:
                violations.append(f"{py_file.relative_to(project_root)}: {stripped}")

    assert violations == [], (
        "dal/ contains imports from pipeline/:\n" + "\n".join(violations)
    )

# ---------------------------------------------------------------------------
# A-2 — GrainViolationError must be removed (zero usages)
# ---------------------------------------------------------------------------

def test_grain_violation_error_not_used():
    """A-2 FAILING TEST: GrainViolationError must have zero usages after retirement.

    Checks dal/ source only (not tests/) to avoid the test file catching itself.
    FAILS before fix (opponent_context.py uses GrainViolationError). PASSES after fix.
    """
    project_root = Path(__file__).parent.parent
    # Check only source directories — tests/ may have transitional references in comments
    source_dirs = [project_root / "dal"]
    # Use indirect string construction to avoid this file catching itself
    _retired_name = "Grain" + "Violation" + "Error"

    usages = []
    for source_dir in source_dirs:
        for py_file in source_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(errors="ignore")
            for line in content.splitlines():
                stripped = line.strip()
                if _retired_name in stripped and not stripped.startswith("#"):
                    usages.append(f"{py_file.relative_to(project_root)}: {stripped}")

    assert usages == [], (
        f"{_retired_name} is still used in dal/ source:\n" + "\n".join(usages)
    )

# ---------------------------------------------------------------------------
# A-3 — opponent_context.py must be in dal/intermediate/, not dal/state/
# ---------------------------------------------------------------------------

def test_opponent_context_at_intermediate_layer():
    """A-3 FAILING TEST: opponent_context must be importable from dal.intermediate.

    FAILS before fix (module is at dal.state). PASSES after fix.
    """
    from dal.intermediate.int_opponent_context import build_player_opponent_defensive_context
    assert callable(build_player_opponent_defensive_context)

def test_opponent_context_not_at_state_layer():
    """A-3: dal.state.opponent_context must not exist after reclassification.

    FAILS before fix (module still at state/). PASSES after fix.
    """
    with pytest.raises(ImportError):
        import dal.state.opponent_context  # must no longer exist

        _ = dal.state.opponent_context  # suppress unused import warning
