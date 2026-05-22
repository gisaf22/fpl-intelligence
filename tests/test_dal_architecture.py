"""Architecture tests for DAL intra-layer dependency direction.

Verifies that higher layers do not import from layers they should not.
All checks operate on the actual dal/ directory.

Layer ordering (low → high):
  staging → intermediate → curated → state

Layer-access rules enforced here:
  - State must not import from curated, intermediate, or staging (receives spine as parameter)
  - Validation must not import from curated (it is a cross-cutting concern — V-3 contract)
  - Note: curated imports from intermediate and staging are legitimate (it is the aggregation layer)
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAL_ROOT = REPO_ROOT / "dal"


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in str(path)
    )


def _imports_from(path: Path, forbidden_module: str) -> list[str]:
    """Return violation strings for any import of forbidden_module in path."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == forbidden_module or alias.name.startswith(forbidden_module + "."):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)} imports {alias.name}"
                    )
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == forbidden_module or node.module.startswith(forbidden_module + "."):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)} imports from {node.module}"
                )
    return violations


def test_state_does_not_import_staging() -> None:
    """State layer must not import from dal.staging.

    The state layer receives the curated spine as a parameter — it must not
    access raw staged tables directly.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "state"):
        violations.extend(_imports_from(path, "dal.staging"))
    assert not violations, "State layer imports from staging:\n" + "\n".join(violations)


def test_state_does_not_import_intermediate() -> None:
    """State layer must not import from dal.intermediate.

    The state layer operates only on the spine it receives — no fixture-grain joins.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "state"):
        violations.extend(_imports_from(path, "dal.intermediate"))
    assert not violations, "State layer imports from intermediate:\n" + "\n".join(violations)


def test_state_does_not_import_curated() -> None:
    """State layer must not import from dal.curated.

    The state layer receives the curated spine as a function parameter and adds
    derived columns. It must not call curated constructors or read curated contracts.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "state"):
        violations.extend(_imports_from(path, "dal.curated"))
    assert not violations, "State layer imports from curated:\n" + "\n".join(violations)


def test_validation_does_not_import_curated() -> None:
    """Validation layer must not import from dal.curated.

    Validation is a cross-cutting concern (V-3 in the DAL contract). Validation modules
    must accept layer-specific constants (e.g. PERFORMANCE_COLS) as parameters, not import
    them from the curated layer. Violation means the validation layer is coupled to a specific
    layer's constants and cannot be reused across layers without modification.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "validation"):
        violations.extend(_imports_from(path, "dal.curated"))
    assert not violations, (
        "Validation layer imports from curated — V-3 contract violation:\n"
        + "\n".join(violations)
    )


def test_dal_architecture_tests_are_not_vacuous() -> None:
    """Sanity check: dal/ subdirectories actually exist and contain Python files.

    Prevents architecture tests from silently passing on empty/missing directories.
    The prior version of this file checked the retired pipeline/dal/ path and passed
    vacuously because that path no longer exists.
    """
    for subdir in ("curated", "state", "intermediate", "staging", "validation"):
        path = DAL_ROOT / subdir
        assert path.exists(), f"Expected dal/{subdir}/ to exist — check DAL_ROOT={DAL_ROOT}"
        py_files = _python_files(path)
        assert len(py_files) > 0, (
            f"dal/{subdir}/ exists but contains no .py files — "
            "architecture tests would scan no code"
        )
