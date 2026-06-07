"""Shared writer for per-lens ``evidence.yaml`` verdict records (ADR-009 Phase C).

Each lens validate study, on ``run()``, emits the machine half of its verdict record
alongside the ephemeral run CSVs: ``evidence.yaml`` in its own ``validate/`` directory.
This is the committed, regenerated-each-run input the governance generator
(``model/governance/generate_evaluation_metadata.py``) reads to (re)produce
``evaluation_metadata.yaml``.

This module lives in ``research`` and is imported only by research studies — the
study is the producer of evidence. The schema is a *file contract* with the model-side
generator (deliberately not a shared import: ``research ↛ model``). It carries only the
study-computed statistics; the human judgment half lives in the hand-authored
``annotations.yaml`` next to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Study population label -> governance/runtime position label (mirrors the generator).
_POSITION_LABEL = {"GKP": "GK", "GK": "GK", "DEF": "DEF", "MID": "MID", "FWD": "FWD"}

# Lens status (study _classify output) -> evaluation decision_class. The judgment
# classes (conditional / design-excluded) are annotation overrides, never study-emitted.
_DECISION_CLASS = {"informative": "informative", "uninformative": "uninformative", "unstable": "uninformative"}


def decision_class_for(lens_status: str) -> str:
    """Map a study lens_status to the evaluation decision_class."""
    return _DECISION_CLASS.get(lens_status, "uninformative")


def build_evidence_row(
    signal: str,
    position: str,
    full_corr: dict | None,
    block_corrs: list[dict | None],
    cls: dict,
) -> dict:
    """Build a single evidence row for write_evidence() from per-slice statistics.

    Counts how many GW-block correlation records exclude zero (block_stability_count),
    then projects the full-window CI and the classify verdict into the evidence schema.
    ``position`` is the study population label (e.g. GKP); write_evidence() normalises it.
    """
    n_passing = sum(1 for b in block_corrs if b and b["ci_excludes_zero"])
    return {
        "signal": signal,
        "position": position,
        "rho_pooled": full_corr["rho"] if full_corr else None,
        "rho_ci_lower": full_corr["ci_lower"] if full_corr else None,
        "rho_ci_upper": full_corr["ci_upper"] if full_corr else None,
        "block_stability_count": n_passing if full_corr else None,
        "decision_class": decision_class_for(cls["lens_status"]),
    }


def write_evidence(
    validate_dir: Path,
    lens: str,
    target: str,
    rows: list[dict[str, Any]],
    evidence_run: dict[str, Any],
) -> Path:
    """Write ``evidence.yaml`` for one lens.

    ``rows`` is one dict per studied (signal, position) with keys: ``signal``,
    ``position`` (study label; mapped to the runtime label here), ``rho_pooled``,
    ``rho_ci_lower``, ``rho_ci_upper``, ``block_stability_count``, ``decision_class``.
    """
    signals: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        pos = _POSITION_LABEL.get(r["position"], r["position"])
        signals.setdefault(r["signal"], {})[pos] = {
            "rho_pooled": r["rho_pooled"],
            "rho_ci_lower": r["rho_ci_lower"],
            "rho_ci_upper": r["rho_ci_upper"],
            "block_stability_count": r["block_stability_count"],
            "decision_class": r["decision_class"],
        }
    payload = {"lens": lens, "target": target, "evidence_run": evidence_run, "signals": signals}
    out_path = validate_dir / "evidence.yaml"
    with out_path.open("w") as fh:
        yaml.dump(payload, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return out_path
