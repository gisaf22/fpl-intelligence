"""EDA-3 helper functions — signal-target relationship geometry.

All functions are pure (stateless, no side effects). The notebook is the
stateful orchestrator that calls these, records results, and writes outputs.

Analysis state vocabulary (propagated via support_flags in registry):
  ''                              analyzed — full computation valid
  'insufficient_support:bin_density'
                                  active-bin threshold not met for this scheme
                                  type; geometry set to 'unassessable'
  'insufficient_support:insufficient_n'
                                  n < MIN_N_SHAPE; metrics NaN
  'degenerate'                    zero variance or single unique value; geometry
                                  set to 'indeterminate'
  'skipped'                       intentionally not run for this signal type

Support type taxonomy (support_type field, assigned in notebook):
  'sparse_event_process'    structural_zero or high-sparsity count process
                            (goals, assists, yellow_cards) — sparse by design
  'structural_binary'       binary-by-design signal (was_home, starts)
  'near_constant_position'  degenerate due to positional near-constancy
                            (zero variance or single unique value in position)
  'ordinal_scheme_mismatch' ordinal/fixture signal failing bin density
                            (fdr_*, fixture_count, was_home under ordinal routing)
  'insufficient_n'          sample size below governance threshold
  ''                        no support failure; fully analyzed
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from research.foundation.joint.association import assign_association_class, consolidate_flags
from research.kernels.correlation.panel import decompose_rho
from research.kernels.correlation.tail import haul_concentration
from studies.eda.geometry import (
    ASSOCIATION_CLASS_TAXONOMY,
    BLOCK_ORDER,
    DISCRETE_BINS,
    DISCRETE_LABELS,
    FDR_ORDINAL_BINS,
    FDR_ORDINAL_LABELS,
    FDR_SIGNALS,
    GEOMETRY_TAXONOMY,
    HAUL_DROP_MATERIAL,
    HAUL_THRESHOLD_PTS,
    MATCH_LEVEL_SIGNALS,
    MIN_ACTIVE_BINS,
    MIN_N_HAUL,
    MIN_N_PANEL_PLAYERS,
    MIN_N_PER_BIN,
    MIN_N_SHAPE,
    MONO_CONF_HIGH,
    MONO_CONF_LOW,
    MONOTONIC_GEOMETRIES,
    PANEL_CLASS_THRESHOLDS,
    POPULATION_ROBUSTNESS_VALUES,
    POPULATION_SCOPE_VALUES,
    POSITIONS,
    QUANTILE_N_BINS,
    SPARSE_THRESHOLD,
    SUPPORT_TYPE_TAXONOMY,
    TWO_STAGE_NZ_LABELS,
    UPPER_TAIL_GEOMETRIES,
    bin_analysis,
    classify_geometry,
    get_bin_direction,
    monotonicity_confidence,
    select_bucketing_scheme,
    stability_classify,
)
from studies.eda.semantics import (
    SIGNAL_LAYER_MAPPING,
    SIGNAL_LAYER_VALUES,
    enrich_signal_layers,
)


def validate_registry(registry: pd.DataFrame, expected_n: int) -> list[str]:
    """Validate the completed registry before write.

    Raises ValueError listing all contradiction checks that failed.
    Returns a list of warning strings for permitted failure states
    (structurally expected conditions that downstream consumers must handle).

    Contradiction checks (C-prefixed) — raise on any failure:
      C1  No duplicate (signal, position) primary key
      C2  Row count matches expected_n
      C3  insufficient_support or degenerate flag → geometry must be
          'unassessable' or 'indeterminate' respectively
      C4  within_share > 1.0 → decomposition_flag must be 'unstable_ratio'
          AND panel_class must be 'indeterminate'
      C5  FDR signals → bucketing_scheme must be 'ordinal'
      C6  relationship_geometry values in GEOMETRY_TAXONOMY
      C7  association_class values in ASSOCIATION_CLASS_TAXONOMY
      C8  monotonicity_confidence non-NaN only for monotonic geometry
      C9  support_type non-empty only when support_flags is non-empty
      C10 No duplicate column names
      C11 Non-monotonic geometry → q1_q5_mean_gap must be NaN
      C12 Monotonic geometry → monotonicity_confidence must be >= MONO_CONF_LOW
          (or NaN when bootstrap was skipped)
      C13 Signal-layer metadata complete and in controlled vocabulary
      C14 Layer-level semantic gates are internally consistent
      C15 Downstream status blocks support failures and low-confidence promotion

    Permitted-state warnings (W-prefixed) — returned, not raised:
      W1  unassessable pairs with valid rho_pooled (geometry blocked; rho valid)
      W2  panel_class = indeterminate (within_share > 1.0 or decomp insufficient)
      W3  low_confidence monotonic pairs (bootstrap stability below MONO_CONF_HIGH)
      W4  match-level variable pairs (panel decomposition carries caveats)
    """
    errors: list[str] = []
    warnings_out: list[str] = []

    # C1: No duplicate primary key
    dupes = registry[["signal", "position"]].duplicated().sum()
    if dupes > 0:
        errors.append(f"C1: {dupes} duplicate (signal, position) pairs")

    # C2: Row count matches expected
    if len(registry) != expected_n:
        errors.append(
            f"C2: registry has {len(registry)} rows, expected {expected_n}"
        )

    # C3: support failure flags → geometry must be correct taxonomy value
    #   insufficient_support → 'unassessable'
    #   degenerate           → 'indeterminate'
    if "support_flags" in registry.columns and "relationship_geometry" in registry.columns:
        bad_insuff = registry[
            registry["support_flags"].str.contains("insufficient_support", na=False)
            & (registry["relationship_geometry"] != "unassessable")
        ]
        if not bad_insuff.empty:
            errors.append(
                f"C3a: {len(bad_insuff)} rows have insufficient_support but non-unassessable geometry: "
                + bad_insuff[["signal", "position", "relationship_geometry"]].to_string(index=False)
            )
        bad_degen = registry[
            (registry["support_flags"] == "degenerate")
            & (registry["relationship_geometry"] != "indeterminate")
        ]
        if not bad_degen.empty:
            errors.append(
                f"C3b: {len(bad_degen)} rows have degenerate flag but non-indeterminate geometry: "
                + bad_degen[["signal", "position", "relationship_geometry"]].to_string(index=False)
            )

    # C4: within_share > 1.0 → decomposition_flag = 'unstable_ratio'
    #                        AND panel_class = 'indeterminate'
    if "within_share" in registry.columns:
        decomp_flag_col = registry.get(
            "decomposition_flag", pd.Series("", index=registry.index)
        )
        ws_bad_flag = registry[
            registry["within_share"].notna()
            & (registry["within_share"] > 1.0)
            & (decomp_flag_col != "unstable_ratio")
        ]
        if not ws_bad_flag.empty:
            errors.append(
                f"C4a: {len(ws_bad_flag)} rows have within_share > 1.0 without unstable_ratio flag"
            )
        if "panel_class" in registry.columns:
            ws_bad_pc = registry[
                registry["within_share"].notna()
                & (registry["within_share"] > 1.0)
                & (registry["panel_class"] != "indeterminate")
            ]
            if not ws_bad_pc.empty:
                errors.append(
                    f"C4b: {len(ws_bad_pc)} rows have within_share > 1.0 but panel_class != indeterminate: "
                    + ws_bad_pc[["signal", "position", "within_share", "panel_class"]].to_string(index=False)
                )

    # C5: FDR signals must use ordinal bucketing
    if "bucketing_scheme" in registry.columns:
        fdr_wrong = registry[
            registry["signal"].isin(FDR_SIGNALS)
            & (registry["bucketing_scheme"] != "ordinal")
        ]
        if not fdr_wrong.empty:
            errors.append(
                "C5: FDR signals not using ordinal bucketing: "
                + fdr_wrong[["signal", "position", "bucketing_scheme"]].to_string(index=False)
            )

    # C6: relationship_geometry in controlled vocabulary
    if "relationship_geometry" in registry.columns:
        bad_vocab = registry[~registry["relationship_geometry"].isin(GEOMETRY_TAXONOMY)]
        if not bad_vocab.empty:
            errors.append(
                f"C6: {len(bad_vocab)} rows have relationship_geometry outside GEOMETRY_TAXONOMY: "
                + str(bad_vocab["relationship_geometry"].unique().tolist())
            )

    # C7: association_class in controlled vocabulary
    if "association_class" in registry.columns:
        bad_ac = registry[~registry["association_class"].isin(ASSOCIATION_CLASS_TAXONOMY)]
        if not bad_ac.empty:
            errors.append(
                f"C7: {len(bad_ac)} rows have association_class outside ASSOCIATION_CLASS_TAXONOMY: "
                + str(bad_ac["association_class"].unique().tolist())
            )

    # C8: monotonicity_confidence non-NaN only for monotonic geometry
    if "monotonicity_confidence" in registry.columns and "relationship_geometry" in registry.columns:
        non_mono_with_conf = registry[
            ~registry["relationship_geometry"].isin(MONOTONIC_GEOMETRIES)
            & registry["monotonicity_confidence"].notna()
        ]
        if not non_mono_with_conf.empty:
            errors.append(
                f"C8: {len(non_mono_with_conf)} non-monotonic rows have non-NaN "
                f"monotonicity_confidence"
            )

    # C9: support_type non-empty only when support_flags is non-empty
    if "support_type" in registry.columns and "support_flags" in registry.columns:
        mismatched = registry[
            registry["support_type"].notna()
            & (registry["support_type"] != "")
            & (registry["support_flags"].isna() | (registry["support_flags"] == ""))
        ]
        if not mismatched.empty:
            errors.append(
                f"C9: {len(mismatched)} rows have support_type set but empty support_flags"
            )

    # C10: No duplicate column names
    if registry.columns.duplicated().sum() > 0:
        errors.append("C10: duplicate column names in registry")

    # C11: non-monotonic geometry → q1_q5_mean_gap must be NaN
    if "q1_q5_mean_gap" in registry.columns and "relationship_geometry" in registry.columns:
        non_mono_with_gap = registry[
            ~registry["relationship_geometry"].isin(MONOTONIC_GEOMETRIES)
            & registry["q1_q5_mean_gap"].notna()
        ]
        if not non_mono_with_gap.empty:
            errors.append(
                f"C11: {len(non_mono_with_gap)} non-monotonic rows have non-NaN q1_q5_mean_gap "
                f"(gap metric is only meaningful for monotonic geometry): "
                + non_mono_with_gap[["signal", "position", "relationship_geometry",
                                     "q1_q5_mean_gap"]].to_string(index=False)
            )

    # C12: monotonic geometry with non-NaN confidence → confidence >= MONO_CONF_LOW
    # (any signal below LOW must have been reclassified to indeterminate by Q4.2)
    if "monotonicity_confidence" in registry.columns and "relationship_geometry" in registry.columns:
        mono_low_conf = registry[
            registry["relationship_geometry"].isin(MONOTONIC_GEOMETRIES)
            & registry["monotonicity_confidence"].notna()
            & (registry["monotonicity_confidence"] < MONO_CONF_LOW)
        ]
        if not mono_low_conf.empty:
            errors.append(
                f"C12: {len(mono_low_conf)} monotonic rows have confidence < {MONO_CONF_LOW} "
                f"(should have been reclassified to indeterminate in Q4.2): "
                + mono_low_conf[["signal", "position", "monotonicity_confidence"]].to_string(index=False)
            )

    # C13: signal-layer metadata complete and controlled
    required_layer_cols = [
        "signal_layer",
        "layer_role",
        "feature_candidate_eligible",
        "interpretation_caveat",
        "downstream_status",
    ]
    missing_layer_cols = [c for c in required_layer_cols if c not in registry.columns]
    if missing_layer_cols:
        errors.append(
            "C13a: missing signal-layer registry columns: "
            + str(missing_layer_cols)
        )
    else:
        for col in ["signal_layer", "layer_role", "interpretation_caveat", "downstream_status"]:
            empty = registry[col].isna() | (registry[col].astype(str).str.strip() == "")
            if empty.any():
                errors.append(
                    f"C13b: {int(empty.sum())} rows have empty {col}"
                )

        bad_layers = registry[~registry["signal_layer"].isin(SIGNAL_LAYER_VALUES)]
        if not bad_layers.empty:
            errors.append(
                "C13c: unknown signal_layer values: "
                + str(sorted(bad_layers["signal_layer"].dropna().unique().tolist()))
            )

        expected_signals = set(registry["signal"].unique())
        mapped_signals = set(SIGNAL_LAYER_MAPPING)
        missing_mappings = sorted(expected_signals - mapped_signals)
        if missing_mappings:
            errors.append(
                "C13d: signal-layer mapping missing current registry signals: "
                + str(missing_mappings)
            )

        if registry["feature_candidate_eligible"].map(type).ne(bool).any():
            errors.append("C13e: feature_candidate_eligible must contain bool values")

        bad_status = registry[
            ~registry["downstream_status"].isin({"eligible", "caveated", "blocked"})
        ]
        if not bad_status.empty:
            errors.append(
                "C13f: downstream_status outside controlled values: "
                + str(sorted(bad_status["downstream_status"].dropna().unique().tolist()))
            )

    # C14: layer-level semantic gates
    if {"signal", "variable_level"}.issubset(registry.columns):
        bad_match_level = registry[
            registry["signal"].isin(MATCH_LEVEL_SIGNALS)
            & (registry["variable_level"] != "match_level")
        ]
        if not bad_match_level.empty:
            errors.append(
                f"C14a: {len(bad_match_level)} MATCH_LEVEL_SIGNALS rows are not variable_level=match_level: "
                + bad_match_level[["signal", "position", "variable_level"]].to_string(index=False)
            )

    if {"signal_layer", "feature_candidate_eligible"}.issubset(registry.columns):
        forbidden_feature_layers = {
            "context", "market_behavior", "valuation", "exposure"
        }
        bad_feature_layers = registry[
            registry["signal_layer"].isin(forbidden_feature_layers)
            & (registry["feature_candidate_eligible"] == True)  # noqa: E712
        ]
        if not bad_feature_layers.empty:
            errors.append(
                f"C14b: {len(bad_feature_layers)} rows in non-feature layers are feature_candidate_eligible=True: "
                + bad_feature_layers[["signal", "position", "signal_layer"]].to_string(index=False)
            )

    # C15: downstream_status coherence
    if {"support_flags", "downstream_status"}.issubset(registry.columns):
        insuff_not_blocked = registry[
            registry["support_flags"].str.contains("insufficient_support", na=False)
            & (registry["downstream_status"] != "blocked")
        ]
        if not insuff_not_blocked.empty:
            errors.append(
                f"C15a: {len(insuff_not_blocked)} insufficient_support rows are not downstream_status=blocked"
            )

    if {"low_confidence", "downstream_status"}.issubset(registry.columns):
        lc_eligible = registry[
            (registry["low_confidence"] == True)  # noqa: E712
            & (registry["downstream_status"] == "eligible")
        ]
        if not lc_eligible.empty:
            errors.append(
                f"C15b: {len(lc_eligible)} low_confidence rows are downstream_status=eligible"
            )

    if errors:
        raise ValueError(
            "Registry validation failed — contradictions detected:\n"
            + "\n".join(f"  [{e}]" for e in errors)
        )

    # --- Permitted-state warnings (structurally expected, not errors) ---

    # W1: unassessable pairs with valid rho_pooled
    if "rho_pooled" in registry.columns and "association_class" in registry.columns:
        unassess_with_rho = registry[
            (registry["association_class"] == "unassessable")
            & registry["rho_pooled"].notna()
        ]
        if not unassess_with_rho.empty:
            warnings_out.append(
                f"W1: {len(unassess_with_rho)} unassessable pairs have valid rho_pooled "
                f"(geometry blocked by support failure; rho metrics remain valid for downstream use)"
            )

    # W2: indeterminate panel_class
    if "panel_class" in registry.columns:
        indet = registry[registry["panel_class"] == "indeterminate"]
        if not indet.empty:
            warnings_out.append(
                f"W2: {len(indet)} pairs have panel_class=indeterminate "
                f"(within_share > 1.0 or decomposition below minimum n)"
            )

    # W3: low_confidence monotonic pairs
    if "low_confidence" in registry.columns:
        lc = registry[registry["low_confidence"] == True]  # noqa: E712
        if not lc.empty:
            warnings_out.append(
                f"W3: {len(lc)} pairs have low_confidence=True "
                f"(monotonic geometry with bootstrap stability "
                f"{MONO_CONF_LOW:.0%}–{MONO_CONF_HIGH:.0%})"
            )

    # W4: match-level variables with panel decomposition results
    if "signal" in registry.columns:
        match_level = registry[registry["signal"].isin(MATCH_LEVEL_SIGNALS)]
        if not match_level.empty:
            warnings_out.append(
                f"W4: {len(match_level)} rows are match-level structural variables "
                f"({sorted(match_level['signal'].unique().tolist())}). "
                f"Panel decomposition results must carry caveat: these signals cannot be "
                f"interpreted as player identity or state indicators."
            )

    return warnings_out


# ---------------------------------------------------------------------------
# Findings template
# ---------------------------------------------------------------------------

def build_findings_template(
    results: dict[str, dict[str, Any]],
    registry: pd.DataFrame,
) -> list[str]:
    """Generate hierarchical EDA_FINDINGS.md entry for EDA-3.

    Structure:
      Primary findings — geometry summary, panel summary, haul summary
      Caveats         — temporal flags, low-confidence monotonic signals
      Governance flags — identity_dominant, tail_dependent, weak_association,
                         unassessable cells (support failure or geometry blocked)

    Returns a list of markdown lines for copy-paste into EDA_FINDINGS.md.
    """
    lines: list[str] = [
        "## EDA-3 — Signal-Target Relationship Structure",
        "",
        "Primary output: research/eda/findings/eda_03_joint_registry.csv",
        f"Registry rows: {len(registry)}  "
        f"(signals × positions analyzed)",
        "",
    ]

    # --- Primary findings ---
    lines.append("### Primary findings")
    lines.append("")

    geom_counts = registry["relationship_geometry"].value_counts().to_dict()
    lines.append("Geometry classification:")
    for geom, count in sorted(geom_counts.items()):
        lines.append(f"  {geom}: {count} signal-position pairs")
    lines.append("")

    if "association_class" in registry.columns:
        ac_counts = registry["association_class"].value_counts().to_dict()
        lines.append("Association class distribution:")
        for cls, count in sorted(ac_counts.items()):
            lines.append(f"  {cls}: {count} pairs")
    lines.append("")

    if "panel_class" in registry.columns:
        pc_counts = registry["panel_class"].value_counts().to_dict()
        lines.append("Panel decomposition:")
        for cls, count in sorted(pc_counts.items()):
            lines.append(f"  {cls}: {count} pairs")
    lines.append("")

    if "rho_drop" in registry.columns:
        tail_dep = registry[registry.get("association_class", pd.Series()) == "tail_dependent"]
        lines.append(
            f"Haul concentration: {len(tail_dep)} signal-position pairs "
            f"with rho_drop > {HAUL_DROP_MATERIAL} (tail_dependent)"
        )
    lines.append("")

    # --- Caveats ---
    lines.append("### Caveats")
    lines.append("")

    if "temporal_stability" in registry.columns:
        moderate = registry[registry["temporal_stability"] == "moderate_shift"]
        if not moderate.empty:
            lines.append(
                f"Moderate temporal shift ({len(moderate)} pairs): "
                f"gap direction consistent but magnitude shrinks >50% in one block."
            )
            for _, r in moderate.iterrows():
                lines.append(f"  {r['signal']} × {r['position']}")
        lines.append("")

    if "low_confidence" in registry.columns:
        lc = registry[registry["low_confidence"] == True]  # noqa: E712
        if not lc.empty:
            lines.append(
                f"Low monotonicity confidence ({len(lc)} pairs): geometry retained "
                f"but bootstrap stability {MONO_CONF_LOW:.0%}–{MONO_CONF_HIGH:.0%}:"
            )
            for _, r in lc.iterrows():
                mc = r.get("monotonicity_confidence")
                mc_str = f"{mc:.2f}" if pd.notna(mc) else "n/a"
                lines.append(f"  {r['signal']} × {r['position']}  confidence={mc_str}")
        lines.append("")

    # --- Governance flags ---
    lines.append("### Governance flags")
    lines.append("")
    lines.append(
        "The following constraints must be explicitly handled by lens studies "
        "and synthesis layers that consume signals flagged below."
    )
    lines.append("")

    if "panel_class" in registry.columns:
        id_dom = registry[registry["panel_class"] == "identity_dominant"]
        if not id_dom.empty:
            lines.append(
                f"identity_dominant ({len(id_dom)} pairs) — "
                f"study layer must not frame these as state signals:"
            )
            for _, r in id_dom.iterrows():
                ws = r.get("within_share")
                ws_str = f"{ws:.2f}" if pd.notna(ws) else "n/a"
                lines.append(
                    f"  {r['signal']} × {r['position']}  "
                    f"within_share={ws_str}"
                )
            lines.append("")

    if "association_class" in registry.columns:
        tail = registry[registry["association_class"] == "tail_dependent"]
        if not tail.empty:
            lines.append(
                f"tail_dependent ({len(tail)} pairs) — "
                f"association concentrated in high-return events:"
            )
            for _, r in tail.iterrows():
                rd = r.get("rho_drop")
                rd_str = f"{rd:.3f}" if pd.notna(rd) else "n/a"
                lines.append(
                    f"  {r['signal']} × {r['position']}  "
                    f"rho_drop={rd_str}"
                )
            lines.append("")

        weak = registry[registry["association_class"] == "weak_association"]
        if not weak.empty:
            lines.append(
                f"weak_association ({len(weak)} pairs) — "
                f"indeterminate geometry or no clear structural signal:"
            )
            for _, r in weak.iterrows():
                lines.append(f"  {r['signal']} × {r['position']}")
            lines.append("")

        unassessable = registry[registry["association_class"] == "unassessable"]
        if not unassessable.empty:
            lines.append(
                f"unassessable ({len(unassessable)} pairs) — "
                f"support failure blocked geometry classification; "
                f"rho and panel metrics may still be valid:"
            )
            for _, r in unassessable.iterrows():
                st = r.get("support_type", "")
                lines.append(
                    f"  {r['signal']} × {r['position']}  "
                    f"support_type={st}  flags={r.get('support_flags','')}"
                )
            lines.append("")

    # --- Match-level variable caveats ---
    match_level = registry[registry["signal"].isin(MATCH_LEVEL_SIGNALS)]
    if not match_level.empty:
        lines.append("### Match-level variable caveats")
        lines.append("")
        lines.append(
            "The following signals describe match context, not player form. "
            "Panel decomposition results for these variables must NOT be "
            "interpreted as player identity or state indicators. "
            "Downstream lens studies must annotate these pairs explicitly."
        )
        lines.append("")
        for _, r in match_level.iterrows():
            pc = r.get("panel_class", "n/a")
            vl = r.get("variable_level", "match_level")
            lines.append(
                f"  {r['signal']} × {r['position']}  "
                f"panel_class={pc}  variable_level={vl}"
            )
        lines.append("")

    return lines
