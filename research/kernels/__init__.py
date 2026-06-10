"""Domain-agnostic statistical kernels.

No FPL-specific constants, no governance imports, no signal classification strings.
Anything that imports governance (model/governance/, domain/registry/) or
references FPL concepts belongs in research/families/, not here.

## Import convention

Kernels are imported by **module path**, not via this package's ``__init__``.
The two exports below exist only because panel and tail live inside ``diagnostic/``
but are part of the kernels public surface. All other kernels are imported directly:

    from research.kernels.inferential.resampling import bootstrap_spearman_ci, bootstrap_partial_rho, partial_spearman
    from research.kernels.inferential.monotonicity import monotonicity_confidence
    from research.kernels.diagnostic.stability import assess_distribution_stability, resolve_pooling_strategy
    from research.kernels.diagnostic.redundancy import compute_pairwise_rho, identify_redundant_pairs
    from research.kernels.diagnostic.conditioning import compute_conditional_rho
    from research.kernels.diagnostic.panel import split_between_within_player_rho   # via __init__
    from research.kernels.diagnostic.tail import measure_tail_event_dependence      # via __init__
    from research.kernels.descriptive.binning import bin_analysis, select_bucketing_scheme
    from research.kernels.descriptive.distribution import compute_distribution_stats, compare_cohorts
    from research.kernels.hypothesis.multiplicity import benjamini_hochberg, holm_bonferroni
    from research.kernels.hypothesis.stratification import quintile_stratification

Do NOT add mass re-exports to this file. The module-path pattern keeps import
chains explicit and avoids circular-import risk from the sub-package structure.
"""

from research.kernels.diagnostic.panel import split_between_within_player_rho
from research.kernels.diagnostic.tail import measure_tail_event_dependence

__all__ = ["split_between_within_player_rho", "measure_tail_event_dependence"]
