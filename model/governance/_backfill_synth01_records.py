"""One-shot backfill: split synth01_decisions.yaml into recommendation + annotation records.

ADR-010 ruling (c). The composition study previously computed evidence, applied the
partial-rho threshold rule, AND emitted the APPROVED/EXCLUDED decision in one pass — a
collapse of recommendation and decision authority. This splits that single artifact into
the two-record shape the lens stage already uses (ADR-009 Phase C):

  model/assemble/synth01_recommendations.yaml   machine — the study's evidence + the
        rule's *recommended* decision/weight/role. Written by composition_study.run().

  model/governance/synth01_annotations.yaml     human — governance's *ratification*:
        per key, ratified_decision/weight/contribution_class + rationale. This is the
        real authority surface: governance may ratify (accept) or override the rule.

``model/governance/generate_synth01_decisions.py`` then merges the two into the generated
``synth01_decisions.yaml`` (the composition decision-of-record consumed unchanged by
generate_evaluation_metadata.py).

The split is lossless by construction: every committed decision becomes a recommendation
(decision→recommended_decision, composition_weight→recommended_weight,
contribution_class→recommended_contribution_class) plus a ratification that accepts it
(ratified_* = recommended_*). Re-running regenerates synth01_decisions.yaml byte-for-byte
(semantically). Run once: ``python -m model.governance._backfill_synth01_records``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

DECISIONS_PATH = Path("model/assemble/synth01_decisions.yaml")
RECOMMENDATIONS_PATH = Path("model/assemble/synth01_recommendations.yaml")
ANNOTATIONS_PATH = Path("model/governance/synth01_annotations.yaml")

# Top-level study metadata that travels with the recommendation artifact (the study owns it).
_CARRIED_TOP_LEVEL = (
    "version", "produced", "authority", "candidate_registry", "design_doc",
    "fdr_moderation_check", "group_summary",
)

# Per-record fields owned by the study (evidence + rule output, minus the decision triple).
_RECOMMENDATION_EVIDENCE_FIELDS = (
    "key", "signal", "position", "lens",
    "partial_rho", "partial_ci_lower", "partial_ci_upper", "marginal_gain",
    "weight_ci_lower", "weight_ci_upper", "evidence", "notes",
)

_BACKFILL_RATIONALE = "Backfill ratification: accepts the study recommendation verbatim (ADR-010 ruling c)."


def _split() -> tuple[dict, dict]:
    with DECISIONS_PATH.open() as fh:
        data = yaml.safe_load(fh)

    recommendations: list[dict] = []
    annotations: list[dict] = []
    for d in data["decisions"]:
        rec: dict = {f: d[f] for f in _RECOMMENDATION_EVIDENCE_FIELDS if f in d}
        rec["recommended_decision"] = d["decision"]
        rec["recommended_weight"] = d["composition_weight"]
        rec["recommended_contribution_class"] = d["contribution_class"]
        recommendations.append(rec)

        annotations.append({
            "key": d["key"],
            "ratified_decision": d["decision"],
            "ratified_weight": d["composition_weight"],
            "ratified_contribution_class": d["contribution_class"],
            "rationale": _BACKFILL_RATIONALE,
        })

    rec_doc: dict = {k: data[k] for k in _CARRIED_TOP_LEVEL if k in data}
    rec_doc["recommendations"] = recommendations

    ann_doc: dict = {
        "version": data.get("version", "synth01"),
        "authority": "model/governance — composition ratification (ADR-010 ruling c)",
        "annotations": annotations,
    }
    return rec_doc, ann_doc


def main() -> int:
    rec_doc, ann_doc = _split()
    with RECOMMENDATIONS_PATH.open("w") as fh:
        fh.write(
            "# Machine-written by composition_study.run() — the study's evidence + the rule's\n"
            "# RECOMMENDED decision/weight/role. Ratified into a decision by governance\n"
            "# (model/governance/synth01_annotations.yaml) via generate_synth01_decisions.py (ADR-010 ruling c).\n"
        )
        yaml.dump(rec_doc, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
    with ANNOTATIONS_PATH.open("w") as fh:
        fh.write(
            "# Human-authored governance ratification of composition recommendations (ADR-010 ruling c).\n"
            "# Per key: ratified_decision/weight/contribution_class may ACCEPT or OVERRIDE the study's\n"
            "# recommendation. Merged with synth01_recommendations.yaml by generate_synth01_decisions.py.\n"
        )
        yaml.dump(ann_doc, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Wrote {RECOMMENDATIONS_PATH} ({len(rec_doc['recommendations'])} recommendations)")
    print(f"Wrote {ANNOTATIONS_PATH} ({len(ann_doc['annotations'])} ratifications)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
