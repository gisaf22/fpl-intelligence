"""One-shot backfill: split evaluation_metadata.yaml into per-lens verdict records.

ADR-009 Phase C, step C1. Losslessly projects the hand-authored
``evaluation_metadata.yaml`` into the evidence + annotations records that the
generator will consume going forward (one ``{evidence,annotations}.yaml`` pair per
lens under ``research/families/<fam>/validate/``).

The split is lossless by construction:
  - studied positions (lifecycle_state != not_applicable) -> an evidence row
    (rho/ci/blocks/decision_class) + an annotation row (judgment).
  - ontologically not_applicable positions (no real evidence) -> an annotation row
    only, carrying decision_class too.
  - synth fields (synth01_decision/composition_weight/composition_role/_id) are NOT
    stored here — they are merged from synth01_decisions.yaml at generate time.

Run once: ``python -m model.governance._backfill_verdict_records``. Re-running is
idempotent (overwrites the records from the current YAML).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from model.governance.verdict_records import EVIDENCE_FIELDS, LENS_VALIDATE_DIRS

EVAL_META_PATH = Path("model/governance/evaluation_metadata.yaml")
BACKFILL_SOURCE = "backfill:evaluation_metadata.yaml@v3.0"

_ANNOTATION_FIELDS = (
    "lifecycle_state", "downstream_status", "leakage_risk", "behavioral_reason", "source_gate_decisions",
)

# Studied positions whose decision_class is a judgment label rather than a class the
# study computes (informative/uninformative) carry the computed base in evidence and the
# judgment as an annotation override. `conditional` = "passes gates but scope-constrained"
# → its gate-computed base is `informative` (the YAML reason states the gates pass).
_OVERRIDE_BASE = {"conditional": "informative"}


def _split() -> dict[str, dict]:
    """Build per-lens {evidence, annotations} dicts from the current YAML."""
    with EVAL_META_PATH.open() as fh:
        data = yaml.safe_load(fh)

    produced = str(data.get("version", "v3.0"))
    records: dict[str, dict] = {}

    for entry in data["evaluation_findings"]:
        lens, signal, target = entry["lens"], entry["signal"], entry["target"]
        rec = records.setdefault(
            lens,
            {
                "evidence": {"lens": lens, "target": target,
                             "evidence_run": {"source": BACKFILL_SOURCE, "produced": produced},
                             "signals": {}},
                "annotations": {"lens": lens, "target": target, "signals": {}},
            },
        )
        ev_signals = rec["evidence"]["signals"]
        ann_signals = rec["annotations"]["signals"]

        for pos, pd in entry["per_position"].items():
            is_design_excluded = pd["lifecycle_state"] == "not_applicable"

            ann: dict = {f: pd[f] for f in _ANNOTATION_FIELDS}
            if "notes" in pd:
                ann["notes"] = pd["notes"]
            # decision_class lives in evidence for studied positions; in the
            # annotation only when there is no evidence row (design exclusions).
            if is_design_excluded:
                ann["decision_class"] = pd["decision_class"]
            else:
                ev = {f: pd[f] for f in EVIDENCE_FIELDS}
                if pd["decision_class"] in _OVERRIDE_BASE:
                    ev["decision_class"] = _OVERRIDE_BASE[pd["decision_class"]]
                    ann["decision_class"] = pd["decision_class"]  # judgment override
                ev_signals.setdefault(signal, {})[pos] = ev
            ann_signals.setdefault(signal, {})[pos] = ann

    return records


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        yaml.dump(payload, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)


def main() -> int:
    records = _split()
    for lens, payload in records.items():
        base = LENS_VALIDATE_DIRS[lens]
        _dump(base / "evidence.yaml", payload["evidence"])
        _dump(base / "annotations.yaml", payload["annotations"])
        n_ev = sum(len(p) for p in payload["evidence"]["signals"].values())
        n_ann = sum(len(p) for p in payload["annotations"]["signals"].values())
        print(f"{lens:11s} -> {base}  ({n_ev} evidence, {n_ann} annotation positions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
