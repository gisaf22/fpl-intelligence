"""Architecture tests for DAL intra-layer dependency direction and intelligence layer isolation.

Verifies that higher layers do not import from layers they should not.
DAL checks operate on the actual dal/ directory.
Intelligence checks enforce that runtime scoring does not import from research modules.

Layer ordering (low → high):
  staging → intermediate → fct → feat → mart

Layer-access rules enforced here:
  - feat must not import from fct, intermediate, or staging (receives spine as parameter)
  - validation must not import from fct (it is a cross-cutting concern — V-3 contract)
  - intelligence must not import from research (runtime must not depend on research artifacts)
  - Note: fct imports from intermediate and staging are legitimate (it is the aggregation layer)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[1]
DAL_ROOT = REPO_ROOT / "dal"
INTELLIGENCE_ROOT = REPO_ROOT / "intelligence"

# Research-layer namespaces the runtime must never import. The studies→research module
# migration is complete (see docs/audit/research_migration_phase5_*.md); no production
# code imports `studies.*` any longer, so the guard tracks only the live namespace.
RESEARCH_NAMESPACES = ("research",)


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in str(path))


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
                    violations.append(f"{path.relative_to(REPO_ROOT)} imports {alias.name}")
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == forbidden_module or node.module.startswith(forbidden_module + "."):
                violations.append(f"{path.relative_to(REPO_ROOT)} imports from {node.module}")
    return violations


def test_feat_does_not_import_staging() -> None:
    """Feature layer must not import from dal.staging.

    The feat layer receives the fct spine as a parameter — it must not
    access raw staged tables directly.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "feat"):
        violations.extend(_imports_from(path, "dal.staging"))
    assert not violations, "Feature layer imports from staging:\n" + "\n".join(violations)


def test_feat_does_not_import_intermediate() -> None:
    """Feature layer must not import from dal.intermediate.

    The feat layer operates only on the spine it receives — no fixture-grain joins.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "feat"):
        violations.extend(_imports_from(path, "dal.intermediate"))
    assert not violations, "Feature layer imports from intermediate:\n" + "\n".join(violations)


def test_feat_does_not_import_fct() -> None:
    """Feature layer must not import from dal.fct.

    The feat layer receives the fct spine as a function parameter and adds
    derived columns. It must not call fct constructors or read fct contracts.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "feat"):
        violations.extend(_imports_from(path, "dal.fct"))
    assert not violations, "Feature layer imports from fct:\n" + "\n".join(violations)


def test_validation_does_not_import_fct() -> None:
    """Validation layer must not import from dal.fct.

    Validation is a cross-cutting concern (V-3 in the DAL contract). Validation modules
    must accept layer-specific constants (e.g. PERFORMANCE_COLS) as parameters, not import
    them from the fct layer. Violation means the validation layer is coupled to a specific
    layer's constants and cannot be reused across layers without modification.
    """
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "validation"):
        violations.extend(_imports_from(path, "dal.fct"))
    assert not violations, "Validation layer imports from fct — V-3 contract violation:\n" + "\n".join(violations)


def test_intelligence_does_not_import_studies() -> None:
    """Intelligence layer must not import from the research layer.

    Runtime scoring consumes registry-approved signals only. Research modules
    (now under research/) are analytical artifacts — importing them into
    intelligence/ couples runtime behavior to experimental code paths.
    """
    violations: list[str] = []
    for path in _python_files(INTELLIGENCE_ROOT):
        for namespace in RESEARCH_NAMESPACES:
            violations.extend(_imports_from(path, namespace))
    assert not violations, (
        "Intelligence layer imports from research layer — runtime/research boundary violation:\n"
        + "\n".join(violations)
    )


def test_dal_architecture_tests_are_not_vacuous() -> None:
    """Sanity check: dal/ subdirectories and intelligence/ actually exist and contain Python files.

    Prevents architecture tests from silently passing on empty/missing directories.
    """
    for subdir in ("fct", "feat", "intermediate", "staging", "validation"):
        path = DAL_ROOT / subdir
        assert path.exists(), f"Expected dal/{subdir}/ to exist — check DAL_ROOT={DAL_ROOT}"
        py_files = _python_files(path)
        assert len(py_files) > 0, (
            f"dal/{subdir}/ exists but contains no .py files — architecture tests would scan no code"
        )
    assert INTELLIGENCE_ROOT.exists(), f"Expected intelligence/ to exist — check REPO_ROOT={REPO_ROOT}"
    assert len(_python_files(INTELLIGENCE_ROOT)) > 0, (
        "intelligence/ exists but contains no .py files — architecture tests would scan no code"
    )
