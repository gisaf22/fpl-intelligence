"""Downstream dependency governance enforcement.

Checks that downstream modules (signals/, studies/, intelligence/) do not:
  - import from pipeline.* (retired module namespace)
  - query staging tables directly via sqlite3 or pd.read_sql outside the DAL
  - import dal.staging or dal.intermediate directly

Tests are static (source-scan). They run without a live database.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent

# Directories that are NOT the DAL — downstream consumers must not bypass the DAL.
_DOWNSTREAM_DIRS = [
    _PROJECT_ROOT / "signals",
    _PROJECT_ROOT / "studies",
    _PROJECT_ROOT / "intelligence",
]

# Tests directories are exempt from DAL-layer isolation rules (they may test internals).
_TEST_DIR = _PROJECT_ROOT / "tests"


def _collect_py_lines(dirs: list[Path]) -> list[tuple[Path, int, str]]:
    """Yield (file, lineno, stripped_line) for all .py files under dirs."""
    results = []
    for d in dirs:
        for py_file in sorted(d.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            for lineno, line in enumerate(py_file.read_text(errors="ignore").splitlines(), 1):
                stripped = line.strip()
                if stripped:
                    results.append((py_file, lineno, stripped))
    return results


def _collect_notebook_lines(dirs: list[Path]) -> list[tuple[Path, int, str]]:
    """Yield (file, cell_idx, source_line) for all .ipynb files under dirs."""
    results = []
    for d in dirs:
        for nb_file in sorted(d.rglob("*.ipynb")):
            if "__pycache__" in str(nb_file):
                continue
            try:
                nb = json.loads(nb_file.read_text(errors="ignore"))
            except json.JSONDecodeError:
                continue
            for cell_idx, cell in enumerate(nb.get("cells", [])):
                for line in cell.get("source", []):
                    stripped = line.strip()
                    if stripped:
                        results.append((nb_file, cell_idx, stripped))
    return results


# ---------------------------------------------------------------------------
# G-1 — no imports from pipeline.* namespace
# ---------------------------------------------------------------------------

def test_no_pipeline_imports_in_downstream_py():
    """G-1a: .py files in downstream dirs must not import from pipeline.*"""
    violations = []
    for path, lineno, line in _collect_py_lines(_DOWNSTREAM_DIRS):
        if line.startswith(("from ", "import ")) and "pipeline." in line:
            violations.append(f"{path.relative_to(_PROJECT_ROOT)}:{lineno}: {line}")
    assert violations == [], (
        "Retired pipeline.* imports found in downstream .py files:\n"
        + "\n".join(violations)
    )


def test_no_pipeline_imports_in_notebooks():
    """G-1b: notebooks must not import from pipeline.*"""
    violations = []
    for path, cell_idx, line in _collect_notebook_lines(_DOWNSTREAM_DIRS):
        if line.startswith(("from ", "import ")) and "pipeline." in line:
            violations.append(f"{path.relative_to(_PROJECT_ROOT)} cell {cell_idx}: {line}")
    assert violations == [], (
        "Retired pipeline.* imports found in notebooks:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# G-2 — no direct sqlite3/pd.read_sql outside DAL
# ---------------------------------------------------------------------------

def test_no_direct_sql_in_downstream_py():
    """G-2a: .py files outside DAL must not query the DB directly via sqlite3."""
    violations = []
    for path, lineno, line in _collect_py_lines(_DOWNSTREAM_DIRS):
        if "sqlite3" in line or "pd.read_sql" in line or "read_sql_query" in line:
            violations.append(f"{path.relative_to(_PROJECT_ROOT)}:{lineno}: {line}")
    assert violations == [], (
        "Direct SQL access found outside DAL in .py files:\n"
        + "\n".join(violations)
    )


def test_no_direct_sql_in_notebooks():
    """G-2b: notebooks must not query the DB directly via sqlite3 or pd.read_sql."""
    violations = []
    for path, cell_idx, line in _collect_notebook_lines(_DOWNSTREAM_DIRS):
        if "sqlite3" in line or "pd.read_sql" in line or "read_sql_query" in line:
            violations.append(f"{path.relative_to(_PROJECT_ROOT)} cell {cell_idx}: {line}")
    assert violations == [], (
        "Direct SQL access found in notebooks:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# G-3 — dal.staging and dal.intermediate not imported outside DAL and tests
# ---------------------------------------------------------------------------

_FORBIDDEN_DAL_IMPORTS = ("dal.staging", "dal.intermediate")

_STAGING_ALLOWLIST: set = {}


def test_no_staging_or_intermediate_imports_in_downstream():
    """G-3: downstream .py files must not import dal.staging or dal.intermediate.

    weekly/db.py is the sole allowed exception — it performs GW resolution and
    freshness validation, which legitimately require direct staging access.
    """
    violations = []
    for path, lineno, line in _collect_py_lines(_DOWNSTREAM_DIRS):
        if path in _STAGING_ALLOWLIST:
            continue
        if line.startswith(("from ", "import ")):
            for forbidden in _FORBIDDEN_DAL_IMPORTS:
                if forbidden in line:
                    violations.append(f"{path.relative_to(_PROJECT_ROOT)}:{lineno}: {line}")
    assert violations == [], (
        "Forbidden dal.staging / dal.intermediate imports in downstream modules:\n"
        + "\n".join(violations)
    )


def test_no_staging_or_intermediate_imports_in_notebooks():
    """G-3b: notebooks must not import dal.staging or dal.intermediate."""
    violations = []
    for path, cell_idx, line in _collect_notebook_lines(_DOWNSTREAM_DIRS):
        if line.startswith(("from ", "import ")):
            for forbidden in _FORBIDDEN_DAL_IMPORTS:
                if forbidden in line:
                    violations.append(
                        f"{path.relative_to(_PROJECT_ROOT)} cell {cell_idx}: {line}"
                    )
    assert violations == [], (
        "Forbidden dal.staging / dal.intermediate imports in notebooks:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# G-4 — dal.access and dal.prepared are importable (smoke test)
# ---------------------------------------------------------------------------

def test_dal_access_importable():
    """G-4a: dal.access must export get_curated_spine and get_state_features."""
    from dal.access import get_curated_spine, get_state_features
    assert callable(get_curated_spine)
    assert callable(get_state_features)


def test_dal_prepared_importable():
    """G-4b: dal.prepared must export build_prepared_dataset and GOVERNED_SIGNAL_COLUMNS."""
    from dal.prepared.analytical_dataset import (
        GOVERNED_SIGNAL_COLUMNS,
        build_prepared_dataset,
    )
    assert callable(build_prepared_dataset)
    assert len(GOVERNED_SIGNAL_COLUMNS) > 0
    assert all(isinstance(c, str) for c in GOVERNED_SIGNAL_COLUMNS)
