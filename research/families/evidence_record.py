"""Shared writer for per-lens ``evidence.yaml`` verdict records (ADR-009 Phase C).

Each lens validate study, on ``run()``, emits the machine half of its verdict record
alongside the ephemeral run CSVs: ``evidence.yaml`` in its own ``validate/`` directory.
This is the committed, regenerated-each-run input the governance generator
(``model/governance/generate_evaluation_metadata.py``) reads to (re)produce
``evaluation_metadata.yaml``.

## Vocabulary

- ``lens_status``: the study-computed qualification verdict per (signal, position).
  Values: ``informative`` | ``uninformative`` | ``unstable``.
- ``decision_class``: the governance-facing form of the same verdict.
  ``unstable`` collapses to ``uninformative`` because the governance layer has no
  concept of temporal instability — it only distinguishes usable from not usable.
- ``block_stability_count``: how many of the 3 GW-block windows showed a CI
  that excludes zero. Requires ≥ 2 of 3 for ``informative`` qualification.

This module lives in ``research`` and is imported only by research studies — the
study is the producer of evidence. The schema is a *file contract* with the model-side
generator (deliberately not a shared import: ``research ↛ model``). It carries only
study-computed statistics; the human judgment half lives in the hand-authored
``annotations.yaml`` next to it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Study population label -> governance/runtime position label (mirrors the generator).
_POSITION_LABEL = {"GKP": "GK", "GK": "GK", "DEF": "DEF", "MID": "MID", "FWD": "FWD"}

# lens_status (study qualification verdict) -> decision_class (governance vocabulary).
# The judgment classes (conditional / design-excluded) are annotation overrides,
# never study-emitted. ``unstable`` collapses to ``uninformative`` here because the
# governance layer only tracks usable vs not-usable; temporal instability is recorded
# in the rationale field of the study's classification_summary.csv.
_DECISION_CLASS = {"informative": "informative", "uninformative": "uninformative", "unstable": "uninformative"}


def decision_class_for(lens_status: str) -> str:
    """Convert a study qualification verdict to its governance decision class.

    ``unstable`` maps to ``uninformative`` because governance does not distinguish
    the reason a signal failed qualification — only whether it passed.
    """
    return _DECISION_CLASS.get(lens_status, "uninformative")


def build_signal_verdict(
    signal: str,
    position: str,
    full_window_assoc: dict | None,
    gw_block_assocs: list[dict | None],
    qualification: dict,
) -> dict:
    """Assemble a single signal verdict record for ``write_evidence()``.

    Counts how many GW-block correlation results exclude zero (block_stability_count),
    then combines the full-window CI with the qualification gate verdict into the
    evidence schema consumed by the governance generator.

    Args:
        signal:            Signal name (e.g. ``xgi_roll3``).
        position:          Study population label (e.g. ``GKP``); mapped to the
                           governance runtime label by ``write_evidence()``.
        full_window_assoc: Result dict from ``_measure_rank_association`` for the full
                           study window, or None when observations were insufficient.
        gw_block_assocs:   One result dict per GW block (early/mid/late), each from
                           ``_measure_rank_association``, or None for thin slices.
        qualification:     Qualification gate result from
                           ``_apply_signal_qualification_gates``. Must contain
                           ``lens_status``.

    Returns:
        Dict matching the evidence schema: signal, position, rho_pooled,
        rho_ci_lower, rho_ci_upper, block_stability_count, decision_class.
    """
    n_passing = sum(1 for b in gw_block_assocs if b and b["ci_excludes_zero"])
    return {
        "signal": signal,
        "position": position,
        "rho_pooled": full_window_assoc["rho"] if full_window_assoc else None,
        "rho_ci_lower": full_window_assoc["ci_lower"] if full_window_assoc else None,
        "rho_ci_upper": full_window_assoc["ci_upper"] if full_window_assoc else None,
        "block_stability_count": n_passing if full_window_assoc else None,
        "decision_class": decision_class_for(qualification["lens_status"]),
    }


def write_evidence(
    validate_dir: Path,
    lens: str,
    target: str,
    signal_verdicts: list[dict[str, Any]],
    evidence_run: dict[str, Any],
) -> Path:
    """Write ``evidence.yaml`` for one lens.

    Collects the per-(signal, position) verdict records produced by
    ``build_signal_verdict()``, maps study position labels to governance runtime
    labels, and serialises the result. The output file is the machine half of the
    governance verdict; the human judgment half lives in ``annotations.yaml``
    alongside it.

    Args:
        validate_dir:    Directory that will receive ``evidence.yaml`` (typically
                         the study's ``validate/`` folder).
        lens:            Lens identifier (e.g. ``"form"``).
        target:          Target column name used in this study (e.g. ``"total_points"``).
        signal_verdicts: List of dicts from ``build_signal_verdict()``. Each must
                         have keys: signal, position, rho_pooled, rho_ci_lower,
                         rho_ci_upper, block_stability_count, decision_class.
        evidence_run:    Provenance metadata dict written verbatim into the file.

    Returns:
        Path to the written ``evidence.yaml``.
    """
    signals: dict[str, dict[str, dict[str, Any]]] = {}
    for r in signal_verdicts:
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
