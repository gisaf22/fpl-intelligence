# Data-contract corrections (verified against source before implementation):
#
# 1. Import paths: The task specified `from datasets import FeaturesDataset` and
#    `from context import GameweekContext`. Both modules live inside the
#    fpl_intelligence package (src/fpl_intelligence/); plain names are not
#    importable from the project root. Corrected to fpl_intelligence.* paths.
#    The FeaturesDataset used in runner.py is the Pydantic model in
#    models.pipeline, not the list alias in datasets.py; import updated
#    accordingly.
#
# 2. gw_contexts key: The task states "Keys are team_id" but
#    build_gameweek_context (context.py line 18) documents the return as
#    player_id -> GameweekContext, and steps.py accesses it as
#    gw_contexts[entity_id]. DGW lookup below uses
#    gw_contexts.get(item.entity_id), not gw_contexts.get(item.team_id).
#
# 3. FeaturesDataset (models.pipeline) is a Pydantic model; eligible records
#    are accessed via features.records, not by iterating features directly.
#
# 4. briefing.signals.minutes_filter is a MinutesFilter count model, not a list
#    of signal items. It is not referenced in any of the four checks below.

from __future__ import annotations

from dataclasses import dataclass

from fpl_intelligence.context import GameweekContext
from fpl_intelligence.models.briefing import Briefing
from fpl_intelligence.models.pipeline import FeaturesDataset


@dataclass
class ValidationResult:
    passed: bool
    warnings: list[str]
    errors: list[str]


def validate_pipeline_output(
    features: FeaturesDataset,
    briefing: Briefing,
    gw: int,
    gw_contexts: dict[int, GameweekContext],
) -> ValidationResult:
    warnings: list[str] = []
    errors: list[str] = []

    # Check 1 — Eligible player coverage
    eligible_count = sum(1 for r in features.records if r.is_eligible)
    if eligible_count < 50:
        errors.append(
            f"Only {eligible_count} eligible players found for GW {gw} — check filtering or ingest"
        )

    # Check 2 — Score dispersion
    ovr = briefing.signals.ownership_vs_returns
    undervalued = ovr.undervalued or []
    overvalued = ovr.overvalued or []
    scores = [item.value for item in undervalued] + [item.value for item in overvalued]
    if not scores:
        errors.append(
            f"No signal items found in ownership_vs_returns for GW {gw}"
        )
    else:
        score_range = max(scores) - min(scores)
        if score_range < 0.5:
            errors.append(
                f"Score range is {score_range:.3f} for GW {gw} — normalization may have collapsed"
            )

    # Build full ranked list: undervalued DESC by value, then overvalued ASC by value.
    # Shared by Check 3 and Check 4.
    ranked = (
        sorted(undervalued, key=lambda x: x.value, reverse=True)
        + sorted(overvalued, key=lambda x: x.value)
    )

    # Check 3 — DGW rank distribution (warning only; skip entirely if no DGW players)
    dgw_ranks = []
    for rank, item in enumerate(ranked, start=1):
        ctx = gw_contexts.get(item.entity_id)
        if ctx is not None and ctx.is_dgw:
            dgw_ranks.append(rank)

    if dgw_ranks:
        average_dgw_rank = sum(dgw_ranks) / len(dgw_ranks)
        if average_dgw_rank > 80:
            warnings.append(
                f"DGW players average rank is {average_dgw_rank:.0f} for GW {gw} — check signal weighting"
            )

    # Check 4 — Signal invariants: both directions must be populated
    undervalued = briefing.signals.ownership_vs_returns.undervalued
    overvalued = briefing.signals.ownership_vs_returns.overvalued

    if not undervalued:
        errors.append("No undervalued players in output — degenerate signal")

    if not overvalued:
        errors.append("No overvalued players in output — degenerate signal")

    # Check 5 — Position coverage in top 15 (warning only; one warning per missing position)
    top_15 = ranked[:15]
    EXPECTED_POSITIONS = {"GK", "DEF", "MID", "FWD"}
    found_positions = {
        item.position.value
        for item in top_15
        if item.position is not None
    }
    missing = EXPECTED_POSITIONS - found_positions
    for pos in sorted(missing):
        warnings.append(
            f"Position {pos} has no representation in top 15 for GW {gw}"
        )

    return ValidationResult(
        passed=(len(errors) == 0),
        warnings=warnings,
        errors=errors,
    )
