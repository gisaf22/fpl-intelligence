"""Architecture tests for DAL dependency direction."""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DAL_ROOT = REPO_ROOT / "pipeline" / "dal"


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.name != "__init__.py")


def _forbidden_staging_dependency(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pipeline.dal.staging":
                    violations.append(f"{path.relative_to(REPO_ROOT)} imports {alias.name}")
        if isinstance(node, ast.ImportFrom) and node.module == "pipeline.dal.staging":
            violations.append(f"{path.relative_to(REPO_ROOT)} imports from {node.module}")

    return violations


def _forbidden_raw_staging_api_usage(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pipeline.dal.staging":
            imported_names = {alias.name for alias in node.names}
            forbidden = imported_names & {"load_schema", "stage"}
            if forbidden:
                names = ", ".join(sorted(forbidden))
                violations.append(
                    f"{path.relative_to(REPO_ROOT)} imports forbidden staging APIs: {names}"
                )

    return violations


def test_curated_and_state_do_not_import_staging() -> None:
    violations: list[str] = []
    for layer in ["curated", "state"]:
        for path in _python_files(DAL_ROOT / layer):
            violations.extend(_forbidden_staging_dependency(path))

    assert not violations, "\n".join(violations)


def test_integrated_does_not_import_raw_staging_apis() -> None:
    violations: list[str] = []
    for path in _python_files(DAL_ROOT / "integrated"):
        violations.extend(_forbidden_raw_staging_api_usage(path))

    assert not violations, "\n".join(violations)
