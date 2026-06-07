"""Generate synth01_decisions.yaml from composition recommendations + governance ratifications.

ADR-010 ruling (c). Composition decisions are no longer emitted by the study in one pass.
The study emits a *recommendation* (evidence + the rule's suggested decision); governance
*ratifies* it (accept or override). This generator is the merge — the only writer of the
composition decision-of-record:

  model/assemble/synth01_recommendations.yaml   (machine, from composition_study.run())
  + model/governance/synth01_annotations.yaml   (human ratification — the authority)
        ── merge ──▶  model/assemble/synth01_decisions.yaml   (generated, drift-guarded)

Each output record is the ratified decision (ratified_decision/weight/contribution_class)
joined to the recommendation's evidence — the exact shape generate_evaluation_metadata.py
already consumes. Ratification is the authority: a governance override (ratified_decision
!= recommended_decision) flows straight through, separating recommendation from decision.

Fail-closed: every recommendation must have a ratification and vice-versa (no silent
unratified decision, no orphan ratification).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

RECOMMENDATIONS_PATH = Path("model/assemble/synth01_recommendations.yaml")
ANNOTATIONS_PATH = Path("model/governance/synth01_annotations.yaml")
OUT_PATH = Path("model/assemble/synth01_decisions.yaml")

# Top-level study metadata carried through from the recommendation artifact.
_CARRIED_TOP_LEVEL = (
    "version", "produced", "authority", "candidate_registry", "design_doc",
    "fdr_moderation_check", "group_summary",
)

# Decision-record field order (matches the historical synth01_decisions.yaml layout).
_DECISION_ORDER = (
    "key", "signal", "position", "lens", "decision",
    "partial_rho", "partial_ci_lower", "partial_ci_upper",
    "composition_weight", "contribution_class", "marginal_gain", "evidence", "notes",
    "weight_ci_lower", "weight_ci_upper",
)

_BANNER = (
    "# GENERATED — DO NOT EDIT BY HAND (ADR-010 ruling c).\n"
    "# Regenerate with: python -m model.governance.generate_synth01_decisions\n"
    "# Source: model/assemble/synth01_recommendations.yaml\n"
    "#       + model/governance/synth01_annotations.yaml\n"
)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Synth01 record not found at {path}. Run from the project root directory.")
    with path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Synth01 record at {path} must be a YAML mapping, got {type(data).__name__}")
    return data


def _decision_record(rec: dict[str, Any], ann: dict[str, Any]) -> dict[str, Any]:
    """Join one recommendation's evidence to its ratified decision."""
    merged: dict[str, Any] = {
        **rec,
        "decision": ann["ratified_decision"],
        "composition_weight": ann["ratified_weight"],
        "contribution_class": ann["ratified_contribution_class"],
    }
    # Drop the recommendation-named aliases; keep only the decision shape.
    for alias in ("recommended_decision", "recommended_weight", "recommended_contribution_class"):
        merged.pop(alias, None)
    # Emit in the canonical decision field order; carry any extra keys after.
    ordered = {f: merged[f] for f in _DECISION_ORDER if f in merged}
    for k, v in merged.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def generate(
    recommendations_path: Path = RECOMMENDATIONS_PATH,
    annotations_path: Path = ANNOTATIONS_PATH,
) -> dict[str, Any]:
    """Produce the full synth01_decisions mapping (does not write to disk)."""
    rec_doc = _read_yaml(recommendations_path)
    ann_doc = _read_yaml(annotations_path)

    recs = {r["key"]: r for r in rec_doc["recommendations"]}
    anns = {a["key"]: a for a in ann_doc["annotations"]}

    missing_ann = sorted(recs.keys() - anns.keys())
    if missing_ann:
        raise ValueError(f"Composition recommendations with no governance ratification: {missing_ann}")
    orphan_ann = sorted(anns.keys() - recs.keys())
    if orphan_ann:
        raise ValueError(f"Composition ratifications with no recommendation: {orphan_ann}")

    decisions = [_decision_record(recs[key], anns[key]) for key in recs]
    approved = [d for d in decisions if d["decision"].startswith("APPROVED")]
    excluded = [d for d in decisions if "EXCLUDED" in d["decision"]]

    out: dict[str, Any] = {k: rec_doc[k] for k in _CARRIED_TOP_LEVEL if k in rec_doc}
    # Counts are derived from the ratified decisions, placed to match the historical layout.
    out = {
        **{k: out[k] for k in ("version", "produced", "authority", "candidate_registry", "design_doc") if k in out},
        "total_decisions": len(decisions),
        "approved_count": len(approved),
        "excluded_count": len(excluded),
        **{k: out[k] for k in ("fdr_moderation_check", "group_summary") if k in out},
        "decisions": decisions,
    }
    return out


def write(out_path: Path = OUT_PATH, **kwargs: Any) -> Path:
    """Generate and write synth01_decisions.yaml (with a generated-file banner)."""
    payload = generate(**kwargs)
    with out_path.open("w") as fh:
        fh.write(_BANNER)
        yaml.dump(payload, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return out_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_PATH, help=f"Output path (default {OUT_PATH}).")
    args = parser.parse_args(argv)
    out = write(out_path=args.out)
    n = len(generate()["decisions"])
    print(f"Wrote {out} ({n} ratified composition decisions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
